---
tags:
  - '#exec'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-lazy-import-policy-plan]]"
---

# Make an unclassified site outside the allowlist fail the gate with the site path and the five sanctioned classes named in the message

## Scope

- `src/aeat/tests/test_lazy_import_policy.py`

## Description

- Make `test_no_unclassified_unsanctioned_import_site` fail an unsanctioned function-local first-party import whose edge is not in the allowlist, reporting each offending `path:line  consumer -> target` and naming the five sanctioned classes plus the remediation (restructure away, or add a reviewed allowlist entry).

## Outcome

Verified with a throwaway probe module carrying one unsanctioned `from aeat.core import config`: the gate failed naming `src/aeat/_lazy_probe_tmp.py:6  _lazy_probe_tmp -> core` and the full sanctioned taxonomy, then passed again once the probe was deleted. The gate is non-tautological.

## Notes

The five sanctioned classes are rendered from the `SanctionedClass` enum so the failure message and the recognised taxonomy cannot drift.
