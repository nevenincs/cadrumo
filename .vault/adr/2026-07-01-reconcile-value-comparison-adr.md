---
tags:
  - '#adr'
  - '#reconcile-value-comparison'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-07-01-reconcile-value-comparison-research]]"
---

# `reconcile-value-comparison` adr: `reconcile the filed numbers, not just the receipt identity` | (**status:** `accepted`)

## Problem Statement

`aeat app modelo reconcile` is the surface an autonomous LLM tax-advisor uses to
close the filing loop: pull the AEAT justificante (or read a local one) and confirm
the filing matches what it computed. The research established that the compare is
**identity-only** — `_reconcile_parsed_justificante`
(`src/cadrumo/application/modelo/_reconcile.py`) diffs four header fields (`modelo`,
`ejercicio`, `period`, `tax_id`) and returns `MATCHES` / `MISMATCHES`, but never
loads the calculation revision and never reconciles the receipt totals the parser
already extracts. `verdict=matches` therefore means "this is a receipt for the right
modelo/period/filer", **not** "the filed amount equals my computed result." An agent
that trusts reconcile for closing-the-loop assurance gets a **false green**, and a
filed-amount divergence (especially filed < computed) is structurally invisible.

This ADR decides how deep the compare goes, how divergences are modelled and
persisted, and resolves four adjacent defects the sweep surfaced (dead
`EVIDENCE_INVALID` verdict, lossy history, the pull/file envelope command-id bug,
and the conditional-skip weakening of the header check). It does not author an
implementation plan.

## Considerations

- **The canonical total→casilla spine already exists.**
  `VerificationExpectationDefinition.reconciliation_total_casilla_ids` is a
  registry-declared, build-validated `Mapping[Literal["ingresar","devolver"],
  CasillaId]` (`_schema.py`) mapping each receipt total kind to the revision's
  canonical **result** casilla. `calculation_result_summary`
  (`src/cadrumo/application/modelo/_result_summary.py`) already consumes it to render
  `result_ingresar` / `result_devolver` rows from `revision.casilla_values`. The
  reconciler must reuse this map so the value it compares is the *same* canonical
  result the summary and export surfaces render — satisfying
  `one-aggregation-path-pull-equals-calculate`, not a re-derivation.
- **The map is sparse (8 revisions today).** M303, M100, M130, M200 — the modelos an
  agent most needs to close the loop on — do not declare it. So the reconciler's
  behaviour when the map is absent is the load-bearing safety decision, not an edge
  case: absent must never mean "false green".
- **The receipt exposes totals only.** Casilla-by-casilla reconciliation of the
  *receipt* is not achievable without the deferred declaration parser; the achievable
  depth for the receipt reconcile is **totals**. A parallel casilla-level filed-vs-
  engine surface already exists at the *verify* gate
  (`2026-07-01-verification-reconcile-when-present-adr`), against declaration values,
  not the receipt — complementary, not a substitute.
- **A `matches` verdict must remain honest about depth.** An agent reads the verdict
  as an assurance level; it must be able to tell "identity matched **and** totals
  reconciled" from "identity matched, totals **not** checked".

## Considered options

**Decision 1 — comparison depth.**
- **A. Keep identity-only (status quo).** Rejected: the false green is the whole
  defect.
- **B. Totals reconciliation via `reconciliation_total_casilla_ids` against the
  persisted revision (chosen).** Compare the receipt `total_a_ingresar` /
  `total_a_devolver` against the canonical result casilla value. Achievable with the
  receipt parser as-is; reuses the proven canonical spine.
- **C. Casilla-by-casilla receipt reconciliation now.** Rejected for this pass: the
  receipt does not carry casilla values; requires the deferred declaration parser.
  Sequenced as a follow-on, not blocked.

**Decision 1b — behaviour when the revision declares no total map (sparse coverage).**
- **A. Emit `matches` on identity alone.** Rejected: exactly the false green, now
  disguised as "value-reconciled".
- **B. A distinct "totals not reconciled" signal (chosen).** When the revision
  declares no `reconciliation_total_casilla_ids`, or no persisted revision exists,
  reconcile still runs identity but attaches a non-blocking advisory `Notice`
  (`totals_not_reconciled`, carrying the reason) and the verdict does **not** claim a
  total was checked. Enrolling the map for the missing revisions is a bounded
  registry follow-on tracked against this feature.

**Decision 2 — divergence model + non-lossy history.**
- **A. Keep flat `field_name`/`kind` diffs + count-only history.** Rejected: history
  cannot say *which* field diverged (`no-silent-under-declaration` at the audit
  layer).
- **B. Typed `kind` taxonomy + full diff persistence (chosen).** Introduce a closed
  `ModeloReconciliationDiffKind` (`header_field`, `total`; a `casilla` member is
  reserved for the follow-on) so each divergence is a typed finding; a `total`
  divergence carries the result casilla's `legal_refs` / `source_refs`
  (`aeat-calculation-grounding`). Persist the structured diffs (kind, field, both
  values) in the `MODELO_RECONCILED` payload and read them back in
  `list_modelo_reconciliations`, replacing the count-only string. `diff_count` stays
  a derived convenience.

**Decision 3 — the dead `EVIDENCE_INVALID` verdict.**
- **A. Remove the member (chosen at implementation).** The parse-failure outcome is
  already a first-class, agent-observable *typed refusal*
  (`ReconciliationEvidenceInvalidError` → error code
  `REFUSED_RECONCILIATION_EVIDENCE_INVALID`) raised before any report is built, and
  that refusal carries the documented "is this the right document?" instructive
  guidance (locked by `test_modelo_reconcile_malformed_evidence_refusal_is_clean_and_instructive`).
  The verdict member was never produced and never read (no production consumer, no
  test), so it was a true shell (`aeat-source-hygiene` / no-shells). Removed; no
  consumer reconciliation needed (`list_modelo_reconciliations` only ever reads
  `matches` / `mismatches`).
- **B. Wire it (originally proposed, rejected at implementation).** Returning a
  `verdict=evidence_invalid` *report* on the `file` path would have **regressed** the
  deliberate instructive-refusal contract — a success envelope with an "invalid"
  verdict loses the typed error code and the "wrong document?" guidance the refusal
  surfaces — for no gain over the existing typed error an agent already branches on.
  The proposal was reversed once the existing refusal tests made the regression
  concrete.

**Decision 4 — envelope command-id.**
- **Chosen:** `pull` emits `command="modelo.reconcile.pull"` and `file` emits
  `command="modelo.reconcile.file"` — their registered leaf schemas
  (`_payloads_modelo_reconcile.py`). No new schema; only the emit string is
  corrected. The structural leaf-schema gate does not assert the runtime emit string,
  so this is flagged as a candidate **behavioural** conformance gate for the
  manifest/conformance brief — not scoped or built here beyond fixing reconcile.

**Decision 5 — conditional-skip hardening.**
- **Chosen:** a receipt missing `ejercicio`, or an active profile missing `tax_id`,
  no longer silently drops the field. Reconcile attaches a non-blocking advisory
  `Notice` (`identity_anchor_unverified`, naming the missing anchor) and does not
  count the skipped field as matched. The verdict stays `matches` only when every
  *available* anchor matched **and** the skips are disclosed as advisories — never a
  silent pass on a missing identity anchor.

## Constraints

- **Local-only reconcile invariant survives.** `modelo_reconcile` must stay
  local-only (never `require_live_read`); the value read is against the
  already-persisted `CalculationRevision`, not a fresh calculation. `pull` keeps its
  live boundary in the `application/live` capture service, unchanged.
- **Canonical value, law-determined revision.** The compared value MUST be
  `revision.casilla_values[...]` from the persisted revision resolved by the
  law-determined resolver (`revision-resolution-is-law-determined`); the `--revision`
  arg may only assert-equal the resolution, never inject it.
- **Provenance carried.** A `total` divergence carries the result casilla's
  `legal_refs` / `source_refs` per `aeat-calculation-grounding`.
- **Diagnostics via the Notice channel only** (`cli-notices-are-the-only-diagnostic-
  channel`): `totals_not_reconciled`, `identity_anchor_unverified`, and the parse
  reason are typed `Notice`s on the shared envelope spine, not bespoke result fields.
- **Decimal comparison must be tolerance-aware and sign-correct.** The receipt prints
  a single non-negative magnitude under an ingresar/devolver heading; the result
  casilla value carries its own sign convention. The compare normalises both to the
  `(kind, magnitude)` the map already encodes and compares at the registry
  `tolerance` the verification expectation declares — never a raw `==` on scaled
  Decimals.
- **Parent-feature stability.** All consumed surfaces are shipped and exercised:
  `reconciliation_total_casilla_ids` (+ its build validators),
  `calculation_result_summary`, the persisted `CalculationRevision` read path, the
  justificante parser totals, and the `Notice` envelope spine. No frontier work.
- **Dependency (not owned here):** the custody evidence-bytes gap
  (`bucket-custody-completeness`) — a restored bundle without PDF bytes cannot be
  re-reconciled without a fresh pull. Recorded, not fixed.

## Implementation

The reconcile service gains a value-reconciliation stage layered onto the existing
header compare. After the four identity diffs, `_reconcile_parsed_justificante`
loads the persisted `CalculationRevision` for the work unit (the same read
`calculation_result_summary` / `_load_revision_for_export` use), resolves the
revision snapshot (law-determined), and reads
`reconciliation_total_casilla_ids` from its verification expectations. For each
declared total kind present on the receipt, it compares the receipt magnitude
against `revision.casilla_values[casilla_id]` at the declared tolerance and, on
disagreement, appends a typed `total` `ModeloReconciliationDiff` carrying the result
casilla's grounding. When the map is undeclared or no revision is persisted, it
attaches the `totals_not_reconciled` advisory `Notice` and leaves the verdict scoped
to identity. The identity skips (`ejercicio`, `tax_id`) become disclosed advisories
rather than silent drops.

The divergence model becomes typed: a closed `ModeloReconciliationDiffKind`
(`header_field`, `total`, reserved `casilla`), grounding fields on the `total` diff,
and the `MODELO_RECONCILED` payload persists the full structured diff list so
`list_modelo_reconciliations` and `reconcile history` report *which* fields diverged,
not just a count. The dead `EVIDENCE_INVALID` verdict member is removed (the
parse-failure outcome stays the existing typed refusal, Decision 3.A). The two CLI
verbs emit their registered `.pull` / `.file` command ids. Divergences and advisories
ride the typed `Notice` channel on the envelope.

Verification (implemented in this pass): a behaviour test proving a filed-amount
divergence is **caught and represented as a typed `total` diff** carrying the
expectation's grounding (not a count); a tolerance test (a one-cent gap within the
declared `0.01` tolerance stays clean); a test that an undeclared-map revision (M130)
and a no-persisted-revision case each yield the `totals_not_reconciled` advisory and
no false green; and a history test proving the persisted structured diffs replay
*which* total diverged (`test_reconcile_value_comparison.py`). The existing
malformed-evidence refusal tests continue to pin the parse-failure surface.

## Rationale

Totals-via-`reconciliation_total_casilla_ids` is chosen because the canonical spine
already exists and is already consumed by `calculation_result_summary` (research F2):
reusing it makes reconcile compare the *same* value the rest of the app calls the
filing's result, so pull and calculate cannot disagree, and no new authority is
invented. The receipt's structural limit to totals (research F4) makes casilla-level
receipt reconciliation impossible without the deferred declaration parser, so
sequencing it as a follow-on is honest rather than a shortcut. The sparse-coverage
advisory (Decision 1b) is the direct application of `no-silent-under-declaration`:
the only way to add value reconciliation without lying on the 8-vs-many revisions
that lack the map is to make "not reconciled" a *visible* state, never a silent
`matches`. Removing the dead `EVIDENCE_INVALID` shell (Decision 3.A) and de-lossing
history remove one shell and one lossy trace; the command-id fix removes an envelope
ambiguity that directly defeats the agent's pull-vs-file discrimination. The verdict
effect throughout is advisory — reconcile never files or mutates AEAT
(`aeat-safety-legal-gates`).

## Consequences

- **Gains.** An agent closing the loop now learns whether the filed amount equals its
  computed result, with provenance on divergences; `reconcile history` becomes
  auditable (which field, not how many); pull vs file is discriminable from the
  envelope; the verdict enum is fully live.
- **Honestly framed difficulty.** Value reconciliation is real only where
  `reconciliation_total_casilla_ids` is declared (8 revisions). Until the map is
  enrolled for M303 / M100 / M130 / M200, those reconciles surface
  `totals_not_reconciled` — correct but weaker than an operator might hope. Enrolling
  the map is a bounded, grounded registry follow-on (each entry is the revision's
  existing result casilla), tracked against this feature.
- **A real divergence may now flip a previously-green reconcile.** If the engine
  model for a mapped modelo diverges from AEAT's computed total on a genuine receipt,
  reconcile surfaces it — the intended signal (an engine-grounding follow-up), not a
  regression to suppress.
- **Pathways opened.** The reserved `casilla` diff kind and the declaration-parser
  dependency line up the eventual per-casilla receipt/declaration reconcile; the
  command-id fix seeds the behavioural-conformance gate brief.
- **Pitfalls to avoid in the plan.** Do not give `modelo_reconcile` a live branch; do
  not re-derive the result total (read the persisted revision value); do not compare
  raw Decimals without the declared tolerance and sign normalisation; do not let an
  undeclared-map revision emit `matches` without the advisory.
