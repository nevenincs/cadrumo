---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d24baea2bce3cc1a92e0121b860a4da06d87c5a0ffe22e376eb837499bab9d25'
step_id: 'S21'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
# Model the prior-domiciliation KEEP versus CANCEL_OR_MODIFY filing election with baseline-U provenance, split the M303 2023-2025 and 2026 registry layouts at their official page-3 offsets, and thread the safe semantic election through public filing surfaces so S19 can apply Nota 3 without inference

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`
- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/entrypoints/cli/`
- `src/cadrumo/locales/`

## Description

- Add the closed `PriorDomiciliationElection` axis with neutral `KEEP` and fail-closed `CANCEL_OR_MODIFY`.
- Require the amendment's accepted external baseline, exact filing target and justificante reference, one submitted-file `declaration_type` U header, and a matching typed source-header projection before rendering X.
- Persist only semantic election and safe baseline-U proof coordinates in receipts, observations, and `MODELO_EXPORTED` and `MODELO_FILED` events; retain no account data or header bytes.
- Split M303 2023-2025 from the separately grounded 2026 layout, including the moved page-three fields and marker offsets 406 and 440.
- Thread the typed option through export, quickfile, file, verification/review wrappers, CLI payloads, and all locale catalogues.
- Keep S19's Nota-3 DID predicate unimplemented while exposing its typed election input.

## Outcome

S21 is complete. A non-default prior-domiciliation action is legal only for a Modelo 303 rectificativa with the authoritative baseline-U chain; unsupported or unproven requests refuse before bytes, receipts, events, or filing observations. `KEEP` stays blank by default. The old snapshot ends in 2025 and the 2026 snapshot owns the relocated page-three marker and adjacent records. Formal review found and remediated two issues: a HIGH headerless-projection authority bypass and a MEDIUM omission of U proof coordinates from lifecycle events. No open S21 audit finding remains.

## Verification

`uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py src/cadrumo/application/modelo/tests/test_prior_domiciliation_election.py src/cadrumo/application/modelo/tests/test_prior_domiciliation_export_layout.py src/cadrumo/application/modelo/tests/test_domiciliacion_export_refused.py src/cadrumo/application/modelo/tests/test_export_output_paths.py src/cadrumo/domain/calculations/registry/tests/test_modelo_303_registry.py src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py src/cadrumo/entrypoints/cli/tests/test_modelo_payloads.py -q`

`89 passed in 23.09s`

`uv run --no-sync ruff check` on the S21 core, application, CLI, registry, and test scope

`All checks passed!`

`uv run --no-sync basedpyright` on the S21 core and application production scope

`0 errors, 0 warnings, 0 notes`

`uv run --no-sync aeat app registry verify`

`Verificado=True; NÂº revisiones=91; NÂº referencias legales=606; NÂº referencias de origen=314`

`uv run --no-sync python -m dev.locales scaffold --check`

`ca.yml: ok; en.yml: ok; es.yml: ok; hu.yml: ok`

`uv run --no-sync aeat app modelo export --help` and `uv run --no-sync aeat app quickfile --help`

Both commands exit 0 and advertise `--prior-domiciliation-election <keep|cancel_or_modify>` with default `keep`.

## Notes

The two formal-review findings and their focused re-reviews are recorded in `2026-08-09-m303-carry-reconciliation-prior-domiciliation-s21-audit`. The current feature index, plan research-link, and governing ADR modified-stamp warnings were inherited shared-record warnings during validation; they require the authoritative feature/ADR assembly and are not S21 implementation failures.
