---
tags:
  - '#adr'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:08ed6af01f6a3df48eb3f717fb85ae15d7929f3678bb7a5b9bf76c1a3be4d815'
related:
  - "[[2026-08-07-history-onboarding-reference]]"
  - "[[2026-08-07-declarations-register-pagination-adr]]"
  - "[[2026-08-07-dehu-notification-legal-effect-reference]]"
  - "[[2026-05-04-live-filing-data-capture-adr]]"
  - "[[2026-07-12-justificante-reframing-audit]]"
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

**The completeness claim needs an external denominator.** "We captured every pair we asked
about" is not evidence of completeness — it restates the caller's own guess. The only external
authority for "which `(modelo, ejercicio)` pairs exist for this NIF" is AEAT itself: the
declaraciones register's own modelo/ejercicio combobox, read once per authenticated session, as
currently implemented, exposes its option list only to click a caller-named target
(`_select_combobox_value`, `_declarations.py:566`) and never to enumerate it. Reading that full
option list is a new, narrow, read-only capability — not a new capture mechanism.

**This is a different completeness axis than the sibling pagination decision
(`[[2026-08-07-declarations-register-pagination-adr]]`).** That ADR scopes whether one
`(modelo, ejercicio)` query's row page is complete (AEAT-declared total vs. rows parsed). This
ADR scopes whether the *set of pairs queried at all* is complete (AEAT-declared option list vs.
caller-guessed grid). A history-onboarding pull is only honestly complete when both hold; this
ADR does not restate or supersede the sibling's pending detection decision, and a
history-onboarding coverage report MUST surface per-pair `row_count` without asserting
within-page completeness until that sibling decision ships and is composed in.

**Compose, do not invent.** Bulk capture, IVA wallet reconciliation, and notificaciones pull are
all canonical and complete (`[[2026-08-07-history-onboarding-reference]]`). The only genuinely
new capabilities are (a) AEAT-declared option discovery and (b) an orchestrating onboarding verb
that sequences discovery → bulk capture → IVA wallet reconciliation → notificaciones pull → one
coverage report. No new persistence schema, no new capture mechanism.

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
over a discovered grid produces observations indistinguishable in kind from any other live
capture — correctly so, since an imported historical filing IS an AEAT-sourced filed
declaración, not a lesser-trust echo of one. Introducing a sixth `ObservationSourceKind` here
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

## Constraints

- Verb names obey `aeat-cli-contract`: fetch-from-AEAT is `pull`/`discover` (read-only
  enumeration is not a mutation and is not named `pull`), never `capture`/`refresh`/`fetch`/
  `sync`. No generic `--from-*` importer, per `[[2026-07-12-justificante-reframing-audit]]`.
- No live AEAT probe is authorized by this ADR. Whether the register's combobox option list is
  genuinely NIF-scoped (reflecting only pairs this taxpayer actually filed) versus a static
  universal catalogue is **unverified** — the same unverified-live-behaviour posture the sibling
  pagination reference records for the register's pager. Confirming it needs an authenticated
  live probe against an account with real filing history, under explicit operator authorisation;
  nobody has given that authorisation and it must not be attempted opportunistically. Until
  verified, the discovery step's output is reported as "AEAT's offered option set," never as
  "this NIF's confirmed filing history" — a zero-row result for an offered pair is a genuine
  negative, but an *absent* option cannot yet be positively distinguished from "the combobox
  never lists ejercicios the taxpayer didn't file" versus "the combobox lists every ejercicio
  regardless."
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

The following rows are opened as the concrete follow-on work this ADR authorises. They are not
yet a vault Plan — plan authoring is the next pipeline phase and requires this ADR's acceptance
first — but each is a discrete, scoped unit ready to plan directly from this list:

1. **`discover_filed_declaration_availability`** (new, `adapters/outbound/aeat/sede/_declarations.py`
   or a sibling module): opens the authenticated register page once, reads the modelo combobox's
   full `.z-comboitem-text` option set, and for each modelo option reads the ejercicio combobox's
   full option set, returning a typed `{modelo: tuple[ejercicio, ...]}` availability map. Read-only,
   no persistence, not a `PROFILE_BOUND_WRITE_VERB_PATHS` entry.
2. **`aeat app live filed discover`** (new CLI verb, `filed` group): thin wrapper over (1),
   emits the availability map as the envelope result plus the live-scope caveat above as a
   `Notice`.
3. **`aeat app live filed pull-all`** (new CLI verb, `filed` group): sequences (1) →
   `capture_filed_data_bulk` over the discovered grid → `capture_iva_compensation_wallet` /
   `reconcile_iva_compensation_wallet` → the existing notificaciones pull → one
   `FiledHistoryOnboardingResult` envelope carrying per-pair outcomes, the re-capture divergence
   diff as `WARNING` `Notice`s, and the sibling pagination ADR's per-pair completeness signal once
   that decision lands (interim: raw `row_count`, no completeness assertion). Enrolled in
   `PROFILE_BOUND_WRITE_VERB_PATHS` as `app live filed pull-all`.
4. **Re-capture divergence diff** (new, orchestration layer only, invoked from (3)): compares each
   freshly captured `FiledDeclaracionObservation`'s casilla values against the prior stamped
   observation for the same key; on any changed value, emits a `WARNING` `Notice` naming the
   modelo, period and changed casilla ids, never a silent overwrite.
5. **Overview no-history `Notice`**: when a workable (non-`SETUP_INCOMPLETE`) profile has zero
   observations carrying an official `ObservationSourceKind`, the overview surfaces an `INFO`
   `Notice` naming `aeat app live filed pull-all` as the next action.
6. **Sweep**: `PROFILE_BOUND_WRITE_VERB_PATHS`, error-registry suggestions, `next_action`
   builders, `operator_surface/_help.py`, envelope `command=` identifiers, agent-harness docs,
   and all four locale catalogues, for every string and identifier the new verbs introduce.

No new `ObservationSourceKind`, no new capture schema, no new IVA reconciliation mechanism, no
generic importer.

## Rationale

Every capability this feature needs already exists and is canonical; the only real gap is that
nothing tells the sweep what AEAT actually holds, and nothing sequences the existing primitives
into one operator-facing pull. Discovery closes the honesty gap directly: a coverage report
measured against AEAT's own declared option set is a real external denominator, not a restatement
of the caller's guess. Keeping the onboarding verb standalone rather than wizard-embedded respects
the existing SETUP_INCOMPLETE gate and keeps a live-AEAT round trip out of the guided setup flow.
Reusing the existing official `ObservationSourceKind` and the existing capture/reconciliation
primitives keeps this a sequencing decision, not a new subsystem, consistent with
`aeat-calculation-aggregation`'s one-canonical-mechanism-per-type mandate.

## Consequences

- A new profile gains a single, re-runnable, standalone entry point to backfill its AEAT history,
  reported against an AEAT-sourced denominator rather than a silent local guess.
- The discovery step's completeness claim is explicitly bounded: it reports AEAT's *offered*
  option set, not a verified confirmation that the set is NIF-scoped, until an authorised live
  probe settles that question — carried forward as an open item, not asserted away.
- A `pull-all` sweep composing discovery × bulk capture × IVA reconciliation × notificaciones is
  slower and more failure-surface-prone than any single existing verb; partial failure is
  expected and reported per-pair, never silently swallowed.
- The re-capture divergence diff adds a small, permanent maintenance surface at the orchestration
  layer, justified by closing a real silent-under-declaration path a taxpayer with a corrected
  historical filing would otherwise hit invisibly.
- Full completeness (both axes: pair-set AND per-page) is not achieved until the sibling
  pagination ADR's decision also ships; this ADR's coverage report must not claim more than it
  currently can prove.
