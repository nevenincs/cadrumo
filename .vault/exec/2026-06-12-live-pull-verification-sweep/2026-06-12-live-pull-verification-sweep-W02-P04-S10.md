---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S10'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Prove censo pull and profile reconciliation fetch authenticated Modelo 036 or censo information and derive taxpayer facts without inventing missing obligations

## Scope

- `src/aeat/application/live/_censo.py src/aeat/application/user_profile/_censo_sync.py src/aeat/adapters/outbound/aeat/sede/_censo_live.py`

## Description

- Re-grounded the censo backend row with `vaultspec-rag` against the accepted
  operator-manual enrolment decision and the current application source.
- Confirmed that the former live-snapshot and G313 adapter scope has been
  deleted, and that `CensoSyncService` now derives only the surviving
  home-office ratio from operator-declared profile facts.
- Reconciled this row against the replacement decision: an authenticated
  Modelo 036/censo fetch is no longer a permitted or shipped product surface.

## Outcome

Superseded, not delivered. The accepted censo operator-manual decision retires
the live censo scrape because AEAT provides census data only through a
modification tool, not a safely automatable read-only projection. The original
positive authenticated-fetch acceptance condition cannot therefore be met and
must not remain a live-pull obligation.

The current `src/aeat/application/user_profile/_censo_sync.py` documents and
implements the replacement posture: operator-declared, non-official facts
entered through `config profile edit`; no capture, compare, apply, or snapshot
reconciliation path remains. The removed `application/live/_censo.py` and
`adapters/outbound/aeat/sede/_censo_live.py` targets confirm this is a
delete-not-stub supersession rather than an untested backend.

## Notes

No authenticated censo data was fetched in this reconciliation, and none is
claimed. A future genuine AEAT consulta-only endpoint requires a new ADR before
an automated read may return.
