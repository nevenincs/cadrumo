---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S26'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Add the builder-inited hook in docs conf setup running the engine check mode and emitting cli-tree.json into the static output, scoped for the incremental changed-page build and ## Scope

- `docs/conf.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the builder-inited hook in docs conf setup running the engine check mode and emitting cli-tree.json into the static output, scoped for the incremental changed-page build

## Scope

- `docs/conf.py`
- `dev/docs/sequence_build_gate.py`

## Description

- Add `dev/docs/sequence_build_gate.py` holding the reusable docs-build-half gate: `emit_cli_tree(app)` writes a fresh `_static/cli-tree.json` under the build source tree, and `check_sequence_goldens(app, pages=...)` calls the one engine function `check_sequences`, raising `SphinxError` with the verbatim problems plus the `refresh` remedy on any divergence.
- Wire two new `builder-inited` closures in `docs/conf.py` `setup()` alongside the CLI-reference and glossary hooks: `_emit_cli_tree` emits the projection every build; `_check_cli_sequences` scopes the check to the changed-page set on an incremental build (reusing the existing `_specific_build_sources()` specific-source detection, filtered to `.md` docnames) and runs unscoped on a full build.
- Keep the gate hermetic: execution self-isolates through the runner's storage-root, frozen-clock, English-language, and live-test-off seams, so it honours the `CADRUMO_DOCS_OFFLINE` hermetic build with no network assumption.

## Outcome

Both invocation surfaces now share the one `check_sequences` execution path: the Sphinx build reds on a golden divergence via `_check_cli_sequences`. Reusing the function in a fixture Sphinx conf lets S28 exercise the real hook, not a reimplementation. Ruff and ty clean on the new module; `check_sequences()` unscoped over the whole `docs/` tree runs in ~0.11s with zero enrolled sequences today.

## Notes

Measured build-time cost: `emit_cli_tree` pays a ~4.9s subprocess CLI-tree build every build (the same subprocess-projection pattern the existing CLI-reference hook already pays); the sequence check adds ~2.5s per enrolled sequence executed (fresh crypto sandbox + profile create + frames). With zero enrolled sequences today the check is ~0.1s discovery only; the incremental changed-page scoping means only changed pages' sequences execute on a partial build. The ADR mandates the gate, so the cost is recorded here rather than skipped.
