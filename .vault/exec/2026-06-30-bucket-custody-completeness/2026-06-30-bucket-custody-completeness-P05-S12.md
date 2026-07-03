---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S12'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Wire the cleartext config profile export and import to the structured-only profile and extend the export notice to name the sealed archive as the full backup

## Scope

- `src/aeat/entrypoints/cli/_config/_profile_bundle.py`

## Description

- Keep cleartext `config profile export` on the structured custody profile.
- Emit the not-a-full-backup warning naming the encrypted recovery archive as the complete backup path.
- Validate structured import through the same current bundle schema gate.
- Harden CLI profile bundle command imports to source modules.

## Outcome

- Complete. Cleartext profile export does not carry generic secure-object bytes and tells the operator it is partial.
- Verified by CLI integration tests and direct-source import scan.

## Notes

- The structured manifest now records populated excluded namespaces and row counts, so the test asserts the concrete partial-transport contract.
