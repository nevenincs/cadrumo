---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S19'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---




# Assess loader fragment compiler extraction boundaries

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Inspect current `_loader.py` diff before touching any loader code.
- Enumerate loader classes, public functions, fragment merge helpers,
  catalogue loaders, source discovery helpers, and cache fingerprint helpers.
- Record the fragment-compiler extraction boundary in a vault audit.
- Leave `_loader.py` untouched because it carries peer formatting WIP.

## Outcome

- Fragment compiler extraction boundary identified: manifest/revision fragment
  merge helpers can move behind a private helper module without changing public
  loader semantics.
- Public loader spine, catalogue loading, source discovery, and cache
  fingerprinting should remain in `_loader.py` for now.
- Vault body-link, frontmatter, and plan checks passed.
- `P04.S19` is complete.

## Notes

- `_loader.py` is dirty in the shared worktree with formatting-only changes.
  This slice did not stage or edit that file.
