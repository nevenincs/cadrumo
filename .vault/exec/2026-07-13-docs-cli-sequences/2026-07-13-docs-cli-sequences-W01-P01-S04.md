---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S04'
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
     The S04 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Verify the full documented-command conformance gate passes green and pytest collect-only is clean and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the full documented-command conformance gate passes green and pytest collect-only is clean

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`

## Description

- Add an anti-vacuity tripwire test (`test_gate_scans_a_realistic_invocation_count`) asserting the parsed-invocation count across the doc surface is at or above a `_VACUITY_FLOOR` of 200 (observed ~591), so a re-swept anchor fails loudly instead of passing a vacuous suite.
- Run the full documented-command gate, the reconciled sibling gate, `ruff`, `ty`, and `pytest --collect-only` over the CLI tests directory.

## Outcome

- Documented-command gate: green, 61 passed (60 prior + the new tripwire).
- Sibling self-referential-string gate: green, 8 passed after reconciliation; both gates together 69 passed.
- `ruff check` and `ty check` clean on both edited modules.
- `pytest --collect-only -q` clean across the CLI tests directory: 2319 tests collected, no collection errors (the earlier `ImportError` from the renamed symbol is resolved).

The static conformance floor is honest and non-vacuous, and the vacuity regression cannot recur silently: the floor test reds if the anchor is ever swept off `aeat` again.

## Notes

The tripwire floor is set well below the observed count and well above zero deliberately — a vacuity tripwire, not a brittle exact assertion, so ordinary doc churn never trips it while a re-broken anchor does.
