---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:7ce3a2826c6458f994e2d73947bce8d201ac6debd62ec4e312d952e992940f88'
step_id: 'S02'
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
     The S02 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Extract the current resolved localization matrix without mutating production data and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extract the current resolved localization matrix without mutating production data

## Scope

- `dev/registry/migration`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

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

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Focused validation passed:

- \`uv run --no-sync ruff format --check dev/registry/migration\`
- \`uv run --no-sync ruff check dev/registry/migration\`
- \`uv run --no-sync basedpyright dev/registry/migration\`
- \`uv run --no-sync pytest dev/registry/migration/tests -q -n 0 -m integration\` — 6 passed.

The loader was used only as a read path; source metadata and bytes remained
unchanged. No production schema, locale data, production reader, migration
output, or live registry was modified. Candidate classification and later
emission steps remain out of scope.
