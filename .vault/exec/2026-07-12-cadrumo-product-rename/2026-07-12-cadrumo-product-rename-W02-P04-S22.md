---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S22'
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
     The S22 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Rename product bundle suffixes and reject former bundle formats and ## Scope

- `src/cadrumo sealed bucket archive writer/reader/header/service and focused storage/application/CLI tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename product bundle suffixes and reject former bundle formats

## Scope

- `src/cadrumo sealed bucket archive writer/reader/header/service and focused storage/application/CLI tests`

## Description

- Publish `.cadrumo-bucket.tar.gz` as the sole sealed profile-bundle suffix.
- Advance the sealed archive to schema v3 with a required canonical product marker.
- Bind encrypted payload associated data to the Cadrumo v3 archive identity.
- Refuse former suffixes before opening files and renamed former headers before payload reads.
- Update storage, application, custody, and CLI roundtrip examples and assertions.

## Outcome

The writer accepts only the Cadrumo suffix and emits a required `product: cadrumo` header at archive schema version 3. The reader rejects `.aeat-bucket.tar.gz` before opening it. A former archive renamed to the canonical suffix is rejected after reading only the first header member; payload members are not read or adopted. No refusal path migrates, auto-renames, unpacks, copies, or deletes the source.

Forty-five focused tests passed across header validation, roundtrip, crash windows, real service import/export, schema lineage, custody recovery, and CLI workflows. Sentinel tests prove former-suffix bytes and renamed former archive bytes remain unchanged and no canonical output is created. Ruff, formatting, compilation, and scoped diff checks passed.

## Notes

One broader custody-completeness run exposed an unrelated S21 natural-key resolver finding for `cadrumo.application.modelo.m145_communication_record`; the bundle-specific custody recovery test passed in the final focused run. Official AEAT filing/export formats and authority payload terminology were not changed.
