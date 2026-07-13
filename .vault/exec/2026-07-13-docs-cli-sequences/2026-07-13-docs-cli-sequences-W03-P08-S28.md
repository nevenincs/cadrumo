---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S28'
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
     The S28 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Verify the docs build check surface and the pytest gate both red on an injected golden divergence and both pass green on clean goldens and ## Scope

- `dev/docs/tests/test_sequence_goldens.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the docs build check surface and the pytest gate both red on an injected golden divergence and both pass green on clean goldens

## Scope

- `dev/docs/tests/test_sequence_goldens.py`

## Description

- Add `TestBothSurfacesRedOnDivergence` plus isolated-fixture helpers to `dev/docs/tests/test_sequence_goldens.py`: write a tmp docs tree with one `cli-sequence` page, refresh its correct golden, then inject a divergence by rewriting frame 0's exit code to a value live never emits.
- Build surface: build the fixture page in-process through a fixture Sphinx conf that registers the directive and connects the SAME `check_sequence_goldens` gate the real `docs/conf.py` wires; assert `SphinxError` naming the divergence and the `python -m dev.docs.sequences refresh` remedy.
- Pytest surface: assert the engine `check_sequences` reds on the same fixture, and the CLI `check` mode exits 1 printing the divergence and the refresh remedy to stderr.
- Green control: with the correct golden, assert `check_sequences` is clean AND a real Sphinx build succeeds and renders the sequence container.

## Outcome

Both gate surfaces are proven to red on an injected golden divergence and pass green on clean goldens, over one shared execution path. The build-surface test drives the production `check_sequence_goldens` hook (not a copy), and the pytest surface exercises both the `check_sequences` function the S27 gate uses and the CLI check mode CI runs without a full docs build. The fixture tree is fully isolated under tmp; the committed `docs/` tree is never mutated. All 9 tests in the module pass (`-m "integration and docs"`) in ~11.5s; ruff and ty clean.

## Notes

The divergence is injected as a non-masked field (frame exit code) so the real compare path reports it deterministically rather than being hidden by `GOLDEN_MASK_FIELDS`. The build surface halts at `builder-inited` (before the read phase), so a value-divergent golden reds via the executing check hook even though the directive itself only renders from the golden without executing.
