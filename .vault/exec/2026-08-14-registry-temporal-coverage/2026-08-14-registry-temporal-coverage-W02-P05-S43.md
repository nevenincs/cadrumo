---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:603f2bc0a670608cc993026598bf8c7b6107be9313c77bc9575f5a0f3c8a748a'
step_id: 'S43'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Correct Modelo 038 source-era scope: retain the 2024 dr038 design only from the June 2024 declaration, acquire and hash-pin an earlier official design before asserting the 2002-to-May-2024 window, and split the revision or source binding through the validated temporal authority without guessed coverage, legacy fallback, a filing-grade promotion, or an export layout.

## Scope

- `src/cadrumo/_data/registry/aeat/legal/modelo-038.toml`
- `src/cadrumo/_data/registry/aeat/modelos/038/revisions/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_038/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Register AEAT's `dr038_2005.pdf` through the canonical record-design corpus synchronizer and hash-pin its generated receipt.
- Remove the represented historical URL from the synchronizer exclusion list.
- Rebind the selected `dr038_2024.pdf` source to its June 2024 legal start and split selection into June--December 2024 and 2025 onward.
- Keep the historical receipt out of the modelo and revision source graphs; it carries neither an applicability window nor a design epoch.
- Preserve applicability grade and the absence of an export layout, then add source/selector mutation proof.

## Outcome

- The official historical PDF is bundled at 79,486 bytes with SHA-256 `e9008d9c0c407c76143d6997f3a5fb52a2a482c40571f395da7dcf8a8fee3d9d`, but does not assert a continuous predecessor window.
- M038 refuses all periods before June 2024, selects only the June 2024 source from June 2024 onward, and remains inspection-only/non-fileable.
- Verification passed: canonical corpus synchronizer offline check, M038 source-era mutation plus coverage-matrix tests, and scoped Ruff.
## Notes

- The historical index title and PDF metadata establish publication history only; neither provides the complete period applicability needed to select it.
