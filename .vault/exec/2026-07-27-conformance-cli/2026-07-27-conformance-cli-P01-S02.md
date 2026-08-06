---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:ce3ec46d0d502ce8f0914a9a570d4af4524380f13171358d7c66eb8e8c4fbb4c'
step_id: 'S02'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add optional governance scalars engineered_by, review_status, reviewed_by, reviewed_at to ModeloRevision with a model validator refusing reviewed_by or reviewed_at unless review_status is beyond pending_review, absence defaulting to pending_review

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Add the `RevisionReviewStatusField` coercion alias to the registry schema base module, mirroring the existing `SensitivityClassField` shape, and export it.
- Add `engineered_by`, `review_status`, `reviewed_by`, and `reviewed_at` to `ModeloRevision`, all optional, with `review_status` defaulting to the fail-closed pending member.
- Add a second model validator binding the reviewer identity to the review claim in both directions, refusing a reviewed status that omits its companions and a pending status that carries them.
- Document the governance block on the `ModeloRevision` docstring, stating that absence reads as pending.

## Outcome

`ModeloRevision` now carries a declared governance stamp. Loading the real
bundled tree yields 73 modelos and 90 revisions, every one of them
`pending_review` with an empty stamp block, which is the ADR's predicted opening
state.

Modified files: `src/cadrumo/domain/calculations/registry/_schema.py`,
`src/cadrumo/domain/calculations/registry/_schema_base.py`.

Design constraint that shaped the field types. Registry schema models validate
under `strict=True`, and a probe confirmed that pydantic then refuses a bare
string for an enum-typed field. Without a coercion hop `review_status` would
reject every real `revision.toml` token, so the field uses a named
`BeforeValidator` alias rather than a plain enum annotation. The alias lives in
the schema base module beside the legal catalogue's own single-valued review
vocabulary, with a docstring distinguishing the two subjects, because that
neighbouring name is the likeliest thing for a later reader to conflate. The
reviewer companions mirror the legal catalogue's own field types: a real `date`
and a non-empty string.

The coherence validator refuses both directions rather than only the one the
Step row names, because the authorising decision record requires the companions
exactly when the status is beyond pending. A one-directional check would let a
reviewer and a date sit under `pending_review`, which is a review the status
denies. The reviewed-status test reads the derived companion set from core
rather than comparing against the pending member, so adding a fourth status
enrolls it automatically instead of silently falling through to the pending
branch.

No registry TOML data file was touched. This Step ships schema only; absence of
the block is the valid and intended state for all 90 revisions.

Verification. `ruff format` reported both files unchanged and `ruff check`
reported `All checks passed!`. `ty check` reported `All checks passed!`;
`pyright` reported `0 errors, 3 warnings, 0 informations`, all three warnings
pre-existing on the selector-hint code around lines 803 to 806, which this
change does not touch. A direct probe exercised ten stamp combinations against
the real schema: absent block, explicit pending, and both fully-populated
reviewed statuses were accepted; a reviewed status missing both companions,
missing only the date, a pending status carrying both companions, an unknown
status token, and an empty `engineered_by` were each refused with an error
naming the revision and the offending fields. Loading the real bundled registry
through the tree loader returned `modelos: 73 revisions: 90` with distribution
`{'pending_review': 90}`. The scoped registry schema and loader suites were run
with an explicit empty marker selector, since the repo default
`-m 'unit and not external_tool and not os_keychain'` under-collects here:
`252 passed in 42.38s` across the schema, schema hygiene, directory-mode loader,
directory-fragment loader, authority, registry schema parts one and two, and
orden aplicabilidad modules. The registry cache and TOML parity suites finished
`11 passed in 56.68s` for cache isolation after the interference described
below, with the compiled-cache, disk-cache fingerprint, and TOML parity modules
green.

## Notes

Semantic discovery ran under an explicit operator waiver, with `rg` concept
sweeps and whole-file reads standing in for the stopped code index.

A peer race produced two transient failures that are not owned by this Step. The
first pass of the cache suite failed `test_loader_cache_isolation` twice with two
distinct disk pickles written across two real pytest sessions. The compiled-cache
key folds a content hash of every non-test file in the registry package, and a
peer landed the classification-coherence work while the run was in flight, so the
loader-code fingerprint genuinely differed between the two subprocess sessions.
The file's modification timestamp was just over a minute old at the moment of
triage, and the peer commit sits directly above this Step's predecessor in the
log. Re-running the module once the peer file settled gave
`11 passed in 56.68s`, confirming the race rather than a regression. The
attribution was measured, not assumed: the fingerprint derivation was read first
to establish that a peer source edit can move the key at all.

The unrelated repo-wide period combined-string gate remains red at HEAD from a
peer commit, unchanged by this Step and flagging only sanitizer and declaracion
fixture files.
