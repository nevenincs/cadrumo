---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:69a025bdc976b1e1ce0c06632ad4e6a3aa552c9ccc2264a26fdbe911dee798f0'
step_id: 'S18'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Route the invoice-link success path through the co-commit write authority so the invoice catalogue and the transaction catalogue diff land in one apply_batch transaction, replacing the two independently-committed saves

## Scope

- `src/cadrumo/application/invoices/_linking.py`

## Description

- Replace the two independently-committed saves in `link_invoice_transaction_repositories` with a single co-commit: the updated invoice catalogue is serialised through `to_secure_object_write` and passed to `save_with_secure_object_writes` alongside the transaction-catalogue diff.
- Narrow both repository parameters from the domain protocols to the concrete adapter repositories, because the co-commit methods are adapter-only escape hatches absent from the protocols, and record the rationale as an inline comment mirroring the sibling composer in the ledger package.
- Rewrite the module docstring and the function docstring to describe the one unit of work and name the one-sided state the write can no longer reach.
- Extend the sole invoice-linkage writer's docstring so the atomicity claim covers the accepted path, not only the refusal path.

## Outcome

Both sides of an invoice link now commit in one `apply_batch` transaction. A crash, disk error, or exception during persistence rolls both catalogues back together, so the invoice can no longer come to rest citing a transaction that does not cite it back. The change reuses the existing co-commit authority rather than introducing a second transactional-composition mechanism: the same primitive the ledger package's transaction-plus-invoice-plus-events composer already funnels through.

The fix is behaviour-preserving on the success path and on every refusal: no event emission was added, no signature reordering, and the writer remains invoice-only.

## Notes

The defect predates this campaign. Tracing the two-save shape back through pre-relocation history shows the pre-campaign combined link command called the same non-atomic function, so this was not a regression the campaign introduced — what the campaign did was centralise the function, market it as atomic, and close the CLI's alternate route to it without scoping the claim. That framing is recorded here so the campaign's provenance is not overstated in either direction.

The parameter-type narrowing is a public-signature change. Every in-tree caller already passed concrete repositories, so no call site needed updating; the pre-release no-legacy posture means no compatibility overload was added.
