---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S27'
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
     The S27 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Wire the pytest gate calling the same engine check functions so CI catches golden drift without a full docs build and ## Scope

- `dev/docs/tests/test_sequence_goldens.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Wire the pytest gate calling the same engine check functions so CI catches golden drift without a full docs build

## Scope

- `dev/docs/tests/test_sequence_goldens.py`

## Description

- Extend `dev/docs/tests/test_sequence_goldens.py` with `TestCommittedGoldensCleanGate`, importing the facade `check_sequences` and calling it unscoped over the committed `docs/` tree.
- Assert the returned problem tuple is empty; on failure print every problem verbatim (each already names page, sequence, frame, argv, and diff).
- Leave the existing S18 executor mask-honesty tests untouched.

## Outcome

The pytest half of the two-surfaces-one-engine gate now catches golden drift on the same `check_sequences` execution path the Sphinx `builder-inited` hook wires, without a full docs build. Passes green (`-m "integration and docs"`, the module's marker lane) in ~4.5s with zero enrolled sequences today; scales with the enrolled surface as sequences land.

## Notes

The module carries `pytest.mark.integration`; the default addopts marker filter deselects it unless `-m integration` is passed, matching the existing S18 tests' CI lane.
