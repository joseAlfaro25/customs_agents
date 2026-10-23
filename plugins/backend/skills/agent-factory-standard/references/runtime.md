# Runtime — referencia del esqueleto

Complementa `SKILL.md`: código de `core/runtime/`. Léelo al crear el runtime o al depurar el router, los sub-agentes, las tools, los modelos o los prompts. El núcleo que lo usa está en [core.md](core.md).

## 1. Tools (RUN-05, AGT-03)

```python
# core/runtime/tools.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from langchain_core.tools import BaseTool, StructuredTool

if TYPE_CHECKING:
    from core.agent import BaseAgent


class ToolFactory(ABC):
    @abstractmethod
    def create_tool(self, agent: "BaseAgent", tool_name: str) -> BaseTool: ...


class ProductionToolFactory(ToolFactory):
    """Convierte un método público del agente en tool. El docstring es la descripción para el LLM."""

    def create_tool(self, agent: "BaseAgent", tool_name: str) -> BaseTool:
        method = getattr(agent, tool_name, None)
        if tool_name.startswith("_") or not callable(method):
            raise ValueError(f"{agent} no expone la tool '{tool_name}'")
        return StructuredTool.from_function(func=method, name=tool_name)


class MockToolFactory(ToolFactory):
    """Evaluaciones: misma firma y descripción que la tool real, respuesta fija y registro de llamadas."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_tool(self, agent: "BaseAgent", tool_name: str) -> BaseTool:
        real = ProductionToolFactory().create_tool(agent, tool_name)

        def simulate(**kwargs: Any) -> str:
            self.calls.append((tool_name, kwargs))
            return self.responses.get(tool_name, "OK")

        return StructuredTool(name=real.name, description=real.description, args_schema=real.args_schema, func=simulate)
```

## 2. Modelos (RUN-07, DEF-06)

```python
# core/runtime/models.py
from typing import Any

from core.definition import ModelSettings
from core.secrets import get_secret


def resolve_model_settings(by_provider: dict[str, ModelSettings], provider: str) -> dict[str, Any]:
    if provider not in by_provider:
        raise ValueError(f"Sin model_settings para el proveedor {provider}")
    settings = by_provider[provider].model_dump(exclude_none=True)
    return {
        key: get_secret(value) if isinstance(value, str) and value.startswith("ENV_") else value
        for key, value in settings.items()
    }
```

## 3. Prompts (PRM-01, PRM-02, DEF-05)

```python
# core/runtime/prompts.py
import os
from functools import lru_cache

from langchain_core.prompts import BasePromptTemplate
from langsmith import Client

from core.definition import PromptSettings, TemplateInput


def _identifier(name: str, version: dict[str, str]) -> str:
    env = os.environ["ENV"]  # "dev" | "prod"; se lee al usarse para que importar no exija ENV
    if env not in version:
        raise ValueError(f"El prompt {name} no fija versión para {env}")  # sin fallback a dev
    return f"{name}:{version[env]}"


@lru_cache(maxsize=256)  # la clave es nombre:commit, que es inmutable
def _pull(identifier: str) -> BasePromptTemplate:
    return Client().pull_prompt(identifier)


def _render(prompt: BasePromptTemplate, **variables: str) -> str:
    # Solo el texto: ChatPromptTemplate.format() antepone el rol ("System: ...").
    return "\n\n".join(message.text for message in prompt.invoke(variables).to_messages())


def load_prompt(settings: PromptSettings, **runtime_inputs: str) -> str:
    inputs = {
        key: _render(_pull(_identifier(item.template, item.version))) if isinstance(item, TemplateInput) else item.value
        for key, item in settings.inputs.items()
    }
    return _render(_pull(_identifier(settings.prompt, settings.version)), **inputs, **runtime_inputs)
```

## 4. Sub-agente: grafo `llm ⇄ tools` (RUN-01, DEF-04)

```python
# core/runtime/sub_agent.py
from typing import TYPE_CHECKING, Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from core.definition import SubAgentDefinition
from core.runtime.models import resolve_model_settings
from core.runtime.prompts import load_prompt

if TYPE_CHECKING:
    from core.agent import BaseAgent


class SubAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def build_sub_agent(agent: "BaseAgent", sub: SubAgentDefinition):
    tools = [agent.tool_factory.create_tool(agent, name) for name in sub.tools]  # solo las suyas
    model = init_chat_model(**resolve_model_settings(sub.model_settings, agent.MODELS_PROVIDER)).bind_tools(tools)
    system_prompt = load_prompt(sub.prompt_settings)
    terminal = set(sub.terminal_tools)

    def call_model(state: SubAgentState) -> dict:
        return {"messages": [model.invoke([SystemMessage(content=system_prompt), *state["messages"]])]}

    def after_model(state: SubAgentState) -> str:
        return "tools" if state["messages"][-1].tool_calls else END

    def after_tools(state: SubAgentState) -> str:
        last_ai = next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))
        return END if terminal & {call["name"] for call in last_ai.tool_calls} else "llm"

    graph = StateGraph(SubAgentState)
    graph.add_node("llm", call_model)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))  # red de seguridad de AGT-03
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", after_model, ["tools", END])
    graph.add_conditional_edges("tools", after_tools, ["llm", END])
    return graph.compile()
```

## 5. Router supervisor `router ⇄ call_agent` (RUN-02, RUN-03, RUN-04, OBS-01)

```python
# core/runtime/router.py
import logging
from typing import TYPE_CHECKING, Annotated, Literal, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import Field, create_model

from core.definition import SubAgentDefinition
from core.runtime.models import resolve_model_settings
from core.runtime.prompts import load_prompt
from core.runtime.sub_agent import build_sub_agent

if TYPE_CHECKING:
    from core.agent import BaseAgent

FINISH = "FINISH"
logger = logging.getLogger(__name__)


class RouterState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    next_agent: str


def run_router(agent: "BaseAgent", roster: list[SubAgentDefinition], messages: list[AnyMessage]) -> None:
    router_def = agent.definition.agents_router
    members = {sub.name: build_sub_agent(agent, sub) for sub in roster}  # solo los elegibles

    # El esquema hace imposible elegir un agente que no está en el roster de este turno.
    decision_schema = create_model(
        "RouterDecision",
        reason=(str, Field(description="Por qué este agente, en una frase")),
        agent=(Literal[(*members, FINISH)], ...),  # type: ignore[valid-type]
    )
    decider = (
        init_chat_model(**resolve_model_settings(router_def.model_settings, agent.MODELS_PROVIDER))
        .with_structured_output(decision_schema)
        .with_retry(stop_after_attempt=2)  # una salida que no valida se reintenta una vez
    )
    prompt = load_prompt(
        router_def.prompt_settings,
        members="\n".join(f"- {sub.name}: {sub.description}" for sub in roster),
        examples=load_prompt(router_def.examples) if router_def.examples else "",
    )

    def route(state: RouterState) -> dict:
        decision = decider.invoke([SystemMessage(content=prompt), *state["messages"]])
        logger.info("%s router -> %s (%s)", agent, decision.agent, decision.reason)
        return {"next_agent": decision.agent}

    def call_agent(state: RouterState) -> dict:
        name = state["next_agent"]
        result = members[name].invoke({"messages": state["messages"]}, config={"run_name": name})
        relay = f"El agente {name} respondió: {result['messages'][-1].content}"
        return {"messages": [AIMessage(content=relay, name="supervisor")]}

    graph = StateGraph(RouterState)
    graph.add_node("router", route)
    graph.add_node("call_agent", call_agent)
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router", lambda state: END if state["next_agent"] == FINISH else "call_agent", ["call_agent", END]
    )
    graph.add_edge("call_agent", "router")

    try:
        graph.compile().invoke(
            {"messages": messages},
            config={
                "recursion_limit": router_def.recursion_limit,
                "run_name": str(agent),
                "configurable": {"thread_id": agent.ctx.conversation_id},
                "metadata": dict(agent.ctx.dimensions),
            },
        )
    except GraphRecursionError:
        logger.error("%s: el router no convergió en %s pasos", agent, router_def.recursion_limit)
        agent.on_dead_end()
```
