---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:f3cd09deeb339483f22296468d00cc14fba805c1187375d1197703adc96a452e'
step_id: 'S67'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add path_stat_fingerprint as the path-keyed sibling of file_stat_fingerprint and converge the ten single-file loader call sites across eight modules onto it, excluding the justificante parser cache whose key is primarily a content digest rather than a path identity

## Scope

- `src/cadrumo/core/paths.py`

## Description

- Add `path_stat_fingerprint` in `core/paths.py` as the path-keyed sibling of `file_stat_fingerprint`.
- Converge 10 call sites across 8 files: user_profile schema, IVA rate table, recargo bands, the single-file category-profile loader, the manuals chapter-text reader, the four record-design extractors, the XML-dictionary text reader, and the pdfium declaración backend.
- Exclude `adapters/inbound/justificante/_parsers/__init__.py` as constraint-divergent (content-digest-primary cache key).

## Outcome

Landed in commit `ccb8af3ab6`. Two incidental findings called out in the commit but left for their own fix: `_export_parse.py`'s dual-Path cache-key mismatch (normalised here) and `_recargo.py`'s missing `@lru_cache` decorator (pre-existing, unrelated, untouched).

## Notes
