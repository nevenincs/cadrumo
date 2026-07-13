---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S64'
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
     The S64 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Update Spanish product locale messages through the locales CLI and ## Scope

- `Spanish locale catalogue` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update Spanish product locale messages through the locales CLI

## Scope

- `Spanish locale catalogue`

## Description

- Audit the existing Spanish catalogue WIP by product-versus-authority referent.
- Route every catalogue mutation through `python -m cadrumo.locales set es KEY VALUE` under isolated state roots.
- Rename product commands, settings, storage names, headings, and recovery guidance to Cadrumo.
- Preserve AEAT authority, legal, portal, registry, credential, and evidence-kind vocabulary.

## Outcome

The Spanish catalogue contains 202 semantic product-identity updates, including
the adopted Google Drive state refusal leaf, and no former product command or
executable guidance remains. YAML loading, locale integrity, inter-locale key
parity, and locale CLI round-trip tests pass.

## Notes

The locale CLI audit and scaffold check still report the same 30 missing keys
in every locale; S67 owns that scaffold regeneration. The repository-wide
translation-honesty test also remains red on eight excess Hungarian-to-English
identical values, outside the Spanish scope. No scaffold or honesty allowlist
was edited.

One CLI batch encountered a value beginning with `--binding`; the remaining
atomic updates were resumed using the CLI's `--` argument separator. A later
bounded batch timeout left completed leaves intact, and the final sixteen
residual leaves were applied through the same CLI.
