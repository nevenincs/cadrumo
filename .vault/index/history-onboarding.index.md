---
generated: true
tags:
  - '#index'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:26265fae6b6dff50cc3a24d45d9b1960664a356a5a4c7c64274f9662f134e20f'
related:
  - '[[2026-08-07-history-onboarding-P01-S01]]'
  - '[[2026-08-07-history-onboarding-P01-S02]]'
  - '[[2026-08-07-history-onboarding-P01-S03]]'
  - '[[2026-08-07-history-onboarding-P01-S04]]'
  - '[[2026-08-07-history-onboarding-P01-S17]]'
  - '[[2026-08-07-history-onboarding-P01-S18]]'
  - '[[2026-08-07-history-onboarding-P01-S20]]'
  - '[[2026-08-07-history-onboarding-P02-S05]]'
  - '[[2026-08-07-history-onboarding-P02-S23]]'
  - '[[2026-08-07-history-onboarding-P02-S24]]'
  - '[[2026-08-07-history-onboarding-P02-S25]]'
  - '[[2026-08-07-history-onboarding-P02-S26]]'
  - '[[2026-08-07-history-onboarding-P02-S27]]'
  - '[[2026-08-07-history-onboarding-P02-S28]]'
  - '[[2026-08-07-history-onboarding-adr]]'
  - '[[2026-08-07-history-onboarding-plan]]'
  - '[[2026-08-07-history-onboarding-reference]]'
---

# `history-onboarding` feature index

Auto-generated index of all documents tagged with `#history-onboarding`.

## Documents

### adr

- `2026-08-07-history-onboarding-adr` - `history-onboarding` adr: `New-profile AEAT history discovery and onboarding` | (**status:** `accepted`)

### exec

- `2026-08-07-history-onboarding-P01-S01` - add the FiledDeclarationAvailability and FiledDeclarationAvailabilityReport pydantic v2 models, verified by a strict roundtrip test
- `2026-08-07-history-onboarding-P01-S02` - add discover_filed_declaration_availability reading the modelo combobox's full option set then, per modelo, the ejercicio combobox's full option set, tagged provenance AEAT_REGISTER_OPTIONS and treated as scoping-unconfirmed, verified by a synthetic-fixture test asserting the returned report matches a hand-authored fixture option list exactly
- `2026-08-07-history-onboarding-P01-S03` - add the discover_filed_history application service wrapping the session bring-up shared with capture_filed_data around the new adapter function, verified by a test that a missing auth session raises the same SedeNavigationError the existing capture path raises
- `2026-08-07-history-onboarding-P01-S04` - add the aeat app live filed discover verb emitting the availability report as the envelope result plus the live-scope caveat Notice, verified by test_documented_command_conformance.py and a new JSON-schema conformance case
- `2026-08-07-history-onboarding-P01-S17` - add expected_filed_declaration_grid deriving a taxpayer-specific candidate modelo and ejercicio grid from TaxpayerProfile applicability and activity_start_date, verified by a test asserting the grid matches a hand-built profile fixture's expected modelos and year span
- `2026-08-07-history-onboarding-P01-S18` - add FiledHistoryDiscoveryReport combining the AEAT_REGISTER_OPTIONS combobox signal and the PROFILE_APPLICABILITY expected grid into one provenance-tagged walk set per (modelo, ejercicio) pair, verified by a test asserting a pair present in both signals carries both provenance tags and a pair present in only one carries only that tag
- `2026-08-07-history-onboarding-P01-S20` - add classify_register_scoping_signal comparing the AEAT_REGISTER_OPTIONS modelo set against the profile's confidently_excluded set from build_obligation_coverage, returning LIKELY_UNIVERSAL, LIKELY_NIF_SCOPED or INCONCLUSIVE, verified by three synthetic-fixture tests, one per classification, none asserting a resolved boolean
- `2026-08-07-history-onboarding-P02-S05` - add a parity test capturing the same synthetic declaracion fixture once through capture_filed_data and once through the discovery-driven grid, asserting both persisted observations carry ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE and are otherwise field-equal apart from capture timestamps, verified by the test going red if either path is made to stamp a different kind
- `2026-08-07-history-onboarding-P02-S23` - carry tipo_solicitud through into _filed_observation_source_metadata as aeat_tipo_solicitud, landed only after the file's current peer contention clears and by an executor rather than this plan's authoring agent, verified by a roundtrip test asserting the persisted metadata carries the field when the source Declaracion has one
- `2026-08-07-history-onboarding-P02-S24` - 2026-08-07-history-onboarding-P02-S24
- `2026-08-07-history-onboarding-P02-S25` - 2026-08-07-history-onboarding-P02-S25
- `2026-08-07-history-onboarding-P02-S26` - 2026-08-07-history-onboarding-P02-S26
- `2026-08-07-history-onboarding-P02-S27` - 2026-08-07-history-onboarding-P02-S27
- `2026-08-07-history-onboarding-P02-S28` - 2026-08-07-history-onboarding-P02-S28

### plan

- `2026-08-07-history-onboarding-plan` - `history-onboarding` plan

### reference

- `2026-08-07-history-onboarding-reference` - `history-onboarding` reference: `New-profile AEAT history onboarding grounding`
