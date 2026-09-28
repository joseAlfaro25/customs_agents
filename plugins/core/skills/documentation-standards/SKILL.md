---
name: documentation-standards
description: "Estándares de documentación técnica: README, guías de setup, ADRs, docs de API (OpenAPI), docstrings/TSDoc, changelog y comentarios. Cargar al crear o actualizar documentación, al terminar una feature o cuando el código cambie comportamiento documentado."
---

# documentation-standards

Documenta para **quien llega después**: alguien nuevo en el equipo, tú en 6 meses, u otro agente. La doc desactualizada es peor que ninguna, así que documenta poco pero mantenlo verdadero.

## Qué documento para qué

| Necesidad | Documento | Ubicación |
|---|---|---|
| Qué es, cómo levantarlo, cómo contribuir | README | raíz de cada app/paquete |
| Reglas para agentes y convenciones del repo | CLAUDE.md | raíz (y subcarpetas si difieren) |
| Por qué se tomó una decisión | ADR | `docs/adr/NNNN-*.md` (ver `core:architecture-principles`) |
| Contrato de API | OpenAPI generado (`@nestjs/swagger`, FastAPI `/docs`) + descripciones en código | código + `docs/api/` si se exporta |
| Cómo funciona un subsistema | Doc de arquitectura con diagrama | `docs/architecture/*.md` |
| Cómo operar (deploy, rollback, incidentes) | Runbook | `docs/runbooks/*.md` |
| Qué cambió entre versiones | CHANGELOG | raíz (Keep a Changelog) |
| Qué hace una función no obvia | Docstring / TSDoc | en el código |

Plantillas: [references/templates.md](references/templates.md).

## Reglas de escritura

- **Empieza por lo que el lector necesita hacer.** Setup en ≤ 5 comandos copiables.
- Frases cortas, voz activa, segunda persona ("Ejecuta...", "Configura...").
- Ejemplos reales y probados. Cada comando de la doc debe funcionar tal cual.
- Nombres exactamente como en el código (rutas, variables de entorno, scripts).
- Usa tablas para variables de entorno, scripts y opciones.
- Enlaza en vez de duplicar (a la doc oficial, a otro doc del repo).
- Idioma: el que ya use el proyecto; si no hay, el del equipo.

## Código

**TypeScript (TSDoc)** — en exports públicos y funciones no obvias:

```ts
/**
 * Calcula el total con impuestos aplicando el redondeo bancario.
 *
 * @param items - Líneas del pedido; se ignoran las de cantidad 0.
 * @returns Total en centavos.
 * @throws {InvalidCurrencyError} Si las líneas mezclan monedas.
 */
export function calculateTotal(items: OrderItem[]): number { ... }
```

**Python (docstrings estilo Google)**:

```python
def calculate_total(items: list[OrderItem]) -> int:
    """Calcula el total con impuestos aplicando redondeo bancario.

    Args:
        items: Líneas del pedido; se ignoran las de cantidad 0.

    Returns:
        Total en centavos.

    Raises:
        InvalidCurrencyError: Si las líneas mezclan monedas.
    """
```

- No documentes lo obvio (`/** Returns the name */ getName()`).
- APIs: `summary`/`description` en endpoints, ejemplos en schemas (`@ApiProperty({ example })`, `Field(examples=[...])`), respuestas de error documentadas.
- Prompts de LLM: cada prompt con comentario de propósito, variables esperadas y versión.

## Cuándo actualizar

Actualiza la doc **en el mismo cambio** cuando:

- Cambia cómo se instala, configura, ejecuta o despliega algo.
- Se agrega/quita una variable de entorno (también `.env.example`).
- Cambia un contrato de API o un comportamiento visible.
- Se toma una decisión de arquitectura (ADR).

## Changelog

Formato Keep a Changelog, secciones `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`, con `[Unreleased]` arriba. Una línea por cambio, orientada al usuario del software, no al commit.

## Checklist

- [ ] Los comandos se probaron (o se marcó lo que no se pudo probar).
- [ ] Variables de entorno listadas con descripción y ejemplo sin secretos.
- [ ] Links relativos funcionan.
- [ ] Sin información desactualizada que contradiga el código.
- [ ] Sin secretos, URLs internas sensibles ni datos personales.
