---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:af7ca9b355f6441c8fd05aa8ec8b61f3a8ef59841e7eec0cb05e76bf40ff2746'
step_id: 'S03'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-localization-cascade with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Generate canonical occurrence candidates from model, revision, casilla, and field identity and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Generate canonical occurrence candidates from model, revision, casilla, and field identity

## Scope

- `dev/registry/migration`

## Description

- Re-ground canonical identity rules with `vaultspec-rag` and the accepted ADR.
- Read the canonical `CasillaDefinition.id` and `continuidad_id` contracts.
- Generate immutable candidates from the resolved S02 matrix.
- Serialize grounded continuity addresses or exact revision-occurrence addresses only.
- Add real bundled-corpus tests for exact, grounded, locale-independent, and compound-id keys.

## Outcome

Implemented deterministic canonical occurrence candidates in `dev/registry/migration`.
Each candidate preserves the source Modelo, revision, casilla, locale, field,
resolved value, and loader resolution state, then derives exactly one logical
address:

- `modelo/<modelo-id>/casilla/continuidad/<continuidad-id>/<field>` for a declared continuity id.
- `modelo/<modelo-id>/revision/<revision-id>/casilla/<casilla-id>/<field>` otherwise.

The candidate set remains bound to the S02 corpus fingerprint and contains
126,192 rows over 15,774 occurrences. Locale is deliberately not part of the
semantic key, and no repeated-id, printed-number, label, or text inference is
performed.

Modified files:

- `dev/registry/migration/__init__.py`
- `dev/registry/migration/manager.py`
- `dev/registry/migration/tests/test_canonical_candidates.py`
- `.vault/reference/2026-08-04-modelo-localization-cascade-reference.md`
- `.vault/exec/2026-08-04-modelo-localization-cascade/2026-08-04-modelo-localization-cascade-W01-P01-S02.md` (Vault body re-attestation)
- `.vault/exec/2026-08-04-modelo-localization-cascade/2026-08-04-modelo-localization-cascade-W01-P02-S03.md`
- `.vault/plan/2026-08-04-modelo-localization-cascade-plan.md`
- `.vault/audit/2026-08-04-modelo-localization-cascade-audit.md`

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Focused validation passed:

- `uv run --no-sync ruff format --check dev/registry/migration`
- `uv run --no-sync ruff check dev/registry/migration`
- `uv run --no-sync basedpyright dev/registry/migration`
- `uv run --no-sync pytest dev/registry/migration/tests/test_canonical_candidates.py -q -n 0 -m integration` — 2 passed.

The first focused run exposed a valid colon-bearing compound casilla id in
Modelo 200. Logical canonical-key validation was separated from filesystem
fingerprint path validation so that source identity is preserved exactly.
Production schemas, locale data, readers, migration output, and the live
registry were not modified.
