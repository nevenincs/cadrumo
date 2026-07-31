---
tags:
  - '#adr'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:fc92a7762acad47e502bad42bab1b1eba8432d28543887e8b52d002096986c8c'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-research]]"
  - "[[2026-07-01-reconcile-value-comparison-adr]]"
  - "[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]"
---

# `reconcile-evidence-relocation` adr: `where reconcile diff detail persists` | (**status:** `accepted`)

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
- The shape is systemic. Joining a variable-length value into one capped payload slot
  has now produced four instances: the ledger-export overflow (fixed with bounded
  metadata), the `ledger reset` overflow that bricked reset at eight rows (fixed at HEAD,
  the event now carries a count), the reconcile detail, and a still-live pair in the
  `LEDGER_TRANSACTION_REMOVED` event that joins `purchase_invoice_evidence_ids` and
  `attachment_ids`. Attachment ids are hex-64, so seven fit and the eighth overflows at
  519 characters — removing one transaction with eight or more attachments cannot
  construct its own removal event. That payload already carries a `cascade_count`, so the
  remedy sits beside the defect.
- Reconcile is nonetheless distinguishable from the other three by what the value IS. The
  ledger cases join identifiers recoverable from their own catalogues, so bounded metadata
  loses nothing. The reconcile detail is the only copy, which is why the same remedy is
  lossy here and why this needs a decision rather than the established patch.
- Two narrower inconsistencies are not fixed by relocation: the reconcile command
  validates `source_ref` to 512 characters against the 500-character payload slot it is
  written into, and the live joined-id pair above. Both are independent of this decision.
- No record ratifies the cap, though one designs to it.
  `2026-05-14-ledger-transaction-lifecycle-adr` Decision 4 specifies a `--reason` of "up
  to 500 chars" recorded into the event payload, treating the bound as a given. The figure
  itself is decided nowhere.

### Re-verified at HEAD `7058ef827f`: the four-instance shape has moved, and it moved toward (e)

Semantic search was unavailable for this ruling — the code index was truncated
while reporting `degraded_reasons: []`, so a miss proves nothing. Every statement
below rests on `rg`, on reading the sites, and on git history.

The record above lists four instances of the shape and, under Consequences, three
items left open. **Two of those three closed between the record being written and
this ruling.** The facts as recorded were true when written; the conclusion drawn
from them is not, and must be recomputed.

- **The `LEDGER_TRANSACTION_REMOVED` joined-id pair is fixed**, by
  `5d93814876 fix(ledger): a row with eight attachments could not record its own
  removal`. At `application/ledger/_actions_lifecycle.py:764-778` the payload now
  carries `purchase_invoice_evidence_count`, `attachment_count` and
  `cascade_count` — counts, never the joins. The in-code comment reproduces this
  research's own 519-character arithmetic, and records the reason nothing is lost:
  each cascaded id is already the `object_id` of its own event in the same batch.
  Both counts are kept rather than only their sum so the cascade stays
  decomposable by kind.
- **The `source_ref` 512-against-500 inconsistency is fixed**, by
  `befb5f09fa fix(modelo): an over-long evidence path made a reconciliation
  unrecordable`, and the fix is broader than the item as recorded. It found a
  *second* producer this record missed: the file command's `source_path` is a bare
  `Path` with no bound at all, `str()`-ed into the same slot, so any sufficiently
  deep directory overflowed — and that is the reachable producer, where the 512
  field only had a twelve-character window. It bounds at the shared tail
  (`_bounded_payload_reference`), keeps the reference's tail rather than its head
  since the filename identifies the artifact, and prefixes an explicit elision
  marker so a shortened reference is self-evidently shortened. The field was also
  tightened to 500 rather than removed, deliberately: an app-generated handle past
  the cap is an internal defect and belongs refused where the error names the
  field, while an operator filesystem path has no such contract and is shortened.

So at HEAD the tally is three closed, one live. The live one is `diffs_detail`
(`application/modelo/_reconcile.py:736`, decoded back at `:1258`), unchanged.

**This strengthens (e) rather than weakening it, and the direction matters.** A
reader might take "the shape is systemic" as an argument for a substrate-level
remedy that would cover reconcile too. The opposite is now demonstrated: every
instance that bounded metadata *could* close has been closed by bounded metadata,
each in its own commit, and the residue is precisely the one instance where that
remedy is lossy — because the reconcile detail is the only copy, exactly as this
record argues. The systemic pattern and the reconcile exception are no longer
competing readings; the pattern has resolved itself around the exception.

What remains genuinely open is the third item: a standing guard against joining a
variable-length value into a capped payload slot. Four instances, three closed by
hand, each rediscovered independently by a different pass. That is now the whole
of the systemic residue, and it is carried as a named step rather than left in a
Consequences note.

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

Ruled `accepted` on option (e): a dedicated encrypted, profile-scoped store for
reconciliation records, with the bucket event reduced to verdict plus count. The
work is carried by `2026-07-25-reconcile-evidence-relocation-plan`.

**The store.** A new `MODELO_RECONCILIATION_RECORDS` secure-object namespace at
`AUDIT` sensitivity, `PROFILE_LOCAL` scope, `STRUCTURED_CUSTODY` disposition —
enrolling under the shipped IVA-wallet reconciliation precedent
(`_namespace_registry.py:445-464`) rather than inventing a shape. Under
`compatibility-lifecycle-checkpoint` a new persisted format enrols its floor, its
version and its (empty) upgrader registry **at birth**; the bucket-manifest gap
recorded in the sibling code-dedup ruling is what skipping that looks like later.
Per the ruling on that record, the reader compares its inner envelope version with
equality, not a ceiling.

**The key is the risk.** The object key MUST admit N reconciliations per work
unit rather than overwriting — reconciliation is explicitly repeatable and
`history` is a shipped verb, so a key that collapses runs silently destroys the
history this decision exists to preserve. It MUST also admit the runs that have no
revision at all: both `_reconcile_receipt_totals` and
`_reconcile_declaracion_casillas` emit a `no_persisted_revision` advisory and
still produce a report and an event, and identity-header reconcile needs no
revision. A key derived from a revision id cannot store those, which is one of the
three independent reasons option (c) was rejected.

**The record model.** A new strict-frozen model carrying verdict, source kind,
source reference, work unit id, the grounded diffs, advisories, instant and actor.
The existing diff and advisory models are already strict-frozen and are reused
unchanged. Grounding is **stored, not re-derived** — that is the decisive
objection to option (b) and it survives into the new site: a re-grounding sweep
that moves a casilla's `legal_refs` without moving the revision id would otherwise
silently rewrite the legal basis of a historical reconciliation, and such sweeps
are routine.

**Atomicity.** The reconciliation record and the slimmed event MUST land together
through the existing co-emit write discipline. A crash between them desynchronises
the event log from the detail store, which is the second of the two risks this
record names.

**The seams that must not move.** `list_modelo_reconciliations` keeps its return
type and reads the new store, so `ModeloReconciliationHistoryEntry`, the CLI
payload schema and
`test_history_persists_which_total_diverged_not_just_a_count` are all undisturbed
— that test binds only to the public API, never to the payload, so it is a real
gate on the relocation rather than a fixture to update. The event keeps verdict and
count; `diffs_detail` is **deleted, not migrated**, per `no-legacy-compatibility`
under `PRE_RELEASE`, and already-persisted overflowing values are dropped rather
than read.

**Roundtrip obligations.** Per `aeat-roundtrip-discipline` the new format owes a
strict save-load-equality roundtrip with every defaultable field set to a
non-default value, plus an anti-tautology proof that mutating the stored payload
surfaces a refusal. Use real adapters — real `EphemeralMasterKeyProvider`, real
SQLite — never a double.

**Two corrections to prose that becomes false.** The
`ModeloReconciliationHistoryEntry` docstring asserts that "there is no parallel
reconciliation store"; adding one makes it false and it MUST be rewritten in the
same change. This repo has a documented recurring pattern of prose asserting
guarantees that do not hold, and those assertions actively manufacture false audit
findings on later passes — leaving this one standing would seed exactly that.
Relocation also supersedes Decision 2 / 2.B of
`2026-07-01-reconcile-value-comparison-adr`, whose provenance-carried constraint
must be re-affirmed at the new site; that ADR's remaining decisions are untouched.

**Separable, and deliberately not gating this.** Whether `reconcile history`
should surface the grounded diffs it currently reads and discards is an
operator-experience choice that relocation enables and does not require. The
substrate guard against joining a variable-length value into a capped slot is the
remaining systemic item and is carried as its own step.

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

### Ruling: (e), and why the counter-argument for (f) does not carry

Ruled `accepted` on (e). The record above deferred to the operator; the decision
is taken here so the work stops being invisible, and the reasoning is recorded
rather than asserted.

The honest counter-argument for (f) is preserved above and deserves a direct
answer rather than a restatement of the recommendation. It runs: if reconciliation
history is judged genuinely low-value, bounded metadata is far cheaper and matches
the precedent already set for ledger export. Two things defeat it.

First, the precedent it invokes has now been fully spent, and spending it is what
isolated reconcile. Since this record was written the two remaining
bounded-metadata candidates were closed that way — the transaction-removal joins
and the `source_ref`/`source_path` pair, both detailed in Considerations. The
ledger precedent works because the joined identifiers stay recoverable from their
own catalogues, so the payload need only be a pointer; the removal fix says so
explicitly, noting each cascaded id is already an `object_id` in the same batch.
Reconcile diff detail has no second home. Invoking the precedent therefore no
longer imports its justification — it imports only its shape, applied where the
precondition fails.

Second, (f) is not a cheaper way to keep history; it is a reversal of Decision
2.A's rejection, which refused count-only as `no-silent-under-declaration` at the
audit layer. That reversal may be a legitimate product judgement, but it must be
made as one. Choosing (f) *because it is cheaper* would decide the product
question by implication — the failure mode this record was written to prevent.
Nothing in the corpus has since re-argued that audit-layer refusal, so the
standing decision holds.

The measurement settles the remaining doubt about severity. At a median encoded
diff of 303 characters, two divergences are unpersistable for 99.6% of Modelo 100
casillas and 175 casillas overflow on the first divergence alone — so this is not
a degraded history but an unhandled pydantic `ValidationError` raised before
anything is written, on a production-reachable path where the declaración
comparison produces many diffs at once. A verb that fails on the length of its own
result is a defect regardless of how the history question resolves.

One caveat is recorded honestly rather than argued away: (e) is materially larger
than the one-commit fix originally scoped, and its two named risks — write
atomicity and the N-per-work-unit key — are both correctness risks in encrypted
storage, not merely effort. That is why it carries roundtrip and anti-tautology
obligations in the Implementation above rather than a test-later note.

## Consequences

If (e) is accepted, Modelo 100 reconciliation becomes persistable at any divergence
count, reconciliation history becomes durably grounded, and the event log keeps a slim
verdict trace. The cost is a new persisted format with its roundtrip and atomicity
obligations, and one superseded decision.

If (f) is accepted instead, the defect closes cheaply and reconciliation history
degrades to a verdict and a count, reversing the non-lossy-history decision on purpose
rather than by accident.

Either way three things remain open and are independent of this decision: the
`source_ref` 512-against-500 inconsistency, the live joined-id pair in the
transaction-removal event that breaks removal at eight attachments, and whether the
substrate deserves a standing guard against joining a variable-length value into a
capped payload slot — four instances in, that is a pattern rather than a coincidence.
The docstring asserting that no parallel reconciliation store exists must be corrected
if any store is added.

### What remains open, recomputed at HEAD `7058ef827f`

The three open items this record closes with were true when written. Two have
since been closed by peer commits and only one survives:

- **Closed** — the `source_ref` 512-against-500 inconsistency (`befb5f09fa`,
  which also found and bounded an unbounded second producer this record missed).
- **Closed** — the joined-id pair in the transaction-removal event that broke
  removal at eight attachments (`5d93814876`).
- **Open, and now the only systemic item** — whether the substrate deserves a
  standing guard against joining a variable-length value into a capped payload
  slot. Four instances have now been found and three closed by hand, each
  rediscovered independently. The cap is an inline literal in the domain model
  rather than a central-config constant and no record ratifies the figure, so a
  guard would also give it its first declared home. Carried as a named step on
  the plan.

The docstring asserting that no parallel reconciliation store exists becomes false
the moment the store lands and is corrected in the same change, not after.
