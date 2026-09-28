# Diagramas con Mermaid

Mermaid se renderiza en GitHub, GitLab y la mayoría de visores markdown. Mantén los diagramas junto a la doc que explican.

## Contexto / contenedores (estilo C4 simplificado)

```mermaid
flowchart LR
  user([Usuario])
  web[Next.js web]
  mobile[Expo app]
  api[NestJS API]
  ai[FastAPI + LangGraph]
  db[(PostgreSQL)]
  vec[(pgvector)]
  ls[[LangSmith]]

  user --> web & mobile
  web & mobile -->|REST/JSON| api
  api -->|HTTP interno| ai
  api --> db
  ai --> vec
  ai -.->|traces| ls
```

## Secuencia

```mermaid
sequenceDiagram
  participant C as Cliente
  participant A as API
  participant G as Agente (LangGraph)
  participant L as LLM
  C->>A: POST /chat
  A->>G: invoke(state, thread_id)
  G->>L: prompt + tools
  L-->>G: tool_call
  G->>G: ejecuta tool
  G->>L: resultado
  L-->>G: respuesta
  G-->>A: estado final
  A-->>C: 200 {message}
```

## Estado

```mermaid
stateDiagram-v2
  [*] --> pending
  pending --> paid: pago confirmado
  pending --> cancelled: timeout / usuario
  paid --> refunded
```

## Reglas

- Un diagrama = una pregunta ("¿quién habla con quién?", "¿en qué orden?").
- Nombres iguales a los del código.
- Máximo ~12 nodos; si hay más, divide por nivel.
