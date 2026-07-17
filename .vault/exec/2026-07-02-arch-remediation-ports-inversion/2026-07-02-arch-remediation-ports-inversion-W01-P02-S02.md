---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the submission repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/submission/_repository.py`

## Description

- Relocate the concrete `SubmissionRepository` (a `SecureBoundRepository` subclass) from the domain submission package to the persistence adapter, behind the pre-existing read-side `SubmissionRepositoryProtocol`.
- Delete the domain repository module, drop the concrete from the domain package facade, and expose the protocol as the domain's read-side surface.
- Sweep every consumer and test to the adapter home; keep the two domain roundtrip tests in place under sanctioned adapter test-edges.

## Outcome

- Landed together with the engine inversion and the deferral deletion in commit `48398f93d` (tagged `relocation:submission-repository`); the three plan steps are one inseparable inversion because moving the concrete forces the engine dependency-injection change and makes the deferral comment false.
- The `domain.submission` package no longer imports the persistence substrate; the domain-to-adapters pinned edge for the repository is deleted.

## Notes

- S02, S03, and S04 co-landed in one atomic commit; separating them would leave a non-collectible tree at a checkpoint.
