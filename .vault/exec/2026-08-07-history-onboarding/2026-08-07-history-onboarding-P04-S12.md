---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:fd2790e4d66a0a6f5f08ee9ec83d5d3bad59b6632d4f47455c4d33ceff3d713d'
step_id: 'S12'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace history-onboarding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
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
     The land real es, en, ca and hu values for every new help string, Notice message key and result-field label the P01 through P03 verbs introduce, verified by dev.locales scaffold --check, gated on the shared locale catalogues being free of unrelated in-flight writes before landing and ## Scope

- `src/cadrumo/locales` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# land real es, en, ca and hu values for every new help string, Notice message key and result-field label the P01 through P03 verbs introduce, verified by dev.locales scaffold --check, gated on the shared locale catalogues being free of unrelated in-flight writes before landing

## Scope

- `src/cadrumo/locales`

## Description

- Land real es, en, ca and hu values for all eleven new keys the P01 through P04 surfaces introduce.

## Outcome

Eleven keys across the CLI help, the operator help surface, the run advisories,
the denominator notes and the overview nudge, each with a real translation in all
four catalogues. No key echoes its own name and none was left to a scaffold
placeholder.

## Verification

src/cadrumo/locales/es.yml: +34 -0
    src/cadrumo/locales/en.yml: +29 -0
    src/cadrumo/locales/ca.yml: +33 -0
    src/cadrumo/locales/hu.yml: +30 -0
    COMMITTED 269b3be338

Verified at HEAD after landing: all four catalogues carry all eleven keys with
non-placeholder values.

## Notes

The catalogues are under continuous concurrent write, so every value was applied
through the locale tool's own batch API against a scratch copy of the HEAD blobs
and never against the working copy. That mattered: two earlier attempts would have
DELETED peer content — a `deudas` help block, two ledger-establishment refusal
messages — because the blob was derived from a HEAD snapshot minutes stale. The
landing now rebuilds from HEAD and refuses on any removed line, in the same
command as the commit.

The zero-removal check itself had to be fixed: built naively it rebuilt a
60,000-element set per line and hung for eleven minutes on a 3 MB catalogue.
