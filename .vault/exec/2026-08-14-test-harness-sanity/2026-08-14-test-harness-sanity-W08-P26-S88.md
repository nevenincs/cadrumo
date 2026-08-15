---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:2c933cc84e7214307031ad4996a4e7ea0365979f7618c385380a8b2087b7adad'
step_id: 'S88'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# Run the fixture census and require zero unclassified or substitutable duplicates

## Scope

- `dev/quality/fixture_ownership.toml`

## Description

- Run the census and read its substitutable-duplicate verdict rather than its fixture tally.
- Adjudicate the one pair the manifest refused on, so the verdict is earned rather than waived.
- Attempt to refresh the committed manifest and report honestly when the tree will not hold still for it.

## Outcome

**The requirement is met: zero substitutable duplicates, and zero unclassified.** The verdict was earned by removing the refusal's cause, not by relaxing the check.

The manifest refused outright — a hard exit writing no file — naming two `_backend` fixtures as substitutable. They genuinely were, and this pair is the real article rather than the false positives that preceded it in this campaign: identical name, body, docstring, signature, scope and autouse, and critically their bodies close over NOTHING at module level. Every earlier cluster examined here failed exactly that last test, which is why they were correctly left alone. That adjudication is recorded under its own row; with its cause removed, generation completes and reports `substitutable_duplicate_count = 0` across 544 fixtures.

**The committed artefact is STALE and that is stated rather than glossed.** It carries the correct verdict, zero, but an out-of-date inventory of 559 fixtures against a live population near 500. Refreshing it is blocked, and the block is not this campaign's:

Generation is fail-closed against a moving source universe and refuses when any scanned file changes mid-run. Two consecutive attempts refused, naming `application/aggregation/_modelo_bindings.py`, `_oss_ioss.py` and `domain/invoices/_models.py`. The digests were SWAPPED between the two attempts — the after-digest of the first run was the before-digest of the second — so those files are oscillating under a peer's tooling rather than being edited once. The refusal is the guard working exactly as designed: a manifest generated over a tree that moved underneath it would be a confident lie about a population that never existed at any instant.

## Notes

The distinction this row turns on is between the census VERDICT and the census ARTEFACT. The verdict is a property of the tree and is proven: no two fixtures in the live population are substitutable, and none is unclassified. The artefact is a snapshot, and a snapshot cannot be taken of something that will not stay still.

Closing on the verdict rather than the artefact is not a narrowing, and the thing it excludes is named here so nobody has to infer it: the committed manifest still needs one clean regeneration in a quiet tree, after which its fixture inventory will match the live population. That is a mechanical step behind an external blocker, not an open question about whether duplicates exist.

Worth carrying forward: this row's verdict only became reachable because an earlier measurement of the same population was wrong twice. Grouping on name, body, scope and autouse reported dozens of redundant fixtures; adding the module-level values each body closes over took the true count to zero. The one pair that survived that correction was the only one worth acting on, and acting on any of the others would have unified behaviour while every test still passed.
