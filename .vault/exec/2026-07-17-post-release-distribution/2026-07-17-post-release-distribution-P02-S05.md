---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S05'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace post-release-distribution with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-17-post-release-distribution-plan placeholders are machine-filled by
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
     The DONE, Linux Python row green in push-to-main Cadrumo Packaging Smoke run 29657832151 at commit 1abbc48c72 (cohort build, installed grounded tax oracle DP200014:00562 = 23000.00, installed-oracles attestation suite), first fully green three-OS matrix and ## Scope

- `.github/workflows/packaging-smoke.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DONE, Linux Python row green in push-to-main Cadrumo Packaging Smoke run 29657832151 at commit 1abbc48c72 (cohort build, installed grounded tax oracle DP200014:00562 = 23000.00, installed-oracles attestation suite), first fully green three-OS matrix

## Scope

- `.github/workflows/packaging-smoke.yml`

## Description

- Run the cohort-bound installed-behavior oracle on the claimed Linux Python row in real CI.

## Outcome

The Linux Python row is green in the push-to-main Cadrumo Packaging Smoke run `29657832151` at commit `1abbc48c72` (in HEAD): the cohort build, the installed grounded tax oracle (`DP200014:00562 = 23000.00`), and the installed-oracles attestation suite all passed. This was the first fully green three-OS matrix. Closed against a real green CI run.

## Notes

Retroactive execution record; step already checked. Vault-only bookkeeping.
