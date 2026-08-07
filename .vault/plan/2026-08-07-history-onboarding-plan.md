---
tags:
  - '#plan'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:643e98ebbb5497e20adf62a4571a4599d1314f7fed4ab667f90953ad4788f09b'
tier: L2
related:
  - '[[2026-08-07-history-onboarding-adr]]'
  - '[[2026-08-07-declarations-register-pagination-adr]]'
  - '[[2026-08-07-dehu-notification-legal-effect-reference]]'
---

# `history-onboarding` plan

Roll-up plan executing `[[2026-08-07-history-onboarding-adr]]`: land AEAT-declared history
discovery as the completeness denominator, and the standalone onboarding verb that composes it
with the existing filed-declaration, IVA wallet, and notificaciones capture primitives.

## Description

This plan is the cross-cutting roll-up for the `history-onboarding` cluster. It executes
`[[2026-08-07-history-onboarding-adr]]` in full (discovery capability, provenance settlement,
the pull-all orchestration verb, operator-surface wiring, and the mandatory hand-swept sweep). It
does not restate or duplicate the sibling plans it depends on: `[[2026-08-07-declarations-register-pagination-adr]]`
owns its own self-contained L1 plan for parser-level pagination detection, executing independently
(this plan's coverage report consumes that sibling's per-pair completeness signal once it lands,
but does not block on it, per the ADR's Considerations). `[[2026-08-07-dehu-notification-legal-effect-reference]]`
is still an in-progress reference for a sibling ADR not yet accepted; this plan does not sequence
against it beyond composing the existing, already-shipped notificaciones pull primitive Phase P03
uses.

Every verification gate below uses the repository's existing synthetic-HTML fixture pattern
(the same shape as `declaraciones-modelo-100-paginated-synthetic.html`); no Step in this plan
performs or requires a live authenticated AEAT session. A live-account confidence check of the
discovery combobox's NIF-scoping is explicitly out of scope for this plan and requires separate
operator sign-off not yet given.

## Steps

## Steps

### Phase `P01` - AEAT-declared discovery capability

Land the read-only availability discovery that reads AEAT's own declarations-register combobox
option list and becomes the completeness denominator, replacing the caller-guessed year and
modelo grid.

- [ ] `P01.S01` - add the FiledDeclarationAvailability and FiledDeclarationAvailabilityReport pydantic v2 models, verified by a strict roundtrip test; `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`.
- [ ] `P01.S02` - add discover_filed_declaration_availability reading the modelo combobox's full option set then, per modelo, the ejercicio combobox's full option set, verified by a synthetic-fixture test asserting the returned report matches a hand-authored fixture option list exactly; `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `P01.S03` - add the discover_filed_history application service wrapping the session bring-up shared with capture_filed_data around the new adapter function, verified by a test that a missing auth session raises the same SedeNavigationError the existing capture path raises; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P01.S04` - add the aeat app live filed discover verb emitting the availability report as the envelope result plus the live-scope caveat Notice, verified by test_documented_command_conformance.py and a new JSON-schema conformance case; `src/cadrumo/entrypoints/cli/_app_live.py`.

### Phase `P02` - Provenance parity proof

Prove that a bulk-discovered historical capture stamps the same official ObservationSourceKind
as an existing single-pair live capture, settling the provenance question without introducing a
new kind.

- [ ] `P02.S05` - add a parity test capturing the same synthetic declaracion fixture once through capture_filed_data and once through the discovery-driven grid, asserting both persisted observations carry ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE and are otherwise field-equal apart from capture timestamps, verified by the test going red if either path is made to stamp a different kind; `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.

### Phase `P03` - Onboarding orchestration verb

Sequence discovery, bulk filed capture, IVA wallet reconciliation and notificaciones pull behind
one standalone pull-all verb, with a re-capture divergence diff surfaced as a standing advisory.

- [ ] `P03.S06` - add the FiledHistoryOnboardingResult typed result model carrying per-pair outcomes, IVA wallet reconciliation status, notificaciones pull status and the divergence Notice list, verified by a strict roundtrip test; `src/cadrumo/entrypoints/cli/_app_live_payloads.py`.
- [ ] `P03.S07` - add the re-capture divergence diff comparing a fresh FiledDeclaracionObservation against the prior stamped observation for the same modelo, ejercicio and period key, verified by a test that re-captures a fixture with one changed casilla value and asserts exactly one WARNING Notice naming that casilla; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P03.S08` - add the pull_filed_history orchestration service sequencing discovery then capture_filed_data_bulk over the discovered grid then capture_iva_compensation_wallet and reconcile_iva_compensation_wallet then the existing notificaciones pull, verified by an integration test against synthetic fixtures for every stage asserting the composed FiledHistoryOnboardingResult reflects every stage's outcome; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P03.S09` - add the aeat app live filed pull-all verb, verified by test_documented_command_conformance.py and a new JSON-schema conformance case; `src/cadrumo/entrypoints/cli/_app_live.py`.
- [ ] `P03.S10` - enroll app live filed pull-all in PROFILE_BOUND_WRITE_VERB_PATHS, verified by the existing write-policy guard test asserting the new path is recognised as profile-bound; `src/cadrumo/application/storage_write_policy.py`.

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

P01 has no dependency on any other Phase and can start immediately. P02 depends only on the
existing `capture_filed_data` path (already shipped) and can run in parallel with P01. P03
depends on P01 (needs the discovery output shape from `P01.S01`-`P01.S02`) and on the provenance
settlement recorded by P02, so P03 does not start until both close; within P03, S01-S02 (result
model, divergence diff) can run in parallel with each other but S03 (orchestration) depends on
both, and S04-S05 (CLI verb, write-guard enrollment) depend on S03. P04 depends on P03 closing
(the CLI verb and its identifiers must exist before the sweep can reference them); within P04,
S01 (overview Notice) is independent of S02-S05 and may run in parallel with them. `P04.S02`
(locale rows) additionally carries a standing dependency on the shared locale catalogues settling
any unrelated in-flight peer write before it lands, independent of this plan's own internal
ordering.

This plan's Phases are independent of the sibling `declarations-register-pagination` plan's
Phases; no Step here blocks on that plan's Steps, and no Step there blocks on this plan.

## Verification

The plan is complete when every Step above is closed (`- [x]`) and its named gate is green:
every new pydantic model passes a strict roundtrip test; every new adapter and service function
is verified against synthetic-HTML fixtures, never a live AEAT session; every new CLI verb passes
`test_documented_command_conformance.py` and its JSON-schema conformance case; the write-guard
enrollment test recognises `app live filed pull-all` as profile-bound; the locale gate
(`dev.locales scaffold --check`) is green across all four catalogues; and the hand-swept surfaces
(error-registry suggestions, next-action builder, operator help, envelope command identifiers,
agent-harness docs) pass their existing conformance tests. No Step is verified by, or requires, a
live authenticated AEAT probe; that remains a separate, not-yet-authorised follow-up.
