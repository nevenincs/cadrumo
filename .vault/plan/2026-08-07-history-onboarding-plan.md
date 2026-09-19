---
tags:
  - '#plan'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-09'
body_hash: 'sha256:8eb2ab709b10b5c53882a727f8f0c0617be2bffc0733af43ad74f85172d74297'
tier: L2
related:
  - '[[2026-08-07-history-onboarding-adr]]'
  - '[[2026-08-07-declarations-register-pagination-adr]]'
  - '[[2026-08-07-dehu-notification-legal-effect-reference]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-adr]]'
  - '[[2026-08-07-history-onboarding-reference]]'
---
# `history-onboarding` plan

Roll-up plan executing `[[2026-08-07-history-onboarding-adr]]`: land AEAT-declared history
discovery as the completeness denominator, and the standalone onboarding verb that composes it
with the existing filed-declaration, IVA wallet, and notificaciones capture primitives.

## Description

This plan is the cross-cutting roll-up for the `history-onboarding` cluster. It executes
`[[2026-08-07-history-onboarding-adr]]` in full: dual-tier discovery, provenance settlement, the
pull-all orchestration verb, operator-surface wiring, and the mandatory hand-swept sweep.

Discovery ships as two signals, unioned, never a single unverified one. The AEAT declarations
register's own modelo/ejercicio combobox option list (tagged `AEAT_REGISTER_OPTIONS`) is read,
but whether it is genuinely NIF-scoped or a static universal catalogue is unconfirmed and cannot
be settled without an unauthorised live probe; a completeness claim MUST NOT rest on it alone. The
primary, always-available denominator is `PROFILE_APPLICABILITY`: the taxpayer's own declared
profile facts, walked through the same `derive_modelo_applicability`/`build_obligation_coverage`
machinery the overview calendar already uses, combined with the profile's `activity_start_date`
for the year span. This signal is genuinely taxpayer-specific by construction (it is the
taxpayer's own declared data, not an AEAT-served list) and requires no live session at all. The
two signals are unioned into one walked grid per `P01.S18`; a pair found in neither signal is
never silently walked, and a `PROFILE_APPLICABILITY` pair that yields no captured declaracion is a
real signal worth an advisory (`P03.S19`), while an `AEAT_REGISTER_OPTIONS`-only pair yielding no
rows is reported as a plain negative, never an anomaly, because that signal's informativeness is
still unconfirmed.

Both worlds are handled without needing to know which one applies at build time: if the combobox
is genuinely NIF-scoped, it purely widens coverage; if it is a static universal list, every walked
pair is still captured correctly (each per-pair search is independently authenticated and
taxpayer-scoped through the existing `capture_filed_data` search regardless of the combobox's own
scoping), so accuracy never degrades either way. What changes is only what the report may honestly
claim about pairs that returned nothing. `P01.S20` adds a cheap, offline, zero-extra-cost
self-diagnosing heuristic (`classify_register_scoping_signal`) that compares the combobox's modelo
set against the profile's `confidently_excluded` set: a confidently-excluded modelo appearing with
populated ejercicios is real evidence the list is not filtered per taxpayer (`LIKELY_UNIVERSAL`);
a combobox modelo set that stays entirely inside `surfaced | advised` is weak supportive evidence
of NIF-scoping (`LIKELY_NIF_SCOPED`); neither observed condition is `INCONCLUSIVE`. This is a
label, never a resolved boolean, and it never proves scoping either way. Per the operator's
instruction, `FiledHistoryOnboardingResult` (`P03.S06`) carries NO numeric completeness percentage
or fraction computed over `AEAT_REGISTER_OPTIONS`-tagged pairs; instead it carries the
`scoping_signal` label and a prose `denominator_note` worded per that label, so an operator is
never shown a confidence number implying an unconfirmed AEAT-sourced set represents their own
history.

It does not restate or duplicate the sibling plans it depends on: `[[2026-08-07-declarations-register-pagination-adr]]`
owns its own self-contained L1 plan for parser-level pagination detection, executing independently
(this plan's coverage report consumes that sibling's per-pair completeness signal once it lands,
but does not block on it). `[[2026-08-07-dehu-notification-legal-effect-reference]]` is still an
in-progress reference for a sibling ADR not yet accepted; this plan does not sequence against it
beyond composing the existing, already-shipped notificaciones pull primitive Phase P03 uses. The
liabilities/sanciones register (`2026-08-07-aeat-liabilities-sanciones-adr`) is read-and-display
only and its amounts never reach a modelo casilla; this plan inherits that boundary and does not
re-decide it, and no Step here touches that register.

Every verification gate below uses the repository's existing synthetic-HTML fixture pattern
(the same shape as `declaraciones-modelo-100-paginated-synthetic.html`); no Step in this plan
performs or requires a live authenticated AEAT session, including the scoping heuristic, which is
a pure function over data already fetched for another authorised purpose. A live-account
confidence check of the `AEAT_REGISTER_OPTIONS` combobox's true NIF-scoping is explicitly out of
scope for this plan and requires separate operator sign-off not yet given; the design does not
depend on that check ever resolving, because `PROFILE_APPLICABILITY` ships as the load-bearing
signal regardless of its outcome.

A live smoke test against real AEAT (modelo 303, filing year 2024) found a period carrying two
filings under different `expediente_id`s months apart - almost certainly an original plus a
complementaria. Nothing is lost: `select_declarations_for_capture` already captures every raw
row for a period, and `select_latest_filed_observations_in_history_order` is a genuine
latest-by-presentation SELECTION for the one calculation observation, not an overwrite. But the
EXISTING `BulkFiledDataCaptureReport`/`FiledDataCaptureReport` only ever report a flat total
`captured_count` across a whole `(modelo, year)` sweep, so a period's real multiplicity was
invisible to any coverage report built on top of it - directly undermining this plan's own
"faithful history" premise, and a live reminder that this plan's `(modelo, ejercicio)` pair grid
must never be read as 1:1 with declarations found; `latest_declarations_by_period` already
collapses that assumption elsewhere in the codebase. `P03.S21`/`P03.S22` close this by computing
and surfacing a per-period raw-versus-selected count at `INFO` severity (an amendment is legitimate,
never an anomaly), entirely inside `_filed_data_capture.py` with no edit to the two files
currently under active peer contention (`_filed_observation_persistence.py`,
`adapters/outbound/aeat/sede/_declarations.py`). `P02.S23` separately carries AEAT's own
`tipo_solicitud` request-type field through the persistence boundary so the advisory can
eventually say "original" versus "complementaria" rather than only a count; that row DOES target
a contended file, is authored here, and is landed only by an executor once the contention clears.

## Steps

### Phase `P01` - AEAT-declared discovery capability

Land dual-tier availability discovery: a taxpayer-specific PROFILE_APPLICABILITY grid derived from the taxpayer's own declared profile facts (always available, no live probe needed) as the primary completeness denominator, plus an AEAT_REGISTER_OPTIONS combobox enumeration whose NIF-scoping is unconfirmed, unioned additively and never solely relied on for a completeness claim.

- [x] `P01.S01` - add the FiledDeclarationAvailability and FiledDeclarationAvailabilityReport pydantic v2 models, verified by a strict roundtrip test; `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`.
- [x] `P01.S02` - add discover_filed_declaration_availability reading the modelo combobox's full option set then, per modelo, the ejercicio combobox's full option set, tagged provenance AEAT_REGISTER_OPTIONS and treated as scoping-unconfirmed, verified by a synthetic-fixture test asserting the returned report matches a hand-authored fixture option list exactly; `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `P01.S03` - add the discover_filed_history application service wrapping the session bring-up shared with capture_filed_data around the new adapter function, verified by a test that a missing auth session raises the same SedeNavigationError the existing capture path raises; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P01.S04` - add the aeat app live filed discover verb emitting the availability report as the envelope result plus the live-scope caveat Notice, verified by test_documented_command_conformance.py and a new JSON-schema conformance case; `src/cadrumo/entrypoints/cli/_app_live.py`.
- [x] `P01.S17` - add expected_filed_declaration_grid deriving a taxpayer-specific candidate modelo and ejercicio grid from TaxpayerProfile applicability and activity_start_date, verified by a test asserting the grid matches a hand-built profile fixture's expected modelos and year span; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P01.S18` - add FiledHistoryDiscoveryReport combining the AEAT_REGISTER_OPTIONS combobox signal and the PROFILE_APPLICABILITY expected grid into one provenance-tagged walk set per (modelo, ejercicio) pair, verified by a test asserting a pair present in both signals carries both provenance tags and a pair present in only one carries only that tag; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P01.S20` - add classify_register_scoping_signal comparing the AEAT_REGISTER_OPTIONS modelo set against the profile's confidently_excluded set from build_obligation_coverage, returning LIKELY_UNIVERSAL, LIKELY_NIF_SCOPED or INCONCLUSIVE, verified by three synthetic-fixture tests, one per classification, none asserting a resolved boolean; `src/cadrumo/application/live/_filed_data_capture.py`.

### Phase `P02` - Provenance parity proof

Prove that a bulk-discovered historical capture stamps the same official ObservationSourceKind as an existing single-pair live capture, settling the provenance question without introducing a new kind, and carry the tipo_solicitud request-type signal through the shared persistence boundary once its file's current contention clears.

- [x] `P02.S05` - add a parity test capturing the same synthetic declaracion fixture once through capture_filed_data and once through the discovery-driven grid, asserting both persisted observations carry ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE and are otherwise field-equal apart from capture timestamps, verified by the test going red if either path is made to stamp a different kind; `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.
- [x] `P02.S23` - carry tipo_solicitud through into _filed_observation_source_metadata as aeat_tipo_solicitud, landed only after the file's current peer contention clears and by an executor rather than this plan's authoring agent, verified by a roundtrip test asserting the persisted metadata carries the field when the source Declaracion has one; `src/cadrumo/application/live/_filed_observation_persistence.py`.
- [x] `P02.S24` - author a synthetic declaraciones-register listbox fixture carrying two rows for one period with distinct expediente ids and distinct presentation timestamps alongside normal single-filing periods and populated tipo de solicitud cells, verified by a listbox parser test asserting one period yields two rows whose expediente ids differ and whose tipo_solicitud is populated; `src/cadrumo/tests/fixtures/aeat-sede, src/cadrumo/adapters/outbound/aeat/sede/tests`.
- [x] `P02.S25` - add an order-invariance test for select_latest_filed_observations_in_history_order over duplicated-period observations asserting it collapses to one observation per period, picks the later-presented ALTA row and returns an identical result when the same inputs are fed in reverse order, verified by the test going red when the selector's max-by-rank comparison is weakened to last-write-wins; `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.
- [x] `P02.S26` - add a pinning test proving the justificante match predicate rejects a receipt whose embedded presentation identifier is receipt-shaped while the register row's expediente id is register-shaped even though modelo ejercicio period and tax identity all agree, so no evidence is stamped, verified by the test going red when the predicate's presentation-identifier comparison is dropped; `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.
- [x] `P02.S27` - add a test pinning that tipo_solicitud reaches the raw filed-declaration observation metadata while the persisted calculation-observation source metadata omits it, verified by the test going red once the carry-through row lands and by a mutation adding the key to the persisted metadata; `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.
- [x] `P02.S28` - author a synthetic no-results declaraciones-register fixture in the AEAT empty-body grid shape, verified by a listbox parser test asserting the page parses to zero rows and reports itself not truncated so a clean empty register answer stays distinguishable from a short read; `src/cadrumo/tests/fixtures/aeat-sede, src/cadrumo/adapters/outbound/aeat/sede/tests`.
- [x] `P02.S29` - restore the Modelo 303 filed-observation carry after a peer commit read a generated attribute the derivation never declared, adding the refunded-aware generated component to M303CompensationAvailableDerivation so available equals posterior plus generated on every basis, and repairing the posterior-absent fallback that silently dropped a declared negative resultado's credit to zero, verified by the 13 restored capture tests plus an out-of-tree mutation zeroing generated while leaving available correct; `src/cadrumo/domain/iva_compensation/_filed_derivation.py, src/cadrumo/application/calculations/_iva_compensation_history.py`.

### Phase `P03` - Onboarding orchestration verb

Sequence discovery, bulk filed capture, IVA wallet reconciliation and notificaciones pull behind one standalone pull-all verb, with a re-capture divergence diff and a period-multiplicity advisory both surfaced as standing, non-blocking Notices.

- [x] `P03.S06` - add the FiledHistoryOnboardingResult typed result model carrying per-pair outcomes, IVA wallet reconciliation status, notificaciones pull status, the divergence Notice list, the CoverageScopingSignal classification and a prose denominator_note field, and no numeric completeness percentage or fraction over AEAT_REGISTER_OPTIONS-tagged pairs, verified by a strict roundtrip test plus a test asserting the model schema carries no percentage or fraction field; `src/cadrumo/entrypoints/cli/_app_live_payloads.py`.
- [x] `P03.S07` - add the re-capture divergence diff comparing a fresh FiledDeclaracionObservation against the prior stamped observation for the same modelo, ejercicio and period key, verified by a test that re-captures a fixture with one changed casilla value and asserts exactly one WARNING Notice naming that casilla; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P03.S08` - add the pull_filed_history orchestration service walking the FiledHistoryDiscoveryReport union grid, calling capture_filed_data_bulk over it, then capture_iva_compensation_wallet and reconcile_iva_compensation_wallet, then the existing notificaciones pull, verified by an integration test against synthetic fixtures for every stage asserting the composed FiledHistoryOnboardingResult reflects every stage's outcome; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P03.S09` - add the aeat app live filed pull-all verb, verified by test_documented_command_conformance.py and a new JSON-schema conformance case; `src/cadrumo/entrypoints/cli/_app_live.py`.
- [x] `P03.S10` - enroll app live filed pull-all in PROFILE_BOUND_WRITE_VERB_PATHS, verified by the existing write-policy guard test asserting the new path is recognised as profile-bound; `src/cadrumo/application/storage_write_policy.py`.
- [x] `P03.S19` - add the expected-but-not-found advisory comparing captured rows against every PROFILE_APPLICABILITY-tagged pair, emitting a WARNING Notice naming each modelo and ejercicio the profile expects but no declaracion was captured for, verified by a test asserting the Notice fires only for PROFILE_APPLICABILITY pairs and never for pairs carrying only the AEAT_REGISTER_OPTIONS tag; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P03.S21` - extend FiledDataCaptureReport and BulkFiledDataCaptureReport with a per modelo ejercicio period breakdown of raw register row count versus the one persisted calculation observation, computed from the declarations and selected tuples already held before finalize_filed_capture runs, touching no persistence-boundary file, verified by a synthetic-fixture test asserting a two-row period reports raw count two and selected count one; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P03.S22` - add the found-more-than-expected advisory emitting an INFO Notice for every period whose raw register count exceeds one, naming the modelo, period, winning expediente_id and superseded filing count, degrading gracefully to count-only wording when tipo_solicitud is absent from source metadata, verified by a test asserting INFO severity, never WARNING, and asserting the notice composes with rather than duplicates the re-capture divergence diff; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P03.S32` - relay the justificante unreached-evidence reasons onto the same envelope notices channel this plan's own advisories use, absorbing the sibling justificante-identity plan's deliberately-unlanded forwarding row rather than growing a second advisory channel, declaring the evidence_notices field on BulkFiledDataCaptureReport that the sweep was already passing and whose absence made the orchestration read raise AttributeError on a session-only path, verified by a test driving the full reason enum and asserting one notice per member with its reason readable in context, with the expected set derived from the enum rather than hand-listed; `src/cadrumo/application/live/_remote_state_models.py, src/cadrumo/application/live/_filed_data_capture.py, src/cadrumo/entrypoints/cli/_app_live.py`.

### Phase `P04` - Operator-surface integration and hand-swept sweep

Wire the overview no-history advisory, sweep every surface no gate scans, and land real locale
values in all four catalogues.

- [x] `P04.S11` - add the overview INFO Notice naming aeat app live filed pull-all when a workable profile has zero observations carrying an official ObservationSourceKind, verified by a calendar-overview test asserting the Notice fires for a zero-observation profile and is absent once one official observation exists; `src/cadrumo/application/overview/_calendar_evidence.py`.
- [x] `P04.S12` - land real es, en, ca and hu values for every new help string, Notice message key and result-field label the P01 through P03 verbs introduce, verified by dev.locales scaffold --check, gated on the shared locale catalogues being free of unrelated in-flight writes before landing; `src/cadrumo/locales`.
- [x] `P04.S13` - add the error-registry default_suggestion entries for the new discover and pull-all verb refusals, verified by the existing suggestion-command conformance test; `src/cadrumo/core/errors/registry`.
- [x] `P04.S14` - add the cross-period next_action builder cases pointing at the new discover and pull-all verbs, verified by the existing next-action conformance coverage; `src/cadrumo/application/modelo/_verification_cross_period.py`.
- [x] `P04.S15` - update operator_surface/_help.py with the new discover and pull-all verb entries, verified by test_rule_surface_conformance.py; `src/cadrumo/application/operator_surface/_help.py`.
- [x] `P04.S16` - update the agent-harness docs under src/cadrumo/_data/agent that name the filed verb group to cite the new discover and pull-all verbs, verified by the harness-citation conformance check confirming every named verb resolves against the live operator-surface manifest; `src/cadrumo/_data/agent`.
- [x] `P04.S30` - Enroll the app.* payload modules into the JSON-schema conformance parametrisation in staged per-family batches, since SCHEMA_REGISTRY is populated at collection time from the config payload modules only, so every parametrised case was a config or root key and no app command was inside the gate at all. That is not something a passing run could reveal, because a gate can only check what is registered when it collects. LIVE FAMILY LANDED at commit 71a7cc3ba2, measured from outside the repository first with a probe that refuses rather than passes if the import adds no key: enrolling _app_live_payloads adds 33 schema keys and takes the gate from 163 to 229 cases, all green, so no conformance violation was hiding behind the absence. FOUR FAMILIES REMAIN and are the outstanding batches, named in the test module's own comment so the staging is visible rather than implied: agent-workspace, contract, maintenance and quickfile. Gate for each remaining batch. Measure the delta before landing, land only if green, and if a batch reds then that is a real conformance finding to report rather than a reason to leave the family unenrolled; `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.
- [x] `P04.S31` - add a fixture-anchor assertion beside every test that intersects a candidate set against UNMODELED_OBLIGATIONS, which is currently EMPTY so any such intersection assertion passes vacuously and keeps passing if the filter it guards is deleted, gating instead on the PROPERTY the filter guarantees so the test stays meaningful whether the collection is empty today or populated tomorrow, verified by the anchor failing when the constant is empty and by the property assertion failing when the filter is removed; `src/cadrumo/core/tests, src/cadrumo/application/live/tests`.
- [x] `P04.S33` - Enroll app live filed discover in the profile-bound write allowlist with a comment stating why a read-shaped verb writes: it persists nothing of the register it reads, which is why it is discover rather than pull, but it resolves its session through the central live-session writer, which opens an active-profile storage span and an auth mutation span. Its own docstring asserting that nothing is persisted is true of register data and false of session state, so enrolling on the docstring's word would be the error the census gate's own message warns against. Gate: the name-independent leaf census no longer reports the leaf as accounted for by no mechanism, and the MCP write-policy mutability parity gate still passes, since it requires every write-allowlist entry to map to a non-read-only family; `src/cadrumo/application/storage_write_policy.py`.
- [x] `P04.S34` - DECISION row, not a cleanup row. Rule on whether UNMODELED_OBLIGATIONS is populated or is declared intentionally empty. The REGISTRY_UNMODELED disposition branch in application/overview/_coverage.py cannot be entered by any production input while the declaration is empty, because out-of-scope resolves first, and the prose in core/_modelo.py describing a set that covers the common retencion autoliquidaciones and declaraciones informativas an autonomo, a PYME or an entity may owe describes a populated set that does not exist, which is prose asserting a property the code lacks. The two options are NOT equivalent and the cheap one is destructive. Populating the declaration is a TAX REVIEW against official sources deciding which retired or registry-less obligations still bear a filing duty a taxpayer must be advised of, grounded per entry with human review, not derivable from the code, and Modelo M037 being retired by Orden HAC/1526/2024 is exactly the kind of fact needing a source rather than an inference. Deleting the branch to remove the dead code is REFUSED without a ruling, because it would remove the advisory capability for a real class of taxpayers, the population whose obligation is registry-less, and it reads as tidying, so a later agent optimising for a green tree must not take it. Gate: either the declaration is populated with per-entry legal grounding and the prose becomes true, or the prose is corrected to describe an intentionally-empty declaration and to state the reason it is empty. Not the branch deleted. Whichever way the decision goes, that paragraph changes. Keep the coverage test assertion that the module-level declaration is the same object the core package exports, since it is what keeps the substituted-declaration coverage honest against a refactor that moves the read, and note that today's coverage proves the disposition classifies a substituted declaration correctly rather than that any actually-declared obligation is correct, so the first real entry inherits a gate that already bites; `src/cadrumo/core/_modelo.py, src/cadrumo/application/overview/_coverage.py`.
- [x] `P04.S35` - MEASUREMENT row. Partition the error-registry entries carrying no default_suggestion into operator-reachable and internal-only by reading each entry's raise sites. Measured when S13 landed: 377 of 606 entries carry no suggestion, 62 percent. That count is NOT itself a defect, because an entry an operator can never reach correctly carries none, which REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED demonstrates by firing only under pytest, where suggesting the opt-in environment variable would have armed real AEAT access. The open question is therefore not why 377 lack suggestions but how many of them an operator can actually reach. That is decidable per entry by reading raise sites, as S13 did for ERROR_APPLICATION_LIVE by finding all seven of its direct raises inside stages the history sweep sequences, but nothing in the tree records which side any entry falls on, so it is worth measuring once rather than rediscovering per row. A suggestion that MISDIRECTS is worse than none, because the agent-operator this CLI targets follows it, which is why declining FAIL_SNAPSHOT_NOT_FOUND was correct: a filed-specific citation on a base shared with borrador and deudas would misdirect their misses. The output is a classified inventory plus a per-entry decision, never a blanket sweep adding suggestions to 377 entries. Gate: the partition is total over the suggestion-less set with a stated justification recorded per entry for the side it lands on, gated on totality and per-entry justification rather than on any count, and the suggestion-command conformance test stays green for every suggestion added. Scope-adjacent to history-onboarding rather than native to it, and lives here for provenance because S13 surfaced it; `src/cadrumo/core/errors/registry`.

The envelope command= identifier for each new verb is established by that verb's own Step
(`P01.S04`, `P03.S09`) and verified by the same documented-command-conformance gate; it is not a
separate row.

## Parallelization

P01 has no dependency on any other Phase and can start immediately. Within P01, `S01` (models)
blocks `S02` (AEAT_REGISTER_OPTIONS reader) and `S17` (PROFILE_APPLICABILITY grid), which can run
in parallel with each other once `S01` closes; `S18` (the union report) depends on both `S02` and
`S17`; `S20` (scoping heuristic) depends only on `S02` and `S17` (it reads their output, not
`S18`'s union) and may run in parallel with `S18`; `S03` (service wrapper) depends on `S02`; `S04`
(CLI verb) depends on `S03`, `S18` and `S20`. P02 depends only on the existing
`capture_filed_data` path (already shipped) and can run in parallel with P01; within P02, `S05`
(parity test) and `S23` (tipo_solicitud carry-through) are independent of each other, but `S23`
additionally carries a standing dependency on `_filed_observation_persistence.py`'s current peer
contention clearing, orthogonal to this plan's own ordering. P03 depends on P01 closing in full
(needs `S18`'s union report shape and `S20`'s signal) and on the provenance settlement recorded by
`S05` (P03 does not need `S23` to start; `S22` degrades gracefully without it); within P03, `S06`
(result model) and `S07` (divergence diff) can run in parallel with each other, `S21` (period
multiplicity field) is independent of both and may run in parallel with them, `S08`
(orchestration) depends on `S06`, `S07`, `S18` and `S21`, `S19` (expected-but-not-found advisory)
and `S22` (found-more-than-expected advisory) both depend on `S08` and may run in parallel with
each other, and `S09`-`S10` (CLI verb, write-guard enrollment) depend on `S08`. P04 depends on P03
closing (the CLI verb and its identifiers must exist before the sweep can reference them); within
P04, `S11` (overview Notice) is independent of `S13`-`S16` and may run in parallel with them.
`S12` (locale rows) additionally carries a standing dependency on the shared locale catalogues
settling any unrelated in-flight peer write before it lands, independent of this plan's own
internal ordering.

This plan's Phases are independent of the sibling `declarations-register-pagination` plan's
Phases; no Step here blocks on that plan's Steps, and no Step there blocks on this plan.

## Verification

The plan is complete when every Step above is closed (`- [x]`) and its named gate is green:
every new pydantic model passes a strict roundtrip test; every new adapter and service function
is verified against synthetic-HTML fixtures, never a live AEAT session; the union report tags
each pair with the correct provenance set; the scoping heuristic classifies each of its three
synthetic fixtures correctly and the result model carries no percentage or fraction field over
`AEAT_REGISTER_OPTIONS`-tagged pairs; the expected-but-not-found advisory fires only for
`PROFILE_APPLICABILITY` pairs and never for `AEAT_REGISTER_OPTIONS`-only pairs; the period
multiplicity field correctly reports raw-versus-selected counts against a synthetic two-filing
fixture, and the found-more-than-expected advisory fires at `INFO`, never `WARNING`, severity;
every new CLI verb passes `test_documented_command_conformance.py` and its JSON-schema conformance
case; the write-guard enrollment test recognises `app live filed pull-all` as profile-bound; the
locale gate (`dev.locales scaffold --check`) is green across all four catalogues; and the
hand-swept surfaces (error-registry suggestions, next-action builder, operator help, envelope
command identifiers, agent-harness docs) pass their existing conformance tests. No Step is
verified by, or requires, a live authenticated AEAT probe; that remains a separate,
not-yet-authorised follow-up, and the plan is fully shippable and fully honest about coverage
without it. `P02.S23` is complete only once landed by an executor after its file's contention
clears; every other Step is independently completable.
