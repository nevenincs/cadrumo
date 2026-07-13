---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S40'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S40 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Update the split-companion install probe and wheel globs and ## Scope

- `dev/packaging/smoke_split_install.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the split-companion install probe and wheel globs

## Scope

- `dev/packaging/smoke_split_install.py`

## Description

- Retarget the slim distribution, companion project directories, wheel globs,
  archive prefixes, runtime imports, and install hint to Cadrumo machine
  identities while invoking the sole human `aeat` executable.
- Preserve `aeat_official` only as the authority-owned official corpus partition.
- Strip inherited `CADRUMO_*` settings from every installed-product runtime child and provide isolated temporary storage and SQLite settings.
- Build the real root, manuals, and official wheels and install them into a fresh stdlib virtual environment under a bounded command budget.
- Prove the installed wheel exposes `aeat`/`aeat.exe` and no human `cadrumo` alias.

## Outcome

The split-install lane expects the `cadrumo` runtime wheel and the
`cadrumo-data-manuals` and `cadrumo-data-official` companion wheels from their
canonical project directories. Their archive globs are
`cadrumo_data_manuals-*.whl` and `cadrumo_data_official-*.whl`; both companions
join the `cadrumo_data` namespace. The slim-wheel leak check targets
`cadrumo/_data/corpus`, runtime probes import `cadrumo`, and installed command
probes invoke exactly `aeat` on POSIX or `aeat.exe` on Windows. The real-wheel
test also proves that no `cadrumo`/`cadrumo.exe` human alias is installed.

## Notes

- The root-wheel-only real install test proves `aeat`/`aeat.exe` exists and no
  `cadrumo`/`cadrumo.exe` human alias is installed. Ruff, formatting, Ty,
  former-identity classification, and scoped diff checks pass.
- S35 independently passed all five real-wheel partition tests for the same manuals and official companion projects, including byte membership, disjoint/exhaustive ownership, shared namespace, version parity, and file-cap checks.
- The lane retains `aeat_official` only for the authority-owned official corpus
  partition; it is not a product or executable alias.
- The combined root-plus-two-companion real-wheel test was attempted with a
  five-minute bound and timed out before reporting completion. This is bounded
  incomplete companion acceptance evidence, not a passing run and not a
  failure of the human-script assertion isolated above.
