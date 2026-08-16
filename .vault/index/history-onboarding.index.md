---
generated: true
tags:
  - '#index'
  - '#history-onboarding'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:4f096cc066b6590dece1ff13f2200bc66702c50d031b58658115523c427b08e9'
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
  - '[[2026-08-07-history-onboarding-P02-S29]]'
  - '[[2026-08-07-history-onboarding-P03-S06]]'
  - '[[2026-08-07-history-onboarding-P03-S07]]'
  - '[[2026-08-07-history-onboarding-P03-S08]]'
  - '[[2026-08-07-history-onboarding-P03-S09]]'
  - '[[2026-08-07-history-onboarding-P03-S10]]'
  - '[[2026-08-07-history-onboarding-P03-S19]]'
  - '[[2026-08-07-history-onboarding-P03-S21]]'
  - '[[2026-08-07-history-onboarding-P03-S22]]'
  - '[[2026-08-07-history-onboarding-P03-S32]]'
  - '[[2026-08-07-history-onboarding-P04-S11]]'
  - '[[2026-08-07-history-onboarding-P04-S12]]'
  - '[[2026-08-07-history-onboarding-P04-S13]]'
  - '[[2026-08-07-history-onboarding-P04-S14]]'
  - '[[2026-08-07-history-onboarding-P04-S15]]'
  - '[[2026-08-07-history-onboarding-P04-S16]]'
  - '[[2026-08-07-history-onboarding-P04-S30]]'
  - '[[2026-08-07-history-onboarding-P04-S31]]'
  - '[[2026-08-07-history-onboarding-P04-S33]]'
  - '[[2026-08-07-history-onboarding-P04-S34]]'
  - '[[2026-08-07-history-onboarding-P04-S35]]'
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
- `2026-08-07-history-onboarding-P02-S29` - restore the Modelo 303 filed-observation carry after a peer commit read a generated attribute the derivation never declared, adding the refunded-aware generated component to M303CompensationAvailableDerivation so available equals posterior plus generated on every basis, and repairing the posterior-absent fallback that silently dropped a declared negative resultado's credit to zero, verified by the 13 restored capture tests plus an out-of-tree mutation zeroing generated while leaving available correct
- `2026-08-07-history-onboarding-P03-S06` - add the FiledHistoryOnboardingResult typed result model carrying per-pair outcomes, IVA wallet reconciliation status, notificaciones pull status, the divergence Notice list, the CoverageScopingSignal classification and a prose denominator_note field, and no numeric completeness percentage or fraction over AEAT_REGISTER_OPTIONS-tagged pairs, verified by a strict roundtrip test plus a test asserting the model schema carries no percentage or fraction field
- `2026-08-07-history-onboarding-P03-S07` - add the re-capture divergence diff comparing a fresh FiledDeclaracionObservation against the prior stamped observation for the same modelo, ejercicio and period key, verified by a test that re-captures a fixture with one changed casilla value and asserts exactly one WARNING Notice naming that casilla
- `2026-08-07-history-onboarding-P03-S08` - add the pull_filed_history orchestration service walking the FiledHistoryDiscoveryReport union grid, calling capture_filed_data_bulk over it, then capture_iva_compensation_wallet and reconcile_iva_compensation_wallet, then the existing notificaciones pull, verified by an integration test against synthetic fixtures for every stage asserting the composed FiledHistoryOnboardingResult reflects every stage's outcome
- `2026-08-07-history-onboarding-P03-S09` - add the aeat app live filed pull-all verb, verified by test_documented_command_conformance.py and a new JSON-schema conformance case
- `2026-08-07-history-onboarding-P03-S10` - enroll app live filed pull-all in PROFILE_BOUND_WRITE_VERB_PATHS, verified by the existing write-policy guard test asserting the new path is recognised as profile-bound
- `2026-08-07-history-onboarding-P03-S19` - add the expected-but-not-found advisory comparing captured rows against every PROFILE_APPLICABILITY-tagged pair, emitting a WARNING Notice naming each modelo and ejercicio the profile expects but no declaracion was captured for, verified by a test asserting the Notice fires only for PROFILE_APPLICABILITY pairs and never for pairs carrying only the AEAT_REGISTER_OPTIONS tag
- `2026-08-07-history-onboarding-P03-S21` - extend FiledDataCaptureReport and BulkFiledDataCaptureReport with a per modelo ejercicio period breakdown of raw register row count versus the one persisted calculation observation, computed from the declarations and selected tuples already held before finalize_filed_capture runs, touching no persistence-boundary file, verified by a synthetic-fixture test asserting a two-row period reports raw count two and selected count one
- `2026-08-07-history-onboarding-P03-S22` - add the found-more-than-expected advisory emitting an INFO Notice for every period whose raw register count exceeds one, naming the modelo, period, winning expediente_id and superseded filing count, degrading gracefully to count-only wording when tipo_solicitud is absent from source metadata, verified by a test asserting INFO severity, never WARNING, and asserting the notice composes with rather than duplicates the re-capture divergence diff
- `2026-08-07-history-onboarding-P03-S32` - relay the justificante unreached-evidence reasons onto the same envelope notices channel this plan's own advisories use, absorbing the sibling justificante-identity plan's deliberately-unlanded forwarding row rather than growing a second advisory channel, declaring the evidence_notices field on BulkFiledDataCaptureReport that the sweep was already passing and whose absence made the orchestration read raise AttributeError on a session-only path, verified by a test driving the full reason enum and asserting one notice per member with its reason readable in context, with the expected set derived from the enum rather than hand-listed
- `2026-08-07-history-onboarding-P04-S11` - add the overview INFO Notice naming aeat app live filed pull-all when a workable profile has zero observations carrying an official ObservationSourceKind, verified by a calendar-overview test asserting the Notice fires for a zero-observation profile and is absent once one official observation exists
- `2026-08-07-history-onboarding-P04-S12` - land real es, en, ca and hu values for every new help string, Notice message key and result-field label the P01 through P03 verbs introduce, verified by dev.locales scaffold --check, gated on the shared locale catalogues being free of unrelated in-flight writes before landing
- `2026-08-07-history-onboarding-P04-S13` - add the error-registry default_suggestion entries for the new discover and pull-all verb refusals, verified by the existing suggestion-command conformance test
- `2026-08-07-history-onboarding-P04-S14` - add the cross-period next_action builder cases pointing at the new discover and pull-all verbs, verified by the existing next-action conformance coverage
- `2026-08-07-history-onboarding-P04-S15` - update operator_surface/_help.py with the new discover and pull-all verb entries, verified by test_rule_surface_conformance.py
- `2026-08-07-history-onboarding-P04-S16` - update the agent-harness docs under src/cadrumo/_data/agent that name the filed verb group to cite the new discover and pull-all verbs, verified by the harness-citation conformance check confirming every named verb resolves against the live operator-surface manifest
- `2026-08-07-history-onboarding-P04-S30` - Enroll the app.* payload modules into the JSON-schema conformance parametrisation in staged per-family batches, since SCHEMA_REGISTRY is populated at collection time from the config payload modules only, so every parametrised case was a config or root key and no app command was inside the gate at all. That is not something a passing run could reveal, because a gate can only check what is registered when it collects. LIVE FAMILY LANDED at commit 71a7cc3ba2, measured from outside the repository first with a probe that refuses rather than passes if the import adds no key: enrolling _app_live_payloads adds 33 schema keys and takes the gate from 163 to 229 cases, all green, so no conformance violation was hiding behind the absence. FOUR FAMILIES REMAIN and are the outstanding batches, named in the test module's own comment so the staging is visible rather than implied: agent-workspace, contract, maintenance and quickfile. Gate for each remaining batch. Measure the delta before landing, land only if green, and if a batch reds then that is a real conformance finding to report rather than a reason to leave the family unenrolled
- `2026-08-07-history-onboarding-P04-S31` - add a fixture-anchor assertion beside every test that intersects a candidate set against UNMODELED_OBLIGATIONS, which is currently EMPTY so any such intersection assertion passes vacuously and keeps passing if the filter it guards is deleted, gating instead on the PROPERTY the filter guarantees so the test stays meaningful whether the collection is empty today or populated tomorrow, verified by the anchor failing when the constant is empty and by the property assertion failing when the filter is removed
- `2026-08-07-history-onboarding-P04-S33` - Enroll app live filed discover in the profile-bound write allowlist with a comment stating why a read-shaped verb writes: it persists nothing of the register it reads, which is why it is discover rather than pull, but it resolves its session through the central live-session writer, which opens an active-profile storage span and an auth mutation span. Its own docstring asserting that nothing is persisted is true of register data and false of session state, so enrolling on the docstring's word would be the error the census gate's own message warns against. Gate: the name-independent leaf census no longer reports the leaf as accounted for by no mechanism, and the MCP write-policy mutability parity gate still passes, since it requires every write-allowlist entry to map to a non-read-only family
- `2026-08-07-history-onboarding-P04-S35` - MEASUREMENT row. Partition the error-registry entries carrying no default_suggestion into operator-reachable and internal-only by reading each entry's raise sites. Measured when S13 landed: 377 of 606 entries carry no suggestion, 62 percent. That count is NOT itself a defect, because an entry an operator can never reach correctly carries none, which REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED demonstrates by firing only under pytest, where suggesting the opt-in environment variable would have armed real AEAT access. The open question is therefore not why 377 lack suggestions but how many of them an operator can actually reach. That is decidable per entry by reading raise sites, as S13 did for ERROR_APPLICATION_LIVE by finding all seven of its direct raises inside stages the history sweep sequences, but nothing in the tree records which side any entry falls on, so it is worth measuring once rather than rediscovering per row. A suggestion that MISDIRECTS is worse than none, because the agent-operator this CLI targets follows it, which is why declining FAIL_SNAPSHOT_NOT_FOUND was correct: a filed-specific citation on a base shared with borrador and deudas would misdirect their misses. The output is a classified inventory plus a per-entry decision, never a blanket sweep adding suggestions to 377 entries. Gate: the partition is total over the suggestion-less set with a stated justification recorded per entry for the side it lands on, gated on totality and per-entry justification rather than on any count, and the suggestion-command conformance test stays green for every suggestion added. Scope-adjacent to history-onboarding rather than native to it, and lives here for provenance because S13 surfaced it
- `2026-08-07-history-onboarding-P04-S34` - 2026-08-07-history-onboarding-P04-S34

### plan

- `2026-08-07-history-onboarding-plan` - `history-onboarding` plan

### reference

- `2026-08-07-history-onboarding-reference` - `history-onboarding` reference: `New-profile AEAT history onboarding grounding`
