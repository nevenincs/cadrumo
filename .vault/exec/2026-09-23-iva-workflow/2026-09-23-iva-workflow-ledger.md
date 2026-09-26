---
tags:
  - '#exec'
  - '#iva-workflow'
date: '2026-09-23'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:589f28c76668b17099d724c630146b13a1316fa49b77b9c8da77123e8952e66c'
related:
  - "[[2026-09-23-iva-workflow-plan]]"
---

# `iva-workflow` ledger

## Changes

- `S01` `M` `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`
- `S01` `M` `src/cadrumo/application/filing/producer_snapshot.py`
- `S01` `M` `src/cadrumo/application/filing/export_producer.py`
- `S01` `M` `src/cadrumo/application/filing/projection.py`
- `S01` `M` `src/cadrumo/application/modelo/m303_filing_evidence.py`
- `S01` `M` `src/cadrumo/application/filing/tests/test_producer_snapshot.py`
- `S01` `verify:` `pytest -m 'unit or integration' application/filing/tests domain/modelos/tests + M303 evidence suites: 707 passed` -> `pass`
- `S02` `M` `src/cadrumo/application/modelo/m303_ordinary_evidence_coordinate.py`
- `S02` `M` `src/cadrumo/application/modelo/m303_ordinary_filing_evidence_authoring.py`
- `S02` `M` `src/cadrumo/application/modelo/m303_exonerado_390_applicability_attestation.py`
- `S02` `M` `src/cadrumo/application/modelo/preconditions.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/tests/test_m303_ordinary_filing_evidence_authoring.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/tests/test_m303_exonerado_390_applicability_attestation.py`
- `S02` `verify:` `S02-S05 population pytest -m 'unit or integration': 2210 passed, 7 pre-existing failures (all fail at clean HEAD 1cf639c287)` -> `pass`
- `S03` `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/tests/test_m303_calculate_evidence_admission.py`
- `S03` `verify:` `conformance and calculate-admission tests incl. pending v1 and v2 refusal` -> `pass`
- `S04` `M` `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/_app_quickfile.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/modelo_work_command_specs.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/_app_quickfile_command_specs.py`
- `S04` `M` `src/cadrumo/locales/en/cli.yml`
- `S04` `M` `src/cadrumo/locales/es/cli.yml`
- `S04` `M` `src/cadrumo/locales/ca/cli.yml`
- `S04` `M` `src/cadrumo/locales/hu/cli.yml`
- `S04` `verify:` `M303 CLI, quickfile and dependent CLI tests; dev.locales audit ok in four locales` -> `pass`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/m303_evidence.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/lifecycle.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/view/overview.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S05` `M` `src/cadrumo/locales/en/common.yml`
- `S05` `M` `src/cadrumo/locales/es/common.yml`
- `S05` `M` `src/cadrumo/locales/ca/common.yml`
- `S05` `M` `src/cadrumo/locales/hu/common.yml`
- `S05` `verify:` `TUI modelo tests` -> `pass`
- `S07` `M` `docs/_sequences/contracts/how-to/file-at-aeat/file-at-aeat-chain.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-address-by-id.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-chain.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-exact-ids.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-file.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-history.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-revision-by-id.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-select.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/filing-spine/filing-spine-visible-target.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/iva-lifecycle/iva-lifecycle-q1.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/modelo-303/modelo-303-first-quarter.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/modelo-303/modelo-303-inspect-boxes.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/modelo-303/modelo-303-revision.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/troubleshooting/troubleshooting-period-grammar.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/verification-reports/verification-reports-export-check.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/verification-reports/verification-reports-incomplete.seq`
- `S07` `M` `docs/_sequences/contracts/how-to/verification-reports/verification-reports-modelo-303.seq`
- `S07` `M` `docs/_sequences/how-to/file-at-aeat/file-at-aeat-chain.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-address-by-id.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-chain.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-discard.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-exact-ids.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-file.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-history.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-rename.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-revision-by-id.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-runs.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-select.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-visible-target.json`
- `S07` `M` `docs/_sequences/how-to/filing-spine/filing-spine-work-list.json`
- `S07` `M` `docs/_sequences/how-to/iva-lifecycle/iva-lifecycle-q1.json`
- `S07` `M` `docs/_sequences/how-to/modelo-303/modelo-303-first-quarter.json`
- `S07` `M` `docs/_sequences/how-to/modelo-303/modelo-303-inspect-boxes.json`
- `S07` `M` `docs/_sequences/how-to/modelo-303/modelo-303-revision.json`
- `S07` `M` `docs/_sequences/how-to/modelo-390/modelo-390-annual-2025.json`
- `S07` `M` `docs/_sequences/how-to/modelo-390/modelo-390-inspect.json`
- `S07` `M` `docs/_sequences/how-to/modelo-390/modelo-390-supply-binding.json`
- `S07` `M` `docs/_sequences/how-to/troubleshooting/troubleshooting-period-grammar.json`
- `S07` `M` `docs/_sequences/how-to/verification-reports/verification-reports-export-check.json`
- `S07` `M` `docs/_sequences/how-to/verification-reports/verification-reports-incomplete.json`
- `S07` `M` `docs/_sequences/how-to/verification-reports/verification-reports-modelo-303.json`
- `S07` `M` `docs/_sequences/how-to/verification-reports/verification-reports-work-history.json`
- `S07` `M` `docs/_sequences/seeds/iva-year-2025.seq`
- `S07` `verify:` `python -m dev.docs.sequences check --coherence (7 pages)` -> `pass`
- `S06` `M` `dev/acceptance/iva/installed_m303_evidence_journey.py`
- `S06` `M` `.agents/session-briefs/handoffs/2026-09-23-iva-modelo-evidence-lease-return.md`
- `S06` `verify:` `installed m303 evidence journey at 70fdb5c85b, wheel 883579f8, generation 02bd5859` -> `pass`

## Notes

- `S01` 6 failures in adapters/persistence/profile/tests/test_m303_filing_evidence_validation.py (ModeloProfileReadinessError profile_absent/inactive) reproduce identically at committed source 976971d1be before this Step; pre-existing, reported. 1 failure is the retired-token guard awaiting the error rename.
- `S02` Monthly work for a non-monthly filer was refused by no owner; the authoring now requires the period to belong to a registry filing schedule applicable to the profile (applicable_filing_schedules), grounded in the schedules' RD 1624/1992 art. 71 conditions.
- `S04` The CLI reference is generated at docs build time and has no committed output to regenerate.
- `S05` Whether a period asks the Modelo 390 exemption is a governed fact; the overview first called it outside a pinned scope, which raises in the real TUI. The lifecycle door now resolves it under the pinned authority.
- `S07` committed 12ede7d99d
- `S06` fixes found by earlier attempts landed in ba73e0945f, 9ea5028fa4, 0e46b2a89a, 70fdb5c85b; notice-delivery intermittent seen 2 of 5 runs remains open
