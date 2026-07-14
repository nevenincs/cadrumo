---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S12'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace honest-all-green with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-07-14-honest-all-green-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Root-cause the stale registry disk-cache pickles serving pre-correction snapshots under pytest and prove fingerprint invalidation completeness or fix the gap and ## Scope

- `src/cadrumo/domain/calculations/registry/_loader.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Root-cause the stale registry disk-cache pickles serving pre-correction snapshots under pytest and prove fingerprint invalidation completeness or fix the gap

## Scope

- `src/cadrumo/domain/calculations/registry/_loader.py`

## Description

- Read the disk-cache key construction in `_load_registry_tree_cached`: it
  hashed the hand-maintained `_REGISTRY_TREE_CACHE_SCHEMA_VERSION` string, the
  registry root path, and the per-TOML `(path, size, mtime_ns)` tree
  fingerprints -- but NOTHING about the loader/compiler/schema CODE.
- ROOT CAUSE: the cache stores COMPILED `(modelos, catalogues)` objects. A
  loader/compiler/schema code change that produces different compiled objects
  from IDENTICAL TOML is invisible to the tree fingerprint (which hashes only
  the TOML inputs) and to the version string (unless a developer manually bumps
  it). In the shared OS temp dir under pytest (which persists across sessions
  and code changes), a pre-change pickle keyed by an unchanged tree fingerprint
  is served for the current loader. This is the hypothesis the assignment
  flagged as most likely (loader version not in the key), confirmed by reading
  the key construction.
- FIX: added `_compute_loader_code_fingerprint()` -> module-level
  `_LOADER_CODE_FINGERPRINT`, a sha256 over every non-test `.py` in the registry
  package, computed once at import; and a testable `_registry_disk_cache_key`
  helper that folds it into the key alongside the schema version, root, and tree
  fingerprints. Any registry-module change now yields a new key, so pre-change
  pickles are never looked up -- no manual version bump required. Best-effort
  fallback (interpreter version + cache tag) if the source is unreadable (zip
  import), so the cache degrades gracefully rather than crashing.
- Real-behavior regression test (`test_registry_disk_cache_loader_fingerprint.py`):
  a CONTROL proves the disk cache is live (a poison pickle at the CURRENT key is
  served), and the REGRESSION proves the fix (the same poison keyed to a
  DIFFERENT loader fingerprint is NOT served -- the loader recompiles real
  content). Plus pure-logic key-differs-per-fingerprint and hash-shape checks.
- SUITE-ORDERING POLLUTION (folded-in handoff item): root-caused
  `test_bundled_root_disk_cache_survives_across_separate_real_pytest_sessions`
  flaking under concurrent load. Its subprocess spawns a real pytest session
  against a scratch package under the OS temp dir; with cwd on the Y: drive and
  the scratch node on C:\\Temp, pytest could not compute a cross-drive rootdir
  and, inheriting `testpaths=["src/cadrumo"]`, drove a broad collection walk that
  `lstat()`d sibling temp dirs -- a concurrent agent deleting its own transient
  `cli-sequence-*` temp dir mid-walk surfaced as a spurious collection
  `FileNotFoundError`. Pinned the subprocess `--rootdir` and cwd to the scratch
  package and cleared the inherited `testpaths` so collection never leaves it.
- Verified the eviction (my prior W01.P02.S07 work) already applies in the
  pytest shared dir: `_evict_stale_registry_pickles` runs unconditionally after
  every successful pickle write, regardless of which cache dir is in force.
- Re-pinned the `_loader.py` size budget (+58 lines, SPLIT-CANDIDATE retained).

## Outcome

Stale-pickle root cause CLOSED: the disk-cache key now binds the loader-code
fingerprint, so a loader/compiler/schema change automatically invalidates every
pre-change pickle rather than relying on a hand-bumped version string. The
cross-session proof is now robust under concurrent shared-worktree load (two
back-to-back full runs of the isolation file + the new regression file: 13/13
green each). All existing cache tests stay green. Commits: `ffac0dd718`
(loader-code fingerprint + regression test + budget re-pin), `03ff8a2f7e`
(subprocess collection-scope confinement).

Note on the P01 S01 diagnosis's stale-cache attribution: on re-verification the
five P01 registry findings it attributed to stale pickles were REAL content
defects (the src/aeat corpus-path bug, art-50.3, art-13.1, chain-cohesion,
ley-37-1992) fixed in P01.S02 with real edits -- they were not stale-pickle
victims. The stale-pickle HAZARD this step closes is nonetheless real and latent
(a loader-code change without a version bump WOULD serve a stale pickle); the fix
removes that class of defect regardless of whether it caused the specific S01
reds.

## Notes

- No destructive git; explicit-pathspec commits throughout. The loader-code
  fingerprint reads ~30-40 small source files once per process at import
  (negligible vs the multi-second registry compile it guards). Correctness is
  favoured over cache-hit-rate: any registry-module edit invalidates all
  pickles, which is the safe direction.
