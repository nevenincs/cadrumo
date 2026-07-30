---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S132'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Update write-policy tokens for the accepted destructive and read-only command paths

## Scope

- `src/cadrumo/application/storage_write_policy.py`

## Description

- Read the profile-bound write catalogue in the named module and the matcher that consumes it.
- Confirm the accepted destructive paths are covered and determine how nested reset verbs match.
- Establish why the custody verbs are absent from the catalogue rather than assuming a gap.

## Outcome

The catalogue is correct as it stands, and its shape initially reads like a fail-open gap that it is not.

The matcher is prefix-based by design, so the single `config reset` entry covers the nested reset start, status, and resume verbs; a per-verb enumeration is unnecessary rather than missing. The custody verbs `config passphrase change`, `config recover`, and `config recovery` are absent from this catalogue because they are deliberately bootstrap-exempt, carrying the documented rationale that custody verbs own their own session, recovery, and rewrap flow. Adding them here would have been the actual defect.

The catalogue is independently gated: every guarded write path is asserted to name a live command, and that gate carries its own proof that a stale catalogue entry is rejected.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
