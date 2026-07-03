---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S04'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Move the submission verifier concrete class to adapters behind the existing protocol in one atomic commit and delete the deferral comment, discharging register item D3

## Scope

- `src/aeat/domain/submission/_protocols.py`

## Description

- Discharge register item D3: delete the comment-only deferral on the `SubmissionRepositoryProtocol` docstring that stated the concrete class relocation was "deferred to a later wave".
- Rewrite the protocol docstring to state that the concrete repository now lives in the persistence adapter and the application layer constructs and injects it.

## Outcome

- Landed in commit `48398f93d`. No submission module remains in the domain-to-adapters pinned set, discharging D3.

## Notes

- The "verifier" naming in the plan row refers to the concrete repository behind the protocol; the deferral was the repository-relocation comment, removed as part of the same inversion.
