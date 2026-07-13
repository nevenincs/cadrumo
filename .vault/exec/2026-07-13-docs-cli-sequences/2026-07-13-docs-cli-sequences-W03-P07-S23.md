---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S23'
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
     The S23 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Register the backtick-fenced cli-sequence MyST directive rendering server-side static frames in document order plus one inline application/json payload per sequence and ## Scope

- `docs/conf.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Register the backtick-fenced cli-sequence MyST directive rendering server-side static frames in document order plus one inline application/json payload per sequence

## Scope

- `docs/conf.py`

## Description

- Register the backtick-fenced `cli-sequence` MyST directive: required sequence-id argument, `:verify:` and `:seed:` options, a frame-line body.
- Parse the body via the engine `parse_sequence`, read the sequence's committed golden via `read_golden`, and refuse a missing or stale golden with an instructive build error that names the exact refresh invocation. The directive never executes a command; it renders from the golden.
- Render the command line and tokens from the authored frame (placeholders intact, the reproducible form) and the output, exit code, and captures from the golden; assert body and golden agree on frame count and per-frame kind.
- Emit, in document order, every frame as static HTML (tokenised command spans plus the masked-envelope or normalised-text output in a `pre`) and exactly one inline `application/json` payload per sequence, both rendered from one computed payload so the JSON cannot drift from the visible frames.
- Render the terminal result frame's `:verify:` caption and each `@expect` as a singular imperative verification check; collapse setup frames under a "Preparation" disclosure; escape all text and neutralise a payload `</` sequence so the inline script cannot break out.
- House the directive and its render pipeline in a dedicated module imported by the docs config, and resolve the golden and seed roots from Sphinx config values (defaulting to the committed roots) so the directive is buildable against a fixture tree in isolation.

## Outcome

- The directive renders a complete no-JS transcript plus a well-formed inline payload; the payload frame shape is `{index, kind, command_line, tokens, exit_code, output:{format,body}, stderr, expects:[{json_path,expected,narration}]}` with a sequence-level `sequence_id` and `verify` caption.
- A missing golden fails the build naming `python -m dev.docs.sequences refresh`.
- Ruff and ty are clean.

## Notes

- The render pipeline lives outside the engine package (a new docs module) rather than in the config file, so the HTML/payload projection is directly unit-testable and the config registration stays thin; this also avoided contending with concurrent peer edits to the engine package facade.
- The masked-JSON output view reuses the central observability mask, so displayed surrogate ids show the sentinel and the rendered output is deterministic.
- Follow-up absorbing coordinator caveats after the engine owner published the final facade: the directive now statically refuses an enrolled sequence that reads live AEAT (a pull verb or the app-live group) at build time via the engine's fail-closed live-frame detector, before the golden lookup, so the author gets a clear unenrollable error rather than an opaque missing-golden failure; the tokeniser is now exported through the engine facade (with a public live-refusal re-export) and every directive and test import routes through the facade rather than a private submodule.
