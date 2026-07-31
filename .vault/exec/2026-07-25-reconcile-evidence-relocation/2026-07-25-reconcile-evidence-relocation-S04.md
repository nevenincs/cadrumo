---
tags:
  - '#exec'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:7c7253990d9d2438348cfb14fc5e680a7b213972f440f7ea366b86993b3c8a4e'
step_id: 'S04'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-plan]]"
---

# Write the reconciliation record and the slimmed bucket event atomically through the existing co-emit write discipline, so a crash between them cannot desynchronise the event log from the detail store

## Scope

- `src/cadrumo/application/modelo/_reconcile.py`

## Description

- Add a prepared-write method to the shared bound repository, and factor the envelope build into one private helper that both it and the existing save call.
- Bind the record repository to the same secure-object backend instance the bucket-event catalogue repository already holds.
- Replace the catalogue save with a single batched save carrying both prepared writes.
- Reduce the event payload to the verdict and the two counts, and record at the site why the detail is not there.

## Outcome

The record and the event land in one SQL unit of work. Both repositories prepare a write and hand it to one batched save on the shared backend, which opens a single session scope, so a failure on either rolls both back. This is the same discipline the filing path already uses to keep the participation index from drifting from the filing catalogue.

No parallel write path was introduced. The bucket-event catalogue repository's own prepared-write method is reused unchanged; the record side gained the equivalent method on the shared base class, so every envelope-bound repository now has it, and the committed and prepared forms are built by one helper and cannot drift apart. Existing save behaviour is unchanged.

Atomicity is proven in two halves rather than assumed. A runtime test drives a real compare-and-swap failure on the record write inside the batch and asserts the event-catalogue write queued ahead of it did not survive. A structural test asserts the write path issues exactly one batched save carrying a two-element tuple, and no stray single-row save.

## Notes

The prepared-write method lands on a shared persistence base class, so its blast radius is every repository that inherits it. The shared contract suites were run rather than assumed: the envelope repository contract tests, the profile namespace-binding tests and the storage namespace-adoption tests, forty-seven tests, all passing, with a confirmation that none were deselected by marker rather than executed. Existing save behaviour is unchanged because both the committed and the prepared form now build their envelope through one helper, which is what makes the two structurally incapable of drifting rather than merely consistent today.

The structural half exists because a first attempt at the runtime half was not a gate on the production composition. Splitting the write into two sequential saves as a probe left the runtime rollback test green, because that test builds its own writes and exercises the batching primitive rather than the code that composes it, and no runtime observation on the success path distinguishes one batch from two sequential saves. The structural gate was added, confirmed red against the same split-write probe, and confirmed green after the authored file was restored.

Semantic discovery was unavailable for this work. The vaultspec-rag code index was truncated while reporting itself healthy, and three probes at 120, 300 and 600 second timeouts all expired with the service reporting itself degraded and one then three active index jobs. The service was not restarted. Every statement here rests on reading the owning packages and their exported surfaces directly, and on targeted pattern search against the current tree; a semantic miss would have proven nothing.
