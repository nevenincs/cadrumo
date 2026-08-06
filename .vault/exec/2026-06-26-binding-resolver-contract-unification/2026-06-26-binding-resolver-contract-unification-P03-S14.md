---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:249b60fcf2e62f2bee38830830195fd941893dfa626f22f8517bb54ab57061d7'
step_id: 'S14'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---

# Keep the CLI aggregate verb as a thin delegating projection whose aggregation delegates to the ONE mesh resolver with no re-implemented aggregation in the verb and whose persist-retencion-observations side-effect delegates to the existing single-writer observation repository with no bespoke parallel write path per composition-service-no-parallel-write-path, retiring the verb ONLY if proven to have no distinct operator purpose beyond calculate/pull and then only with the full documented-command-conformance plus how-to plus suggestion/next_action/help sweep

## Scope

- `src/aeat/entrypoints/cli/_modelo.py`

## Description

Prove the retained aggregate command is a thin projection over the application service and shared persistence path, following the live command split to `_modelo_aggregate_cli.py`.

- Re-read the current CLI command implementation and service implementation after the command split. The live entrypoint delegates all aggregation to `aggregate_per_modelo`; it does not call `aggregate_retenciones_*`, `aggregate_counterpart_*`, or `aggregate_foreign_assets_720` directly.
- Confirm the retenciones side effect delegates to `persist_retencion_observations`, with `aggregate_per_modelo` kept pure and the retenciones service branch already routed through `RetencionesAggregationSourceResolver.aggregate` by S13.
- Keep the command because it has a distinct explicit-observation operator purpose and a Modelo 190 per-clave reconciliation projection; no retirement sweep is warranted in this step.
- Update the backend-boundary gate's canonical aggregate CLI path from `_modelo.py` to `_modelo_aggregate_cli.py` so the gate follows the live module split while still rejecting duplicate aggregate surfaces and family-specific aggregation calls outside the canonical entrypoint.

## Outcome

S14 evidence is complete at HEAD. The aggregate command remains a single CLI projection over `aggregate_per_modelo`; retenciones persistence is a call to the existing repository-facing `persist_retencion_observations`; and the boundary gate proves there is no second CLI aggregation surface or CLI-local family aggregation implementation.

Focused verification passed in the original evidence pass:

- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_backend_boundary.py::test_per_modelo_aggregation_duplicate_cli_surfaces_stay_absent` -> `1 passed`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_190_clave_breakdown.py` -> `2 passed`.
- `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_per_modelo_service.py` -> `23 passed`.

Current follow-up verification (2026-07-04) re-ran the S14-specific gates after the plan-file WIP cleared:

- `uv run --no-sync vaultspec-rag search "aggregate CLI thin projection aggregate_per_modelo persist_retencion_observations" --type code --port 8766 --max-results 12 --timeout 30`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_backend_boundary.py::test_per_modelo_aggregation_duplicate_cli_surfaces_stay_absent` -> `1 passed`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_190_clave_breakdown.py` -> `2 passed`.
- `uv run --no-sync aeat app modelo aggregate --help` confirms the retained operator-visible aggregate command and accepted observation flags.

The broader `src/aeat/application/aggregation/tests/test_per_modelo_service.py` suite is currently red in the shared worktree because non-authored untracked Modelo 145 registry scaffolding invalidates registry authority before the aggregation assertions run. That registry WIP is outside the S14 CLI projection target and is recorded separately as gate-health inventory; it does not show a duplicate aggregate CLI surface or a CLI-local family aggregation implementation.

## Notes

RAG discovery was attempted first but remained blocked: the service on port 8766 was unreachable, and `vaultspec-rag server start --port 8766` refused to start because a resident Python process owned the machine singleton. This pass used targeted source, CLI help, and test evidence after recording that blocker.

`uv run --no-sync aeat app modelo aggregate --help` confirms the command remains operator-visible for modelos 111, 115, 123, 180, 190, 193, 347, 349, and 720 with typed observation flags. The generated scope row still names `_modelo.py`; the live registration has been split into `_modelo_aggregate_cli.py`, so the evidence follows the current entrypoint. The S14 target files and the plan file were clean before the follow-up checkbox reconciliation.
