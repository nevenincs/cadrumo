---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:80765c9967eefe8261d0d90c2d708599cf8f79f388c4226a41be9a61377961d2'
step_id: 'S81'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Make generic manual-field updates refuse all evidence fields, reserve evidence catalogue and provenance mutation for attach, and expose a single atomic invoice-only linkage writer

## Scope

- `src/cadrumo/application/ledger/_actions_manual.py`
- `src/cadrumo/application/ledger/__init__.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD rather than re-implementing it. The predecessor ledger-evidence-atomicity campaign landed the identical requirement in commit `744c61adb8`, with follow-on hardening in `b59cbfcb1e`, `0a9cf770d5`, and `a7d8f8aa38`.

- Reserve the evidence axis behind a module-level frozenset in `_actions_manual.py` naming `purchase_invoice_evidence_id` and `attachment_ids`.
- Refuse an evidence-touching patch at the generic field door: `update_manual_transaction_fields` rejects when the patch's set fields intersect the reserved axis, naming the offending fields in the refusal context.
- Refuse an evidence-changing command at the generic command door: `update_manual_transaction` rejects when the replacement command would move either evidence field away from the stored value.
- Gate both refusals on a private `_evidence_authority` keyword threaded only by the evidence writer, so `attach_manual_transaction_evidence` remains the single door that mutates the evidence catalogue and provenance.
- Expose `link_manual_transaction_invoice` as the sole invoice-linkage writer: it resolves the transaction, enforces the invoice missing and cross-bucket policy before any catalogue write, then delegates the bidirectional mutation to the invoices facade, co-committing both catalogues and the linkage audit event in one secure-object batch. It never reads or writes an evidence field.
- Re-export `attach_manual_transaction_evidence` and `link_manual_transaction_invoice` from the ledger package facade so cross-package consumers reach them without dotting into a private module.

## Outcome

Evidence catalogue and provenance mutation is reachable only through the attach authority; both generic update doors refuse it with a refusal that names the reserved fields rather than a bare rejection. Invoice linkage is a distinct, atomic, invoice-only writer that cannot disturb evidence, and its accepted path is all-or-nothing across the transaction catalogue, the invoice catalogue, and the event history.

Verified against HEAD by inspection of the two scoped files and by the gates in the sibling Steps: `uv run --no-sync pytest -m "" src/cadrumo/application/ledger/tests/` reports 427 passed, and `uv run --no-sync pytest --collect-only -q` collects 13992 tests with no errors.

## Notes

The bulk classify path reaches the in-memory update builder directly, below the wrapper guard. That is safe only because the bulk column allowlist and the reserved evidence axis are disjoint, and a dedicated gate in the sibling Step keeps the two sets disjoint so a future column addition cannot open an unguarded evidence door.
