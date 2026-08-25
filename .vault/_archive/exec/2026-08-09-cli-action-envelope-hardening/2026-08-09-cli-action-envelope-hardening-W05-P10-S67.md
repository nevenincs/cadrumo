---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d054fadd4b86ff677e041a76545d39342afdaf325843d41eb454909d1c79fa4f'
step_id: 'S67'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate inbound censo parse-refusal action producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/adapters/inbound/censo/_parser.py`

## Description

- Audit the declared inbound censo parser for refusal producers carrying prose or an unresolved recovery.

## Outcome

- Both refusals in the module already render from their own distinct locale keys, one for a source that is not a PDF and one for an unpinned extraction.
- Neither carries an operator-facing sentence, an embedded command, nor a flattened cause, so the step's contract is already satisfied and no change was made.
- Distinct keys per condition rather than one shared key means a consumer can tell the two refusals apart without parsing text.
- Structural verification: the audit is a scan of the declared file, and both producers were read in full.

## Notes

- Closed as already satisfied, with the rationale recorded so a later reader does not re-open the step expecting a migration the module does not need.
- No carry-forward.
