---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d0c42c42560fb1580919ff1266aaa9a52c955141eee258e2863d9c8f293d0ae6'
step_id: 'S59'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Remove stale lazy schema-owner-table claims from the config payload surface while S91 exclusively owns residual Modelo CLI action producers

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

- Establish whether the lazy schema-owner table the config payload surface cites still exists.
- Correct both comments to name the mechanism the wizard result schemas actually register through.

## Outcome

- No lazy schema-owner table exists anywhere in the tree. A repository-wide search for the table and its aliases returns only the two comments in the config payload module that cite it.
- The wizard-owned profile result schemas register at their own producer through the schema decorator, which is the real mechanism the stale comments displaced.
- Both comments now describe that mechanism. The surrounding rationale is preserved unchanged, because it remains true and load-bearing: the config group resolves this module at group-resolution time, so importing the wizard here would pull its dependency tail into every config verb and redden the cold-start guard.
- No production behaviour changed; this step removes a false claim about registration, not a code path.
- The schema-conformance and config payload selection passes five hundred and sixty-two tests, and the module is lint clean.

## Notes

- The single failure in that selection is unrelated peer breakage: a profile fixture missing a now-required tax-residence jurisdiction-scope flag. It was confirmed by reading the traceback and does not reach this module.
- A stale comment of this kind is worth removing rather than tolerating, because it describes an architecture that never shipped; a reader trusting it would look for a registration table that does not exist.
- No carry-forward.
