---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S18'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add validate behavior backed by registry and source authority

## Scope

- `src/aeat/application/modelo`

## Description

- Add a backend `validate_m145_communication_record` service that reads the persisted bucket-local communication record and resolves the current Modelo 145 registry snapshot for the same communication scope.
- Add immutable validation result and issue models carrying communication id, bucket id, revision id, validity, issue count, issue details, legal refs, and source refs.
- Validate active revision alignment, persisted authority refs, undeclared casillas, required registry casillas, current registry data types, per-casilla source authority, and registry text/numeric constraints without introducing a new validator convention.
- Promote the validation service and result vocabulary through the `aeat.application.modelo` facade.
- Add real-runtime tests that create encrypted bucket records, validate a clean record, validate missing required registry casillas with registry-sourced refs, and validate current non-text Modelo 145 data-type failures.

## Outcome

- `P04.S18` behavior is implemented behind the backend-owned local communication record surface.
- The public API remains communication-specific and does not add filing, deadline, live-read, portal, submit, receipt, AEAT electronic-tramite, shim, stub, or compatibility-alias surfaces.
- Focused verification passed:
  - `uv run --no-sync ruff check` on the touched M145 service, facade, and tests.
  - `uv run --no-sync pytest -q -n 0` for the M145 validation/create/service-contract slice: 15 passed.
  - Background-captured validation-only pytest log: 7 passed.
- Code-review audit updated with no findings for `P04.S18`.

## Notes

- No blockers or formal deferrals.
- No new binding source kind, resolver convention, or validator convention was introduced.
- The existing registry API still names its year parameter `filing_year`; this step did not expose that vocabulary through the M145 public service surface.
