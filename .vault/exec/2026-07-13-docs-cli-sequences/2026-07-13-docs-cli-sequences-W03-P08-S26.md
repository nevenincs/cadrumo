---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:21f4fc5dd497c2b69631f9838b8b61378c27bdb9efa9fefba74458fc552cc2f4'
step_id: 'S26'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Add the builder-inited hook in docs conf setup running the engine check mode and emitting cli-tree.json into the static output, scoped for the incremental changed-page build

## Scope

- `docs/conf.py`
- `dev/docs/sequence_build_gate.py`
- `dev/docs/tests/test_sequence_build_gate.py`

## Description

- Add `dev/docs/sequence_build_gate.py` holding the reusable docs-build-half gate: `emit_cli_tree(app)` writes a fresh `_static/cli-tree.json` under the build source tree, and `check_sequence_goldens(app, pages=...)` calls the one engine function `check_sequences`, raising `SphinxError` with the verbatim problems plus the `refresh` remedy on any divergence.
- Wire two new `builder-inited` closures in `docs/conf.py` `setup()` alongside the CLI-reference and glossary hooks: `_emit_cli_tree` emits the projection; `_check_cli_sequences` scopes the check to the changed-page set on an incremental build (reusing the existing `_specific_build_sources()` specific-source detection, filtered to `.md` docnames) and runs unscoped on a full build.
- Keep the gate hermetic: execution self-isolates through the runner's storage-root, frozen-clock, English-language, and live-test-off seams, so it honours the `CADRUMO_DOCS_OFFLINE` hermetic build with no network assumption.
- Build-cost parity fix (P08 review MEDIUM): guard the projection emit behind `should_emit_cli_tree(output_path, specific_sources=...)`, mirroring the sibling `_should_generate_cli_reference` shape — regenerate on a full/update build, when the artifact is absent, or when forced (`CADRUMO_DOCS_FORCE_CLI_TREE`); skip on an incremental changed-page build whose artifact already exists (`CADRUMO_DOCS_SKIP_CLI_TREE` forces the skip). `_emit_cli_tree` passes `_specific_build_sources()` through so an incremental docs-only build no longer pays the ~4.9s subprocess for a projection that cannot have changed.
- Add `dev/docs/tests/test_sequence_build_gate.py` pinning the guard across every build mode (full regenerate, incremental-existing skip, incremental-absent regenerate, force/skip env overrides) plus a behavioral test proving `emit_cli_tree` leaves an existing artifact untouched on an incremental build (a sentinel a real rebuild would overwrite survives, so the subprocess never ran).

## Outcome

Both invocation surfaces share the one `check_sequences` execution path: the Sphinx build reds on a golden divergence via `_check_cli_sequences`. Reusing the function in a fixture Sphinx conf lets S28 exercise the real hook, not a reimplementation. The projection emit now has build-cost parity with the CLI-reference hook: only a full build, an absent artifact, or a force regenerates it. Ruff and ty clean; the 6 guard tests pass in ~0.5s in the `unit` lane, and the full `test_sequence_goldens.py` module (9) stays green.

## Notes

Measured build-time cost: `emit_cli_tree` pays a ~4.9s subprocess CLI-tree build only when it actually regenerates (full build / absent artifact / forced); an incremental changed-page build now skips it. The sequence check adds ~2.5s per enrolled sequence executed (fresh crypto sandbox + profile create + frames); with zero enrolled sequences today it is ~0.1s discovery only, and the incremental changed-page scoping means only changed pages' sequences execute on a partial build.

LOW follow-up (deferred, not implemented — W06/curate candidate): an orphan golden directory (a golden dir under `docs/_sequences` whose live page was renamed or removed) is never flagged by the check surface — `discover_sequences` walks live pages, so a golden with no page simply goes unchecked rather than erroring. Worth a curate/W06 sweep that reconciles the committed golden tree against the live enrolled-page set.
