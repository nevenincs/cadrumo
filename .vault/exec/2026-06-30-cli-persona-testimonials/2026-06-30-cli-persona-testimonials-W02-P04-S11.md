---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:28bd00dff7105acd56f301a1138501739586880ec00db007b9d4fc0fe1b28f1d'
step_id: 'S11'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Exercise corpus import-export roundtrip without permissive imports

## Scope

- `src/aeat/entrypoints/cli/tests/test_ledger_corpus_import_export.py`

## Description

- Replace permissive corpus export re-import assertions with explicit refusal or
  no-phantom-row behavior for canonical ledger exports.
- Verify that JSONL and canonical CSV exports do not enter the raw bank provider
  as successful imports.
- Keep restore semantics out of the bank-import surface.

## Outcome

`src/aeat/entrypoints/cli/tests/test_ledger_corpus_import_export.py` now asserts
the stricter corpus import/export boundary. Canonical ledger exports are not
accepted as raw bank statements, and failed re-imports leave the active row count
unchanged.

## Notes

The focused ledger test set reported 62 passed and 7 deselected after all W02.P04
corrections.
