---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-22-cli-workflow-redesign-exec]]'
  - '[[2026-05-23-cli-workflow-redesign-exec]]'
---

# `cli-workflow-redesign` W03.S13 Rate Schedules Review

Status: PASS. No findings.

Scope reviewed: the W03.S13 closure supplement in
`src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py`
only. Production code was not edited.

The stale W03.S13 plan row is defensible to close from the combined
evidence. The original W03.S13 execution record documents the Modelo 200
LIS Art. 29 rate schedule correction, the scalar legal-entity rate
parameters, the micro-empresa bracket table, the legal-entity-form
profile binding, and the formula dispatch into casilla 00558. The
2026-05-23 review record independently passed that implementation with
no Critical or High findings and called out the remaining micro-empresa
runtime dispatch boundary as an explicit deferred design item rather
than a hidden wrong-rate path.

The supplement adds the missing registry-level closure guard across the
entity-type surface. It verifies that the Modelo 100 natural-person path
carries the 2025 IRPF bracket-table schedules for estatal general,
estatal ahorro, autonómica ahorro, and CCAA-dispatched autonómica
general scales, with the expected LIRPF legal grounding and source
grounding. It also verifies that the Modelo 200 legal-entity path carries
the LIS scalar rates, the micro-empresa bracket schedule, the
profile-sourced `legal_entity_form` binding, and the
`modelo-200-tipo-gravamen-por-forma-juridica` dispatch table with the
expected legal grounding and routing.

This is not tautological coverage: the test checks registry shape,
grounding, and dispatch wiring across loaded snapshots; the numeric
rate-oracle and runtime-dispatch behaviours remain covered by the
existing W03.S13 tests named in the execution and review evidence. The
supplement does not replace those tests, but it closes the plan-row
question of whether both taxpayer entity routes have registered,
grounded bracket/rate schedules visible at the registry boundary.

Verification performed during this audit:

- `uv run pytest src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py -q` -> 2 passed.
- `uv run ruff check src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py` -> passed.
- `uv run aeat app registry verify` -> `Verificado=True`.

Residual risk: the worktree contains broad unrelated WIP outside this
supplement. I treated it as ambient shared-branch state and reviewed only
the requested W03.S13 closure supplement plus the named execution and
review evidence.
