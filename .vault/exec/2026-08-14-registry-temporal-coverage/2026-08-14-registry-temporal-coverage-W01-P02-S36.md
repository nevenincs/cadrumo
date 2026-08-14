---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e505d76718b048cdc88c4286c461a271778d3522b5f3d9e9a19281d7c10fd2ea'
step_id: 'S36'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Reduce the per-load cost the sanctioned authority path charges every caller, by bounding the source-evidence fingerprint collection the way the registry tree fingerprint is already bounded rather than leaving it an uncached recursive walk over the evidence corpus, and by keying the authority cache on a digest of the fingerprint tuples rather than on the tuples themselves so the key hash stops scaling with corpus size, measured before and after against a warm real bundled tree and proven not to weaken invalidation by rerunning the staleness gates that prove a tree edit is seen

## Scope

- `src/cadrumo/domain/calculations/registry/_source_evidence_fingerprint.py`
- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

This record documents work found already present, uncommitted, in the working
tree at the time of writing. It was built by a prior session that did not leave
an execution record; this record is written retrospectively from the code and
tests as they exist now, not from having performed the implementation.

Only the bounding half of the row is built:

- Add a bundled-root fingerprint window to `collect_source_evidence_fingerprints`
  in `_source_evidence_fingerprint.py`: a source-evidence root resolving inside
  the package-bundled data tree is served from an in-process cache for
  `BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS`, the same constant the registry-tree
  fingerprint already uses, stamped at walk completion rather than walk start.
- Extract the walk itself into `_walk_source_evidence`, and add
  `_is_bundled_evidence_root` (fails closed to "always walk" on any
  resources-boundary error) plus a process-cached `_bundled_data_root()` lookup.
- Add `clear_source_evidence_fingerprint_cache` and publish it in the module's
  `__all__`.
- Leave a caller-supplied specimen root (outside the bundled tree) walking fresh
  on every call, unchanged and never cached, mirroring the same bounded/unbounded
  split the registry-tree fingerprint already enforces.
- Add `test_source_evidence_fingerprint_bound.py` (3 tests): a specimen root's
  edit is visible on the very next call; the bundled root returns the identical
  cached tuple object across two calls, proving it is served rather than
  re-walked; clearing the cache forces a fresh walk that reproduces an identical
  fingerprint.

The `_authority.py` changes present in the working tree at the same time are NOT
part of this row's work: that diff generalises the M303-specific annual-orden
compilation into a modelo-keyed `supplementary_orden` mechanism, which belongs to
a different plan row (`W01.P02.S04`). `_authority.py`'s call to
`collect_source_evidence_fingerprints` is unchanged.

## Outcome

The recursive filesystem walk `collect_source_evidence_fingerprints` performs
over the bundled evidence corpus — previously repeated on every call, including
every registry load through `ValidatedRegistryAuthority.load` — is now paid once
per TTL window for the bundled tree, mirroring the bound the registry-tree
fingerprint already has. Verified by re-running the new test module and the S02
coverage test module together: `26 passed` (`test_schema_family_coverage.py` +
`test_source_evidence_fingerprint_bound.py`, `pytest -n 0 -q`, 5.91s).

## Notes

This record documents work found already present on disk from a prior session;
it is written retrospectively and does not represent implementation performed by
the agent writing this record. The work is UNCOMMITTED at the time of writing
(`git status` shows `_source_evidence_fingerprint.py` and `_authority.py` as
modified, unstaged).

**The row's second requirement is not built.** The row asks to key "the authority
cache on a digest of the fingerprint tuples rather than on the tuples
themselves so the key hash stops scaling with corpus size." The authority cache
is `_load_authority` in `_authority.py` (`@lru_cache(maxsize=16)`), and as of
this verification it is still keyed directly on the raw parameters
`root, source_root, _registry_fingerprint, _source_evidence_fingerprint` — the
full fingerprint tuples themselves, not a digest of them. A diff of
`_authority.py` against `HEAD` confirms the only change to that function's
neighbourhood is the unrelated M303-to-supplementary-orden generalisation
described above; no digest computation, `hashlib` call, or cache-key change was
found anywhere in the registry package's uncommitted diff. This half of the row
is open work, not completed work being under-reported.

**No before/after measurement is evidenced.** The row asks for the improvement
to be "measured before and after against a warm real bundled tree." No such
measurement — wall-clock, call count, or otherwise — exists in the diff or the
test module. `test_the_bundled_evidence_root_is_served_from_the_window` proves
the SECOND call returns the identical cached tuple object rather than a
re-walked one (an `is` identity check), which demonstrates the caching mechanism
functions, but this is a correctness proof, not the requested before/after
performance measurement. Treat the performance claim as not evidenced.

**Staleness re-run, partial.** Re-ran the source-evidence-specific staleness gate
`test_authority_cache_invalidates_when_source_evidence_changes` in
`test_authority.py` together with `test_mutable_tree_fingerprint_invalidation.py`
(13 tests total): it passed, confirming a source-evidence corpus edit under a
specimen (non-bundled) root is still seen by the authority cache after this
change. Three unrelated tests in `test_authority.py` failed in the same run
(`test_authority_returns_cached_validated_snapshot_for_repeated_filing_context`,
`test_authority_snapshot_runs_real_modelo_calculation`,
`test_authority_snapshot_is_authority_owned_revision_projection`), each on
`modelo 130 revision 2019-y-siguientes is 'pending_review'; filing-grade
snapshot requires operator_reviewed revision`. This is unconnected to
source-evidence fingerprinting or authority-cache keying — it reads as
concurrent peer work on registry review-status data in this shared worktree —
and is reported here rather than silently absorbed into this Step's scope.

This Step consumed no entry from the plan's Deletion inventory: nothing was
deleted, and the fingerprint-cache plumbing this row's sibling row (`S29`)
targets for removal was not touched here.
