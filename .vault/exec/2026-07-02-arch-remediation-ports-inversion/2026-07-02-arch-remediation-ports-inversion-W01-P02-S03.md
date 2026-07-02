---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the submission engine persistence behind a port in one atomic commit, deleting its pinned domain-to-adapters errors entry

## Scope

- `src/aeat/domain/submission/_engine.py`

## Description

- Invert the submission engine persistence: the engine now takes an injected `SubmissionRepositoryProtocol` in its constructor instead of instantiating the concrete repository inside its read methods.
- Remove the engine's direct import of the adapter storage error; the malformed-id validation still raises the domain submission error, while a secure-storage integrity failure now propagates to the outer layer.
- Update the sole production construction site (the modelo workflow gate) and the test construction sites to build the concrete adapter repository and pass it in.

## Outcome

- Landed in commit `48398f93d`; the `domain.submission._engine` to persistence-storage pinned edge is deleted.
- Engine preflight and historical-record reads behave identically for the malformed-id and not-found paths; a repository classification refusal keeps surfacing its native error to the repository's own callers rather than being swallowed.

## Notes

- An initial attempt translated the storage error inside the relocated repository's load override; that swallowed the classification and traversal errors the repository's own contract exposes and broke two adapter tests. Reverted to leaving the repository contract intact and translating only the malformed-id path in the engine.
