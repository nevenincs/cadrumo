---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:3bbc492dd0e838b758fb96d28b62f0a9475d4c34ad66717c0c313655b83763ca'
step_id: 'S02'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Raise an instructive localised conflict error when a stored row exists for the same idempotency key but the command content differs, naming the conflicting field set

## Scope

- `src/aeat/application/ledger/_actions_manual.py`

## Description

- Raise an instructive, localised `TransactionValidationError` when the supplied idempotency key names an already-stored row whose content differs from the command, the `idempotent_guarded` conflict arm.
- Carry the translated message `application.ledger.errors.idempotency_key_conflict`, added across the `en`, `es`, `ca`, and `hu` locale catalogues, naming the recovery (use a new key, or omit the key to append a deliberate duplicate).

## Outcome

Landed in commit `8349fc8b3`. A recycled key over different content now refuses loudly instead of a silent last-wins overwrite.

## Notes

Code authored by a teammate and committed before this task was reassigned; this record documents the landed change. The conflict-refusal behaviour proof lands under Phase `P05` (`S14`).
