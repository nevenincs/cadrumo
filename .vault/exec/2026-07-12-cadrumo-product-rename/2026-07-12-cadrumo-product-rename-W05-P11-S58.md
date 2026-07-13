---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S58'
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
     The S58 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Retarget CI source paths and named product jobs and ## Scope

- `.github/workflows/ci.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retarget CI source paths and named product jobs

## Scope

- `.github/workflows/ci.yml`

## Description

- Verify the production workflow retains Cadrumo-owned labels and source paths
  while invoking `aeat` as the sole human CLI.
- Replace the blanket `aeat` token ban with exact registry-command assertions.
- Reject former product distribution, import, package, and source identities,
  and reject any `cadrumo` human executable alias.

## Outcome

The primary CI workflow remains `Cadrumo CI`, with Cadrumo-owned job identity
and `src/cadrumo` source paths. Its two registry commands invoke the sole human
CLI exactly as `uv run --no-sync aeat ...`. The structural gate permits those
contractual executable uses while rejecting `cadrumo` in executable position
and former `aeat` product/package/source identities.

## Notes

Direct YAML parsing, Ruff formatting and lint, Ty, two real workflow structure
tests, plan validation, and scoped diff validation passed. The production CI
workflow required no edit. Justfile, documentation, release runbooks, and other
workflow files were excluded.

## Reopened (2026-07-13, bookkeeping audit)

This Step was reopened during the W06.P14.S76 residue audit. Reinspection found
that the production workflow already used `aeat` for both registry commands;
the stale record described superseded bytes. The remaining defect was the test's
contradictory blanket assertion that no `aeat` token could appear despite its
own exact `aeat` command requirements. The referent-aware structural gate now
closes that defect without weakening former-identity or dual-executable checks.
