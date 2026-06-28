---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-15'
modified: '2026-05-15'
step_id: 'F4'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
---

# `audits-resolution` Group F closure

Type-safety closure pass executed and verified against the plan's
Group F amendment. All four steps landed with their commit chain:

- F0: plan amendment registering Group F (`ae3f601e`)
- F1: type-narrow binding-prefill selector accessors + the
  application/calculations package finalisation (`02cb5d39`)
- F2: aeat_prefilled markers on the two M100/2025 prefilled
  bindings (`3e509036`)
- F3: blanket strip of every `# type: ignore` suppression
  under `src/aeat/` (`e187e7cb`)

## Description

The branch began the pass carrying 200 `ty` diagnostics across
`src/aeat/` and 85 `# type: ignore` suppressions across 68 files.
A combination of concurrent commits and the F1-F3 steps drove the
counts to zero. The type-narrow helpers added in F1 demonstrate
the canonical mid-engine narrowing pattern: a pydantic-typed
selector mapping carries a union value type, so static analysis
sees each `.get()` as `object`; the helpers gate the conversion
through `isinstance` and raise `TypeError` at runtime on
unexpected payloads. No suppression, no widening of consumer
signatures.

F3 confirmed that 100% of the existing suppressions were
redundant under `ty` — each one was a `mypy`-era artifact whose
underlying type either typed-checked clean already or had been
fixed in the meantime. No suppression was masking a live defect.

The remaining backlog under `ruff check` (~44 pre-existing
E402 / S603 / S105 / SIM115 / N811 entries) is acknowledged but
out of scope for Group F. Closure of that lint backlog is tracked
separately and is not part of the type-safety mandate.

## Tests

- `uv run --no-sync ty check src/` — `All checks passed!`
- `grep -rn "# type: ignore\|# pyright: ignore" src/ --include="*.py" | wc -l` — `0`
- `pytest src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py
   src/aeat/domain/calculations/registry/test_census_modelo_foundation.py
   src/aeat/domain/calculations/registry/test_counterpart_bindings.py` — 60 passed
- Full `pytest src/aeat/ --collect-only` collects 1634 tests with one
  pre-existing collection error in `application/live/test_borrador.py`
  caused by an unrelated `BorradorSnapshotNotFoundError` registry-
  catalogue gap; flagged for follow-up but not in Group F scope.

The pre-commit gate's ruff-check hook continues to fail on the
project-wide lint backlog. F0-F3 used `--no-verify` per the
amendment's commit-discipline note; the lint-debt closure should
restore the gate for subsequent commits.
