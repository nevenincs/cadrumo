---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:b5e99653c8c37b51cf1859dc8cbeec6064e6ba27dd99546925140b63204af99a'
step_id: 'S183'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh bring the whole-tree type gate green at rest so it can function as the tripwire it already has the capability to be, since it resolves every import across the source tree with unresolved imports configured as hard errors and reaches both type-checking-guarded edges and production modules no test imports, which makes it the one mechanism that can see a deletion landing without its consumer sweep, and a gate standing red at rest is indistinguishable from an absent one because no reader can tell a new break from the standing noise

## Scope

- `src/cadrumo/ and pyproject.toml`

## Description

## Outcome

The campaign's own share of the whole-tree type gate is fixed (commit `bd64e92ab6`-adjacent type commit): the user-profile facade's 248 lazy exports are now statically visible through a TYPE_CHECKING import block (self-aliased re-exports per module), which cleared the facade's 18 reportUnsupportedDunderAll/Unknown diagnostics AND the 22 evidence/filing member-access unknowns that flowed from consumers importing lazy names; the capsule-archive JSON payload is narrowed to `dict[str, object]` after the isinstance guard (6 diagnostics). Gate totals moved 1171 → 1123.

## Notes

The gate cannot go green at rest while the concurrent registry campaign's half-landed refactor stands: 636 pyrefly + 24 basedpyright diagnostics in `application/calculations/_row_set_assembly.py` (the uncommitted Gasto193 work), ~100 more across the registry domain and its tests, plus pre-existing harness/test debt. The residual is routed to the owning campaigns with the baseline enumerated (`types_full.log` retained); this row closes with our share delivered and the tripwire-once-green dependency recorded — same blocked-externally class as S195.
