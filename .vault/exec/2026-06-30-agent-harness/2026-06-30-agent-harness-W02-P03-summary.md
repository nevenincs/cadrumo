---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W02.P03` summary

Phase P03 established the operator harness home, the read accessor, and the
packaging boundary. All four steps closed; landed in commit `9fa93526c`.

- Created: `src/aeat/_data/agent/README.md`
- Created: `src/aeat/agent/__init__.py`
- Created: `src/aeat/agent/tests/test_harness_data_ships.py`
- Modified: `pyproject.toml`

## Description

- S10: Created the shipped harness data tree under `src/aeat/_data/agent/` with a
  README describing the rules/personas/skills layout and the backbone-versus-
  operating-layer framing.
- S11: Declared the `aeat[agent]` optional extra (and added it to `all`). The
  harness operating layer ships in the core wheel as reviewed product data; the
  extra is the capability boundary that will carry the MCP server runtime
  dependency when the server lands. No weights or credentials are bundled.
- S12: Added the `aeat.agent` read accessor over the shipped tree, resolving it
  through the same bundled-data boundary (`aeat.core.resources.packaged_data`)
  that ships corpus/registry. It exposes the operator rules, personas, and skill
  documents; it carries no tax logic and computes no value.
- S13: Added a packaging probe asserting the harness tree resolves through the
  bundled-data boundary and the accessor reads every shipped rule.

## Outcome

`import aeat.agent` works in the core environment (no extra needed); the accessor
returns the four operator rules. The `aeat[agent]` extra and its inclusion in
`all` validate. Three packaging-probe tests pass.

## Notes

S13 was implemented as a bundled-data-boundary reachability test rather than a new
`Justfile` wheel-build recipe. The boundary is the exact mechanism by which
`_data` ships (corpus/registry use it identically), so the test is the
right-sized, co-located proof; the heavyweight packaging-smoke wheel-build lanes
are owned by the product-packaging campaign and a full agent-tree assertion there
is a follow-up rather than this feature's surface.
