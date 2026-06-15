---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S04'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Delete the temporary sensitive PDF helper and fold the bbox branch into the in-memory bytes path

## Scope

- `src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py`

## Description

- Collapse the bbox and non-bbox branches in
  `_observed_casillas_from_declaration_pdf` to one `parse_declaracion_bytes` call.
- Delete `_temporary_sensitive_pdf_path` and `_write_all_fd` plus their re-exports
  in `_declarations.py`, the test support module, and the direct unit test.
- Remove the now-stale `tempfile.mkstemp` / `os.write` entries from the
  sensitive-persistence-policy allowlist so the gate proves the disk path is gone.

## Outcome

No decrypted declaration bytes touch disk on any extraction branch. The
sensitive-persistence-policy gate passes with the allowlist entries removed
(245 passed across the declaracion + sede + policy suites); collect-only clean
across the touched trees. Committed in `25224b9e0`.

## Notes

Blast radius beyond the two scope files: the facade re-export, the test-support
re-export, the obsolete direct unit test, and the policy allowlist. All swept in
the same commit.
