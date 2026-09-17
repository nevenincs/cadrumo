---
tags:
  - '#reference'
  - '#filing-chain-reconciliation'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:7d942f8514d4882b6631a268a8b92285bfed3d2fcb34013b681047fc19b4fdeb'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace filing-chain-reconciliation with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

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
