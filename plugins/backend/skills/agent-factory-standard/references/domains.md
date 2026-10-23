# Dominios — referencia del esqueleto

Complementa `SKILL.md`: lo que se agrega en cada cambio (variante, etapa, dimensión, dominio, tool). El ejemplo es ficticio: un dominio `orders` (pedidos) que decide por `organization → stage`, con los casos `returns` (devoluciones, etapa `delivered`) y `tracking` (seguimiento, etapa `in_transit`) para las organizaciones `acme` y `globex`, y un segundo dominio `leads`. Cambia dimensiones y nombres por los de tu negocio (sede, región, plan...); el núcleo que usan está en [core.md](core.md).

## 1. Jerarquía: dominio → General → hoja (AGT-01 a AGT-05)

```python
# domains/orders/main.py
from langchain_core.messages import AnyMessage

from core.agent import BaseAgent


class OrdersAgent(BaseAgent):
    """Tools, persistencia y elegibilidad comunes al dominio de pedidos."""

    def load_history(self) -> list[AnyMessage]:
        ...  # mensajes de la colección de pedidos desde el último resumen

    def get_orders(self) -> str:
        """Lista los pedidos del usuario con su estado y sus artículos."""
        ...


# domains/orders/general/returns/main.py
from typing import Annotated

from langchain_core.messages import AnyMessage, SystemMessage

from domains.orders.main import OrdersAgent


class ReturnsAgentGeneral(OrdersAgent):
    """Lógica de devoluciones compartida entre variantes."""

    def build_context(self) -> list[AnyMessage]:
        return [SystemMessage(content="## Contexto del pedido\n- ...")]  # solo lo que el usuario ve (AGT-05)

    def request_return(self, item_id: Annotated[int, "ID del artículo que el usuario quiere devolver"]) -> str:
        """Solicita la devolución del artículo que el usuario eligió. Confírmalo con el usuario antes de llamarla."""
        ...

    def cancel_return(self, return_id: Annotated[int, "ID de la devolución que el usuario cancela"]) -> str:
        """Cancela una devolución que el usuario ya no quiere."""
        ...


# domains/orders/acme/returns/main.py
from pathlib import Path

from domains.orders.general.returns.main import ReturnsAgentGeneral


class ReturnsAgentAcme(ReturnsAgentGeneral):
    DEFINITION_PATH = Path(__file__).with_name("definition.json")
    MODELS_PROVIDER = "azure"
```

Cada tool va en el nivel más alto donde aplica: `get_orders` sirve a todo el dominio; `request_return` y `cancel_return`, solo a devoluciones. La hoja de otra variante (`ReturnsAgentGlobex`) es igual, con su propio `definition.json` al lado.

## 2. `definition.json` de la hoja (DEF-01 a DEF-06)

`domains/orders/acme/returns/definition.json`:

```json
{
  "name": "orders_returns_acme",
  "description": "Devoluciones de pedidos entregados - organización Acme",
  "agents_router": {
    "prompt_settings": {"prompt": "agents_router", "version": {"dev": "<commit>", "prod": "<commit>"}},
    "examples": {"prompt": "acme_returns_router_examples", "version": {"dev": "<commit>", "prod": "<commit>"}},
    "model_settings": {
      "azure": {"model": "<modelo>", "model_provider": "openai", "api_key": "ENV_AZURE_OPENAI_API_KEY", "base_url": "ENV_AZURE_OPENAI_ENDPOINT", "temperature": 0}
    },
    "recursion_limit": 12
  },
  "agents": {
    "communication": {
      "name": "communication_agent",
      "description": "Redacta y envía TODO mensaje al usuario. Nunca es el primer agente del turno.",
      "prompt_settings": {
        "prompt": "acme_communication",
        "version": {"dev": "<commit>", "prod": "<commit>"},
        "inputs": {"tone": {"kind": "template", "template": "acme_tone", "version": {"dev": "<commit>", "prod": "<commit>"}}}
      },
      "model_settings": {"azure": {"model": "<modelo>", "model_provider": "openai", "api_key": "ENV_AZURE_OPENAI_API_KEY", "base_url": "ENV_AZURE_OPENAI_ENDPOINT"}},
      "tools": ["send_message"],
      "terminal_tools": ["send_message"]
    },
    "returns": {
      "name": "returns_agent",
      "description": "Consulta pedidos y solicita o cancela devoluciones. Llámalo cuando el usuario quiera devolver un producto o pregunte por una devolución; no lo llames para el estado de un envío. No le escribe al usuario.",
      "prompt_settings": {"prompt": "acme_returns", "version": {"dev": "<commit>", "prod": "<commit>"}},
      "model_settings": {"azure": {"model": "<modelo>", "model_provider": "openai", "api_key": "ENV_AZURE_OPENAI_API_KEY", "base_url": "ENV_AZURE_OPENAI_ENDPOINT"}},
      "tools": ["get_orders", "request_return", "cancel_return"]
    }
  }
}
```

## 3. La regla de negocio: factory del dominio (FAC-01 a FAC-03)

```python
# domains/orders/factory.py
import logging

from core.agent import BaseAgent
from core.context import TurnContext
from domains.orders.acme.returns.main import ReturnsAgentAcme
from domains.orders.acme.tracking.main import TrackingAgentAcme
from domains.orders.globex.returns.main import ReturnsAgentGlobex
from domains.orders.globex.tracking.main import TrackingAgentGlobex

logger = logging.getLogger(__name__)


class OrdersAgentFactory:
    """Regla de negocio de pedidos: qué agente atiende según organización y etapa."""

    REGISTRY: dict[str, dict[str, type[BaseAgent]]] = {  # organization → stage → agente
        "acme": {"in_transit": TrackingAgentAcme, "delivered": ReturnsAgentAcme},
        "globex": {"in_transit": TrackingAgentGlobex, "delivered": ReturnsAgentGlobex},
    }

    def resolve(self, ctx: TurnContext) -> type[BaseAgent] | None:
        if ctx.dimension("business_line") != "orders":
            return None  # guard: el turno no es de este dominio
        agent_class = self.REGISTRY.get(ctx.dimension("organization"), {}).get(ctx.dimension("stage"))
        if agent_class is None:
            logger.info("orders sin agente dimensions=%s", dict(ctx.dimensions))
        return agent_class
```

Otras dimensiones son el mismo patrón: `sede → etapa` cambia las llaves del primer nivel; `organización → sede → etapa` agrega un nivel (`.get(ctx.dimension("site"), {})` en medio). El test de contrato recorre cualquier profundidad.

## 4. Registrar un dominio (FAC-04)

Una línea por dominio, en el orden de la prioridad de negocio y con su porqué:

```python
# composition.py
from core.factory import RootAgentFactory
from domains.leads.factory import LeadsAgentFactory
from domains.orders.factory import OrdersAgentFactory


def build_root_factory() -> RootAgentFactory:
    return RootAgentFactory(
        [
            OrdersAgentFactory(),  # 1. con un pedido en curso, pedidos manda sobre cualquier etapa comercial
            LeadsAgentFactory(),   # 2. leads abiertos (dimensión lead_stage) sin pedido en curso
        ]
    )
```

## 5. Tests (TST-01, TST-02, TST-04)

Tabla de la factory (sin mocks: `resolve` es pura) y precedencia entre dominios que reclaman el mismo contexto. El test de contrato ([core.md](core.md) §7) cubre la hoja nueva sin cambios.

```python
# tests/unit/domains/orders/test_factory.py
import pytest

from core.context import TurnContext
from domains.orders.acme.returns.main import ReturnsAgentAcme
from domains.orders.acme.tracking.main import TrackingAgentAcme
from domains.orders.factory import OrdersAgentFactory
from domains.orders.globex.returns.main import ReturnsAgentGlobex


@pytest.mark.parametrize(
    ("business_line", "organization", "stage", "expected"),
    [
        ("orders", "acme", "delivered", ReturnsAgentAcme),
        ("orders", "globex", "delivered", ReturnsAgentGlobex),
        ("orders", "acme", "in_transit", TrackingAgentAcme),
        ("leads", "globex", "delivered", None),     # guard: el turno es de otro dominio
        ("orders", "globex", "unknown", None),      # etapa sin agente registrado
        ("orders", "initech", "delivered", None),   # organización sin registro
        ("orders", None, "delivered", None),        # dimensión ausente
    ],
)
def test_orders_resolves_the_agent_by_organization_and_stage(business_line, organization, stage, expected):
    dimensions = {"business_line": business_line, "organization": organization, "stage": stage}
    ctx = TurnContext(conversation_id="c-1", dimensions=dimensions)

    assert OrdersAgentFactory().resolve(ctx) is expected


# tests/unit/core/test_root_factory.py
from composition import build_root_factory
from core.context import TurnContext
from domains.leads.factory import LeadsAgentFactory
from domains.orders.acme.returns.main import ReturnsAgentAcme
from domains.orders.factory import OrdersAgentFactory


def test_orders_wins_over_leads_when_both_claim_the_turn():
    # Cliente con un pedido entregado que además sigue abierto como lead.
    dimensions = {"business_line": "orders", "organization": "acme", "stage": "delivered", "lead_stage": "qualified"}
    ctx = TurnContext(conversation_id="c-1", dimensions=dimensions)
    assert OrdersAgentFactory().resolve(ctx) is not None
    assert LeadsAgentFactory().resolve(ctx) is not None  # el conflicto existe; si no, el test no prueba nada

    assert type(build_root_factory().get_agent(ctx)) is ReturnsAgentAcme
```

Evaluación (TST-04): la hoja se construye con tools simuladas ([runtime.md](runtime.md) §1) y corre contra su dataset. `calls` registra qué tools llamó el agente y con qué argumentos, incluido el texto de `send_message`:

```python
tools = MockToolFactory({"get_orders": "Pedido 1042: entregado hace 3 días, 2 artículos."})
ReturnsAgentAcme(ctx, tool_factory=tools).process()
tools.calls  # [("get_orders", {}), ("send_message", {"message": "..."})]
```
