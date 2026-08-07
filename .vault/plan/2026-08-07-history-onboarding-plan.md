---
tags:
  - '#plan'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:2cd424874aa69f86b66696e82a1817a83ebcc045e6e91e6e350dbc8633957374'
tier: L2
related:
  - '[[2026-08-07-history-onboarding-adr]]'
  - '[[2026-08-07-declarations-register-pagination-adr]]'
  - '[[2026-08-07-dehu-notification-legal-effect-reference]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-adr]]'
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

## Steps

### Phase `P01` - AEAT-declared discovery capability

Land dual-tier availability discovery: a taxpayer-specific PROFILE_APPLICABILITY grid derived from the taxpayer's own declared profile facts (always available, no live probe needed) as the primary completeness denominator, plus an AEAT_REGISTER_OPTIONS combobox enumeration whose NIF-scoping is unconfirmed, unioned additively and never solely relied on for a completeness claim.

- [x] `P01.S01` - add the FiledDeclarationAvailability and FiledDeclarationAvailabilityReport pydantic v2 models, verified by a strict roundtrip test; `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`.
- [ ] `P01.S02` - add discover_filed_declaration_availability reading the modelo combobox's full option set then, per modelo, the ejercicio combobox's full option set, tagged provenance AEAT_REGISTER_OPTIONS and treated as scoping-unconfirmed, verified by a synthetic-fixture test asserting the returned report matches a hand-authored fixture option list exactly; `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `P01.S03` - add the discover_filed_history application service wrapping the session bring-up shared with capture_filed_data around the new adapter function, verified by a test that a missing auth session raises the same SedeNavigationError the existing capture path raises; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P01.S04` - add the aeat app live filed discover verb emitting the availability report as the envelope result plus the live-scope caveat Notice, verified by test_documented_command_conformance.py and a new JSON-schema conformance case; `src/cadrumo/entrypoints/cli/_app_live.py`.
- [ ] `P01.S17` - add expected_filed_declaration_grid deriving a taxpayer-specific candidate modelo and ejercicio grid from TaxpayerProfile applicability and activity_start_date, verified by a test asserting the grid matches a hand-built profile fixture's expected modelos and year span; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P01.S18` - add FiledHistoryDiscoveryReport combining the AEAT_REGISTER_OPTIONS combobox signal and the PROFILE_APPLICABILITY expected grid into one provenance-tagged walk set per (modelo, ejercicio) pair, verified by a test asserting a pair present in both signals carries both provenance tags and a pair present in only one carries only that tag; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P01.S20` - add classify_register_scoping_signal comparing the AEAT_REGISTER_OPTIONS modelo set against the profile's confidently_excluded set from build_obligation_coverage, returning LIKELY_UNIVERSAL, LIKELY_NIF_SCOPED or INCONCLUSIVE, verified by three synthetic-fixture tests, one per classification, none asserting a resolved boolean; `src/cadrumo/application/live/_filed_data_capture.py`.

### Phase `P02` - Provenance parity proof

Prove that a bulk-discovered historical capture stamps the same official ObservationSourceKind
as an existing single-pair live capture, settling the provenance question without introducing a
new kind.

- [ ] `P02.S05` - add a parity test capturing the same synthetic declaracion fixture once through capture_filed_data and once through the discovery-driven grid, asserting both persisted observations carry ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE and are otherwise field-equal apart from capture timestamps, verified by the test going red if either path is made to stamp a different kind; `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.

### Phase `P03` - Onboarding orchestration verb

Sequence discovery, bulk filed capture, IVA wallet reconciliation and notificaciones pull behind
one standalone pull-all verb, with a re-capture divergence diff surfaced as a standing advisory.

- [ ] `P03.S06` - add the FiledHistoryOnboardingResult typed result model carrying per-pair outcomes, IVA wallet reconciliation status, notificaciones pull status, the divergence Notice list, the CoverageScopingSignal classification and a prose denominator_note field, and no numeric completeness percentage or fraction over AEAT_REGISTER_OPTIONS-tagged pairs, verified by a strict roundtrip test plus a test asserting the model schema carries no percentage or fraction field; `src/cadrumo/entrypoints/cli/_app_live_payloads.py`.
- [ ] `P03.S07` - add the re-capture divergence diff comparing a fresh FiledDeclaracionObservation against the prior stamped observation for the same modelo, ejercicio and period key, verified by a test that re-captures a fixture with one changed casilla value and asserts exactly one WARNING Notice naming that casilla; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P03.S08` - add the pull_filed_history orchestration service walking the FiledHistoryDiscoveryReport union grid, calling capture_filed_data_bulk over it, then capture_iva_compensation_wallet and reconcile_iva_compensation_wallet, then the existing notificaciones pull, verified by an integration test against synthetic fixtures for every stage asserting the composed FiledHistoryOnboardingResult reflects every stage's outcome; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P03.S09` - add the aeat app live filed pull-all verb, verified by test_documented_command_conformance.py and a new JSON-schema conformance case; `src/cadrumo/entrypoints/cli/_app_live.py`.
- [ ] `P03.S10` - enroll app live filed pull-all in PROFILE_BOUND_WRITE_VERB_PATHS, verified by the existing write-policy guard test asserting the new path is recognised as profile-bound; `src/cadrumo/application/storage_write_policy.py`.
- [ ] `P03.S19` - add the expected-but-not-found advisory comparing captured rows against every PROFILE_APPLICABILITY-tagged pair, emitting a WARNING Notice naming each modelo and ejercicio the profile expects but no declaracion was captured for, verified by a test asserting the Notice fires only for PROFILE_APPLICABILITY pairs and never for pairs carrying only the AEAT_REGISTER_OPTIONS tag; `src/cadrumo/application/live/_filed_data_capture.py`.

### Phase `P04` - Operator-surface integration and hand-swept sweep

Wire the overview no-history advisory, sweep every surface no gate scans, and land real locale
values in all four catalogues.

- [ ] `P04.S11` - add the overview INFO Notice naming aeat app live filed pull-all when a workable profile has zero observations carrying an official ObservationSourceKind, verified by a calendar-overview test asserting the Notice fires for a zero-observation profile and is absent once one official observation exists; `src/cadrumo/application/overview/_calendar_evidence.py`.
- [ ] `P04.S12` - land real es, en, ca and hu values for every new help string, Notice message key and result-field label the P01 through P03 verbs introduce, verified by dev.locales scaffold --check, gated on the shared locale catalogues being free of unrelated in-flight writes before landing; `src/cadrumo/locales`.
- [ ] `P04.S13` - add the error-registry default_suggestion entries for the new discover and pull-all verb refusals, verified by the existing suggestion-command conformance test; `src/cadrumo/core/errors/registry`.
- [ ] `P04.S14` - add the cross-period next_action builder cases pointing at the new discover and pull-all verbs, verified by the existing next-action conformance coverage; `src/cadrumo/application/modelo/_verification_cross_period.py`.
- [ ] `P04.S15` - update operator_surface/_help.py with the new discover and pull-all verb entries, verified by test_rule_surface_conformance.py; `src/cadrumo/application/operator_surface/_help.py`.
- [ ] `P04.S16` - update the agent-harness docs under src/cadrumo/_data/agent that name the filed verb group to cite the new discover and pull-all verbs, verified by the harness-citation conformance check confirming every named verb resolves against the live operator-surface manifest; `src/cadrumo/_data/agent`.

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
`capture_filed_data` path (already shipped) and can run in parallel with P01. P03 depends on P01
closing in full (needs `S18`'s union report shape and `S20`'s signal) and on the provenance
settlement recorded by P02, so P03 does not start until both close; within P03, `S06` (result
model) and `S07` (divergence diff) can run in parallel with each other, `S08` (orchestration)
depends on both plus `S18`, `S19` (expected-but-not-found advisory) depends on `S08`, and
`S09`-`S10` (CLI verb, write-guard enrollment) depend on `S08`. P04 depends on P03 closing (the
CLI verb and its identifiers must exist before the sweep can reference them); within P04, `S11`
(overview Notice) is independent of `S13`-`S16` and may run in parallel with them. `S12` (locale
rows) additionally carries a standing dependency on the shared locale catalogues settling any
unrelated in-flight peer write before it lands, independent of this plan's own internal ordering.

This plan's Phases are independent of the sibling `declarations-register-pagination` plan's
Phases; no Step here blocks on that plan's Steps, and no Step there blocks on this plan.

## Verification

The plan is complete when every Step above is closed (`- [x]`) and its named gate is green:
every new pydantic model passes a strict roundtrip test; every new adapter and service function
is verified against synthetic-HTML fixtures, never a live AEAT session; the union report tags
each pair with the correct provenance set; the scoping heuristic classifies each of its three
synthetic fixtures correctly and the result model carries no percentage or fraction field over
`AEAT_REGISTER_OPTIONS`-tagged pairs; the expected-but-not-found advisory fires only for
`PROFILE_APPLICABILITY` pairs and never for `AEAT_REGISTER_OPTIONS`-only pairs; every new CLI verb
passes `test_documented_command_conformance.py` and its JSON-schema conformance case; the
write-guard enrollment test recognises `app live filed pull-all` as profile-bound; the locale gate
(`dev.locales scaffold --check`) is green across all four catalogues; and the hand-swept surfaces
(error-registry suggestions, next-action builder, operator help, envelope command identifiers,
agent-harness docs) pass their existing conformance tests. No Step is verified by, or requires, a
live authenticated AEAT probe; that remains a separate, not-yet-authorised follow-up, and the plan
is fully shippable and fully honest about coverage without it.
