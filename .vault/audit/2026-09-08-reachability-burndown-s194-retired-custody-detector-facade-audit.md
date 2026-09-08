---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:b578460ce33cfacc8533f49a24f57ae873e8d2b6571d55134522ae7ba5713174'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S194]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `reachability-burndown` audit: `S194 retired custody detector facade implementation review`

## Scope

Independent bounded review of W05.P12.S194 against the accepted profile-password-custody hard-cutover contract. The review covered the Step row and Step Record plus the current diff in `capsule_discovery.py` and `test_capsule.py`, limited to removal of the test-only public detector facade and migration of its direct assertions to the live refusal boundary. Unrelated pre-existing test-file hunks in the shared dirty worktree were excluded from S194 attribution.

## Findings

No findings.

The removed `detect_retired_profile_custody_member_paths` function was a public, test-only projection over the same private anchored detector used by `refuse_retired_profile_custody_paths`; its removal introduces no replacement alias, compatibility surface, allowlist, or metastate mechanism. The live boundary still performs existence-only detection, reports operator-safe root-relative wildcard context, and raises `LEGACY_CUSTODY_DETECTED` with only destructive-reset or re-enrolment guidance. The focused tests continue to exercise both retired bucket and retired keystore members through live capsule discovery, retain the audit-hook proof that retired content is never opened, retain the anchored/no-follow obstruction controls, and retain the current-store negative control.

The Step Record names the exact two touched files and exact Ruff, focused pytest, production-metastate, residue, and live reachability commands. Its reachability entry accurately records the dirty-tree aggregate as findings while separately proving the removed symbol absent; it does not misattribute peer-owned aggregate movement to S194. Independent execution of the focused capsule suite passed 23 tests, and the exact residue scan returned no matches.

## Recommendations

Approve W05.P12.S194. No production, test, decision, or evidence correction is required.
