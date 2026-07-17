---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Stamp the bundled-tree verdict into the release build so the first end-user touch skips runtime validation, keyed by the same fingerprint tuples and ## Scope

- `packaging/cadrumo_data_official/hatch_build.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Stamp the bundled-tree verdict into the release build so the first end-user touch skips runtime validation, keyed by the same fingerprint tuples

## Scope

- `packaging/cadrumo_data_official/hatch_build.py`

## Description

- Add `compute_bundled_verdict_key`: an install-stable key over the package version plus the sorted `(relative-path, size)` of every registry FILE, dropping the mtime component and the directory entries that do not survive packaging.
- Add `stamp_bundled_verdict` (writes an install-stable verdict from caller-supplied fingerprints) and `shipped_verdict_location` (the sibling-of-registry path shared by the build stamp and the runtime read).
- Update `registry_validation_is_certified` to match the shipped verdict against the install-stable key, computed lazily only when a shipped verdict is actually present so the file-stat pass never runs on a warm load or a development tree.
- Add the `stamp_bundled_registry_verdict` authority facade (collects the registry-tree and convenio fingerprints, stamps the sibling location) and export it from the registry package `__all__`.
- Wire the stamp into `dev/packaging/python_cohort.py` `build_python_cohort`: after the `git archive` extraction and before `uv build`, write `_data/registry/aeat-validation-verdict.json` into the wheel tree so the cadrumo wheel ships it.
- Update the S01 helper tests for the new `registry_validation_is_certified` signature; add real-behavior stamp tests proving install-stability (identical key across an absolute-path move and mtime rewrite) and content binding (size, file-set, and package-version sensitivity).

## Outcome

The chosen build surface is `dev/packaging/python_cohort.py`, not the plan-named `packaging/cadrumo_data_official/hatch_build.py`: that hatch hook builds the corpus DATA companion wheel, which ships neither the registry tree nor the full checkout, so it cannot compute or ship a registry verdict. The cohort builder is the surface that genuinely runs at release build and assembles the cadrumo wheel that carries `_data/registry`, and the wheel `packages = ["src/cadrumo"]` config ships the sibling `.json` with no exclusion.

The shipped verdict key is install-stable by design. The cohort builds from a `git archive` extraction and installation rewrites file mtimes and directory sizes, so an mtime-keyed shipped verdict (the per-storage-root key from S02) would never match at runtime. The bundled tree is byte-identical per release (the cohort pins every companion to `==version`), so the shipped key drops mtime and directory entries and binds to the release version plus the registry files' relative paths and sizes; per the ADR, install byte integrity is owned by the package-manager digest chain, and any file-set or size change re-validates. The per-storage-root verdict (S02) remains the robust, installer-independent win; the shipped verdict removes the residual first-touch validation on a fresh install.

`ruff check`, `ruff format --check`, and `ty check` are clean on all touched files; `_validate_verdict.py` stays at 297 lines, under the 300-line `_validate*.py` reviewability ceiling. The new stamp tests (5) and the updated location tests (10) pass, as does the reviewability gate.

## Notes

The full cohort build cannot be exercised end-to-end here: `build_python_cohort` requires a clean source snapshot and this shared worktree carries active peer WIP, so the wiring is verified by unit-testing the stamp facade and its install-stability directly rather than by running a wheel build. A shipped-verdict MISS is always safe (it falls through to a single validation plus the per-storage-root verdict), so an imperfect match degrades gracefully to S02 behavior.

Peer-owned full-tree gate failures observed during verification are outside this Step's surface and left for their owners: `test_public_api_boundaries` and `test_exception_hygiene` on P02's `_validate_evidence.py`/`test_extraction_sidecar_freshness.py`, and `test_import_hygiene_gate`/`test_lazy_import_policy` on P02's corpus test debt and P04's `application/user_profile/*` and `entrypoints/mcp/*` in-process work. None name this Step's files. These are reported to the coordinator, not fixed here, per the distinguish-owner discipline. No incidents; no scaffolds left in code.
