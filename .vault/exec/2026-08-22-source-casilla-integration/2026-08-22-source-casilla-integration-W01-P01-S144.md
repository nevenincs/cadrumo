---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:b93963ef7e5b418c7c68e36f75364237618a50915fe3116936dd407c2d73a39f'
step_id: 'S144'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# make repository evidence digest verification descriptor-safe against path replacement races

## Scope

- `src/cadrumo/application/registry`

## Description

- Open repository evidence once and hash bytes through that verified descriptor.
- Verify the operating-system final handle path, root containment, exact requested path, and regular-file type before reading.
- Reject malformed repository references, path traversal, replacement races, and leaf or intermediate link escapes.
- Exercise real-file, changed-content, non-regular, reparse escape, and controlled descriptor-substitution cases.

## Outcome

Repository evidence verification now fails closed unless the final path bound to the open descriptor is the exact root-contained file requested. Windows uses `GetFinalPathNameByHandleW`; Linux uses the descriptor link; unsupported platforms refuse verification.

## Notes

The adversarial replacement test substitutes the `os.open` request with a real descriptor for a different real file. Production still performs final-path, `fstat`, and byte hashing against that descriptor; no digest, descriptor metadata, or authority result is fabricated.

Focused registry authority tests passed with 23 cases. Ruff formatting and lint checks passed for both changed source files. The independent re-review reported no remaining findings. The feature-scoped Vault check passed with only the existing stale feature-index and empty generated Steps-section warnings.
