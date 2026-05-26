---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
step_id: 'S72'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-exception-hierarchy-audit]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `secure-storage-production-hardening` `W11.P18.S72`

Repaired and verified secure-storage exception hierarchy coverage.

## Changes

- Adopted the in-flight bucket lifecycle error repair so `BucketError` derives from `SecureStorageError`, keeping bucket lifecycle failures inside the secure-storage catch family.
- Ensured bucket lifecycle errors render from registered `translated_message` keys rather than literal constructor strings.
- Re-ran central registry enforcement to confirm every imported `AeatError` subclass still binds exactly one registry code.

## Validation

- `uv run ruff check src\aeat\adapters\persistence\storage\errors.py src\aeat\adapters\persistence\storage\bucket\_errors.py src\aeat\adapters\persistence\storage\test_errors.py src\aeat\core\errors\test_registry_enforcement.py`
- `uv run pytest src\aeat\adapters\persistence\storage\test_errors.py src\aeat\adapters\persistence\storage\bucket\test_bucket_errors.py src\aeat\core\errors\test_registry_enforcement.py -q`
