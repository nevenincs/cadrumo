---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S112'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S112

Completed the first convention-hardening audit for declaration extraction and
adjacent shared surfaces.

- Created: `.vault/audit/2026-05-26-declaracion-extraction-convention-hardening-audit.md`
- Modified: `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`

## Description

Added Wave `W06` to the plan and recorded concrete rows for localization,
exception hierarchy, exception swallowing/logging, tautology resistance,
settings centralisation, and shared model/pydantic reuse.

The audit found that the current exception inheritance chain is largely
correct, declaration extraction does not introduce new direct environment
wrangling, and the implementation uses existing pydantic/shared model
boundaries. It also found concrete hardening work: raw operator-facing parse
messages need `tr()`, inbound declaration/PDF modules need AST exception
hygiene guard coverage, and the new Modelo 840 source-grounding test should
pin printed labels explicitly.

## Tests

No runtime tests were run for this audit-only step. Follow-up rows `W06.P19.S113`
through `W06.P19.S118` carry the implementation and test slices.
