---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:3676e1873c2fad2dc99d7472df3618a992f0fe0111cf83a414df5111e84d66c5'
step_id: 'S27'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Re-measure the orphaned test population against its anchors and resolve any test still reported after the module or symbol it covers has been resolved

## Scope

- `dev/audit`

## Changes

- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --json` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `fail, two peer-owned symbols unrelated to this step`

## Notes

No code changed: the defect this step exists to find does not exist, and the
measurement is the deliverable.

Every subject of all 25 orphaned test modules resolves to a live finding in the
same run: zero name a module or symbol the audit no longer reports. That is
structural rather than lucky. The population is derived inside the scan from the
module and symbol findings it has just computed, so a test cannot outlive its
anchor by one run; the failure mode the step was written against cannot occur
while the derivation stays in-scan.

All 25 carry `exact` confidence, which is why the value-binding fix in the
preceding step moved the symbol count by 175 and left this population at 25:
these tests are anchored on dead MODULES, not on the weak tiers that fix
corrected.

The gating is sound in both directions. The ratchet records 23 orphaned test
modules and reports both a module the tree newly orphans and a recorded module
the tree no longer reports; the live population is 25, of which 2 are deferred
under the frozen entrypoints prefix, so the 23 match exactly.

One blind spot was found and is not a defect in the tree. The orphan walk skips
any test module naming no shipped subject, and 239 of 3334 test modules under
the package are skipped that way. Sampling them shows they are not subjectless:
they reach shipped code one hop away through a support module inside their own
test package, and that support module imports the real code. Subject extraction
follows imports and does not traverse the hop. These 239 are therefore live
tests wrongly invisible rather than dead tests wrongly hidden, but a genuinely
dead test sitting behind such a support module could never be reported, which
is a completeness gap in the population this step measured.

No threshold, exclusion, baseline, skip or allowlist was changed.
