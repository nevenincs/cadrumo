---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S21'
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
     The S21 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Write projection tests and make a documented command path absent from the projection a hard build failure and ## Scope

- `dev/docs/tests/test_cli_tree.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Write projection tests and make a documented command path absent from the projection a hard build failure

## Scope

- `dev/docs/tests/test_cli_tree.py`

## Description

- Add `dev/docs/tests/test_cli_tree.py`, marked `unit`/`hex_entrypoint`/`docs` per the sibling drift-gate convention.
- Assert the projection generates a populated mapping and is byte-deterministic across two independent subprocess builds.
- Verify the canonical serialisation has sorted top-level keys and a trailing newline.
- Prove coverage non-tautologically: an independent subprocess walk via `_collect_commands` (NOT the projection generator) yields the full path-key set, asserted equal to the projection keys — so the projection loop drops no collected node.
- Regression-guard the `TyperArgument` classification: `ledger view` projects a required `transaction_id` positional as an argument, not an option.
- Cover the lookup surface: tuple and string resolution agree, a path missing the leading `aeat` still resolves, serialise→load round-trips to an equal projection, and the strict node model rejects an unknown field.
- Gate the missing-path failure: a mistyped verb raises `CliTreePathNotFoundError` carrying nearest-candidate hints, and `assert_documented_paths_present` passes real paths and raises on the first absent one.
- Confirm `write_cli_tree` emits canonical JSON at the default `_static/cli-tree.json` location and is byte-idempotent on a second write.

## Outcome

15 tests pass. The documented-path-absent case is a hard, loud failure with candidate hints — the free conformance gate ruling D5 predicts — and the coverage test is a genuine two-walk comparison rather than a restatement of the generator's own output.

## Notes

The coverage and determinism assertions run the CLI-materialising subprocess several times; the module-scoped `cli_tree` fixture amortises most of it. Full module runs in ~33s.
