---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S17'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename product-owned settings and CADRUMO environment parsing while retaining authority settings

## Scope

- `src/cadrumo configuration consumers/tests`
- `dev configuration consumers`
- `env/.env.example`
- `packaging/mcpb/manifest.json`
- `.github/workflows`
- `justfile`
- `conftest.py`

## Description

- Ground the configuration boundary in the accepted S02 environment matrix, audit resolution, product identity, live settings model, and exact consumers.
- Expand the Step scope through the plan CLI to cover the cohesive configuration, consumer, test, workflow, packaging, and active-example surface.
- Rename every product-owned environment name and matching settings field or accessor by exact matrix membership.
- Preserve every authority-owned AEAT environment name and field, including authority endpoints, credentials, browser/session controls, and official-data settings.
- Retarget real configuration tests, developer controls, MCP controls, workflow variables, locales, and active environment examples without adding compatibility readers.

## Outcome

The hard cut is complete across the live tracked configuration surface. The 102 product-owned public controls now use the identical `CADRUMO_*` suffix; 97 of them are Settings fields named `cadrumo_*` and five remain direct non-Settings controls. All 49 authority-owned controls remain `AEAT_*` and `aeat_*`. The wallet diagnostic control is now `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` / `cadrumo_wallet_diagnostic_dump_dir`.

The controlled rewrite updated 423 files, comprising 642 exact environment-name occurrences and 1,634 exact field/accessor occurrences. A post-change matrix audit found 97 Cadrumo product fields, zero former product fields, all 49 retained authority fields, and zero retired product-name residue in the active tracked configuration surface. Direct isolated Settings checks proved that the former wallet variable has no effect while the Cadrumo variable is read.

## Notes

The user authorised preserving and cross-committing overlaps; exact token replacement retained all concurrent file content. The first focused pytest invocation was blocked at shared fixture setup because the ignored operator-local `env/.env` still contains five former product keys. Strict settings validation rejected those unknown keys before any test body ran. That secret-bearing local file was not read into evidence, edited, migrated, or committed. A clean-dotenv mirror then passed all 51 focused configuration and environment-loader tests. One checkout-root assertion initially selected installed mode because the mirror lacked a `.git` marker; it passed when rerun with the checkout marker present. The local operator must rename or remove the five private former controls before ordinary commands in this worktree can load that dotenv file.
