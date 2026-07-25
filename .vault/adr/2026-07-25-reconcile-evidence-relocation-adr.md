---
tags:
  - '#adr'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-research]]"
  - "[[2026-07-01-reconcile-value-comparison-adr]]"
  - "[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]"
---

# `reconcile-evidence-relocation` adr: `where reconcile diff detail persists` | (**status:** `proposed`)

## Problem Statement

A Modelo 100 declaración reconcile that finds divergences cannot persist its own
result. The per-divergence detail is serialised as one JSON string into a single
`MODELO_RECONCILED` bucket-event payload value, and that value is capped at 500
characters. The write raises a pydantic `ValidationError` before anything is saved,
so the operator gets an unhandled validation error rather than a reconciliation.

The severity was previously recorded as "roughly 400 characters per diff, so two
overflow". Measured against all 11,374 grounded Modelo 100 casilla entries in the
registry authoring tree, it is worse: median encoded size 303 characters, p90 458,
max 632. Two divergences are unpersistable for 99.6% of casillas, and for 175
casillas (1.5%) the very first divergence overflows on its own. The cap is
effectively a one-divergence ceiling for Modelo 100.

This is production-reachable, not fixture-only. Modelo 100 is enrolled in
casilla-level filed-declaration reconciliation, and the declaración path compares the
whole computed casilla set, so a genuinely divergent filing produces many diffs at
once rather than one or two.

The detail is not decorative. It is what makes reconciliation history auditable:
`list_modelo_reconciliations` decodes it and returns grounded diffs, and a test
asserts that `legal_refs` survives the persist-and-read-back round trip. Counting
only was the option explicitly rejected as `no-silent-under-declaration` at the audit
layer when this surface was designed.

## Considerations

- The 500-character cap belongs to `BucketEvent`, a substrate every event in the
  application shares. No decision record ratifies the figure, and it is an inline
  literal in the domain model rather than a central-config constant, but it is not
  reconcile's to renegotiate.
- The overflow is an unforeseen consequence of a decision, not an accepted trade-off.
  `2026-07-01-reconcile-value-comparison-adr` Decision 2.B chose to persist structured
  diffs in the payload and nowhere reasons about a size ceiling. That decision also
  reserved the `casilla` diff member for a follow-on; the follow-on landed, and
  casilla-level reconciliation is exactly what multiplied the volume past the cap.
- "There is no parallel reconciliation store" is a docstring assertion, not a ratified
  invariant. A search of the decision corpus finds no record establishing it — the only
  hit is a generated search index. It narrates what Decision 2.B produced, phrased as
  though it were a principle. Relocation therefore does not overturn a documented
  invariant; it supersedes one decision and corrects a docstring.
- The opposite precedent already ships. IVA-wallet reconciliation decisions persist
  through profile secure storage, with two dedicated namespaces at `AUDIT` sensitivity,
  `PROFILE_LOCAL` scope and `STRUCTURED_CUSTODY` disposition. A dedicated,
  N-per-target, encrypted reconciliation store is an established in-house shape.
- Grounding must survive whatever store is chosen. `aeat-calculation-grounding`
  requires `legal_refs` and `source_refs` to reach the operator-facing surface, and the
  round-trip test binds only to the public read API, so any storage site satisfies it
  provided the API still returns populated grounded diffs.
- Today the persisted detail is read and then discarded at the `reconcile history` CLI
  surface, which projects only `diff_count`. The grounding an operator actually sees
  comes from the fresh in-memory report. So relocation restores a capability that is
  currently persisted-but-unsurfaced; a decision to surface it is separable and is not
  taken here.
- The compatibility regime is `PRE_RELEASE`, so a new persisted format enrols at birth
  with no upgrader or durability-floor obligation, and already-persisted overflowing
  values are deleted rather than migrated.
- An independent latent defect sits in the same payload and is not fixed by relocation:
  the reconcile command validates `source_ref` to 512 characters while the payload value
  it is written into caps at 500, so a 501-512 character reference passes the command
  boundary and then overflows.

## Considered options

- **(a) Revert to count-only history and keep the status quo.** Rejected. The Modelo 100
  defect is real and operator-facing, and count-only is the option this surface's own
  governing ADR rejected as `no-silent-under-declaration` at the audit layer.
- **(b) Drop `legal_refs` / `source_refs` from the persisted copy and re-derive the
  grounding at read time.** Rejected on two independent grounds. Capacity: measured, a
  bare realistic diff is 165 characters, so three fit and four overflow — even a
  physically minimal diff overflows at four. The ceiling rises from one-or-two to three,
  still far below a real Modelo 100 divergence set, so the cliff moves rather than
  disappears; the assumption that five would fit is wrong. Faithfulness, which is
  decisive: re-derivation resolves the snapshot from modelo, filing year and period,
  never from a stored revision id, per `revision-resolution-is-law-determined`. A
  re-grounding sweep that changes a casilla's `legal_refs` without moving the revision id
  would silently change the legal basis displayed for a historical reconciliation, and
  such sweeps are routine. If the correction does move the revision id, the read raises a
  revision-divergence error and the history becomes unreadable. Historical evidence must
  stay self-describing.
- **(c) Bundle reconcile detail into the encrypted calculation-revision envelope.** This
  was the previously favoured option. Rejected on structural grounds. Lifecycle: the
  ledger bundle is computed and frozen onto the revision at verify, whereas a reconcile
  runs after filing and only reads the revision, so this would require writing into an
  already-frozen content-addressed record. Cardinality: the bundle is one per revision
  written once, while reconciliation is explicitly repeatable and has a `history` verb.
  Existence: reconcile runs with no revision at all, emitting a `no_persisted_revision`
  advisory and still producing a report and an event, and identity-header reconcile needs
  no revision — those runs would have nothing to attach to. Conceptually a ledger
  evidence row explains why a casilla holds its value; a reconcile diff is a comparison
  verdict against what AEAT printed. The analogy to
  `ledger-derived-revisions-bundle-evidence` is superficial.
- **(d) Raise the 500-character cap.** Rejected. The cap is a property of a substrate
  shared by every bucket event; raising it to accommodate one unbounded producer trades a
  local refusal for unbounded growth in the event log generally, and the real payload is
  not bounded by any larger constant either.
- **(e) Give reconcile records a dedicated encrypted, profile-scoped store, and reduce
  the bucket event to verdict plus count.** Recommended. Follows the shipped IVA-wallet
  reconciliation precedent exactly: a new secure-object namespace at `AUDIT` sensitivity,
  `PROFILE_LOCAL` scope, `STRUCTURED_CUSTODY` disposition, keyed to admit N
  reconciliations per work unit. Grounding is stored, not re-derived, so history stays
  faithful. Nothing is bounded by a 500-character string. `list_modelo_reconciliations`
  keeps its return type, so the round-trip test and the CLI schema are undisturbed.
- **(f) Keep the payload but reduce it to bounded metadata — count, digest, first and
  last field.** Rejected here, though it is the in-house precedent: the ledger-export
  overflow of the same class was fixed this way. That worked because the row identities
  were recoverable from the transaction catalogue, so the payload only had to be a
  pointer. Reconcile diff detail is the only copy, so bounded metadata returns history to
  the count-only state option (a) is rejected for. Bounded metadata is the right shape for
  the event *after* the detail has a durable home, which is what (e) does.

## Constraints

- Grounding must survive the boundary. `aeat-calculation-grounding` requires
  `legal_refs` and `source_refs` on the operator-facing surface, and the existing
  round-trip test asserts it across a persist-and-read-back cycle.
- Reconciliation must remain local-only. The governing justificante ADR forbids
  `modelo_reconcile` contacting AEAT; a new store must not acquire a live branch.
- Any new persisted store is encrypted, profile-scoped secure storage. Reconcile detail
  carries casilla values from a taxpayer's filing, so
  `sensitive-financial-data-secure-storage-only` applies.
- A new persisted format owes a strict save-load-equality roundtrip with every
  defaultable field set non-default, plus an anti-tautology proof that mutating the
  stored payload surfaces a refusal, per `aeat-roundtrip-discipline`.
- The write must be atomic. The reconciliation record and the slimmed event must land
  together, or a crash between them desynchronises the event log from the detail store.
- Relocation supersedes Decision 2 / 2.B of `2026-07-01-reconcile-value-comparison-adr`
  and must re-affirm its provenance-carried constraint at the new site. The remaining
  decisions of that ADR are untouched.

## Implementation

Not decided; this record exists to obtain the decision. If (e) is chosen, the shape is:

A new `MODELO_RECONCILIATION_RECORDS` secure-object namespace at `AUDIT` sensitivity,
`PROFILE_LOCAL` scope, `STRUCTURED_CUSTODY` disposition, its object key admitting N
reconciliations per work unit rather than overwriting. A new strict-frozen
reconciliation record model carrying verdict, source kind, source reference, work unit
id, the grounded diffs, advisories, instant and actor; the existing diff and advisory
models are already strict-frozen and are reused unchanged. The reconcile finalisation
writes the record and the slimmed event together through the existing co-emit write
discipline. `list_modelo_reconciliations` reads the new store while keeping its return
type, so the CLI payload and the round-trip test are unchanged. The event keeps verdict
and count; `diffs_detail` is deleted rather than migrated, per `no-legacy-compatibility`
under the `PRE_RELEASE` regime. The `ModeloReconciliationHistoryEntry` docstring is
rewritten, since its "no parallel reconciliation store" sentence becomes false.

The riskiest part is write atomicity, and the second risk is key design: N
reconciliations per work unit must each persist distinctly rather than overwrite.

Two items are separable and should not gate this decision. The `source_ref` 512-against-500
inconsistency is an independent defect in the same payload. Whether `reconcile history`
should surface the grounded diffs it currently discards is an operator-experience choice
that relocation enables but does not require.

## Rationale

Deferred to the operator. The recommendation is (e).

Four constraints have to hold simultaneously: the cap is legitimate and shared, the
Modelo 100 defect is real, the detail is genuinely read, and grounding must survive the
boundary. (a) and (f) fail the second and give up audit fidelity. (b) fails the first
by only moving the cliff to three diffs, and fails historical faithfulness outright —
it makes a past reconciliation's legal basis a live projection of current law. (c) was
the previously favoured option and fails on lifecycle, cardinality and existence: it
would require writing into a deliberately frozen record, has no room for repeated
reconciliations, and cannot store the runs that have no revision at all. (d) trades a
bounded local refusal for unbounded global growth.

(e) is the only option where all four hold, and it is less novel than it first appears:
the codebase already persists reconciliation decisions this way for the IVA wallet, so
this is enrolment under an existing pattern rather than a new architecture. It is
materially larger than the one-commit fix originally scoped — a new namespace, a new
persisted model, an atomic write path and its roundtrip obligations — which is why it is
an ADR rather than a patch.

The honest counter-argument for (f) deserves recording: if reconciliation history is
judged genuinely low-value, bounded metadata in the payload is far cheaper and matches
the precedent already set for ledger export. That is a product judgement about whether
auditable reconciliation history is worth a persisted format, and it is the judgement
this record asks for.

## Consequences

If (e) is accepted, Modelo 100 reconciliation becomes persistable at any divergence
count, reconciliation history becomes durably grounded, and the event log keeps a slim
verdict trace. The cost is a new persisted format with its roundtrip and atomicity
obligations, and one superseded decision.

If (f) is accepted instead, the defect closes cheaply and reconciliation history
degrades to a verdict and a count, reversing the non-lossy-history decision on purpose
rather than by accident.

Either way the `source_ref` 512-against-500 inconsistency remains open, and the
docstring asserting that no parallel reconciliation store exists must be corrected if
any store is added.
