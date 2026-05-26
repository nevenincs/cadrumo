---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
step_id: 'S75'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-test-hygiene-audit]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `secure-storage-production-hardening` `W11.P19.S75`

Repaired secure-storage test shortcut coverage by removing platform skip gates from file-mode tests.

## Changes

- Replaced the blob materialisation `skipif` with a real behavior assertion that runs on every platform and checks POSIX mode bits only where POSIX mode semantics exist.
- Replaced the master-key file-mode `skipif` with the same platform-neutral pattern, staged as a narrow hunk to avoid folding unrelated in-flight master-key work into this step.
- Confirmed no `skipif` or `xfail` markers remain under secure-storage tests.

## Validation

- `uv run ruff check src\aeat\adapters\persistence\storage\blob_store\test_materialisation.py src\aeat\adapters\persistence\storage\master_key\test_master_key.py`
- `uv run pytest src\aeat\adapters\persistence\storage\master_key\test_master_key.py src\aeat\adapters\persistence\storage\blob_store\test_materialisation.py -q`
- `rg -n "skipif|xfail" src\aeat\adapters\persistence\storage -g "test_*.py"`
