---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:fd1cc5a6d7e6a8ceb111344bdf7e1bede8f990b35a38a2033c9862f22e6ef0b5'
step_id: 'S176'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enumerate canonical runtime inventory activities into deterministic atomic three-operation row cohorts

## Scope

- `src/cadrumo/application/aggregation/_inventory.py`

## Description

- Validate one complete 0177/0181/0182 inventory row-template cohort before reading storage.
- Load the encrypted inventory document once and expand complete 2025 activities in canonical lexical order.
- Project every activity through the sealed inventory projection and emit only row values plus typed row identities.
- Retain conflicts as value-free per-activity diagnostics and atomically refuse missing, unreadable, incomplete, or malformed sources.
- Harden the inventory ledger activity identity at its owning domain boundary against whitespace and control characters.
- Restore fake and real encrypted absence, success, conflict, corruption, tamper, determinism, confidentiality, and no-binding coverage.

## Outcome

The inventory resolver now expands the registry-owned three-operation template into one aligned row cohort per complete 2025 activity. All three operations share the same one-based row index, opaque activity identity, and sealed projection fingerprint without summing across activities.

Storage is read exactly once after template validation. Any incomplete cohort or source failure returns no partial values or identities. Independent review reported zero findings; 15 focused resolver tests and the broader 22-test resolver/projection selection passed, with Ruff and ty clean.

## Notes

Scope expanded minimally to the canonical `InventoryLedger` activity identifier because the domain previously admitted whitespace/control identities that the generic row identity correctly refused. S43 registry data and S177 downstream persistence proofs remain untouched.
