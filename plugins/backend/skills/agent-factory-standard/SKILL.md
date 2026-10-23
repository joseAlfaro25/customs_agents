---
name: agent-factory-standard
description: "Estándar obligatorio para agentes conversacionales con factory por reglas de negocio (LangChain + LangGraph): la factory elige el agente por dimensiones del negocio (organización, sede, etapa...) con un REGISTRY y prioridad entre dominios, jerarquía BaseAgent → dominio → General → variante, definition.json validado con Pydantic, prompts de LangSmith fijados por commit, router supervisor con salida estructurada y recursion_limit, tools inyectables y tests de tabla, precedencia y contrato. Usar al diseñar, implementar, revisar o extender estos agentes (variante, etapa, dominio, tool o prompt nuevos) y siempre que el repo tenga composition.py, domains/*/factory.py con REGISTRY o definition.json de agentes."
---

# agent-factory-standard

Estándar **obligatorio** para agentes conversacionales en los que una regla de negocio elige qué agente atiende cada turno. Las reglas **DEBE** no se negocian: si una tarea obliga a romper una, detente y explica por qué antes de escribir código. Lo marcado **NO** se rechaza en review.

> **Proyecto existente**: si ya tiene el núcleo (`core/`, `composition.py`), su código es la plantilla y las referencias solo cubren lo que falte. Este estándar manda en lo nuevo; las desviaciones del código existente se anotan, no se migran fuera del alcance.

## Antes de empezar

1. Carga `core:project-context` y lee las versiones del manifiesto: Python ≥ 3.11, `langchain` ≥ 1.0, `langgraph` ≥ 1.0, `pydantic` ≥ 2 y `langsmith`, fijadas con versión exacta.
2. Identifica las **dimensiones** con las que el negocio decide quién atiende (organización, sede, etapa, línea de negocio, canal...) y su orden. El esqueleto usa `organization → stage`; cámbialas por las del proyecto.
3. Lee solo lo que pide la tarea. Las referencias son el esqueleto que implementa estas reglas (verificado con langchain 1.4.7, langgraph 1.2.16, langchain-core 1.7.0 y pydantic 2.14.1): respeta sus contratos (firmas, hooks, esquema) y adapta los nombres al dominio.

| Tarea | Lee |
|---|---|
| Cambiar un prompt, revisar un PR, decidir dónde va algo | Solo esta skill |
| Agregar una variante, una etapa, un dominio o una tool | [references/domains.md](references/domains.md) |
| Crear o cambiar el núcleo: `TurnContext`, `definition.json`, `BaseAgent`, `RootAgentFactory`, entrypoint, test de contrato | [references/core.md](references/core.md) |
| Crear o depurar el runtime: router, sub-agentes, tools, modelos, prompts | [references/runtime.md](references/runtime.md) |

Proyecto desde cero: `core.md` → `runtime.md` → `domains.md`.

## 1. La idea

Separa tres decisiones que cambian a ritmos distintos y por razones distintas:

| Decisión | Pregunta | Dónde vive | Cambia cuando… |
|---|---|---|---|
| **QUIÉN** atiende | ¿Qué agente atiende este turno, según el estado del negocio? | Factory del dominio (función pura) | cambia una regla de negocio |
| **QUÉ** puede hacer | ¿Qué sub-agentes, tools, modelos y versiones de prompt tiene? | `definition.json` del agente | cambia la configuración |
| **CÓMO** razona | ¿Qué dice y cómo decide? | Prompts versionados en LangSmith + runtime LangGraph | cambia un prompt o el runtime |

La factory **es** la regla de negocio de enrutamiento: una tabla de decisión sobre las dimensiones del negocio (p. ej. `organización × etapa → agente` o `sede × etapa → agente`), guards de pertenencia al dominio y una prioridad entre dominios. Escalar es agregar una variante (organización, sede...), una etapa o un dominio **sin tocar** el entrypoint, la factory raíz ni el runtime: solo archivos nuevos y una línea de registro.

**Vocabulario**: *dimensión* = dato del negocio que decide quién atiende; *variante* = valor de la dimensión que separa las hojas (una organización, una sede); *caso* = flujo de un dominio (devoluciones, seguimiento...), normalmente uno por etapa.

## 2. Flujo de un turno

```text
entrypoint (Lambda / FastAPI / worker)
  ├─ ctx = load_turn_context(conversation_id)   # dimensiones y estado del negocio, UNA vez por turno
  ├─ agent = root_factory.get_agent(ctx)        # QUIÉN: cadena de factories de dominio
  └─ agent.process()                            # template method del agente
        ├─ agent_roster()   → sub-agentes elegibles este turno (reglas en código + JSON)
        ├─ build_context()  → mensajes de sistema con datos del negocio
        ├─ load_history()   → historial del turno
        └─ run_router()     → LangGraph: router ⇄ call_agent hasta FINISH
                                 └─ cada sub-agente: LangGraph llm ⇄ tools
```

## 3. Estructura

```text
src/
  composition.py                    # composition root: el único módulo que conoce todos los dominios
  core/                             # no importa nada de domains/
    context.py                      # TurnContext
    definition.py                   # esquema Pydantic de definition.json
    agent.py                        # BaseAgent: template method + hooks + tools transversales
    factory.py                      # RootAgentFactory + protocolo DomainAgentFactory
    secrets.py                      # adaptador al gestor de secretos
    runtime/                        # tools.py, models.py, prompts.py, sub_agent.py, router.py
  domains/<dominio>/
    factory.py                      # LA REGLA DE NEGOCIO: guards + REGISTRY
    main.py                         # <Dominio>Agent
    general/<caso>/main.py          # <Caso>AgentGeneral
    <variante>/<caso>/main.py       # <Caso>Agent<Variante>: la hoja (variante = organización, sede...)
    <variante>/<caso>/definition.json
  entrypoints/handler.py
tests/
  unit/domains/<dominio>/test_factory.py      # TST-01
  unit/core/test_root_factory.py              # TST-02
  contract/test_definitions.py                # TST-03
  evals/<dominio>/<variante>/datasets/*.json  # TST-04
```

## 4. Reglas

### Arquitectura (ARQ)

- **ARQ-01 DEBE** — El entrypoint solo conoce `load_turn_context`, `build_root_factory().get_agent` y `BaseAgent.process`. Nunca importa agentes concretos ni pregunta por dimensiones del negocio.
- **ARQ-02 DEBE** — Las dependencias van en una sola dirección: entrypoint → factory → agente → runtime. `core/` no importa nada de `domains/`; solo `composition.py` (el *composition root*) conoce todos los dominios.
- **ARQ-03 DEBE** — Agregar una variante, una etapa o un dominio se hace con archivos nuevos y una línea de registro (en el `REGISTRY` del dominio o, para un dominio nuevo, en `composition.py`). Si el cambio exige editar el entrypoint, el runtime o `RootAgentFactory`, el diseño está mal: detente y propón la alternativa.

### Factory = regla de negocio (FAC)

- **FAC-01 DEBE** — La regla es una función pura `resolve(ctx: TurnContext) -> type[BaseAgent] | None`: sin I/O, sin LLM, sin efectos. Todo lo que necesita para decidir viene en `TurnContext`, que se carga una sola vez por turno.
- **FAC-02 DEBE** — `resolve` tiene dos partes, en este orden: (1) guards que responden «¿este turno es de mi dominio?» y devuelven `None` si no; (2) un lookup en el `REGISTRY` del dominio. `None` significa «no es mío», nunca «error».
- **FAC-03 DEBE** — `REGISTRY` es un dict declarativo anidado por dimensión, `{dimensión_1: {dimensión_2: Clase}}` (p. ej. `organización → etapa`; con tres dimensiones, un nivel más). Es la única fuente de verdad de qué agentes existen; los tests lo recorren. Comenta en el `REGISTRY` qué dimensión es cada nivel.
- **FAC-04 DEBE** — `RootAgentFactory` recorre las factories de dominio en una lista ordenada y gana la primera que devuelve una clase. El orden **es** la prioridad de negocio: comenta por qué cada dominio va antes que el siguiente y cubre cada conflicto de precedencia con un test.
- **FAC-05 DEBE** — Si ninguna factory resuelve, registra un evento estructurado `no_agent_selected` con las dimensiones del contexto y lanza una excepción explícita. Nunca un agente «por defecto» que esconda estados de negocio sin flujo.
- **FAC-06 DEBE** — Cada decisión queda en el log: qué factory resolvió, con qué dimensiones y qué clase eligió.
- **FAC-07 NO** — `if/elif` por organización, sede, etapa u otra dimensión dentro de un agente para decidir quién atiende: eso es una entrada nueva en el `REGISTRY`.
- **FAC-08 NO** — Estado global mutable en factories (singletons en un dict de módulo). Si hace falta memoizar dentro de un turno, el alcance es el request o la invocación.

### Jerarquía de agentes (AGT)

- **AGT-01 DEBE** — Cuatro niveles, cada uno con una responsabilidad:
  1. `BaseAgent` (core): infraestructura común, el template method `process()`, los hooks (`agent_roster`, `build_context`, `load_history`, `on_dead_end`) y las tools transversales (`send_message`).
  2. `<Dominio>Agent(BaseAgent)`: tools, persistencia y reglas de elegibilidad del dominio.
  3. `<Caso>AgentGeneral(<Dominio>Agent)`: lógica del caso de uso compartida entre variantes.
  4. `<Caso>Agent<Variante>(<Caso>AgentGeneral)`: la hoja. Idealmente solo atributos de clase (`DEFINITION_PATH`, `MODELS_PROVIDER`) y, si hace falta, overrides de hooks o tools exclusivas de la variante.
- **AGT-02 DEBE** — Una hoja nunca copia código de otra. Lo común sube a `General`; si dos hojas tienen el mismo método, refactoriza.
- **AGT-03 DEBE** — Una tool es un método público del agente con type hints (`Annotated[tipo, "descripción"]`) y docstring, que es lo que el LLM lee para decidir usarla. Devuelve un `str` legible por el modelo también en caso de error; nunca deja escapar una excepción cruda hacia el LLM.
- **AGT-04 DEBE** — Una instancia de agente vive un turno. El estado persistente vive en la base de datos, no en atributos de la instancia.
- **AGT-05 DEBE** — `build_context` solo expone al LLM lo que el usuario puede ver. Los datos internos (IDs, teléfonos, direcciones) se quedan en atributos privados y solo los usan las tools.

### `definition.json` (DEF)

- **DEF-01 DEBE** — Cada agente hoja tiene su `definition.json` junto a su `main.py`. La variante (organización, sede...) se discrimina por carpeta, no por llaves dentro del JSON.
- **DEF-02 DEBE** — El JSON se valida con un modelo Pydantic al cargarse (`AgentDefinition.load`). Una definición inválida falla en los tests o al arrancar, no a mitad de una conversación.
- **DEF-03 DEBE** — Cada sub-agente declara `name`, `description`, `prompt_settings`, `model_settings` y `tools`, y opcionalmente `terminal_tools` y `channels`. La `description` es el contrato que lee el router: escribe cuándo SÍ y cuándo NO llamarlo.
- **DEF-04 DEBE** — `tools` son nombres de métodos del agente. Cada sub-agente recibe solo las tools que declara (mínimo privilegio), nunca todas las del agente.
- **DEF-05 DEBE** — `prompt_settings.version` fija un commit por ambiente (`{"dev": "<commit>", "prod": "<commit>"}`). Prohibido `latest` y prohibido caer en silencio a la versión de `dev` cuando falta la de `prod`.
- **DEF-06 DEBE** — `model_settings` se agrupa por proveedor (`{"azure": {...}, "openai": {...}}`) y las credenciales son referencias (`"ENV_AZURE_OPENAI_API_KEY"`) que el runtime resuelve contra el gestor de secretos. Nunca un secreto literal.

### Runtime LangGraph (RUN)

- **RUN-01 DEBE** — Cada sub-agente es un `StateGraph` `llm ⇄ tools` que termina cuando el modelo no pide tools o cuando ejecuta una de sus `terminal_tools`.
- **RUN-02 DEBE** — El router es un `StateGraph` supervisor `router ⇄ call_agent` que corre hasta `FINISH`. Decide con `with_structured_output`; el campo `agent` es un `Literal` con los nombres elegibles de ESTE turno más `FINISH`, así un nombre inexistente es imposible por esquema, y `reason` va antes que `agent`. Si la salida no valida se reintenta una vez; después el error sube.
- **RUN-03 DEBE** — Todo `invoke` del router lleva un `recursion_limit` explícito, tomado de `definition.json`, y captura `GraphRecursionError` llamando a `on_dead_end()`: una salida controlada para el usuario (mensaje de fallback o traspaso a una persona) que además registra el bucle. Nunca dependas del límite por defecto.
- **RUN-04 DEBE** — La elegibilidad de sub-agentes del turno (`agent_roster`) se resuelve ANTES de construirlos: lo que no es elegible no se construye, no descarga su prompt y no aparece en el menú del router. Las reglas declarativas (como `channels`) van en el JSON; las que dependen del estado del negocio, en el hook.
- **RUN-05 DEBE** — Las tools se crean con un `ToolFactory` inyectable: `ProductionToolFactory` en producción, `MockToolFactory` en evaluaciones. Ningún sub-agente crea tools por su cuenta.
- **RUN-06 DEBE** — Todo mensaje al usuario pasa por un único sub-agente de comunicación cuya tool terminal es `send_message`. Los demás sub-agentes le devuelven información al router; no le escriben al usuario.
- **RUN-07 DEBE** — Los modelos se crean con `init_chat_model(**settings)`. El proveedor por defecto lo fija la clase (`MODELS_PROVIDER`).

### Prompts (PRM)

- **PRM-01 DEBE** — Los prompts viven en LangSmith (Prompt Hub), no en el código. El código solo referencia `nombre:commit`.
- **PRM-02 DEBE** — Las piezas reutilizables (tono, ejemplos) se inyectan como `inputs` declarados en `prompt_settings`, también fijados por commit.
- **PRM-03 DEBE** — Todo prompt con salidas cerradas incluye una salida de escape explícita para entradas inesperadas (botones, números sueltos, mensajes fuera de tema). Un prompt con solo dos salidas válidas produce callejones sin salida.
- **PRM-04 DEBE** — Al replicar un agente a otra variante (otra organización, otra sede), compara cada prompt y su dataset de evaluación con los de la variante de origen y porta los casos borde (banderas internas que hay que traducir, fallbacks, mensajes especiales). La herencia protege el código, pero los prompts se copian, y ahí se pierden los casos borde.
- **PRM-05 DEBE** — Ningún texto interno (banderas, códigos, mensajes para el router) llega al usuario: el agente de comunicación lo convierte al idioma y al tono de la variante.

### Observabilidad (OBS)

- **OBS-01 DEBE** — Cada `invoke` lleva `run_name` = nombre de la clase del agente, un `thread_id` estable de la conversación y `metadata` con las dimensiones de negocio del turno.
- **OBS-02 DEBE** — La PII se anonimiza antes de enviar trazas.
- **OBS-03 DEBE** — Las decisiones de la factory y del roster quedan en logs estructurados, no solo en la traza del LLM.

### Pruebas (TST)

- **TST-01 DEBE** — Cada factory tiene un test de tabla `ctx → clase esperada | None` que incluye cada guard que rechaza. No necesita mocks porque `resolve` es pura.
- **TST-02 DEBE** — `RootAgentFactory` tiene un test de precedencia por cada par de dominios que puedan reclamar el mismo contexto.
- **TST-03 DEBE** — Un test de contrato recorre TODOS los `REGISTRY` (con cualquier número de dimensiones) y, para cada clase, valida su `definition.json` contra el esquema, comprueba que cada tool declarada existe como método público, que `terminal_tools ⊆ tools` y que cada prompt (también ejemplos e inputs) tiene versión para cada ambiente. Así un agente nuevo queda cubierto sin escribir tests nuevos.
- **TST-04 DEBE** — Cada agente hoja tiene su dataset de evaluación (LangSmith) que corre con `MockToolFactory`.
- **TST-05 DEBE** — Los cambios al prompt del router o a las `description` de los sub-agentes se validan corriendo la suite de evaluación (antes contra después), no reproduciendo mensajes a mano.

## 5. Recetas

El código de cada paso está en [references/domains.md](references/domains.md).

**Agregar una variante (organización, sede...) a un caso existente**
1. `domains/<dominio>/<variante>/<caso>/main.py`: hoja que hereda de `<Caso>AgentGeneral`, solo con atributos de clase.
2. `definition.json` al lado, partiendo de la variante de origen.
3. Compara prompts y datasets con la variante de origen y porta los casos borde (PRM-04). Crea el dataset de la hoja.
4. Una línea en el `REGISTRY` de la factory del dominio y una fila en su test de tabla.
5. Corre el test de contrato (cubre la clase nueva sin tocarlo) y la evaluación.

**Agregar una etapa (un caso) a un dominio**
1. La lógica común va en `general/<caso>/main.py`; las hojas por variante heredan de ella.
2. Un `definition.json` por variante.
3. Una línea por variante en el `REGISTRY` y sus filas en el test de tabla.

**Agregar una dimensión** (p. ej. pasar de `organización → etapa` a `organización → sede → etapa`)
1. Que `load_turn_context` la cargue en `ctx.dimensions`.
2. Un nivel más de anidación en el `REGISTRY` del dominio, su comentario y la columna nueva en el test de tabla. El núcleo no cambia.

**Agregar un dominio**
1. `domains/<dominio>/factory.py` con guards y `REGISTRY`; `domains/<dominio>/main.py` con `<Dominio>Agent`.
2. Regístralo en `build_root_factory()` en la posición que dicta la prioridad de negocio, con su comentario y su test de precedencia.

**Agregar una tool**
1. Método público en el nivel más alto donde aplique (dominio, luego general, luego variante), con `Annotated` y docstring.
2. Decláralo solo en las `tools` del sub-agente que la usa.
3. Agrega su respuesta simulada en el dataset de evaluación.

**Cambiar un prompt**
1. Publica el commit nuevo en LangSmith.
2. Actualiza el hash de `dev`, corre la evaluación y compara; después actualiza `prod`.

## 6. Antipatrones (recházalos en review)

- El LLM decide el dominio, la variante o la etapa: eso es trabajo de la factory (FAC-01).
- Factories que consultan APIs o bases de datos, o que llaman a un LLM (FAC-01).
- `if organization == ...` (o sede, etapa...) dentro de un agente para cambiar de flujo (FAC-07).
- Copiar una hoja completa en vez de subir lo común a `General` (AGT-02).
- Tools que no están en `definition.json`, o todas las tools para todos los sub-agentes (DEF-04).
- Prompts como strings en el código, o `latest` en producción (PRM-01, DEF-05).
- Un agente por defecto silencioso cuando nada coincide (FAC-05).
- Un router sin `recursion_limit` o sin salida controlada (RUN-03).
- Singletons en un dict de módulo dentro de un servidor de larga vida (FAC-08).

## Final Checklist

Antes de entregar o aprobar un PR. Marca ✅ / ❌ (con archivo y motivo) / N/A sobre lo que cambió:

- [ ] El cambio agrega archivos y una línea de registro, sin tocar entrypoint ni runtime (ARQ-03)
- [ ] `resolve` sigue siendo pura y el test de tabla tiene las filas nuevas (FAC-01, TST-01)
- [ ] Cada dominio nuevo tiene su comentario de prioridad y su test de precedencia (FAC-04, TST-02)
- [ ] El test de contrato pasa: esquema, tools existentes, versiones por ambiente (TST-03)
- [ ] Los prompts están fijados por commit en `dev` y `prod` (DEF-05)
- [ ] La evaluación del agente se corrió y se comparó contra la versión anterior (TST-04, TST-05)
- [ ] Logs de decisión y `metadata` de la traza llevan las dimensiones de negocio (FAC-06, OBS-01)

## Referencias

- [references/domains.md](references/domains.md): jerarquía dominio → General → hoja, `definition.json` de ejemplo, factory con guards y `REGISTRY` por dimensiones, registro en `composition.py`, tests de tabla y precedencia, y evaluación con `MockToolFactory`. Léelo al agregar una variante, una etapa, una dimensión, un dominio o una tool.
- [references/core.md](references/core.md): `TurnContext` con sus dimensiones, esquema Pydantic de `definition.json`, `BaseAgent`, `RootAgentFactory`, secretos, entrypoint y test de contrato. Léelo al crear o cambiar el núcleo.
- [references/runtime.md](references/runtime.md): `ToolFactory` (producción y mock), modelos, prompts fijados por commit, grafo del sub-agente y router supervisor. Léelo al crear o depurar el runtime.
- `backend:langgraph-agents`: StateGraph, reducers, checkpointers y streaming en general.
- `backend:langsmith-observability`: prompts versionados, datasets y `evaluate()` (TST-04, TST-05).
- `backend:backend-testing`: modelos fake y fixtures para los tests.
