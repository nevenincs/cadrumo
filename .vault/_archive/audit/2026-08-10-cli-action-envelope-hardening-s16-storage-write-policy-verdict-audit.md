---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b6359ffd41ad3b765071521fcd4bfe33bb49bf4967512400bc32e8b3dd0eef7a'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# `cli-action-envelope-hardening` audit: `S16 storage write-policy verdict`

## Scope

Independent review of `W03.P05.S16` only: the typed refusal verdicts in
`storage_write_policy.py` and their direct production-import tests. The review
checked the accepted ADR, research, reference, plan, and S08-S17 contracts for
application ownership, stable identities, factual evidence, action binding
shape, terminal no-recovery shape, presentation separation, and preservation
of the existing root refusal path. A fresh review after the S17 boundary
cutover verified both real root refusal routes. Findings status: two closed
findings and no additional findings.

## Findings

### root-refusal-cutover | high | Removing `refusal_context` breaks both root refusal routes

Status: closed. S17 removed the stale consumer and projects the typed verdict
through the shared CLI policy-refusal handoff without restoring a compatibility
shim. The real root-fallback route preserves its requested leaf and exposes the
canonical `operator.profile.create` action with missing `profile_name`. The
real explicit-database route preserves its requested leaf and exposes the
closed `operator_decision` outcome with factual setting-name evidence. Both
routes retain their established refusal behavior, and sequential root
invocations prove the requested-leaf context is cleared without leakage. The
root typed-projection integration suite passed all 11 tests in the fresh
independent review.

### s16-export-formatting | low | New public identity exports fail the formatter check

Status: closed. The added `StorageWritePolicyCondition` and
`StorageWritePolicyEvidence` entries in `__all__` used different line endings
from the surrounding list. The repository formatter normalised the list, and
the targeted formatter, lint, and diff checks now pass. The public exports
remain appropriate for the planned downstream identity checks.

## Recommendations

- `root-refusal-cutover` (closed): the S17 cutover now transports both S16
  verdicts through the typed policy projection, with real-entrypoint coverage
  for both routes and no legacy `refusal_context` shim.
- `s16-export-formatting` (closed): the changed `__all__` list was normalised
  with the repository formatter; targeted formatter, lint, and diff checks
  passed.
