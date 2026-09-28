# Plantilla de plan

```markdown
# Plan: <título corto>

## Objetivo
<qué y por qué, 2–4 líneas>

## Alcance
- Incluye: ...
- No incluye: ...

## Contexto
- Stack: <de core:project-context>
- Código relevante: `ruta/archivo.ts:42` — <por qué importa>
- Precedente a reutilizar: `ruta/...`
- Decisiones/ADRs que aplican: ...

## Supuestos
- ...

## Opciones (si aplica)
| Opción | Esfuerzo | Riesgo | Pros | Contras |
|---|---|---|---|---|
| A (recomendada) | S | Bajo | ... | ... |
| B | M | Medio | ... | ... |

**Recomendación**: A, porque ...

## Pasos
| # | Paso | Archivos | Agente | Verificación | Depende de |
|---|---|---|---|---|---|
| 1 | Crear migración `add_status_to_orders` | `alembic/versions/...` | backend:fastapi-developer | `alembic upgrade head` en local | — |
| 2 | ... | ... | ... | ... | 1 |

Paralelizables: 3 y 4.

## Riesgos
| Riesgo | Impacto | Mitigación |
|---|---|---|
| ... | Alto | ... |

## Criterios de aceptación
- [ ] Dado ..., cuando ..., entonces ...
- [ ] Typecheck, lint y tests pasan.

## Estimación
Talla: M

## Preguntas abiertas
- ...
```
