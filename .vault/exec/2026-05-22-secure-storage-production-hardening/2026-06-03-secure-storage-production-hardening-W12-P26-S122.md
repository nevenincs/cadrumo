---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S122'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s122-review-audit]]'
---

# W12.P26.S122 - close AFR-020 for G313 censo live fetch

## Scope

Plan row `W12.P26.S122` closes `AFR-020` for
`src/aeat/adapters/outbound/aeat/sede/_censo_live.py`, classified with signal
`remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Reviewed `_censo_live.py` as an authenticated outbound AEAT Sede browser adapter.
- Verified the file derives external URLs from centralized `Settings.external_constants()`
  and accepts `Settings` explicitly at the live-fetch boundary.
- Verified the no-session user-facing failure uses `tr()` and raises the typed
  `SedeNavigationError`.
- Scanned the file for secure-storage, settings-route, filesystem, environment, and
  provider APIs.
- Ran focused censo live and Playwright wait-constant tests plus targeted Ruff.
- Marked `AFR-020` closed in the affected-file register and closed `W12.P26.S122`
  through the vaultspec plan CLI.

## Outcome

`_censo_live.py` is not a persistence backend and does not implement a remote mirror
provider. Its scanner signal is accepted as an outbound remote AEAT live-call boundary:
it uses authenticated browser storage state to fetch G313 HTML, parses it into
`CensoFactSet`, and returns typed facts for the application censo snapshot service.

## Notes

No source code changed for this step.
