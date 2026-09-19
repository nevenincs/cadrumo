---
tags:
  - '#reference'
  - '#filing-chain-reconciliation'
date: '2026-09-17'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:723e1acd06c9a2cde5db6a9f99079a02c1d6f2d59b9fff960caf18f212d9ddb7'
related: []
---

# `filing-chain-reconciliation` reference: `Filing chain, amendment and AEAT reconciliation code map`

Code map for how Cadrumo records filings, local corrections, AEAT evidence and manual overrides of one period, and where those paths disagree. The sources are the live tree on 2026-09-17, a legal-mechanics survey (section "Legal mechanics") and a CLI/TUI/test surface map (section "Surfaces").

## Summary

### Two stores describe the filed answer of a period

- The filing catalogue `ModeloRecordCatalogue` (`src/cadrumo/domain/modelos/filing_record.py:307`) is already a chain. Each `ModeloRecord` (`:161`) has a `status` (`VIGENTE`/`SUPERSEDIDO`), `superseded_by_filing_record_id`, `amends_filing_record_id`, `aeat_accepted` and `external_evidence`. The catalogue enforces one `VIGENTE` per `(bucket, modelo, year, period, member)` (`:330`) and two-sided amendment links (`:352`). `history_for` (`:455`) returns the chain ordered by `filed_at`.
- The observation store `CalculationObservationRepository` (`src/cadrumo/adapters/persistence/profile/calculation_observations.py:74`) holds ONE envelope per `observation_key(modelo, period)` (`src/cadrumo/application/calculations/observations_repository.py:406`), with an optional member widening (`:437`). The envelope `ObservationEnvelopePayload` (`:196`) carries `source_kind` (`ObservationSourceKind`, `:89`: `app_filing`, `operator_manual`, and three official AEAT kinds), `source_metadata` and `source_headers`. Seventeen production call sites read it through `load_observation`/`iter_modelo`. Among them are the `previous_filing` carry and the cross-period clean-state gate (`src/cadrumo/application/calculations/cross_period_clean_state.py:867`).
- Nothing projects one store from the other. Each write path updates them independently.

### Write paths

- Local file: `file_modelo_revision` (`src/cadrumo/application/modelo/filing_actions.py:124`) calls `persist_filed_revision` (`src/cadrumo/application/modelo/revision_persistence.py`). That function prepares the `app_filing` observation before the commit (`:1146`), commits the catalogue, revision, work unit and events in one unit (`:1283`), then writes the observation after the commit (`:1304`). The new record has `aeat_accepted=False` and no evidence, and it supersedes the prior `VIGENTE` record.
- Amend: `amend_modelo_revision` (`src/cadrumo/application/modelo/amendment_actions.py:286`) requires the baseline to carry `external_evidence` and be `VIGENTE` (`:132`, `:140`). It validates the kind through the registry policy (`_amendment_kind_resolution.py:58`, fact `src/cadrumo/_data/registry/aeat/facts/0135-amendment-regime-policy.toml`) and the M303 motive (`:201`). It builds a record with `aeat_accepted=False` and `amends_filing_record_id=baseline` (`:756`), then commits catalogue, revisions, work unit and the `MODELO_AMENDED` event (`:784`). It writes NO observation.
- AEAT import: `import_external_filing_evidence` (`src/cadrumo/application/modelo/external_import_actions.py:791`) creates a new accepted record (`:952`, `amends_filing_record_id` never set) and supersedes whatever is current (`:932`). Only for CSV-register evidence does it write an official observation (`:704`).
- Live filed pull: `persist_filed_calculation_observation` (`src/cadrumo/application/live/filed_observation_persistence.py:167`) writes the official `aeat_sede_justificante` observation. `enroll_filed_justificante_evidence` (`:345`) stamps `external_evidence` + `aeat_accepted` onto `catalogue.current_for(...)` (`:300`), whatever that record is. The match `justificante.matches_filing_target` (`src/cadrumo/domain/justificante/schema.py:111`) compares only modelo, ejercicio, period and NIF. AEAT's `tipo_solicitud` is carried in metadata but not elected on (`filed_observation_persistence.py:722`). Selection keeps the latest ALTA per period (`:240`).
- Complete non-303 pull baseline: `import_complete_filed_observation_baseline` (`:98`) routes to the import path above.
- Manual observation: `local_observation_actions.py:147` passes `replace_official_evidence` to the repository.

### Guard and refusals

- `_refuse_official_evidence_displacement` (`calculation_observations.py:226`) refuses any non-official write into a slot holding official evidence unless `replace_official_evidence=True`. That flag overwrites the official row permanently. Error: `ObservationEvidenceDisplacementError` (`src/cadrumo/application/calculations/errors.py:141`). Tests: `src/cadrumo/adapters/persistence/profile/tests/test_observation_evidence_displacement_guard.py`.
- The clean-state gate turns a non-official current observation into `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` and evaluates the chain through `history_for` (`cross_period_clean_state.py:1374`).

### Defects this map establishes

1. After `amend`, the chain's current record is the local correction, but the observation slot still holds the imported original. Later periods carry forward the original's figures.
2. `file` after an AEAT import is refused by the displacement guard, because the single slot cannot hold both the official and the pending local answer.
3. A live pull stamps AEAT acceptance onto the current record, even when that record is an unpresented local amendment. The original's CSV then becomes "acceptance" of the correction.
4. An import that confirms a local filing supersedes it instead of confirming it, and imported corrections lose their `amends` link.
5. `amend` refuses a baseline without evidence, so an unconfirmed local correction cannot be corrected again.
6. `replace_official_evidence` is the only override of an official value, and it destroys that value with no record of what it replaced.

### Reusable pieces

- Amendment identity: `CalculationRevisionAmendmentIdentity` / `CalculationRevisionAmendmentKind` (`src/cadrumo/domain/modelos/calculation_revision_amendment.py:22`, `:48`).
- Per-modelo kind policy: `resolve_amendment_kind_regime_for_period` (`src/cadrumo/domain/calculations/registry/amendment_regime_policy.py`).
- Receipt fields usable for content matching: `Justificante.presentation_id`, `total_a_ingresar`, `total_a_devolver`, `presented_at` (`schema.py:67`).
- Supersession helper: `supersede_prior_current_filing` (`revision_persistence.py:964`).

### Legal mechanics

This section is a survey of official sources, paraphrased. The locators are BOE and AEAT pages.

- The autoliquidación rectificativa (LGT art. 120.4, added by Ley 13/2023, BOE-A-2023-12946, and developed by RD 117/2024, BOE-A-2024-1771) is a full restatement of the period. Its economic effect is only the difference from the previously declared result. It carries the número de justificante of the declaration it corrects. The classic request procedure remains in art. 120.3. Locators: BOE-A-2003-23186 art. 120 and art. 122.
- Successive rectificativas chain to the immediately preceding declaration, not to the original. For M303, casilla 69 of correction N feeds casilla 70 of correction N+1 (AEAT manual IVA 2025, cap. 8). This was confirmed only through a summary of the manual page.
- The rectificativa is the sole mechanism for:
  - M303 from September 2024 (monthly) and 3T 2024 (quarterly), under Orden HAC/819/2024 (BOE-A-2024-16129);
  - M200/M220 for periods starting in 2024, under Orden HAC/657/2025 (BOE-A-2025-12818);
  - M100/M714 from the 2024 campaign (box 103 marks it; box 104 holds the prior justificante).
- No evidence of adoption was found for M111, M115, M130, M131 or M202/M222. They keep the complementaria (LGT art. 122.2) for increases and the solicitud de rectificación (art. 120.3, RGAT arts. 126-128) for decreases. The solicitud is a request that AEAT resolves; it is not a declaration.
- M390 and M349 are informative declarations outside arts. 120/122 and are corrected by a declaración sustitutiva. M349 first requires a baja por sustitución.
- Repo agreement: `src/cadrumo/_data/registry/aeat/facts/0135-amendment-regime-policy.toml` matches the M303, M100 and M200 boundary dates. It still admits `sustitutiva` for every autoliquidación, which the survey does not support. That is an open grounding item and is not changed by this feature.
- Uncertain: the exact position of the M303 prior-justificante field in the record design; the M111, M115, M130, M131 and M202 status (absence of evidence only); and the RD 117/2024 article numbering, which comes from a secondary source.

Consequence for the model: the chain is linear. Each correction supersedes the previous in-force declaration and references its justificante, and the latest AEAT-accepted entry is the one in force.

### Surfaces

CLI leaves:
- **`aeat app modelo work file`**: spec `src/cadrumo/entrypoints/cli/modelo_work_command_specs.py:417`, handler `_modelo_work_verification_cli.py:367`.
- **`work amend`**: `_modelo.py:392`.
- **`work amend-wizard`**: spec `modelo_work_command_specs.py:437`, handler `_modelo_amend_wizard_cli.py:188`, payload `_modelo_amend_wizard_payloads.py:44`.
- **`filing-record import`**: spec `_modelo_nonwork_filing_record_command_specs.py:73`, handler `_modelo_records_cli.py:252`.
- **`filing-record observe-local`**: spec `:137`, handler `_modelo_records_cli.py:352`; it carries `--replace-official-evidence` at `:360`.
- **`filing-record list` and `view`**: specs `:33` and `:56`, handlers `_modelo_records_cli.py:194` and `:238`.
- **`aeat app live filed pull`**:
  - spec `_app_live_foundation_command_specs.py:154`;
  - handler `_app_live.py:1567`, which calls `capture_filed_data` and `capture_filed_data_bulk` (`src/cadrumo/application/live/filed_data_capture.py`);
  - payload `_app_live_filed_payloads.py`;
  - the real `SedeFiledDataCapturePort` is built inline by `compose_live_state()` (`src/cadrumo/entrypoints/live_state_composition.py:278`).
- **`aeat app modelo reconcile`** (`_modelo_reconcile_cli.py`): compares a revision with a justificante or declaración PDF (`src/cadrumo/application/modelo/reconciliation.py:337`, receipt totals `:818`, casillas `:1025`). It does not touch the filing chain.

TUI:
- `src/cadrumo/entrypoints/tui/declarations/filing_history.py:73` renders the filings and lifecycle read-only.
- `controller.py:142` accepts an unused `filing_handoff` seam.
- `action_guards.py:27` declares only read actions.
- Pilot tests: `entrypoints/tui/declarations/tests/test_declarations_workspace.py:469`.

Live CLI test harness:
- `src/cadrumo/entrypoints/cli/tests/cli_runner.py:74` (`invoke_cached_cli`);
- profile fixtures `_cli_surface_profile_fixture.py:15` and `modelo_profile_seed.py:26`;
- work-unit helpers `modelo_cli.py:14` and `_modelo_work_ux_support.py:116` (M130), `:125` (M303), `:168`;
- baseline seeding `test_modelo_amend_wizard.py:182`, `:207` and `:224`.

Non-live pull:
- `finalize_filed_capture` (`src/cadrumo/application/live/filed_capture_finalizer.py:59`) and `capture_filed_data*` take `filed_data_port` and `FiledObservationPersistencePorts` (`filed_observation_ports.py:91`, `:324`) as parameters.
- In-memory fakes live in `src/cadrumo/application/live/tests/filed_observation_test_support.py:500`.
- The CLI has no seam: the Sede port is constructed inline in the composition root.
