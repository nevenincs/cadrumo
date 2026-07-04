---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S11'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-workflow-redesign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Add Modelo 145 registry TOML using only source-backed communication, validation, and export authority and ## Scope

- `registry/aeat/modelos` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add Modelo 145 registry TOML using only source-backed communication, validation, and export authority

## Scope

- `registry/aeat/modelos`

## Description

- Inspect the current Modelo 145 registry scaffold without modifying it.
- Re-run registry-authority load and collect-only gates that are blocking the D9 binding-closure plans.
- Record why the current scaffold cannot close `P03.S11` or unblock downstream D9 verification in this pass.

## Outcome

- `P03.S11` remains unchecked.
- Current untracked Modelo 145 registry files declare the modelo manifest, one revision, and communication/payer-delivery/export application links, but no casilla definitions and no workbook parity reference.
- Registry authority load still fails before unrelated modelo snapshots can resolve:
  `modelo 145 revision 2012-01-31-y-siguientes: revision must declare official workbook parity coverage`
  and `revision must declare at least one casilla`.
- Full collect-only is still red for the same registry-validation failure:
  `uv run --no-sync pytest --collect-only -q` wrote full output to
  `C:\Users\hello\AppData\Local\Temp\aeat-goal-current-collect-20260704.log`
  and exited `2` (`12103/14810 tests collected`, `2707 deselected`, `8 errors`).
- The D9 resolver proof slice is still red because `resources().modelos.authority`
  fails before M349/M720 assertions can run:
  `uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests/test_per_modelo_service.py -k "counterpart or foreign_asset or foreign_assets or m720 or 720"`
  (`2 failed`, `3 passed`, `19 deselected`).
- Locale audit is clean at the same observed state:
  `uv run --no-sync python -m aeat.locales audit` reports `ok` for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

## Notes

- No Modelo 145 source files were edited. The registry scaffold is untracked shared WIP, so this pass treats it as non-authored and does not take ownership.
- Completing `P03.S11` requires an owned registry TOML landing with source-backed casillas and official workbook parity coverage, then a clean registry-authority load.
- No plan check was run for `P03.S11`.
