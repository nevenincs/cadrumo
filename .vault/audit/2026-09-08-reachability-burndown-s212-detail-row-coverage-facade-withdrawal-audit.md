---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:993b6ea857fb30477837988c8c8c43e3869073855f1b63b880ad909922dcd250'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S212]]"
---

# `reachability-burndown` audit: `S212 detail row coverage facade withdrawal review`

## Scope

Independent bounded review of W05.P12.S212: removal of the production coverage facade/helper, test-owned union-to-identity-table comparison and mutation proof, retained runtime row identity/merge behavior, cadence guidance, and Step Record evidence.

## Findings

No findings.

Production retains `_ROW_IDENTITY_FIELDS` as the live dispatch authority plus its conservative fallback, union deduplication, and conflicting-row refusal behavior. Only the audit projection over that authority was removed. The test now derives the union population independently with `get_args(ModeloDetailRow)` and compares it to the live identity table; removing `Modelo184MemberRow` from a copied table proves the comparison detects an uncovered union arm. This preserves detector teeth without a duplicate production helper or any production dependency on tests/dev.

The complete focused file passes seven tests. The Step Record provides exact Ruff, focused pytest, residue, metastate, and reachability evidence; exact unused falls 315 to 314 while the 63-module, 15-orphan, and 2028/2092 graph remains stable.

## Recommendations

Approve W05.P12.S212. No code or evidence correction is required.
