---
tags:
  - '#exec'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:626b9fd2bc79fe3656e8882e199c4e6d609c2df7214f8c2286e08b1419b93f03'
step_id: 'S06'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-plan]]"
---

# Prove the new persisted format with a strict save-load-equality roundtrip populating every defaultable field to a non-default value, plus an anti-tautology proof that a mutated stored payload surfaces a refusal, using real adapters and a real master-key provider rather than doubles

## Scope

- `src/cadrumo/application/modelo/tests/`

## Description

- Add a store test module driving the real key provider, the real per-bucket database and the real serializer.
- Prove a save and load round trip with strict equality, from a fixture that displaces every defaultable field.
- Prove the round trip is not tautological by re-persisting the same record with one required field deleted and asserting the read refuses, with an unmodified positive control alongside.
- Prove several reconciliations of one work unit persist distinctly, at the repository and end to end through the verb.
- Prove a run carrying no persisted revision persists and reads back.
- Prove the batch rolls back as a unit, and that the write path issues exactly one batched save.

## Outcome

Eight tests, all on real adapters. No doubles, no skips, no expected failures, no tautological assertions.

The round-trip fixture displaces every default rather than accepting one: the source reference is non-empty, both containers carry real entries, the diff kind is the non-default member, both value strings and both grounding tuples are populated, and the advisory context mapping is non-empty. A dropped field would otherwise be invisible, because the reload would re-default it and the equality would still hold.

The anti-tautology proof runs the mutated payload through the production encryption path and carries an unmodified positive control, so a refusal caused by the mutation procedure itself could not be mistaken for the property under test.

Two gates were confirmed to bite by temporarily regressing the production module and observing the expected reds before restoring it: the key tests against a collapsed key, and the structural atomicity gate against a split write.

## Notes

Two failures during authoring were real information rather than noise, and both were fixed in the test rather than worked around. Seeding a work unit with a fabricated revision pin diverts reconcile into a snapshot-unavailable advisory instead of reaching the no-persisted-revision branch, because the snapshot resolver asserts the stored revision equals the one the law selects; the helper now resolves the law-determined revision id. And an enrolment assertion reached for storage internals that are deliberately absent from the storage facade, so it was replaced by an assertion that the repository restates no namespace constant of its own, which is what makes the registry-wide lineage gate govern this store.

The type checker reports no errors. It warns about private-symbol use from the test module, matching the existing sibling reconcile test that imports the same internal entry point.

Semantic discovery was unavailable for this work. The vaultspec-rag code index was truncated while reporting itself healthy, and three probes at 120, 300 and 600 second timeouts all expired with the service reporting itself degraded and one then three active index jobs. The service was not restarted. Every statement here rests on reading the owning packages and their exported surfaces directly, and on targeted pattern search against the current tree; a semantic miss would have proven nothing.
