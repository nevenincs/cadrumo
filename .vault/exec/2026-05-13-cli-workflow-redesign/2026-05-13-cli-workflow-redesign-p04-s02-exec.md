---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-07-31'
body_hash: 'sha256:76ff370a4aa32a7b966d8440b5e8ea181b2d2446e52d0bc52cd8b4505783696d'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P04.S02`

Confirmed the `secure_objects.integrity` warn branch already carries
`next_action="aeat config repair quarantine --yes"` from the P01
rename sweep. The ok branches (empty table and all-decryptable) stay
without a recovery field per the discriminated-union contract.

- Verified: `src/aeat/application/diagnostics.py::_secure_objects_integrity_check`

## Tests

Test `test_secure_objects_integrity_check_reports_unreadable_rows_from_rotated_master_key`
asserts the literal `aeat config repair quarantine --yes`; green
under the P04 run.
