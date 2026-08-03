---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ea792f4a7748ee04f613326c278a87f6dcccb04208fa62ba950515de332e51ef'
step_id: 'S10'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add effective_storage_root to the paths module returning the caller override or the settings root, normalised, gated by a test asserting a relative override anchors to the platform user-data root one level above the storage root

## Scope

- `src/cadrumo/core/paths.py`

## Description

- Search vaultspec-rag by meaning for an existing "effective storage root" resolver before writing one; find none, so proceed.
- Read all six inline "override or settings root" duplicates across the application layer to find the true union of correct semantics before writing the accessor.
- Add `effective_storage_root(root, *, settings=None, state_root_inputs=None)` to `paths.py`, routing an explicit override through the already-tested `resolve_project_path` and returning the already-normalised settings default unchanged when no override is given.
- Add gating tests covering relative-override anchoring, absolute-override passthrough, settings fallback, an injected `settings=` object, and override-wins-over-settings precedence.

## Outcome

Landed in commit `6ce5a3d4dc`, gated by `test_paths.py`'s new `effective_storage_root` test section (5 tests, all green). Comparing the six duplicate sites surfaced real drift rather than mere duplication: one site normalised an override with a bare `Path.resolve()`, which anchors a relative override at the process working directory; four sites returned an explicit override completely unnormalised (no `expanduser`, no `resolve`). Both are defects against the module's own documented anchoring rule (never the cwd, always the platform user-data root). The accessor fixes both by routing every override through `resolve_project_path`. Attribution is by construction: the accessor has one distinct, greppable name, so `rg "effective_storage_root"` finds every caller; no taxonomy or provenance-gate registration was needed because the function only reads/normalises the root, it never joins a subpath onto it (the provenance gate's AST detector matches `settings.cadrumo_local_storage_root / X` joins, not a plain-read-then-normalise call).

## Notes

None.
