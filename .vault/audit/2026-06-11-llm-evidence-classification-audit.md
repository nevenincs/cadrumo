---
tags:
  - '#audit'
  - '#llm-evidence-classification'
date: '2026-06-11'
modified: '2026-06-11'
related:
  - '[[2026-06-10-llm-evidence-classification-plan]]'
  - '[[2026-06-10-llm-evidence-classification-adr]]'
---



# `llm-evidence-classification` audit: `Persona roll round 1: evidence-aware LLM classification pipeline`

## Scope

W04.P09 persona roll, round 1. An operator persona drove the shipped
evidence-aware LLM classification pipeline end to end against the real CLI
(in-process via the typer runner) with the environment's authenticated cloud
CLIs (`codex`/`agy`) and a real text-layer purchase-invoice PDF. The roll:
create profile, import a one-row bank statement (302,50 EUR outgoing), register
the invoice as secure-storage evidence, attach it to the transaction, then
`classify --llm codex --saturate --read-evidence`. This is hands-on rolling, not
unit testing — the goal is to find integration and UX gaps no in-tree test
exercises because each test seeds one store directly.

## Findings

### F1 — `evidence add` rejected its own `attachment_id` field (HIGH, fixed in working tree)

`aeat app ledger evidence add <pdf>` failed with a pydantic `extra_forbidden`
error on `attachment_id`. Root cause: W01.P01.S05 added `attachment_id` to
`PurchaseInvoiceEvidence`, and `_evidence_payload` dumps the whole record, but
the strict `EvidenceRecordPayload` CLI schema (parent of the add/view/update/
remove envelopes) never gained the field, so it rejected the dump. The
evidence-ingest CLI was unusable. Fix: add `attachment_id: str | None = None` to
`EvidenceRecordPayload`. Verified: after the fix, `evidence add` returns an
`evidence_id` and the `attachment_id` content address. The fix coexists with an
extensive concurrent peer refactor of the same module (`_ledger_payloads.py`),
so it is held uncommitted until the peer lands to avoid bundling peer WIP.

### F2 — evidence-aware flow is split across two disconnected stores (HIGH, pre-existing, blocks end-to-end)

The documented operator flow cannot be driven end to end. `evidence add`
persists a `PurchaseInvoiceEvidence` record to the
`LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE` secure-object store and returns its
id. `aeat app ledger attach --purchase-invoice-evidence-id <that id>` then
refuses: "purchase_invoice_evidence_id must reference an existing purchase
invoice evidence record" — because `_verify_purchase_invoice_evidence` checks
the `InvoiceCatalogue` (a different store, requiring `kind == RECEIVED`), not the
evidence store the id came from. Worse, the two directions contradict: the
evidence-reading path (`classify --read-evidence`) resolves the transaction's
`purchase_invoice_evidence_id` via `PurchaseInvoiceEvidenceService.view`, i.e.
the evidence store — so even an id that passes `attach`'s invoice-catalogue
check would not be found by the reader. An operator therefore cannot put a
readable invoice onto a transaction through the CLI at all. This is pre-existing
(the two subsystems predate this feature); the evidence-reading work (W01-W02)
sits on top of it. In-tree tests passed only because they seed each store
directly and never exercise `attach` then `read` together.

### F3 — `classify --llm` blocked by a peer mid-refactor (transient, peer WIP)

The real cloud-CLI classify never started: `_ledger_saturate_llm` does
`from ._ledger_payloads import LedgerClassifyResult`, which raised
`ImportError: cannot import name 'LedgerClassifyResult'` — the peer refactor of
`_ledger_payloads.py` had that symbol mid-flight. Transient; resolves when the
peer commits. The cloud-classify leg of the roll is therefore not yet
validated end to end.

### F4 — profile `create` is wizard-only; no headless bootstrap (LOW, UX/test-friction)

`aeat config profile create` is an interactive wizard with no non-interactive
flag or answers-file, so an automated or headless persona roll cannot bootstrap
a profile through the real CLI; the roll had to register the profile via the
application API. Worth a `--non-interactive`/`--set` path for scripted setup.

## Recommendations

- Commit F1 (`EvidenceRecordPayload.attachment_id`) as soon as the peer
  `_ledger_payloads.py` refactor lands, so the two changes do not collide.
- F2 needs a decision (likely an ADR): unify the purchase-invoice evidence
  store and the invoice catalogue, or make `attach` and `classify --read-evidence`
  agree on one store. Until then the evidence-aware classify/split flow is only
  reachable programmatically, not via the documented CLI. Track as a blocking
  follow-up for the feature's end-to-end claim.
- Re-run the cloud-classify leg (F3) once the peer refactor settles; it is the
  one persona step not yet exercised against a real model.
- Consider a headless profile-bootstrap path (F4) so future persona rolls and
  CLI integration tests need no application-API shim.

## Codification candidates


- **Source:** finding F1 (a strict CLI payload schema rejected a field the
  application record now emits).
  **Rule slug:** `cli-payload-schema-mirrors-emitted-record`.
  **Rule (candidate):** When a persisted/boundary record gains a field, the
  strict `OutputSchema` CLI payload that mirrors its `model_dump` must gain the
  same field in the same change; the relocation/field-add is not complete until
  the emit-site schema validates the new dump. Deferred until a second
  occurrence confirms the pattern is recurring rather than a one-off.

F2 (two-store evidence split) is an architecture decision, not a constraint to
codify yet — it belongs in an ADR, not a rule. F3/F4 are transient/UX and do not
meet the durability bar.
