---
tags:
  - '#adr'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:33e4345124199f1892c04dbec5629915aedcd2f3379586e9dc6c666e483fc126'
related:
  - "[[2026-08-07-history-onboarding-reference]]"
  - "[[2026-08-07-declarations-register-pagination-adr]]"
  - "[[2026-08-07-dehu-notification-legal-effect-reference]]"
  - "[[2026-05-04-live-filing-data-capture-adr]]"
  - "[[2026-07-12-justificante-reframing-audit]]"
  - '[[2026-08-07-history-onboarding-plan]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-adr]]'
---
# `history-onboarding` adr: `New-profile AEAT history discovery and onboarding` | (**status:** `accepted`)

## Problem Statement

A brand-new profile that has just completed setup has no way to pull its AEAT-held history:
filed declaraciones by modelo, justificantes, evidence bytes, notificaciones, and the IVA
compensación balance against AEAT's own online balance. Every capture primitive this needs
already exists (`[[2026-08-07-history-onboarding-reference]]`), but nothing sequences them for
a first-time pull, and the one existing bulk sweep, `capture_filed_data_bulk`, is bounded by a
caller-guessed `(modelo, year_from, year_to)` grid rather than by what AEAT actually holds for
this NIF. A taxpayer whose real history falls outside that guess is silently excluded, and
nothing ever reports that exclusion.

## Considerations

**The completeness claim needs an external denominator, and the obvious one is load-bearing but
unverified.** "We captured every pair we asked about" is not evidence of completeness — it
restates the caller's own guess. The declarations register's own modelo/ejercicio combobox, read
once per authenticated session, is a candidate AEAT-sourced denominator — as currently implemented
it exposes its option list only to click a caller-named target (`_select_combobox_value`,
`_declarations.py:614`) and never to enumerate it, so reading the full list is new, narrow,
read-only work. But whether that list is genuinely NIF-scoped, or a static universal catalogue
the UI renders regardless of taxpayer, is unconfirmed, and settling it needs a live authenticated
probe nobody has authorised. Following that risk to its consequence: if the list is static and
universal, it carries zero taxpayer-specific information, and a coverage report measured against
it ALONE would assert completeness over a denominator that has nothing to do with the subject —
worse than no report at all. The design cannot make this signal load-bearing on its own.

**The fallback denominator is the taxpayer's own declared profile, and it already exists.**
Semantic search for "what else is NIF-scoped and already available" surfaces the overview
calendar's own obligation-coverage machinery: `derive_modelo_applicability` and
`build_obligation_coverage` (`application/overview/_coverage.py:126`) already reconcile the full
registry modelo universe against a `TaxpayerProfile`'s three declared axes into `surfaced` /
`confidently_excluded` / `advised` / `out_of_scope`, and `partition_cross_period_requirements_by_activity_start`
(`application/calculations/_cross_period_clean_state.py:110`) already scopes a requirement set by
the profile's declared `activity_start_date`. Both are pure functions over data the taxpayer
themselves declared during setup — no live AEAT call, no combobox, no scoping uncertainty. Every
modelo NOT `confidently_excluded` or `out_of_scope`, crossed with the year span from
`activity_start_date.year` through the current year, is a genuinely taxpayer-specific candidate
grid: call this signal `PROFILE_APPLICABILITY`. It ships today, requires no specimen and no live
probe, and is the load-bearing denominator. The combobox signal (`AEAT_REGISTER_OPTIONS`) is kept
as an ADDITIVE second signal — unioned into the same walk grid so it can only ever widen coverage,
never substitute for the taxpayer-specific one — and the coverage report tags every walked pair
with which signal(s) nominated it. A `PROFILE_APPLICABILITY` pair that yields zero captured rows
is a real anomaly worth a `WARNING` advisory (the taxpayer's own declared facts expected a filing
that was not found); an `AEAT_REGISTER_OPTIONS`-only pair yielding zero rows is reported as a
plain negative, never an anomaly, because that signal's informativeness for THIS taxpayer remains
unconfirmed. The verified-scoping upgrade, if a future authorised probe confirms it, promotes
`AEAT_REGISTER_OPTIONS` results to the same advisory treatment; it is not a precondition for the
design to exist or ship.

**Both worlds, made explicit.** If the combobox IS NIF-scoped, `AEAT_REGISTER_OPTIONS` genuinely
widens `PROFILE_APPLICABILITY` with pairs the profile's declared facts could not predict (an
undeclared activity, an obligation the operator answered incompletely) — a pure coverage gain. If
the combobox is a STATIC UNIVERSAL list, walking it still captures real, correctly-scoped rows for
every pair (each per-pair search is independently authenticated and NIF-scoped through the
existing `capture_filed_data` search, which is unaffected by whether the DROPDOWN's own option
enumeration is universal) — so accuracy of what is captured never degrades in either world. What
changes between worlds is only what the REPORT may honestly claim about the pairs that returned
NOTHING: in the NIF-scoped world a zero-row `AEAT_REGISTER_OPTIONS` pair is a genuine negative; in
the universal world it is uninformative, because AEAT offering the option proves nothing about
this taxpayer. The design does not need to know which world it is in to behave correctly — it
needs to know which world it is in only to decide how to WORD the report, which is why the
provenance tag, not a resolved boolean, is what the report carries forward.

**A cheap, offline, self-diagnosing heuristic exists, and it is worth a row.** Search by MEANING
for a graded-confidence-by-arithmetic precedent surfaced
`_retencion_rate_advisory.py:365` (`inferred_retencion_rate_unmatched` / `_sectoral_rate_unconfirmed`
/ silent) — three outcomes from one arithmetic comparison, ranked by how strong the match is,
never asserted as certain. The same shape applies here: `build_obligation_coverage`'s
`confidently_excluded` set (modelos the profile POSITIVELY answers "no" for — `NOT_APPLICABLE` /
`ATTRIBUTION_PASS_THROUGH`, e.g. Impuesto sobre Sociedades for a natural-person profile) is a
structural impossibility list. If the combobox offers a `confidently_excluded` modelo AND its
ejercicio sub-list comes back non-empty, that is real evidence the list is not filtered per
taxpayer (AEAT would not populate candidate years for a form this taxpayer's own declared facts
make categorically inapplicable) — classify `LIKELY_UNIVERSAL`. If every combobox modelo instead
falls inside `surfaced | advised` (never `confidently_excluded`), that is weak supportive evidence
of NIF-scoping — classify `LIKELY_NIF_SCOPED`. If the profile has no `confidently_excluded`
modelos to test against, or the combobox returns no options at all, classify `INCONCLUSIVE`. This
heuristic needs no separate live access beyond the authenticated session discovery already opens
for its own purpose (reading the combobox), so it is not a new probe requiring additional
authorisation, and it is fully unit-testable against a synthetic combobox fixture asserting each
of the three classifications. It upgrades or downgrades confidence; it never proves scoping either
way, and the report must say so.

**The report renders words, never a number, when provenance is uncertain.** Per the operator's
instruction, an operator must never be shown a completeness figure implying the AEAT-sourced set
represents "your history" when that has not been established. Concretely: `FiledHistoryOnboardingResult`
carries NO numeric completeness percentage or fraction computed over `AEAT_REGISTER_OPTIONS`-tagged
pairs, ever. It carries `scoping_signal: CoverageScopingSignal` (the heuristic's classification)
and a prose `denominator_note` field stating, in each case: `LIKELY_UNIVERSAL` — "some offered
pairs may not relate to you; only the pairs matching your declared obligations are used to flag a
possible gap"; `LIKELY_NIF_SCOPED` — "AEAT's offered options are consistent with your declared
obligations, but this has not been independently verified"; `INCONCLUSIVE` — "AEAT's offered
options could not be checked against your declared obligations." The only number the report ever
asserts confidently is the `PROFILE_APPLICABILITY`-tagged coverage (found vs. expected against the
taxpayer's own declared facts), because that denominator's provenance is never in question.

**This is a different completeness axis than the sibling pagination decision
(`[[2026-08-07-declarations-register-pagination-adr]]`).** That ADR scopes whether one
`(modelo, ejercicio)` query's row page is complete (AEAT-declared total vs. rows parsed). This
ADR scopes whether the *set of pairs queried at all* is complete (the dual-tier denominator vs.
a caller-guessed grid). A history-onboarding pull is only honestly complete when both hold; this
ADR does not restate or supersede the sibling's pending detection decision, and a
history-onboarding coverage report MUST surface per-pair `row_count` without asserting
within-page completeness until that sibling decision ships and is composed in.

**Compose, do not invent.** Bulk capture, IVA wallet reconciliation, and notificaciones pull are
all canonical and complete (`[[2026-08-07-history-onboarding-reference]]`); the obligation-coverage
machinery the `PROFILE_APPLICABILITY` signal reuses is likewise canonical and already shipped. The
only genuinely new capabilities are (a) the dual-tier discovery union and (b) an orchestrating
onboarding verb that sequences discovery -> bulk capture -> IVA wallet reconciliation ->
notificaciones pull -> one coverage report. No new persistence schema, no new capture mechanism,
no new applicability engine.

**Onboarding is distinct from an ad-hoc bulk pull, but both compose the same primitives.** A
new profile has nothing to gain from a wizard-embedded history pull: `_profile_readiness_gate.py`
refuses filing-grade modelo work while `status is SETUP_INCOMPLETE`, so the earliest a
filing-grade capture can attach observations to a workable profile is post-setup-completion
anyway, and the wizard catalogue is already a long guided sequence that a live-AEAT round trip
(browser session, possible MFA, minutes of walk time) does not belong inside. A **standalone
verb**, discoverable and re-runnable at any time after setup, is the right shape; a **standing
Notice** on the overview when a profile shows zero official-AEAT-sourced observations is the
sufficient nudge, mirroring the calendar's existing undetermined-not-empty posture for an
incomplete obligation universe.

**Provenance needs no new kind.** `capture_filed_data`/`_filed_observation_persistence.py:116`
already stamps `ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE` (official, per `is_official_aeat`)
for calculation observations derived from a captured declaración; `capture_filed_data_bulk`
reuses that same finalizer. A history-onboarding pull that composes `capture_filed_data_bulk`
over the discovered grid produces observations indistinguishable in kind from any other live
capture — correctly so, since an imported historical filing IS an AEAT-sourced filed
declaración, not a lesser-trust echo of one, regardless of whether the discovering signal was
`AEAT_REGISTER_OPTIONS` or `PROFILE_APPLICABILITY` — the discovery signal decides WHICH pairs to
walk, never the trust level of what is captured. Introducing a sixth `ObservationSourceKind` here
would be inventing a distinction the domain does not have: the cross-period clean-state gate and
the calendar advisory already treat `AEAT_SEDE_JUSTIFICANTE` correctly for this case.

**Partial success is the expected outcome, and re-capture divergence needs a signal.**
`capture_filed_data_bulk` already records per-pair failures
(`FiledDataCaptureFailureRow`) and continues past them — correct, unchanged. Re-capturing an
already-captured pair is an unconditional upsert with no divergence detection
(`[[2026-08-07-history-onboarding-reference]]`). Per `no-silent-under-declaration`, a re-capture
that silently overwrites a previously observed casilla value with a different one is exactly the
unwatched direction that rule exists to close. Refusing outright is too strong — AEAT itself can
legitimately correct a prior filing (a complementaria) — so the orchestrating onboarding verb
must diff the new capture against the prior stamped observation for the same `(modelo, ejercicio,
period)` key and surface a `WARNING` `Notice` enumerating every casilla whose value changed,
mirroring the `apply_cotejo`/`censo_divergence_notice` shape: one commit event per apply, a
standing advisory, never a silent auto-resolve. This diff is new orchestration-layer logic; it
MUST NOT be pushed into `capture_filed_data_bulk` itself, which stays the generic reusable
primitive every other capture caller also uses unchanged.

**A live smoke test found a real multiplicity gap, verified against HEAD, and it is squarely this
ADR's to own.** For modelo 303, filing year 2024, the AEAT register returned six rows for a
naive four-quarter year: 1T, 2T, 3T, 4T, plus a second 3T and a second 4T presented months later
under different `expediente_id`s — almost certainly originals plus complementarias.
`select_declarations_for_capture` (`application/live/_filed_data.py:71-97`) already captures EVERY
matching raw row for a period, not just one, so `filed pull --modelo 303 --year 2024 --period 3T`
persisted `captured_count=2` with two distinct raw observations and six artefacts. Nothing is lost:
`select_latest_filed_observations_in_history_order` (`application/live/_filed_observation_persistence.py:130-159`,
confirmed at HEAD) is a genuine latest-by-presentation SELECTION for the ONE calculation
observation, ranked `(is ALTA, presented_at, expediente_id)` — the same rank tuple
`_select_authoritative_declaration` (`adapters/outbound/aeat/sede/_declarations.py:1384-1397`,
confirmed at HEAD) and `latest_declarations_by_period` (`_filed_observation_persistence.py:311-`)
both use, blind to which candidate amends which. This is a DIFFERENT scenario from the re-capture
divergence diff above: that diff detects divergence ACROSS separate runs of the same pair; this
gap is plurality WITHIN one run, already on AEAT's register before this feature ever executes.
Two real holes follow, both inside this feature's own promise of a faithful history: (1) the
per-period raw count is computed and then thrown away — `BulkFiledDataCaptureReport` /
`FiledDataCaptureReport` report only a flat total `captured_count` across the whole
`(modelo, year)` sweep (`_filed_data_capture.py:238,301`, confirmed at HEAD), with no per-period
breakdown, so a coverage report built on top of it cannot tell "one filing" from "two filings,
newer kept" for any given period; and (2) `Declaracion.tipo_solicitud`
(`adapters/outbound/aeat/sede/_declarations_schema.py:26`, confirmed at HEAD) — AEAT's own
original-versus-complementaria signal — is parsed and reaches CLI display
(`_declarations.py:1166`) but is dropped at `_filed_observation_source_metadata`
(`_filed_observation_persistence.py:491-506`, confirmed at HEAD: builds only
`aeat_register_status`, `aeat_expediente_id`, `authenticated_identity` and CSVs), so even the
label distinguishing "original" from "amendment" is discarded at the exact boundary a coverage
report would want to read it from.

This is in scope, not deferred, because a feature whose Problem Statement is "import this
taxpayer's history faithfully" cannot silently collapse a period's real multiplicity into a single
number without contradicting its own premise — the `(modelo, ejercicio)` pair grid this ADR
already treats as the completeness axis must NOT be read as 1:1 with declarations found; that
assumption is exactly what `latest_declarations_by_period`'s existing collapse already breaks, and
this ADR's own row-count denominator work must be checked against it rather than silently
inheriting it. The fix is symmetric to the expected-but-not-found advisory this ADR already
specifies: a period whose raw register count exceeds the persisted-observation count of 1 is not
an anomaly (AEAT amendments are legitimate) but IS a fact the coverage report must surface, at
`INFO` severity (never `WARNING`, which stays reserved for genuine gaps). `tipo_solicitud`
carry-through is a smaller, separable, higher-value enrichment of the same signal — it lets the
notice say "original" versus "complementaria" instead of only "N filings, newest kept" — and is
opened as its own row rather than folded into the multiplicity row, because it touches a file this
ADR's author is not permitted to edit directly (`_filed_observation_persistence.py` is under
active peer contention); the multiplicity count itself needs no such edit, since the raw
declaration list is already in scope inside `_filed_data_capture.py` (this ADR's own target file)
before any call into the persistence module.

## Considered options

1. **No discovery; widen the default year range and modelo set.** Rejected: any fixed default is
   still a guess, and the honesty requirement ("nothing ever reports the exclusion") is not met
   by a wider guess, only by a smaller one.
2. **Discovery reads AEAT's own register combobox option list as the denominator; the
   onboarding verb walks it.** Accepted. This is the only source in this codebase that can
   answer "what does AEAT say this NIF has," and it requires no new AEAT surface — the combobox
   already renders on the same authenticated register page every capture already opens.
3. **A generic `aeat filing import --from-*` omnibus verb.** Rejected outright.
   `[[2026-07-12-justificante-reframing-audit]]` already ruled against reviving this exact
   vocabulary; per-evidence-kind verbs landing on one shared boundary is the accepted successor
   shape, and this ADR's new verbs follow it (`filed`-group extensions, not a new root family).
4. **Fold history pull into the setup wizard.** Rejected per the onboarding-is-distinct
   consideration above: SETUP_INCOMPLETE already blocks the filing-grade work this history feeds,
   and a live-AEAT round trip does not belong inside a guided answer sequence.
5. **Make `AEAT_REGISTER_OPTIONS` the sole denominator, gated behind a future live-scoping
   probe.** Rejected: this makes the feature's existence and honesty depend on an authorisation
   nobody has given, with no date. **Make `PROFILE_APPLICABILITY` the sole denominator, dropping
   the combobox read entirely.** Rejected: it discards a real, if unconfirmed, AEAT-sourced signal
   that can only ever widen coverage once unioned in. **Union both, load-bearing on the
   taxpayer-specific one.** Accepted: ships today, never asserts more than it can prove, and
   upgrades cleanly if the live-scoping question is later settled in `AEAT_REGISTER_OPTIONS`'s
   favour.
6. **No self-diagnosing heuristic; wait for an authorised live specimen.** Rejected: leaves a
   cheap, buildable, zero-extra-cost signal on the table for an indeterminate wait. **A hard
   boolean "is this NIF-scoped" heuristic decided from one comparison.** Rejected: one comparison
   cannot prove a negative (a taxpayer whose declared profile happens to have no
   `confidently_excluded` modelo produces no evidence either way, and asserting `NIF_SCOPED` from
   silence would be a false confidence claim of exactly the kind this whole task exists to avoid).
   **A three-way graded classification (`LIKELY_UNIVERSAL` / `LIKELY_NIF_SCOPED` / `INCONCLUSIVE`),
   surfaced as a label the report reads from, never resolved into a boolean.** Accepted, mirroring
   the graded-confidence shape `_retencion_rate_advisory.py` already uses for a structurally
   similar problem (inferring a fact from indirect arithmetic evidence, ranked by strength, never
   asserted as certain).
7. **Leave period multiplicity uninstrumented; treat it as pre-existing, out-of-scope behaviour.**
   Rejected: it directly undermines this ADR's own "faithful history" premise once a bulk sweep
   can silently walk past an amended period with no trace. **Push the multiplicity check into
   `select_latest_filed_observations_in_history_order` itself, so the selector raises or warns.**
   Rejected: that function is the shared selection authority for every capture route, not an
   onboarding-specific reporting surface, and the ADR's own no-shared-primitive-mutation
   constraint applies here exactly as it does to the re-capture diff. **Compute and surface the
   raw-vs-selected count in the onboarding orchestration layer, from data `_filed_data_capture.py`
   already holds before the collapse.** Accepted: no shared-primitive edit, an `INFO` (not
   `WARNING`) severity matching that amendments are legitimate, and it composes with, rather than
   duplicates, the existing re-capture divergence diff.

## Constraints

- Verb names obey `aeat-cli-contract`: fetch-from-AEAT is `pull`/`discover` (read-only
  enumeration is not a mutation and is not named `pull`), never `capture`/`refresh`/`fetch`/
  `sync`. No generic `--from-*` importer, per `[[2026-07-12-justificante-reframing-audit]]`.
- No live AEAT probe is authorized by this ADR. Whether the register's combobox option list is
  genuinely NIF-scoped (reflecting only pairs this taxpayer actually filed) versus a static
  universal catalogue is **unverified** — the same unverified-live-behaviour posture the sibling
  pagination reference records for the register's pager. Confirming it needs an authenticated
  live probe against an account with real filing history, under explicit operator authorisation;
  nobody has given that authorisation and it must not be attempted opportunistically. This is why
  `PROFILE_APPLICABILITY` — not `AEAT_REGISTER_OPTIONS` — is the load-bearing signal: the design
  ships fully honest and fully functional with the live-scoping question permanently unresolved.
  Until verified, `AEAT_REGISTER_OPTIONS` output is reported as "AEAT's offered option set," never
  as "this NIF's confirmed filing history" — a zero-row result for an offered pair is a genuine
  negative, but an *absent* option cannot yet be positively distinguished from "the combobox
  never lists ejercicios the taxpayer didn't file" versus "the combobox lists every ejercicio
  regardless."
- `FiledHistoryOnboardingResult` and `FiledDeclarationAvailabilityReport` MUST NOT carry a numeric
  completeness percentage or fraction computed over `AEAT_REGISTER_OPTIONS`-tagged pairs, in this
  ADR or any later revision, without a new ADR amendment recording that live NIF-scoping has been
  confirmed. The scoping heuristic's output is a label (`CoverageScopingSignal`), never a resolved
  boolean, and the report's uncertainty-facing text is prose (`denominator_note`), never a number.
- `_filed_observation_persistence.py` and `adapters/outbound/aeat/sede/_declarations.py` are under
  active peer contention; the `tipo_solicitud` carry-through row targeting the former is authored
  here and landed by an executor, never edited directly by this ADR's authoring agent. Every other
  row targets `_filed_data_capture.py` (this ADR's own file) precisely because that avoids editing
  either contended file to compute the multiplicity signal.
- Every new verb needs its own line in `PROFILE_BOUND_WRITE_VERB_PATHS`
  (`storage_write_policy.py:122`) if it writes, plus a hand-swept pass through the
  error-registry `default_suggestion` fields, cross-period `next_action` builders,
  `operator_surface/_help.py`, envelope `command=` identifiers, and the agent-harness docs under
  `src/cadrumo/_data/agent/` (`aeat-cli-contract`).
- Every new user-facing string needs real `es`/`en`/`ca`/`hu` values through `dev.locales set`;
  the catalogues carry unrelated concurrent WIP right now, so locale work must be scheduled to
  land cleanly against `main`, not against the transient conflict.
- The re-capture divergence diff and the discovery denominator are both **new orchestration-layer
  code**; neither may be implemented by mutating `capture_filed_data_bulk`'s own contract, which
  stays the shared primitive its other callers (single-pair capture, relation-source capture)
  depend on unchanged.

## Implementation

The following rows are opened as the concrete, executable follow-on work this ADR authorises,
carried into the roll-up plan `[[2026-08-07-history-onboarding-plan]]`. Every row below is
buildable without live AEAT access: verification uses the repository's existing synthetic-HTML
fixture pattern (the same shape as `declaraciones-modelo-100-paginated-synthetic.html`, provenance
`synthetic_generated`), never a live authenticated session. No row in this list requires operator
sign-off; a live-account confidence check of the discovery combobox behaviour is a SEPARATE,
not-yet-authorised follow-up, tracked as an open item in Consequences, not as an Implementation row.

1. **`discover_filed_declaration_availability`** (new, `adapters/outbound/aeat/sede/_declarations.py`):
   opens the authenticated register page once, reads the modelo combobox's full `.z-comboitem-text`
   option set, and for each modelo option reads the ejercicio combobox's full option set for that
   modelo. Returns a new typed `FiledDeclarationAvailability` model
   (`modelo: str`, `ejercicios: tuple[int, ...]`) collected into a
   `FiledDeclarationAvailabilityReport` (`items: tuple[FiledDeclarationAvailability, ...]`,
   `discovered_at: UtcInstant`), tagged provenance `AEAT_REGISTER_OPTIONS`. Read-only, no
   persistence, not a `PROFILE_BOUND_WRITE_VERB_PATHS` entry.
1a. **`expected_filed_declaration_grid`** (new, `application/live/_filed_data_capture.py`):
   derives a `PROFILE_APPLICABILITY`-tagged candidate `(modelo, ejercicio)` grid from the active
   `TaxpayerProfile` by reusing `derive_modelo_applicability`/`build_obligation_coverage`
   (`application/overview/_coverage.py:126`) for the modelo axis and the profile's declared
   `activity_start_date` through the current year for the ejercicio axis. Pure function over
   already-persisted profile data; no live session, no new engine.
1b. **`FiledHistoryDiscoveryReport`** (new, `application/live/_filed_data_capture.py`): unions (1)
   and (1a) into one walk grid, tagging each `(modelo, ejercicio)` pair with the provenance
   signal(s) that nominated it.
1c. **`classify_register_scoping_signal`** (new, `application/live/_filed_data_capture.py`):
   compares (1)'s combobox modelo set against the profile's `confidently_excluded` set from
   `build_obligation_coverage`. Returns `CoverageScopingSignal.LIKELY_UNIVERSAL` when a
   confidently-excluded modelo appears with a non-empty ejercicio sub-list,
   `CoverageScopingSignal.LIKELY_NIF_SCOPED` when every combobox modelo falls inside
   `surfaced | advised`, else `CoverageScopingSignal.INCONCLUSIVE`. Pure function over data (1)
   and (1a) already fetched; no new AEAT surface, no separate authorisation.
2. **`aeat app live filed discover`** (new CLI verb, `filed` group): thin wrapper composing (1),
   (1a), (1b) and (1c), emits the tagged union report plus the scoping signal as the envelope
   result, and the live-scope caveat (Constraints, below) worded per the signal, never numerically,
   as a `Notice`.
3. **`aeat app live filed pull-all`** (new CLI verb, `filed` group): sequences (1b) ->
   `capture_filed_data_bulk` over the union grid -> `capture_iva_compensation_wallet` /
   `reconcile_iva_compensation_wallet` -> the existing notificaciones pull -> one
   `FiledHistoryOnboardingResult` envelope carrying per-pair outcomes, `scoping_signal` and
   `denominator_note` (prose, per Constraints - never a numeric completeness figure over
   `AEAT_REGISTER_OPTIONS`-tagged pairs), the re-capture divergence diff as `WARNING` `Notice`s,
   the expected-but-not-found advisory for `PROFILE_APPLICABILITY` pairs with no captured rows,
   and the sibling pagination ADR's per-pair completeness signal once that decision lands
   (interim: raw `row_count`, no within-page completeness assertion). Enrolled in
   `PROFILE_BOUND_WRITE_VERB_PATHS` as `app live filed pull-all`.
4. **Re-capture divergence diff** (new, orchestration layer only, invoked from (3)): compares each
   freshly captured `FiledDeclaracionObservation`'s casilla values against the prior stamped
   observation for the same key, and on any changed value emits a `WARNING` `Notice` naming the
   modelo, period and changed casilla ids, never a silent overwrite.
4a. **Period multiplicity signal** (new, `application/live/_filed_data_capture.py`): extends
   `FiledDataCaptureReport`/`BulkFiledDataCaptureReport` with a per-`(modelo, ejercicio, period)`
   breakdown of raw register row count versus the one persisted calculation observation, computed
   from the `declarations`/`selected` tuples the bulk capture path already holds before calling
   `finalize_filed_capture` — no edit to `_filed_observation_persistence.py` or `_declarations.py`.
4b. **Found-more-than-expected advisory** (new, orchestration layer only, invoked from (3)): for
   every period whose raw count from (4a) exceeds 1, emits an `INFO` `Notice` (never `WARNING`)
   naming the modelo, period, the winning `expediente_id`, and the count of superseded filings
   preserved as evidence; composes with, never duplicates, the re-capture divergence diff (4),
   which detects divergence ACROSS runs, not plurality WITHIN one run.
5. **Overview no-history `Notice`**: when a workable (non-`SETUP_INCOMPLETE`) profile has zero
   observations carrying an official `ObservationSourceKind`, the overview surfaces an `INFO`
   `Notice` naming `aeat app live filed pull-all` as the next action.
6. **Hand-swept surface pass**: `PROFILE_BOUND_WRITE_VERB_PATHS`, error-registry
   `default_suggestion` fields, the cross-period `next_action` builder
   (`application/modelo/_verification_cross_period.py`), `operator_surface/_help.py`, envelope
   `command=` identifiers, and the agent-harness docs under `src/cadrumo/_data/agent/`, for every
   identifier the new verbs introduce.
7. **Locale rows**: real `es`/`en`/`ca`/`hu` values for every new help string, `Notice` message key
   and result-field label the new verbs introduce, landed through `dev.locales set` then
   `scaffold`/`scaffold --check`.
8. **`tipo_solicitud` carry-through** (new field on `_filed_observation_source_metadata`,
   `application/live/_filed_observation_persistence.py:491-506`): adds `aeat_tipo_solicitud` to
   the returned metadata dict from `observation.tipo_solicitud`, sourced through to (4b)'s notice
   text so it can say "original" versus "complementaria" instead of only "N filings, newest kept."
   Targets a file under active peer contention; opened here, landed by an executor, never edited
   by this ADR's authoring agent. (4a)/(4b) do not depend on this row landing first — they degrade
   gracefully to the count-only wording when `tipo_solicitud` is absent from source metadata.

No new `ObservationSourceKind`, no new capture schema, no new IVA reconciliation mechanism, no
generic importer. Row 7 (and, transitively, rows 2 and 3 which cannot ship without their locale
keys) carries a dependency on the shared locale catalogues being free of unrelated in-flight
writes before landing; that dependency is a sequencing constraint on WHEN a row merges, not a
reason to defer authoring it. Row 8 carries a dependency on `_filed_observation_persistence.py`'s
current contention clearing before an executor can land it; rows 4a/4b do not share that
dependency and can land independently.

## Rationale

Every capability this feature needs already exists and is canonical; the only real gap is that
nothing tells the sweep what this taxpayer actually holds, and nothing sequences the existing
primitives into one operator-facing pull. Dual-tier discovery closes the honesty gap without
betting the feature's existence on an unauthorised live probe: `PROFILE_APPLICABILITY` is a real,
taxpayer-specific denominator built entirely from the profile's own declared facts and the
overview calendar's already-shipped applicability machinery, so it ships and is trustworthy today;
`AEAT_REGISTER_OPTIONS` is unioned in additively, so it can only widen coverage and never weakens
the honest claim the report makes. Keeping the onboarding verb standalone rather than
wizard-embedded respects the existing SETUP_INCOMPLETE gate and keeps a live-AEAT round trip out
of the guided setup flow. Reusing the existing official `ObservationSourceKind` and the existing
capture/reconciliation primitives keeps this a sequencing decision, not a new subsystem, consistent
with `aeat-calculation-aggregation`'s one-canonical-mechanism-per-type mandate.

## Consequences

- A new profile gains a single, re-runnable, standalone entry point to backfill its AEAT history,
  reported against a denominator that is genuinely taxpayer-specific by construction
  (`PROFILE_APPLICABILITY`) rather than a silent local guess, with the AEAT-sourced signal unioned
  in as a coverage-widening bonus rather than a load-bearing dependency.
- The discovery step's `AEAT_REGISTER_OPTIONS` component stays explicitly bounded: it reports
  AEAT's *offered* option set, not a verified confirmation that the set is NIF-scoped, until an
  authorised live probe settles that question — carried forward as an open item, not asserted
  away, and the feature's honesty never depended on that probe running.
- A `pull-all` sweep composing discovery × bulk capture × IVA reconciliation × notificaciones is
  slower and more failure-surface-prone than any single existing verb; partial failure is
  expected and reported per-pair, never silently swallowed.
- The re-capture divergence diff adds a small, permanent maintenance surface at the orchestration
  layer, justified by closing a real silent-under-declaration path a taxpayer with a corrected
  historical filing would otherwise hit invisibly.
- Full completeness (both axes: pair-set AND per-page) is not achieved until the sibling
  pagination ADR's decision also ships; this ADR's coverage report must not claim more than it
  currently can prove.
- A period carrying multiple AEAT filings (an amendment) is now visible in the coverage report at
  `INFO` severity instead of silently collapsing to the single latest-by-presentation calculation
  observation `select_latest_filed_observations_in_history_order` already selects; the raw evidence
  for every superseded filing was already preserved before this ADR (six artefacts persisted for
  the smoke-tested 3T pair), so this closes a VISIBILITY gap, not a data-loss one.
- The `tipo_solicitud` carry-through row depends on a currently-contended file clearing before an
  executor can land it, so the notice's wording may ship in its degraded "N filings, newest kept"
  form for a period before the richer "original versus complementaria" wording becomes available;
  this is an acceptable, explicitly-tracked staged rollout, not a silent gap.
