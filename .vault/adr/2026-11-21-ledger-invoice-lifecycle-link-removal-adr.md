---
tags:
  - '#adr'
  - '#ledger-invoice-lifecycle'
date: '2026-11-21'
modified: '2026-11-21'
body_schema: 'body-v2'
body_hash: 'sha256:e2c5187d3121a2988eeca91057f0a87721bd764c1ed4f7fad6b2d8608d763ca9'
related:
  - "[[2026-09-24-ledger-invoice-lifecycle-adr]]"
  - "[[2026-10-23-desktop-ledger-editor-adr]]"
  - '[[2026-10-24-desktop-ledger-editor-audit]]'
  - '[[2026-09-24-ledger-invoice-lifecycle-research]]'
---

# `ledger-invoice-lifecycle` adr: `Ledger invoice links are removable` | (**status:** `proposed`)

Proposed 2026-11-21. Implementation proceeds on PRIME's explicit instruction of 2026-11-21, relaying the operator's standing order; this record stays proposed until the operator accepts it.

## Problem Statement

`ledger.link` binds a movement and a catalogue invoice by writing both sides of the relationship, the movement's `invoice_id` and the invoice's `linked_transaction_ids`, together with a `ledger.transaction.invoice.linked` event (`src/cadrumo/application/ledger/actions_manual.py:260`). No operation removed a link. A person who linked the wrong invoice could only remove the movement, and the desktop told them so: "A link cannot be removed later".

The operator's standing order of 2026-11-20 reads: "everything must be manually editable, fixable and changeable by the operator". PRIME ruled on 2026-11-21 that `ledger.link` must therefore be removable: the unlink is revision-guarded, recorded as an event so the history is kept rather than erased, and refused with a served cause only when a finalized calculation or filing references the link.

The "links are permanent" wording comes from usability ruling R6 in `2026-10-24-desktop-ledger-editor-audit`. That ruling described the product truthfully at the time; it was a consequence of the missing operation, not a decision that links must stay permanent, and no accepted ADR commits to permanence. The atomic link and audit write of `2026-09-24-ledger-invoice-lifecycle-adr` is unaffected and is the pattern the unlink follows.

## Considerations

- The operator order of 2026-11-20 makes every stored fact correctable by the person; a link is such a fact.
- A finalized calculation that cites a movement sealed its link: the movement's filing snapshot carries `invoice_id` (`src/cadrumo/application/aggregation/ledger_filing_snapshot.py:426`) and the invoice side of IVA pairs the movement as the invoice's payment (`src/cadrumo/application/aggregation/invoice_iva_source.py:120`).
- The existing finalized-reference guard reads the sealed revisions' source movements (`src/cadrumo/application/ledger/actions_common.py:242`), as the purchase-evidence release does.
- The IVA invoice side restores a link held only by the movement (`src/cadrumo/application/aggregation/invoice_iva_source.py:237`), so an unlink must clear both sides or calculation would read the link back.

## Considered options

- **Keep links permanent.** No new operation and no new event. Rejected: it contradicts the operator's order and leaves a wrong link uncorrectable except by deleting the movement.
- **Unlink with event history and a finalized-reference refusal.** A registered write clears both sides and appends an unlinked event in one guarded batch; the link's own event stays. Chosen.
- **Correction by replacement.** Remove and re-create the movement, or relink it to another invoice in one step. Rejected: removing the movement loses its edit lineage and other facts, and a combined relink hides the removal inside another verb, so the history no longer says that a link ended.

## Constraints

- The unlink is refused, with a typed cause and next step, only for these causes: `link_not_found` (neither record cites the other, or one does not exist), `transaction_changed` and `invoice_changed` (the stored records differ from what the person saw), and `finalized_calculation_reference`, which names the citing revisions as `finalized_revisions` and the next step `reopen_finalized_calculation`. Every refusal is decided before any write and leaves every row, invoice and event unchanged.
- The request carries the revisions the person saw: the movement's `modified_at` and the invoice's `linked_transaction_ids`. Both catalogues are written under their loaded revisions, so a concurrent change rolls the batch back.
- The two reciprocal catalogue updates and the event commit in one secure-object batch, exactly as `ledger.link` does. No state can land without its event, and no event without its state.
- The event `ledger.transaction.invoice.unlinked` is anchored on the movement and names the invoice id and the actor. Like the link event it carries identifiers and the operator's verb only, never invoice content. The link's own event is never removed or rewritten.
- A one-sided link, held by only one of the two records, is removed the same way, so the person can repair it.
- `ledger.unlink` joins the desktop host's closed admitted list as a write. This amends `2026-10-23-desktop-ledger-editor-adr`, whose admitted list changes only by amendment.
- The operation takes the link's capabilities, replay policy and access resolution, so automation attribution follows the session label as it does for the link.

## Implementation

We will expose the removal as the registered write `ledger.unlink`.

- Service: `src/cadrumo/application/ledger/invoice_unlink.py:118` decides the refusals in `_plan` (`:210`), including the finalized guard (`:232`), and co-commits both catalogues and the event (`:178`). The pure two-sided removal is `src/cadrumo/application/invoices/transaction_linking.py:83`, over the domain helpers `src/cadrumo/domain/invoices/service.py:188` and `src/cadrumo/domain/transactions/service.py:58`.
- Event: `src/cadrumo/domain/buckets/event.py:252`, collected in movement history at `src/cadrumo/application/ledger/history_query.py:49`.
- Operation: `src/cadrumo/application/ledger/unlink_operation.py:75` (request at `:84`, access at `:374`, definition at `:388`), composed at `src/cadrumo/entrypoints/operation_composition_ledger.py:407` and classed a local write at `src/cadrumo/application/operations/access_facts.py:297`.
- Desktop: admitted as a write at `native/desktop/src-tauri/src/shell/ledger/admitted.rs:212`; the window's definition mirror and typed requests at `native/desktop/frontend/src/shell/ledger.ts:352`.
- The CLI verb `aeat app ledger unlink` is not yet exposed; the operation is listed among operations without a command (`src/cadrumo/entrypoints/cli/command_operation_table.py:520`) until its help and refusal texts are in the locale catalogues. This is a rollout gap, not part of the decision.

## Rationale

The chosen option is the only one that satisfies all three conditions of the ruling: the person can correct a link, the history keeps both that the link existed and that it ended, and a sealed calculation is protected by the same guard the other ledger corrections use. It reuses the link's atomic co-commit, so no new durability mechanism is introduced.

## Consequences

- A wrong link is correctable without removing the movement. The desktop and audit wording that a link is permanent becomes untrue and must change with the window's unlink door.
- After an unlink, every derived read sees the removal at once, because the IVA invoice side, reconciliation suggestions and readiness derive from the stored catalogues: the movement no longer pays the invoice and is counted on its own again. A draft calculation that read the link becomes stale through its ledger fingerprint, which already covers `invoice_id` and `linked_transaction_ids`.
- A link a finalized calculation sealed stays until that calculation is reopened or amended.
- Revisit this record if calculations come to record the invoices they read directly, so that the finalized guard can also be keyed on the invoice.
