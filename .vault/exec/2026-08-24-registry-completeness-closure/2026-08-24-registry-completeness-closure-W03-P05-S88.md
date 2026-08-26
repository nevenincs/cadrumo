---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:416b31da8e84b2657daceec1f8b96146e4f53ca041187d7fabc92a855c2a866c'
step_id: 'S88'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Repair corpus localization drift introduced by the Modelo 165 and 353 revision splits by moving only legally corresponding revision subtrees through the dev.locales CLI, authoring every newly required Spanish source value and all supported-locale leaves, removing stale revision identities, and rerunning runtime, parity, and translation-honesty gates

## Scope

- `dev/locales/`
- `src/cadrumo/locales/`
- `dev/locales/tests/`

## Description

- Ground the locale move authority, revision scanner, canonical runtime resolver, and current Modelo 165 and 353 revision declarations.
- Inspect the split commits and dry-run every proposed move before mutation.
- Move Modelo 165 `2013-y-siguientes` across its four legal successor revisions through `python -m dev.locales move-revision`.
- Move Modelo 353 `2008-2025` only to `2021-2025` and `2026-y-siguientes` only to `2026-desde-02`, retaining the separate historical and 2026 source values.
- Run the runtime-localization, revision-parity, translation-honesty, and scaffold-drift gates sequentially.

## Outcome

- All three moves were lossless: 616 cross-catalogue leaf writes and 432 released stale leaves, with no overwrite, conflict, skipped leaf, or undistributed source leaf.
- The four catalogue shards retain authored Spanish source text and real English, Catalan, and Hungarian translations; no key echo or identical-value exemption was added.
- `test_modelo_revision_locale_key_parity.py` passed all 10 checks. `python -m dev.locales scaffold --check` reported all four catalogues `ok`.
- The pre-existing Modelo 165 and 353 stale revision identities are gone, and their current legal revision identities are present.

## Notes

- The aggregate runtime gate ran 5 checks with 4 passing; its sole failure contains 14,028 missing Spanish Modelo 200 `2025-y-siguientes` values from concurrent M200 work. This Step neither owns nor changes Modelo 200.
- The translation-honesty gate ran 6 checks with 4 passing. Its two failures are the same concurrent Modelo 200 source-value gap (3,510 leaves) and three pre-existing Modelo 309 Spanish-identical Catalan/Hungarian values. This Step neither owns nor changes Modelo 309.
