# Núcleo — referencia del esqueleto

Complementa `SKILL.md`: código de `core/` (salvo `core/runtime/`, que está en [runtime.md](runtime.md)), el entrypoint y el test de contrato. Se escribe una vez por proyecto.

## 1. Contexto del turno (FAC-01)

```python
# core/context.py
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class TurnContext:
    """Estado del negocio que las reglas necesitan, cargado una sola vez por turno."""

    conversation_id: str
    dimensions: Mapping[str, str | None]  # las que decide el negocio: business_line, organization, site, stage...
    channel: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def dimension(self, name: str) -> str:
        """Valor de una dimensión, o "" si falta: un lookup en el REGISTRY nunca falla por un None."""
        return self.dimensions.get(name) or ""
```

`dimensions` es lo único que miran las factories y lo que viaja a logs y trazas (FAC-05, FAC-06, OBS-01); `attributes` guarda el resto del estado del negocio que necesiten los agentes.

## 2. Esquema de `definition.json` (DEF-02 a DEF-06)

Un ejemplo completo de `definition.json` está en [domains.md](domains.md) §2.

```python
# core/definition.py
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ENVIRONMENTS: tuple[str, ...] = ("dev", "prod")


class TemplateInput(BaseModel):
    """Pieza reutilizable (tono, ejemplos) que es otro prompt de LangSmith."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["template"]
    template: str                                 # nombre en LangSmith
    version: dict[str, str]                       # {"dev": "<commit>", "prod": "<commit>"}


class ValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["value"]
    value: str


PromptInput = Annotated[TemplateInput | ValueInput, Field(discriminator="kind")]


class PromptSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str                                   # nombre en LangSmith
    version: dict[str, str]                       # {"dev": "<commit>", "prod": "<commit>"}
    inputs: dict[str, PromptInput] = {}


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra="allow")      # temperature, base_url, model_kwargs...

    model: str
    model_provider: str
    api_key: str | None = None                    # referencia "ENV_...", nunca el valor


class SubAgentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str                              # el contrato que lee el router
    prompt_settings: PromptSettings
    model_settings: dict[str, ModelSettings]      # por proveedor
    tools: list[str] = Field(min_length=1)
    terminal_tools: list[str] = []
    channels: list[str] | None = None             # None = todos los canales


class RouterDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_settings: PromptSettings               # recibe {members} y {examples}
    examples: PromptSettings | None = None
    model_settings: dict[str, ModelSettings]
    recursion_limit: int = 12                     # cada vuelta router → agente son 2 pasos


class AgentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    agents_router: RouterDefinition
    agents: dict[str, SubAgentDefinition]
    tools: dict[str, dict] = {}                   # configuración que usan las tools por dentro

    @classmethod
    def load(cls, path: Path) -> "AgentDefinition":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
```

## 3. `BaseAgent` (AGT-01, RUN-04, OBS-03)

```python
# core/agent.py
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, ClassVar

from langchain_core.messages import AnyMessage

from core.context import TurnContext
from core.definition import AgentDefinition, SubAgentDefinition
from core.runtime.router import run_router
from core.runtime.tools import ProductionToolFactory, ToolFactory

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Infraestructura común y template method. Las hojas solo declaran atributos de clase."""

    DEFINITION_PATH: ClassVar[Path]
    MODELS_PROVIDER: ClassVar[str] = "azure"

    def __init__(self, ctx: TurnContext, tool_factory: ToolFactory | None = None) -> None:
        self.ctx = ctx
        self.tool_factory = tool_factory or ProductionToolFactory()
        self.definition = AgentDefinition.load(self.DEFINITION_PATH)

    def __str__(self) -> str:
        return type(self).__name__

    def process(self) -> None:
        """El orden de los pasos es fijo; cada paso es un hook."""
        roster = self.agent_roster()
        logger.info("agent_roster", extra={"agent": str(self), "roster": [sub.name for sub in roster]})
        messages = [*self.build_context(), *self.load_history()]
        run_router(self, roster, messages)

    # ---------- hooks ----------
    def agent_roster(self) -> list[SubAgentDefinition]:
        """Sub-agentes elegibles este turno. Override para reglas que dependen del negocio."""
        return [
            sub
            for sub in self.definition.agents.values()
            if sub.channels is None or self.ctx.channel in sub.channels
        ]

    def build_context(self) -> list[AnyMessage]:
        """Mensajes de sistema con los datos del negocio que el usuario puede ver."""
        return []

    @abstractmethod
    def load_history(self) -> list[AnyMessage]:
        """Historial del turno; cada dominio sabe dónde guarda sus mensajes."""

    def on_dead_end(self) -> None:
        """Salida controlada cuando el router no converge."""
        self.send_message("Dame un momento, una persona del equipo te va a contactar.")

    # ---------- tools transversales ----------
    def send_message(self, message: Annotated[str, "Mensaje final para el usuario"]) -> str:
        """Envía el mensaje al usuario. Es la única vía para hablarle y cierra el turno."""
        ...  # persistir y enviar por el canal del turno
        return "Mensaje enviado. Esperamos la respuesta del usuario."
```

## 4. `RootAgentFactory` (FAC-04 a FAC-06)

```python
# core/factory.py
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from core.agent import BaseAgent
from core.context import TurnContext

logger = logging.getLogger(__name__)


class DomainAgentFactory(Protocol):
    REGISTRY: Mapping[str, Any]  # {dimensión_1: {dimensión_2: ... Clase}}, tantos niveles como dimensiones

    def resolve(self, ctx: TurnContext) -> type[BaseAgent] | None: ...


class NoAgentForTurn(Exception):
    """Ningún dominio reclamó el turno: es un estado de negocio sin flujo."""


class RootAgentFactory:
    """Cadena de responsabilidad: el orden de `factories` ES la prioridad de negocio."""

    def __init__(self, factories: Sequence[DomainAgentFactory]) -> None:
        self.factories = factories

    def get_agent(self, ctx: TurnContext, **agent_kwargs: Any) -> BaseAgent:
        dimensions = dict(ctx.dimensions)
        for factory in self.factories:
            agent_class = factory.resolve(ctx)
            if agent_class is not None:
                logger.info(
                    "agent_selected",
                    extra={"factory": type(factory).__name__, "agent": agent_class.__name__, "dimensions": dimensions},
                )
                return agent_class(ctx, **agent_kwargs)

        logger.warning("no_agent_selected", extra={"dimensions": dimensions})
        raise NoAgentForTurn(f"Sin flujo para la conversación {ctx.conversation_id}")
```

## 5. Secretos (DEF-06)

```python
# core/secrets.py
import os


def get_secret(reference: str) -> str:
    """Resuelve "ENV_<NOMBRE>". Aquí contra variables de entorno; cámbialo por tu gestor de secretos."""
    name = reference.removeprefix("ENV_")
    if not (value := os.environ.get(name)):
        raise KeyError(f"Falta el secreto {name}")  # nunca un valor vacío por defecto
    return value
```

## 6. Entrypoint (ARQ-01)

```python
# entrypoints/handler.py
from composition import build_root_factory
from core.context import TurnContext


def load_turn_context(conversation_id: str) -> TurnContext:
    """Lee la conversación y el estado del negocio una sola vez por turno (base de datos, CRM...)."""
    ...


def handle_message(conversation_id: str) -> None:
    ctx = load_turn_context(conversation_id)
    agent = build_root_factory().get_agent(ctx)
    agent.process()
```

## 7. Test de contrato (TST-03)

Recorre todos los `REGISTRY`: un agente registrado queda cubierto sin escribir tests nuevos.

```python
# tests/contract/test_definitions.py
from collections.abc import Mapping
from typing import Any

import pytest

from composition import build_root_factory
from core.agent import BaseAgent
from core.definition import ENVIRONMENTS, AgentDefinition, TemplateInput


def leaf_classes(registry: Mapping[str, Any]) -> set[type[BaseAgent]]:
    """Clases de un REGISTRY con cualquier número de dimensiones anidadas."""
    return {
        agent_class
        for value in registry.values()
        for agent_class in (leaf_classes(value) if isinstance(value, Mapping) else {value})
    }


def registered_agent_classes() -> list[type[BaseAgent]]:
    classes = set().union(*(leaf_classes(factory.REGISTRY) for factory in build_root_factory().factories))
    return sorted(classes, key=lambda agent_class: agent_class.__name__)


def pinned_prompts(definition: AgentDefinition) -> list[tuple[str, dict[str, str]]]:
    """Todo prompt que se descarga: router, ejemplos, sub-agentes e inputs de plantilla."""
    router = definition.agents_router
    settings = [router.prompt_settings, *(sub.prompt_settings for sub in definition.agents.values())]
    if router.examples:
        settings.append(router.examples)
    templates = [item for s in settings for item in s.inputs.values() if isinstance(item, TemplateInput)]
    return [(s.prompt, s.version) for s in settings] + [(t.template, t.version) for t in templates]


@pytest.mark.parametrize("agent_class", registered_agent_classes())
def test_every_registered_agent_honours_its_definition(agent_class):
    definition = AgentDefinition.load(agent_class.DEFINITION_PATH)  # valida el esquema

    for sub in definition.agents.values():
        for tool in sub.tools:
            assert not tool.startswith("_") and callable(getattr(agent_class, tool, None)), (
                f"{agent_class.__name__} no tiene la tool {tool}"
            )
        assert set(sub.terminal_tools) <= set(sub.tools)
    for prompt, version in pinned_prompts(definition):
        assert set(ENVIRONMENTS) <= set(version), f"{prompt} sin versión por ambiente"
        assert "latest" not in version.values(), f"{prompt} usa latest"
```
