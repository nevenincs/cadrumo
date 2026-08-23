# cadrumo-harness

Agent-facing operating layer for [Cadrumo](https://github.com/nevenincs/cadrumo): operator
rules, tax-advisor personas, workflow skills, and the MCP server that exposes the `aeat`
CLI to an LLM operator.

`cadrumo` is a deterministic Spanish tax calculation CLI. It carries no dependency on this
package. `cadrumo-harness` depends on `cadrumo` and operates it through its public
interface — it never reaches into `cadrumo`'s private modules.

## Contents

- `cadrumo_harness._data.agent` — the reviewed markdown operating layer: operator rules,
  tax-advisor personas, and per-modelo workflow skills.
- `cadrumo_harness` (top level) — the read accessor for that data.
- `cadrumo_harness.mcp` — the `cadrumo-mcp` stdio MCP server, wrapping `cadrumo` CLI/
  application commands as agent-callable tools, resources, and prompts.

## Install

```
pip install cadrumo-harness
```

Installs `cadrumo` as a dependency and provides the `cadrumo-mcp` console script.
