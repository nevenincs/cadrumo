---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S18'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P04.S18 scaffold seeded modelo locale files through CLI

Scope: `src/aeat/_data/registry/aeat/modelos`.

## Description

- Scaffold existing seeded schema-local locale files for M100, M130, M200, and M303 in `ca`, `en`, and `hu` through `python -m aeat.locales modelo scaffold`.
- Preserve Spanish schema labels as the official fallback; do not create Spanish schema-local TOML files.
- Fix revision-local all-revision deduplication so repeated casilla ids across revisions do not make selected-revision translations look stale.
- Restore M100 seeded translated leaves through `python -m aeat.locales modelo set` after the scaffold regression exposed the deduplication bug.
- Re-run the full seeded scaffold set and confirm it is idempotent.

## Outcome

Seeded schema-local locale files are now aligned by the modelo locale CLI. M100 has placeholder coverage for the full 2024 schema while preserving the existing translated M100 leaves. M130 remains complete. M200 and M303 have full placeholder scaffolds while preserving their existing translated leaves.

## Notes

The initial S18 scaffold exposed a manager bug: `inventory_keys(modelo_id)` deduped revision-local keys without including `revision_id`, so M100 revision-local seeded translations were treated as stale when the same casilla ids appeared in other revisions. The manager now includes `revision_id` in revision-local inventory identity, and a regression test covers this case.

Focused evidence: M100 scaffold became idempotent after the fix; M100 coverage reports `3/2068` translated labels and help for each seeded non-Spanish locale; M130 coverage remains `20/20`; M200 and M303 retain their `2/...` translated seeded leaves with placeholders for the rest. Registry locale parity tests passed after restoration.
