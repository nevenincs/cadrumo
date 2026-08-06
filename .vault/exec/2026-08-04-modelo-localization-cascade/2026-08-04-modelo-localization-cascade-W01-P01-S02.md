---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:82a7bb5225bfe072b7463f69e624de0c5b21cc26f7db510d1a9883b517e9822d'
step_id: 'S02'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

# Extract the current resolved localization matrix without mutating production data

## Scope

- `dev/registry/migration`

## Description

- Re-ground the extraction contract with \`vaultspec-rag\` code and Vault searches.
- Read the current loader's locale compiler and public registry boundary.
- Add strict immutable records for every resolved locale/field coordinate.
- Extract through the real loader with before/load/after corpus drift checks.
- Add real bundled-corpus tests for resolution precedence, fallback, completeness, and no mutation.

## Outcome

Implemented the read-only resolved localization matrix in \`dev/registry/migration\`.
The matrix is bound to the S01 corpus fingerprint and contains all supported
\`modelo/revision/casilla/locale/field\` coordinates:

- 73 modelos and 90 supported revisions.
- 15,774 casilla occurrences.
- 126,192 deterministic rows across \`es\`, \`en\`, \`ca\`, and \`hu\`, with \`label\` and \`help\`.
- 42,108 localized values, 37,326 official-Spanish label fallbacks, and 46,758 absent help values.
- Current corpus fingerprint \`0798a5518e615ee7d52e251f581f2522219ee83fe7d4561b89bd89d1cc9e025e\`
  over 16,519 TOML files, 24,849,174 bytes, and 281 locale files.

Modified files:

- \`dev/registry/migration/__init__.py\`
- \`dev/registry/migration/manager.py\`
- \`dev/registry/migration/tests/test_localization_matrix.py\`
- \`.vault/reference/2026-08-04-modelo-localization-cascade-reference.md\`
- \`.vault/exec/2026-08-04-modelo-localization-cascade/2026-08-04-modelo-localization-cascade-W01-P01-S02.md\`
- \`.vault/plan/2026-08-04-modelo-localization-cascade-plan.md\`
- \`.vault/audit/2026-08-04-modelo-localization-cascade-audit.md\`

## Notes

Focused validation passed:

- \`uv run --no-sync ruff format --check dev/registry/migration\`
- \`uv run --no-sync ruff check dev/registry/migration\`
- \`uv run --no-sync basedpyright dev/registry/migration\`
- \`uv run --no-sync pytest dev/registry/migration/tests -q -n 0 -m integration\` — 6 passed.

The loader was used only as a read path; source metadata and bytes remained
unchanged. No production schema, locale data, production reader, migration
output, or live registry was modified. Candidate classification and later
emission steps remain out of scope.
