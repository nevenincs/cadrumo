---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'P01.S01'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-fragment-headroom-audit]]'
---

# P01.S01 Execution Record

## Step

`P01.S01`: Audit current TOML fragment and row-size headroom; `.vault/audit`.

## Result

Completed. The committed TOML corpus is currently inside both reviewability
gates:

- maximum TOML fragment length: 1706 lines;
- maximum row-size gate: no committed TOML row exceeds 600 characters;
- highest-risk path: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/completeness-manifest.toml`.

The audit also found an additional lower-priority pressure edge:
`src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`
at 1218 lines. That edge is now tracked as `P04.S27`.

## Artifacts

- `2026-06-02-registry-hardening-fragment-headroom-audit`
- `2026-06-02-registry-hardening-next-work-p01-s01-review`

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable -q`
  - Result: 1 passed in 2.84s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
  - Result: 24 passed in 70.78s.
- `uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-06-02-registry-hardening-next-work-plan.md`
  - Result before closeout: L2, 4 phases, 26 steps, 0/26 complete.
