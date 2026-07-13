---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S20'
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
     The S20 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Implement the cli-tree.json projection generator reusing the English-pinned reference environment, lazy-import forcing, and per-option param extraction and ## Scope

- `dev/docs/cli_tree.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement the cli-tree.json projection generator reusing the English-pinned reference environment, lazy-import forcing, and per-option param extraction

## Scope

- `dev/docs/cli_tree.py`

## Description

- Add `dev/docs/cli_tree.py`, the build-time `cli-tree.json` help-projection generator (ADR ruling D5).
- Reuse the reference machinery verbatim: import `_force_lazy_imports`, `_collect_commands`, `_assert_no_fallback_surfaces`, and `_reference_subprocess_environment` from the sibling `dev/docs/cli_reference.py` rather than copy-pasting.
- Walk every reachable node (groups and leaves alike) so a group token and a leaf token both resolve to hover help; key each node by the space-joined command path including the leading `aeat` executable token.
- Emit typed strict-frozen pydantic models: `CliParam` (names, kind, required, help), `CliCommandNode` (path, kind group/leaf, help, deterministic usage synopsis, params), and a `CliTree` RootModel mapping path-key to node.
- Classify parameters on Click's `param_type_name`, not `isinstance(param, click.Argument)`: Typer wraps positionals in `TyperArgument`, which is not a `click.Argument` subclass, so an isinstance classifier silently mislabels every positional as an option.
- Synthesise the usage line locally (deterministic, context-free) instead of `Command.get_usage`, which wraps to a terminal-width-dependent line count.
- Provide the language-pinning pair mirroring the reference: in-process `build_cli_tree` under `override_settings(cadrumo_output_language="en")` and the clean-guarantee `build_cli_tree_in_subprocess`.
- Serialise canonically via `serialise_cli_tree` (sorted keys, two-space indent, trailing newline) and emit through `write_cli_tree` to the gitignored `_static/cli-tree.json` (`CLI_TREE_STATIC_RELPATH`), copied by Sphinx into the built site's `_static/` for a same-origin widget fetch.
- Gitignore `docs/_static/cli-tree.json` alongside the other generated docs surfaces.

## Outcome

Generator materialises the live tree (350 nodes) English-pinned, byte-deterministic across two builds, with every positional argument correctly classified and a stable usage synopsis per node. The artifact is emitted to `_static/cli-tree.json` and never committed.

## Notes

Discovered and fixed a latent classification hazard: `TyperArgument` is not a `click.Argument` subclass, so the sibling `_render_param_table` in `cli_reference.py` mislabels typer positionals as options. Left the sibling untouched (out of scope) but classified correctly here via `param_type_name`. The ty gate targets `src/` only, so `dev/docs` type diagnostics (the benign typer-vs-click Command boundary mismatch the sibling also carries) are outside the gate.
