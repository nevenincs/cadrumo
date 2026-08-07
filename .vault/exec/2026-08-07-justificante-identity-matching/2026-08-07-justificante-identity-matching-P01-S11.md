---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:aeffdb95e86bd4f61f17a4e67067b0fd69044be394dafe5bc4a6f3931e055f47'
step_id: 'S11'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Confirm extract_csv_from_url already resolves through the sede package public facade before landing S01, promoting it only if a fresh HEAD read shows it missing

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/__init__.py`

## Description

A fresh HEAD read showed `extract_csv_from_url` defined and `__all__`-exported in
`_declarations_remote.py`, but absent from the sede package's `__init__.py` - so
the row's conditional applied and the promotion was needed rather than merely
confirmed. Semantic search confirmed it is the sole canonical CSV-from-URL reader
in the tree and that exporting it shadows no existing facade name.

## Outcome

Added the `from ._declarations_remote import extract_csv_from_url` line and the
matching `__all__` entry. The function itself is unchanged: only where the symbol
is reachable from moved, not when it executes.

Also corrected the module docstring, which enumerated the helper's consumers as
`_declarations.py` and `_parse.py`; it now records that the symbol is reachable
through the package facade for a consumer outside the adapter.

## Verification

`extract_csv_from_url` imports from the package facade and returns the CSV from a
cotejo document URL. `ruff check` and `ty check` clean on both files.

## Notes

No `__all__` baseline file exists for this package, so nothing else needed
updating alongside the export.
