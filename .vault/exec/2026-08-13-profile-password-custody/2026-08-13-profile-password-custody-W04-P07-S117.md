---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:d3f1d21df0dd168c85f4e7eaff59be5b2a95852a2ac0c33d18a2c0bda45aa3ae'
step_id: 'S117'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh remove the bucket manifest reader now that the retirement is ruled, taking its per-bucket session-window override with it

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_manifest_io.py and src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py`

## Description

- Remove the per-bucket session-window override the ruling found had no
  producer, and point its live caller at settings directly.
- Drop the facade exports and the application wrappers that carried it.
- Establish where the readers live at edit time rather than at task start.

## Outcome

The override is gone: the reader module, its live caller now reading settings
directly, both facade exports, and two application wrappers that turned out to
have no callers at all. Ninety-three deletions against three insertions.

**Checking where the readers lived immediately before editing, rather than at
task start, changed the shape of the step.** A concurrent step had relocated
both readers into a new module to protect them, and that module carried a
docstring warning that losing them "would silently collapse every profile's idle
and absolute session windows to the deployment defaults, which is a behaviour
change wearing the costume of a cleanup."

That warning was written on the team lead's instruction, before the governing
measurement existed. The ruling then established that the override has no
producer and never had one, so **the relocation existed to protect a capability
that cannot exist.** The removal supersedes it, and the commit records why the
warning does not hold rather than silently contradicting it -- a later reader
finding a deleted warning and no explanation would reasonably assume it had been
overlooked.

The sequence is worth naming beyond this step: a caution became a docstring, the
docstring read as an established fact, and only a measurement dissolved both.
On a tree where several agents write concurrently, a caution hardens into
apparent evidence quickly, and the only thing that reverses it is a measurement
rather than a second opinion.

## Notes

The manifest reader itself is NOT removed here. After this commit its only
remaining production consumer is the digest helper, whose deletion is a separate
step, so the reader waits on that rather than being unblocked by smuggling the
other step's deletion into this commit. That restraint cost a round trip and was
correct: the digest deletion carries no ruling behind it, so burying it inside a
behaviour-change commit would have made it invisible to review.

A defect of the author's own was found and fixed here. An earlier relocation had
added a symbol to the custody facade's lazy export map and to `__all__`, but not
to the type-checking import block. The symbol therefore resolved at runtime and
typed as bare `object`, so every call through it was unchecked while looking
correct. **The runtime half of a lazy facade proves nothing about the type
half**, and it surfaced only under the type checker run against the CONSUMING
package rather than the owning one.

The full suite could not be run: a concurrent step had a shared test-support
module mid-edit against an import the tree still used, so collection failed on
that in-flight state rather than on anything here. The gap was reported rather
than a number quoted that could not be taken.
