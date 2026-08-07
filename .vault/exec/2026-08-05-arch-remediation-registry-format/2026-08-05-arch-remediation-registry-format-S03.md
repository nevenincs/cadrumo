---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8db1d8805e97ce7f73ad2c36b2baff7107131f236c5bf9410face6314fd33bf8'
step_id: 'S03'
related:
  - "[[2026-08-05-arch-remediation-registry-format-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-registry-format with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-08-05-arch-remediation-registry-format-plan placeholders are machine-filled by
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
     The Record in the workbook parity gate docstring that section order is deliberately unasserted, so a future reader does not re-add the claim from the rule history and ## Scope

- `src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_parity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Record in the workbook parity gate docstring that section order is deliberately unasserted, so a future reader does not re-add the claim from the rule history

## Scope

- `src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_parity.py`

## Description

- Add a docstring to the workbook parity gate naming the three properties it enforces.
- State that section order is deliberately unasserted, and why a reader should not re-add it.

## Outcome

The gate now documents its own scope at the point where a future reader meets it.
The paragraph names the omission explicitly and gives the reason it is an omission
rather than a gap: section is presentation, the casilla set and numbering are the
properties that must mirror the official modelo, and both are gated above.

It also records that a project rule previously claimed this gate enforced section
order and that the claim was corrected rather than satisfied - so a reader who
finds that history does not treat it as authority to add the assertion.

## Verification

The gate still passes with the docstring in place:

    uv run --no-sync pytest -q -p no:randomly src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_parity.py
    9 passed in 16.35s

## Notes

Docstring only; no assertion was added or removed, so the gate's behaviour is
unchanged and the 9-test result is the same selection as before the edit.
