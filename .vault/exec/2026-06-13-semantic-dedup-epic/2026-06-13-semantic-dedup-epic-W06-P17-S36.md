---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S36'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S36 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C1 Sweep the inline strict-frozen ConfigDict literal tail onto STRICT_FROZEN_CONFIG and ## Scope

- `src/aeat/core/_models.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C1 Sweep the inline strict-frozen ConfigDict literal tail onto STRICT_FROZEN_CONFIG

## Scope

- `src/aeat/core/_models.py`

## Description

- Scripted (dry-run-reviewed) the conversion of inline `model_config =
  ConfigDict(strict=True, frozen=True, extra="forbid")` to
  `model_config = STRICT_FROZEN_CONFIG` across 106 peer-clean modules
  (236 occurrences), adding the relative core import per module; the script
  skipped peer-dirty files and core/ files, and the regex matched only the
  exact canonical shape (extra-key configs untouched).
- `ruff --fix` dropped the now-unused `ConfigDict` imports and merged/sorted
  the core imports.
- Fixed three residuals by hand: `_calc_sheets_pull` imports the canonical
  aliased (`as _STRICT_FROZEN`) so its converted lines point at the alias; the
  two `contribuyente/*/__init__.py` had `ConfigDict` left in their import
  (ruff does not auto-strip `__init__` imports).

## Outcome

Committed as `8401ce4cf`, tagged `relocation:STRICT_FROZEN_CONFIG` (106 files,
+444/-377). Ruff clean across all changed files; full collect-only clean
(15,479 collected); 1086 representative domain tests pass. Behaviour-identical
(STRICT_FROZEN_CONFIG IS that exact ConfigDict).

## Notes

Two `test_llm_split_schema.py` failures are peer churn in the actively-edited
`application/ledger/_llm_classification.py` (peer-dirty, NOT in my C1 set; the
split-schema validation is mid-edit by a peer) — same LLM surface as the
earlier `vision_model` failure. Not caused by this behaviour-identical config
swap. Commit isolated via explicit owned-file pathspec; the sweep skipped all
dirty files at apply time so every committed file's diff is mine.
