---
name: testing-strategy
description: "Estrategia general de testing: qué testear, en qué nivel (unit, integración, e2e), cómo nombrar y estructurar tests, datos de prueba, mocks y cobertura. Cargar al escribir tests, definir cómo verificar una feature o revisar la calidad de una suite, junto con la skill de testing del stack."
---

# testing-strategy

Los tests existen para **poder cambiar el código con confianza**. Un test que no fallaría si el comportamiento se rompe no sirve; uno que falla con cada refactor tampoco.

## Qué nivel usar

| Nivel | Qué cubre | Velocidad | Cuándo |
|---|---|---|---|
| **Unit** | Función/clase/componente aislado | ms | Lógica de negocio, cálculos, validaciones, reducers, hooks, parsers |
| **Integración** | Varios módulos reales + infra real o en contenedor (DB, HTTP) | s | Endpoints, repositorios, Server Actions, grafo LangGraph con modelo falso |
| **E2E** | Sistema completo desde la UI | s–min | Pocos flujos críticos: login, checkout, onboarding |

Regla práctica: muchos unit, bastantes de integración en los bordes (API, DB), pocos e2e para lo que da dinero o bloquea usuarios.

Skill por stack:

- Web: `frontend:frontend-testing` (Vitest/Jest, React Testing Library, MSW, Playwright)
- API / LLM: `backend:backend-testing` (Jest + @nestjs/testing, pytest + httpx, fakes de LLM)
- Mobile: `mobile:mobile-testing` (jest-expo, RNTL, Maestro/Detox)
- Evaluación de calidad de LLM: `backend:langsmith-observability` (datasets y evaluadores; complementa, no reemplaza, los tests)

## Qué testear (prioridad)

1. Reglas de negocio y casos límite (vacío, cero, negativo, máximo, unicode, fechas/zonas horarias).
2. Caminos de error: validación, no encontrado, no autorizado, dependencias caídas, timeouts.
3. Contratos: forma de la respuesta de la API, códigos de estado.
4. Regresiones: **todo bug arreglado lleva un test que falla sin el fix**.
5. Flujos críticos de usuario (e2e).

No testees: getters triviales, el framework, librerías de terceros, detalles de implementación (estado interno, métodos privados, clases CSS).

## Estructura de un test

- **Arrange / Act / Assert**, separados visualmente.
- Un comportamiento por test; varios `expect` están bien si verifican ese comportamiento.
- Nombre = comportamiento esperado:
  - TS: `it('returns 404 when the order does not exist')`
  - Python: `def test_returns_404_when_order_does_not_exist():`
- Sin lógica en los tests (`if`, bucles con condiciones). Usa tablas parametrizadas (`it.each`, `@pytest.mark.parametrize`).
- Independientes y en cualquier orden: sin estado compartido entre tests.

## Datos de prueba

- Factories/builders con valores por defecto válidos y overrides explícitos (`buildOrder({ status: 'paid' })`).
- Solo especifica en el test los campos que importan para ese caso.
- Nada de datos reales de producción ni PII.
- Tiempo y aleatoriedad controlados (fake timers, `freezegun`/`time-machine`, seeds).

## Mocks: dónde cortar

- Mockea en la **frontera del sistema**: red externa (MSW, `respx`), LLMs (fake chat models), reloj, email, pagos.
- No mockees lo que es tuyo y barato de usar de verdad (servicios internos, la DB en tests de integración si hay contenedor/SQLite compatible).
- Prefiere **fakes** (implementación en memoria) sobre mocks con expectativas de llamadas.
- Si para testear algo necesitas 5 mocks, el diseño tiene demasiadas dependencias: señálalo.

## LLMs y código no determinista

- Tests: modelo falso con respuestas fijas → testeas la orquestación (ruteo de nodos, parseo, manejo de errores, tools), no la "inteligencia".
- Calidad de respuestas: datasets + evaluadores en LangSmith, fuera del pipeline de unit tests o como job separado.
- Nunca llames a un LLM real en la suite por defecto (costo, flakiness). Márcalos (`@pytest.mark.llm`) y ejecútalos a demanda.

## Cobertura

- Úsala para encontrar código **sin** tests, no como objetivo. Mejor 70 % con buenos asserts que 95 % sin ellos.
- Código nuevo de lógica de negocio: cubrir caminos felices y de error.
- Respeta el umbral del proyecto si existe (config de Jest/Vitest/pytest-cov).

## Tests flaky

Un test intermitente es un bug. Causas típicas: esperas fijas (`sleep`), orden de ejecución, reloj real, red real, estado compartido. Arregla la causa; no agregues reintentos para taparlo.

## Checklist

- [ ] Cada criterio de aceptación tiene al menos un test.
- [ ] Caminos de error cubiertos.
- [ ] El test falla si se revierte el cambio (verifícalo mentalmente o de verdad).
- [ ] Sin llamadas a red/LLM reales.
- [ ] Nombres describen comportamiento.
- [ ] La suite afectada pasa localmente; reporta el comando y el resultado.
