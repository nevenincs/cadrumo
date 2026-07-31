---
tags:
  - '#research'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:de740196f83ec6ce4a4ee98565057dbfbf9d88e147de72c7385b1766423be176'
related: []
---

# `reconcile-evidence-relocation` research: `the 500-char payload ceiling on reconcile diff detail`

Modelo reconciliation persists its per-divergence detail as one JSON string inside a
`MODELO_RECONCILED` bucket-event payload value. That value is capped at 500
characters. For Modelo 100 the cap is reached almost immediately, so a real
declaración reconcile that finds divergences cannot persist its own event and raises
before the write. The question is where that detail should live instead.

The measurements below were taken against the registry authoring tree at HEAD, not
estimated. They matter because the severity was previously recorded as "a per-diff
detail is ~400 chars, so two diffs overflow"; the real distribution is worse than
that, and the correction changes how the option space reads.

## Findings

### The cap is a per-value constraint on the shared bucket-event substrate

`_PayloadValue` is `Annotated[str, StringConstraints(strip_whitespace=True,
min_length=0, max_length=500)]` at `src/cadrumo/domain/buckets/_event.py:52-55`, applied
to each value of `BucketEvent.payload` at `src/cadrumo/domain/buckets/_event.py:313`.
The cap is per VALUE, not per payload. Exceeding it raises a plain pydantic
`ValidationError` at `BucketEvent(...)` construction — not the module's own
`BucketEventValidationError`, which fires only on a derived-id mismatch
(`src/cadrumo/domain/buckets/_event.py:327`). There is no error code and no
instructive refusal.

The `500` is an inline literal in the domain model rather than a central-config or
`core/` constant. No decision record ratifies the figure: a search of the whole
`.vault/` corpus found it discussed nowhere. It is a code-level contract of a
substrate shared by every bucket event, so it is a constraint to design around rather
than one reconcile can renegotiate for itself.

### The detail is one unbounded JSON array in a single payload value

`_finalise_reconciliation` builds the payload at
`src/cadrumo/application/modelo/_reconcile.py:714-721`, where `"diffs_detail":
_encode_diffs(diffs)`. `_encode_diffs`
(`src/cadrumo/application/modelo/_reconcile.py:1133-1139`) is
`json.dumps([diff.model_dump(mode="json") for diff in diffs], separators=(",", ":"))`
— every diff for the run concatenated into one value. There is no truncation, no
chunking across keys, and no `try`/`except` around the `BucketEvent(...)` construction
at `src/cadrumo/application/modelo/_reconcile.py:735-745`, so the overflow surfaces as
an unhandled validation error before `catalogue_repo.save(...)`.

`ModeloReconciliationDiff`
(`src/cadrumo/application/modelo/_reconcile.py:166-192`) carries seven fields, and
`model_dump` emits all seven regardless of defaults. A `casilla` or `total` diff
carries the reconciling casilla's or verification expectation's `legal_refs` /
`source_refs`; `header_field` diffs carry empty grounding.

### Measured: for 99.6% of Modelo 100 casillas, two divergences cannot be persisted

Method: parsed every casilla fragment under
`src/cadrumo/_data/registry/aeat/modelos/100/revisions` with `tomllib` (an explicit
Python walk, not a shell count), collected each entry's real `legal_refs` /
`source_refs`, rebuilt the production `model_dump(mode="json")` field set for a
`casilla_value_mismatch` diff, and encoded with the production
`separators=(",", ":")`. 11,374 grounded casilla entries were measured.

Per-diff encoded size: min 216, median 303, p90 458, max 632 characters.

| Divergences that fit under the cap | Casillas | Share |
| --- | --- | --- |
| 0 — a single divergence already overflows | 175 | 1.5% |
| 1 | 11,150 | 98.0% |
| 2 | 49 | 0.4% |

So the cap is effectively a one-divergence ceiling for Modelo 100: two divergences are
unpersistable for 99.6% of casillas, and for 175 casillas the very first divergence
exceeds the cap on its own. The earlier "~400 chars, two overflow" figure understated
it.

This is reachable in production, not only under a fixture. Modelo 100 is enrolled in
`_DECLARATION_CASILLA_RECONCILE_MODELOS`
(`src/cadrumo/application/modelo/_reconcile.py:66-68`), and
`_reconcile_declaracion_casillas`
(`src/cadrumo/application/modelo/_reconcile.py:986-1007`) compares the whole computed
casilla set, so a real divergent declaración produces many diffs at once rather than
one or two.

### The unbounded-value-in-a-capped-field shape is systemic, not unique to reconcile

`diffs_detail` is not the only field at risk, and the cap has now produced four
instances of one shape: a variable-length value joined into a single capped payload
slot.

Two are closed. The ledger-export overflow recorded in
`2026-05-14-cli-workflow-redesign-w61-p304-s1823-code-review-audit` was fixed with
bounded metadata. The `ledger reset` overflow recorded as EDGE-HIGH-1 in
`2026-06-18-aeat-user-docs-hardening-audit` — a joined `removed_transaction_ids`
string that bricked reset at eight or more rows — is also fixed at HEAD: the reset
event now carries `"removed_transaction_count": str(len(removed_ids))`
(`src/cadrumo/application/ledger/_actions_lifecycle.py:550-554`), and
`removed_transaction_ids` is a `tuple[str, ...]` on the report
(`src/cadrumo/application/ledger/_models.py:701`) rather than a joined payload value.

Two are live. Besides `diffs_detail`, the `LEDGER_TRANSACTION_REMOVED` event joins two
unbounded id lists into payload values at
`src/cadrumo/application/ledger/_actions_lifecycle.py:764-770`:
`"purchase_invoice_evidence_ids": ",".join(purchase_evidence_ids)` and
`"attachment_ids": ",".join(attachment_ids)`. `AttachmentId` is exactly hex-64
(`src/cadrumo/domain/attachments/_ids.py:18`), so seven attachment ids fit at 454
characters and the eighth overflows at 519; a purchase-invoice evidence id is a
16-hex-char digest (`src/cadrumo/application/ledger/_evidence.py:136-160`), so
twenty-nine fit and the thirtieth overflows at 509. Removing one transaction carrying
eight or more attachments therefore cannot construct its own removal event. The same
payload already carries `"cascade_count"`, so the bounded-metadata remedy is present
alongside the unbounded joins rather than instead of them.

A third, narrower inconsistency sits in the reconcile payload itself:
`ModeloReconciliationBytesCommand.source_ref` is `Field(min_length=1, max_length=512)`
at `src/cadrumo/application/modelo/_reconcile.py:247` and is written into the payload
as `"source_path"` (`src/cadrumo/application/modelo/_reconcile.py:717`), so a
501-512 character reference passes the command boundary and then overflows the cap.

None of these are fixed by relocating the diffs, and they are named here because they
bear on whether the right answer is a per-producer relocation or a substrate-level
guard against joining a variable-length value into a capped slot. The reconcile case is
distinguished from the other three by what the value IS: the ledger cases join
identifiers recoverable from their own catalogues, so bounded metadata loses nothing,
whereas the reconcile detail is the only copy.

### An ADR designs a field to the cap without ratifying it

`2026-05-14-ledger-transaction-lifecycle-adr` Decision 4 specifies a `--reason`
"free-text up to 500 chars) recorded into the event payload". So a prior decision
treats the 500-character bound as a given it designs within, which is the closest the
corpus comes to endorsing the figure. It does not decide or justify the cap, and no
record does; the `_PayloadValue` type is merely catalogued as an inventory row in
`2026-05-31-core-authority-types-v2-reference` (at a since-shifted line number). The
cap therefore remains an un-ratified code-level contract that prior decisions design
around.

### The detail round-trips through the app API but no CLI surface renders it

`list_modelo_reconciliations`
(`src/cadrumo/application/modelo/_reconcile.py:1179-1226`) reads the bucket-event
catalogue and decodes `payload["diffs_detail"]` at
`src/cadrumo/application/modelo/_reconcile.py:1221`, populating
`ModeloReconciliationHistoryEntry.diffs` with grounding intact. It is exported from
`src/cadrumo/application/modelo/__init__.py:800`.

The `reconcile history` CLI verb
(`src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py:302-372`) calls it and then
projects onto `ModeloReconciliationHistoryRowPayload`
(`src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py:101-120`), which carries only
`diff_count` — no diffs, no grounding. So the persisted detail is read and discarded at
the history surface. The grounding an operator does see comes from the fresh in-memory
report on the `reconcile pull` / `reconcile file` verb
(`src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py:129-140`), which never touches
the persisted copy.

The round-trip is nonetheless defended by a test:
`test_history_persists_which_total_diverged_not_just_a_count`
(`src/cadrumo/application/modelo/tests/test_reconcile_value_comparison.py:246-262`)
asserts `diff_kind`, `field_name` and `"rd-439-2007:art-110" in
entry.diffs[0].legal_refs` after a read-back. It binds only to the public API, never to
the payload, so any storage site satisfies it provided `list_modelo_reconciliations`
still returns populated grounded diffs. That single-total case is ~240 characters and
does not itself exercise the overflow.

### The owning decision is Decision 2.B of the reconcile-value-comparison ADR

`2026-07-01-reconcile-value-comparison-adr` Decision 2 chose option B: "Persist the
structured diffs (kind, field, both values) in the `MODELO_RECONCILED` payload and read
them back in `list_modelo_reconciliations`, replacing the count-only string." Its
rejected option A was count-only history, refused as
`no-silent-under-declaration` at the audit layer. It also fixed the grounding
requirement: "a `total` divergence carries the result casilla's `legal_refs` /
`source_refs` (`aeat-calculation-grounding`)."

That ADR nowhere reasons about a payload-size ceiling, so the overflow is an unforeseen
consequence of 2.B rather than an accepted trade-off. Notably 2.B reserved the
`casilla` diff member for a follow-on; the casilla member has since landed, and it is
casilla-level reconciliation that multiplies the diff volume into the overflow.

### "There is no parallel reconciliation store" is a docstring assertion, never a decision

`ModeloReconciliationHistoryEntry`'s docstring
(`src/cadrumo/application/modelo/_reconcile.py:140-150`) states that
"`modelo_reconcile` persists no stored record" and "there is no parallel reconciliation
store". A search of the `.vault/` corpus for that phrasing returns no source document:
the only hit is `.vault/data/search-data/qdrant/.../storage.sqlite`, a generated search
index, not an authored record. The claim is therefore a narration of what Decision 2.B
happened to produce, phrased as though it were a principle. No decision record forbids a
dedicated reconciliation store.

The opposite precedent already ships. `2026-05-26-live-iva-remote-evidence-reconciliation-adr`
persists IVA-wallet reconciliation decisions — "authority source, local recurrence
value, remote evidence references, divergence status" — through profile secure storage
rather than a bucket event, and the namespaces exist:
`IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE` and
`IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE` at
`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:445-464`, both
`SensitivityClass.AUDIT`, `StorageNamespaceScope.PROFILE_LOCAL`,
`StorageCustodyDisposition.STRUCTURED_CUSTODY`. Sibling analogues include
`CALCULATION_OBSERVATIONS_NAMESPACE`
(`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:397`) and
`AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE`
(`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:779`).

### The calculation-revision envelope is a poor structural fit

Relocating into the encrypted revision envelope under
`ledger-derived-revisions-bundle-evidence` fails on three independent axes.

Lifecycle: the ledger bundle is computed and frozen onto the revision at VERIFY by
`_persist_verified_revision_evidence`
(`src/cadrumo/application/modelo/_verification_actions.py:897-944`), which stamps
`ledger_filing_evidence` together with `state=VERIFICADO_COMPLETO`. A reconcile runs
after filing and only READS the persisted revision
(`src/cadrumo/application/modelo/_reconcile.py:1078-1090`). Attaching reconcile records
would require writing into an already-frozen, content-addressed record.

Cardinality: `LedgerFilingEvidence`
(`src/cadrumo/domain/modelos/_ledger_filing_snapshot.py:216`) is one bundle per
revision, written once. Reconciliation is explicitly repeatable — the `history` verb
exists, and the entry's own docstring calls it "repeatable on demand". The envelope has
no slot for N dated verdicts per revision.

Existence: reconcile runs with no revision at all. Both
`_reconcile_receipt_totals` and `_reconcile_declaracion_casillas` emit a
`no_persisted_revision` advisory and still produce a report and an event
(`src/cadrumo/application/modelo/_reconcile.py:863-865`,
`src/cadrumo/application/modelo/_reconcile.py:978`). Identity-header reconcile needs no
revision. Evidence keyed to a revision cannot store those runs.

Conceptually the two are also different things: a `LedgerEvidenceRow` projects a ledger
row's tax facts (why a casilla holds its value), whereas a reconcile diff is a
comparison verdict between the app's computed value and what AEAT printed.

### Dropping the grounding and re-deriving it at read time does not work

Two independent disqualifications.

Capacity: measured by building the real `model_dump(mode="json")` with empty
`legal_refs` / `source_refs` and the production separators, a bare realistic
`casilla_value_mismatch` diff is 165 characters — three fit (493) and four overflow
(657). Even a physically minimal diff (one-character field and kind, one empty value)
is 127 characters, so four still overflow at 505. The ceiling rises from one or two
divergences to three, which is far below what a real Modelo 100 reconcile produces. The
premise that roughly five would fit is wrong.

Faithfulness: this is the deciding objection. Re-derivation would resolve the registry
snapshot from `(modelo, filing_year, period)`, because
`resolve_registry_snapshot_for_work_unit`
(`src/cadrumo/application/modelo/_calculation_helpers.py:82-118`) never passes a stored
`revision_id` into resolution, per `revision-resolution-is-law-determined`. A registry
re-grounding that changes a casilla's `legal_refs` without moving the revision id would
therefore silently change the legal basis displayed for a historical reconciliation —
and such sweeps are routine, `casilla-grounding-corrects-actividades-default-by-section`
having re-grounded thousands of Modelo 100 casillas. If the correction does move the
revision id, the read raises `WorkUnitRevisionDivergenceError`
(`src/cadrumo/application/modelo/_calculation_helpers.py:131-136`) and the history
becomes unreadable. Either way, historical evidence stops being self-describing, which
is what `carried-observations-stamp-their-revision` exists to prevent.

A secondary problem: a `total` diff's grounding comes from the verification expectation
(`src/cadrumo/application/modelo/_reconcile.py:920-927`), not a `CasillaDefinition`, so
re-deriving it means re-folding the verification policy as well.

One point does favour the option: the work unit remains resolvable after a discard,
because `discard_work_unit`
(`src/cadrumo/application/modelo/_work_lifecycle.py:269-310`) is a soft tombstone and
`catalogue.get(...)` still returns the row.

### Why the established bounded-metadata remedy is lossy for reconcile

The fix chosen for the ledger-export instance was bounded metadata in the payload — row
count, byte size, export digest, `transaction_ids_sha256`, first and last id. That
worked because the row identities stayed recoverable from the transaction catalogue, so
the payload only had to be a pointer to durable data.

Reconcile diff detail has no such second home: it is the only copy. A count plus digest
would therefore return history to exactly the count-only state that Decision 2.A was
rejected for as `no-silent-under-declaration` at the audit layer. Any option that
reduces the reconcile payload to bounded metadata must put the detail somewhere durable
first, which is what makes this a decision rather than an application of the existing
patch.

### What was not investigated

No live AEAT call was made; the overflow was established by reading the guard and
measuring the encoder, not by driving a reconcile against the portal. The exact per-diff
sizes for modelos other than 100 were not enumerated — Modelo 100 is the binding case,
though 111, 130, 190, 303 and 390 are also enrolled in casilla-level reconciliation. The
migration disposition for already-persisted `diffs_detail` values was not examined; the
`PRE_RELEASE` regime at `src/cadrumo/core/compatibility_lifecycle.py:53` and
`no-legacy-compatibility` imply deletion rather than migration, but that is an ADR
question.

The evidence favours giving reconcile detail a dedicated encrypted, profile-scoped store
on the precedent already set for IVA-wallet reconciliation decisions, and reducing the
bucket event to verdict plus count. What the ADR must settle is whether that store is
warranted against the alternative of accepting a reduced-fidelity history, since the
relocation supersedes Decision 2.B and introduces a persisted format with its own
roundtrip obligations.

## Sources

- `src/cadrumo/domain/buckets/_event.py:52-55`, `:313`, `:327`
- `src/cadrumo/application/modelo/_reconcile.py:66-68`, `:140-150`, `:166-192`, `:247`, `:714-721`, `:735-745`, `:863-865`, `:920-927`, `:978`, `:986-1007`, `:1078-1090`, `:1133-1139`, `:1179-1226`
- `src/cadrumo/application/modelo/__init__.py:800`
- `src/cadrumo/application/modelo/_calculation_helpers.py:82-118`, `:131-136`
- `src/cadrumo/application/modelo/_verification_actions.py:897-944`
- `src/cadrumo/application/modelo/_work_lifecycle.py:269-310`
- `src/cadrumo/application/modelo/tests/test_reconcile_value_comparison.py:246-262`
- `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py:129-140`, `:302-372`
- `src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py:101-120`
- `src/cadrumo/domain/modelos/_ledger_filing_snapshot.py:216`
- `src/cadrumo/domain/modelos/_calculation_revision.py:202-226`, `:288-360`, `:549-564`
- `src/cadrumo/application/modelo/_revision_persistence.py:225-258`
- `src/cadrumo/application/ledger/_actions_manual.py:612-650`
- `src/cadrumo/application/ledger/_actions_lifecycle.py:550-554`, `:764-770`
- `src/cadrumo/application/ledger/_models.py:701`
- `src/cadrumo/application/ledger/_evidence.py:136-160`
- `src/cadrumo/domain/attachments/_ids.py:18`
- `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py:163-193`
- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py:397`, `:445-464`, `:779`
- `src/cadrumo/core/compatibility_lifecycle.py:53`, `:62`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions` (11,374 casilla grounding entries measured)
