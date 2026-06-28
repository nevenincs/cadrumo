---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-11'
modified: '2026-06-11'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-06-secure-storage-production-hardening-W13-P27-S396]]'
  - '[[2026-06-06-secure-storage-production-hardening-W13-P27-S397]]'
  - '[[2026-06-06-secure-storage-production-hardening-W13-P27-S398]]'
  - '[[2026-06-11-secure-storage-production-hardening-W13-P28-S399]]'
  - '[[2026-06-11-secure-storage-production-hardening-W13-P28-S400]]'
---

# S401 testimonial retest synthesis and final dispositions

## Scope

S401 closes the W13 testimonial adoption wave for secure-storage production hardening. It synthesizes the S396 ownership reconciliation, S397 research requirements, S398 classification register, S399 focused retests, and S400 repair-adoption decision.

## Final dispositions

| Finding | Final disposition | Evidence |
|---|---|---|
| FRESH-004 manual route discoverability | Not secure-storage-owned. External CLI workflow or capability discovery work if a route alias, help bridge, or richer formula hint is desired. | S397 and S398 classify this as registry/manual-source discoverability with no storage readiness, custody, repair, or profile-bound evidence failure. |
| FRESH-007 profile-filtered obligation explanation | Not secure-storage-owned. External CLI workflow or capability guidance work unless a future retest proves runtime-backed profile reads fail. | S397 and S398 identify `overview explain` and calendar as the applicability owners; the remaining issue is next-action discovery. |
| FRESH-011 undecryptable stored draft readiness blocker | Secure-storage-owned and closed without new repair rows. | S399 clean Modelo 111 readiness passed; repair integrity metadata-only unreadable-row diagnostics passed; backend unreadable-row integrity/list tests passed. S400 adopted no new repair row. |
| REPAIR-PROFILE-PRIVACY-001 repair-profile identifier leakage | Secure-storage-owned and closed as remediated regression coverage. | S399 repair-profile redaction, quarantine dry-run, integrity objects, and sessionless bootstrap gates passed. S400 adopted no new repair row. |

## Retest evidence

S399 used existing real fixtures and isolated storage roots. It did not add fakes, stubs, monkeypatches, skips, or xfails.

Passing gates:

- Clean Modelo 111 readiness names the preflight scope.
- `config repair profile` redacts profile and bucket identifiers.
- `config repair integrity objects` reports unreadable rows as metadata only.
- `config repair quarantine --dry-run` is metadata-only and non-mutating.
- Backend unreadable-row integrity grouping and unreadable filtering pass.
- Sessionless repair verbs run on a fresh root.

## Residual observations

The multi-agent persona sidecar dispatch failed before execution because the agent runtime returned usage-limit errors. The local focused retest completed the same S399 scope.

A broader direct state-projection probe still hit the profile-key registration harness issue already recorded by the period-grammar standardisation execution record. That observation is not a W13 secure-storage blocker because the S399 CLI readiness and repair surfaces passed under the scoped fixtures.

## Decision

W13 introduces no further secure-storage repair work. The remaining open secure-storage work moves to non-W13 rows.
