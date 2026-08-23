# AEAT operator agent-harness data

This tree is the **operating layer** for an LLM tax-advisor agent that drives the
deterministic `aeat` CLI. It is reviewed product data shipped inside the wheel and
read through the bundled-data boundary (`aeat.agent`). It carries no code and no
secrets.

The `aeat` CLI is the **backbone**: it computes the tax deterministically. The
harness is the **operating layer**: the agent orchestrates, extracts, classifies,
narrates, and hands off — but never computes a tax value itself.

Subtrees:

- `rules/` — the operator operating contract: always-on behavioural boundaries the
  agent loads every session. These are the operator analogues of the engineer-facing
  project rules, re-cast for the agent that *uses* the tool.
- `personas/` — tax-advisor role definitions (coordinator and task-scoped roles),
  each given the capability manifest and the operating rules, with tool access scoped
  to its mutability tier.
- `skills/` — executable workflow playbooks (preconditions, command sequence, JSON
  success assertions) for the canonical end-to-end tax flows.

The capability catalogue the agent reads first is served by the MCP server's
`contract` tool.
