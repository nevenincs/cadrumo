---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:a5d47bc8d68a3dd9895f0219261100b0d214c0fb5cbf256b2b1e3aef9322bdb5'
step_id: 'S04'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

# Classify candidates as grounded, revision-exact, or continuity-candidate without promoting provisional identity

## Scope

- `dev/registry/migration`

## Description

- Re-ground the classification boundary with `vaultspec-rag`, the ADR, and feasibility research.
- Group only ungrounded declared `casilla.id` values by Modelo and repeated revision presence.
- Classify declared continuity as `grounded`, unique ungrounded occurrences as `revision_exact`, and repeated ungrounded occurrences as `continuity_candidate`.
- Attach an explicit migration-only provisional group token without changing the S03 canonical address.
- Add real bundled-corpus tests for the measured partition and refusal to serialize incomplete provisional state.

## Outcome

Implemented immutable structural classification in `dev/registry/migration`.
The complete current population partitions into:

- 144 grounded rows from 18 declared continuity occurrences.
- 32,008 revision-exact rows.
- 94,040 continuity-candidate rows across 2,354 provisional groups.

Classification uses only declared continuity presence and repeated
Modelo/casilla occurrence across revisions. It never promotes a provisional
group into `continuidad_id`, and it never uses values, labels, printed
numbers, or normalized text as semantic evidence.

Modified files:

- `dev/registry/migration/__init__.py`
- `dev/registry/migration/manager.py`
- `dev/registry/migration/tests/test_candidate_classification.py`
- `.vault/reference/2026-08-04-modelo-localization-cascade-reference.md`
- `.vault/exec/2026-08-04-modelo-localization-cascade-W01-P02-S04.md`
- `.vault/plan/2026-08-04-modelo-localization-cascade-plan.md`
- `.vault/audit/2026-08-04-modelo-localization-cascade-audit.md`

## Notes

Focused validation passed:

- `uv run --no-sync ruff format --check dev/registry/migration`
- `uv run --no-sync ruff check dev/registry/migration`
- `uv run --no-sync basedpyright dev/registry/migration`
- `uv run --no-sync pytest dev/registry/migration/tests/test_candidate_classification.py -q -n 0 -m integration` — 2 passed.

No production schemas, locale data, readers, migration output, or live
registry were modified. Later source-hash manifest and emission steps remain
out of scope.
