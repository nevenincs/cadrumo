---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P07.S05'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` P07.S05 — diagnostic row names harmonised to `profile.readiness` and `auth.readiness`

## Finding

M-1 (MEDIUM). The implementation emitted four row names
(`profile.active`, `profile.required_keys`, `auth.provider`,
`auth.session`) while the ADR §3.6 mapping table promised two
(`profile.readiness`, `auth.readiness`). The two-source divergence is
the bug — operators reading the ADR table would search for rows that
the implementation never emits.

## Decision

Chose option **(a)** — harmonise the implementation onto the
ADR-canonical two-row contract. The four-row split carried no
information that the `summary` field cannot encode: the branch the row
covers (no active profile / missing keys / no provider / no session) is
already encoded in the summary text and the `next_action`. Collapsing
to two rows preserves every byte of operator-visible information while
matching the ADR table that downstream documentation cites.

## Resolution

Updated `_profile_check` and `_auth_check` in
`src/aeat/application/diagnostics.py` to emit the same row name across
every branch: `profile.readiness` for the profile dispatch helper,
`auth.readiness` for the auth dispatch helper. Updated
`src/aeat/application/test_diagnostics.py` and
`src/aeat/application/test_diagnostics_dispatch.py` to assert on the
consolidated row names (and the rephrased docstrings describing why
the row name is uniform).

## Verification

`pytest src/aeat/application/test_diagnostics.py
src/aeat/application/test_diagnostics_dispatch.py` runs green; the
emitted row set now matches the ADR mapping verbatim.
