---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e94a2fcd3b4cd726f670a4fe08cab4b278187d71b2fcfae856a49b2d25b711ed'
step_id: 'S38'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Build the canonical invoice update operation before the bare verbs are repointed, because the canonical surface has create, view, list and remove but NO update, so repointing the five bare verbs would silently drop the operator's only way to correct a persisted invoice and deleting the slim store would remove the sole update surface with nothing named to replace it

## Scope

- `src/cadrumo/application/invoices/_lifecycle.py`

## Description

- Built the canonical update operation, its patch model and its result type.
- Excluded the identity fields from the patch model structurally rather than refusing them at runtime.
- Carried the transaction links forward explicitly and re-validated the corrected record in full.
- Generalised the event table to the created/updated/removed triple and emitted the UPDATED event.
- Corrected the module docstring's retired rationale.

## Outcome

**The blocker this Step was raised for is closed: the canonical surface can now correct a persisted invoice.**

The design turns on one fact the slim store did not have to reckon with. The canonical `invoice_id` is **content-addressed**, derived from kind, number, issue date, counterparty tax id, currency and grand total. So an update touching any of those does not correct the record — it describes a different invoice, and rewriting it in place would strand every transaction already bound to the old id.

**The identity fields are therefore absent from the patch model entirely, and that is deliberately structural rather than a runtime refusal.** A runtime check can be bypassed by a future caller assembling the payload another way; a field that does not exist cannot be set by any caller. On the one axis where getting it wrong strands a link, the stronger guarantee is worth the smaller surface.

**This is a real narrowing against the slim store**, whose id was content-independent and whose update could therefore change an invoice number in place. It is the price of content-addressing, and the campaign has already accepted that trade elsewhere. What matters is that it is stated at the boundary rather than discovered: an identity correction is remove-and-recreate, and the remove verb already guards that path by refusing to delete a record that still carries links.

Three further behaviours, each guarding a distinct failure:

- **The links are carried forward explicitly**, not left to survive by accident. They are why this aggregate is the reconciliation authority; an update that dropped them would sever a bidirectional binding nobody asked to break, and it would do so silently.
- **The corrected record is re-validated in full.** A blind merge would persist an invoice violating its own invariants — and the persistence boundary would then refuse to LOAD it, converting a correctable input error into an unreadable record.
- **An empty patch refuses** rather than no-opping, because accepting it would emit an UPDATED audit event for a record nothing changed on, polluting the trail the event exists to provide.

The UPDATED lifecycle event is now emitted — the one `S37` deliberately left unemitted because no canonical update existed to emit it. The event table is generalised to the same (created, updated, removed) triple the slim store declared, kept as a single table so a caller cannot pair a created event with a removed object type.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_lifecycle.py -m "integration or unit" -n 0 -q --no-header
    10 passed in 7.24s

    uv run --no-sync pytest src/cadrumo/application/invoices src/cadrumo/application/ledger -m "integration or unit" -q --no-header
    772 passed in 34.27s

    uv run --no-sync ruff check src/cadrumo/application/invoices/
    All checks passed!

The identity-stability proof asserts the reloaded record keeps BOTH its id and its transaction links, and the structural proof asserts the patch model's field set is disjoint from the identity set — so the guarantee is checked as a property of the model rather than only as the outcome of one call.

## Notes

**Why the conservation gate missed this.** The `S28` inventory reasoned about the STORE's fields and found every one replaceable. This gap lives in the SERVICE's verb set — the same defect class one abstraction level up. It is the second time in this campaign that scoping an inventory to the wrong axis hid a real gap; the first was comparing field presence rather than defaults and nullability.

The general lesson is worth carrying: a capability inventory must enumerate what an operator can DO, not only what a record can HOLD.

**Not in scope here:** the CLI `update` verb still writes the slim store. Repointing it is the next Step's work, and this Step deliberately stops at the application boundary so the repoint has something proven to point at.

The apidocs drift gate remains red for peer modules only; no module was added here, and the regeneration command was again not run because it sweeps the whole tree.
