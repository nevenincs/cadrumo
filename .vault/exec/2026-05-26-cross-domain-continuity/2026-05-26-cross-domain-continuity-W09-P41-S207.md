---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:577aa404d7bcc7eb779310fcad0e692eb5a44ff91fb2e816bca195d6ef71185b'
step_id: 'S207'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# add inline comment in _command_matches_current confirming attachment_ids equality is value-equal not identity-equal

## Scope

- `pydantic-frozen collection safety note`
- `Wave-1 audit FU-E`
- `src/aeat/application/ledger/_actions.py`

## Description

- Reconciles the checked historical S207 row against the direct evidence named in the related reconciliation audit.
- Adds no production-source change.

## Outcome

- Restores the one-Step/one-record traceability edge for this historical checked row.
- The related audit names the exact supporting audit, execution record, or commit evidence.

## Notes

- This record asserts no new implementation or re-run verification; it records evidence reconciliation only.
