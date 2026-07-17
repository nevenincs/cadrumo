---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S257'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-W07-E hexagonal violation in modelo project CLI verb: calculate_registry_snapshot imported from domain.calculations.registry directly at the CLI layer

## Scope

- `extract snapshot acquisition + engine call into a thin application.modelo service function and have the verb call only that service`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

Verified at HEAD (no re-implementation): the named hexagonal violation is absent from the production CLI layer.

- Grep-confirmed no production file under `entrypoints/` imports `calculate_registry_snapshot` from `domain.calculations.registry`; the only reaches are test oracles (`test_modelo_compare.py`, `test_modelo_projection.py`, `test_registry_cli_live.py`), which legitimately call the engine directly to build an independent oracle side.
- Confirmed `entrypoints/cli/_modelo.py` acquires its snapshot and runs the engine only through the `application.modelo` facade (`build_work_calculate_input_bundle`, `calculate_modelo_work_revision`, `assemble_work_unit_history`), not by dotting into the domain registry; its sole `domain.calculations.registry` import is the typed `CasillaId` / `RegistryValidationError` / `validated_casilla_id` value contract, which is not the snapshot-acquisition/engine-call surface the violation named.
- Confirmed the snapshot-acquisition-plus-engine-call boundary lives in the application layer (`application/verification/_verify.py`, `application/filing`, `application/calculations/_binding_prefill.py`), consistent with the hexagonal direction.

## Outcome

Step closed as pre-satisfied at HEAD. The modelo CLI verb calls only application-layer services for snapshot acquisition and engine execution; the domain registry engine is no longer imported at the CLI layer.

Gate green: the production import-hygiene ratchet in `test_import_hygiene_gate.py` passes (9 production checks green).

## Notes

RAG/grep queries run: grep `calculate_registry_snapshot` across `entrypoints/`, `application/`, and `domain/`; grep the `application.modelo` / `application.verification` reach in `_modelo.py`.

Peer-churn distinguished per the full-tree-gate-owner discipline: two rows in `test_import_hygiene_gate.py` are red — `test_test_only_underscore_reaches_do_not_exceed_test_debt_count` and `_are_exactly_the_named_test_debt_set`. Both concern TEST-file private-symbol reaches (e.g. `derive_work_unit_id`, `ErrorCategory`) against a peer-owned test-debt baseline; neither is a production hexagonal violation and neither touches the CLI snapshot/engine boundary this Step owns.
