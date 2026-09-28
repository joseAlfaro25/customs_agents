# suite

Plugin "paraguas": no trae agentes ni skills propios, solo declara como dependencias los 5 plugins
de la suite. Al instalarlo, Claude Code instala y habilita automáticamente `core`, `frontend`,
`backend`, `devops` y `mobile`.

```bash
claude plugin install suite@my-agents
```

Para desinstalar todo: `claude plugin uninstall suite@my-agents --prune -y`.
