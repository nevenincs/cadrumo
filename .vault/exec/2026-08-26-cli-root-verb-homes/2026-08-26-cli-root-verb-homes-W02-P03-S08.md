---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:14573a40d4b96ec40543db0bf6e793c6b65a207198994643483cd622d1c02597'
step_id: 'S08'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Re-key the four envelope command identifiers and their result schemas

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_payloads.py`
- `verify:` `pytest operator_surface/tests + transport locus gate` -> `pass`
