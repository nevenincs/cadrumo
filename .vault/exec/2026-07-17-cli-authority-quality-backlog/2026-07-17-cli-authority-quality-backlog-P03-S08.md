---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S08'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-quality-backlog with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-17-cli-authority-quality-backlog-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Remove duplicate namespace metadata from profile, calculation, aggregation, and filed-observation repositories and bind repository construction to registry definitions and ## Scope

- `src/cadrumo/application/user_profile/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove duplicate namespace metadata from profile, calculation, aggregation, and filed-observation repositories and bind repository construction to registry definitions

## Scope

- `src/cadrumo/application/user_profile/`

## Description

- Re-verified on HEAD that the profile, calculation, and aggregation observation repositories already single-source their namespace metadata: the profile value/snapshot repository, the calculation observations repository, and the retencion/percepciones aggregation repositories all bind their `namespace`, `sensitivity`, and `schema_version` class descriptors to the matching `SecureObjectNamespaceDefinition` in the storage namespace registry. Those three families needed no change.
- Found the filed-observation repository as the residual duplication: the sede `FiledDeclaracionObservationStore` bound only `.namespace` from its three registry definitions (filed-declaration artefacts, filed-declaration observations, IVA-compensation-wallet observations) while restating `SensitivityClass.FINANCIAL` and the integer envelope version `1` as module literals.
- Bound each of the three sede row families to its own registry definition: replaced the shared `_ARTEFACT_CLASSIFICATION`/`_OBSERVATION_CLASSIFICATION` literal pair and the `_OBSERVATION_ENVELOPE_VERSION = 1` literal with per-namespace constants read from `AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE`, `AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`, and `AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE` (`.sensitivity` and `.schema_version`).
- Replaced the two `schema_version=1` / `max_supported_version=1` artefact literals with the artefact namespace's declared version, and switched the IVA-wallet persist/load/list methods off the filed-declaration observation constants onto their own IVA-wallet namespace constants, removing a latent cross-namespace coupling.
- Dropped the now-unused `SensitivityClass` import from the store module.
- Added a real-behaviour binding proof that persists one row of each family through the store, reads the raw `SecureObjectRow` back from the encrypted SQL backend, and asserts each persisted `classification` and `schema_version` equals exactly what its registry definition declares.

## Outcome

- Behaviour-preserving: all three sede namespace definitions declare `SensitivityClass.FINANCIAL` and `schema_version = SECURE_OBJECT_SCHEMA_VERSION_V1 = 1`, so the bound values are byte-identical to the retired literals; no stored classification, version, or namespace string changed.
- The registry definition is now the sole authority for the filed-observation family's sensitivity and envelope version, matching the profile/calculation/aggregation families already bound.
- Gates: the new binding proof plus the existing observation-store roundtrip and store suites pass; the storage `test_namespace_registry.py` gate passes; `ruff format` and `ruff check` clean on both touched files. The only failures under the sede suite are the pre-existing `*_live` tests gated on `CADRUMO_LIVE_TESTS_ENABLED`, untouched by this change.

## Notes

- Scope hint on the Step row names `src/cadrumo/application/user_profile/`; the four named repository families span `application/user_profile/`, `application/calculations/`, `application/aggregation/`, and the sede filed-observation store under `adapters/outbound/aeat/sede/`. The only residual literals lived in the sede store; the other three families were already bound by prior work.
- Did not touch the operator-door WIP (`user_profile/__init__.py`, `user_profile/_custody.py`) or any docs/locales peer WIP present in the shared working tree.
