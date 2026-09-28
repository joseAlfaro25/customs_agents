# Plantilla de pull request

```markdown
## Qué
<Resumen de 1–3 líneas del cambio.>

## Por qué
<Problema o necesidad. Link al ticket: PROJ-123>

## Cómo
- <Decisiones de implementación relevantes para el reviewer>
- <Alternativas descartadas, si aplica>

## Cómo probarlo
1. `pnpm dev`
2. Ir a /orders y pulsar "Exportar"
3. Resultado esperado: se descarga `orders.csv` con N filas

## Checklist
- [ ] Tests agregados/actualizados
- [ ] Typecheck, lint y tests pasan
- [ ] Docs / `.env.example` actualizados
- [ ] Migraciones compatibles hacia atrás
- [ ] Sin secretos ni datos sensibles

## Capturas / notas de despliegue
<Si aplica: screenshots de UI, variables nuevas, orden de despliegue, feature flags.>
```
