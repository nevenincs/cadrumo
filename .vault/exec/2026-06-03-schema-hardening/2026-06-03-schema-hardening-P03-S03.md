---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S03'
related:
  - "[[2026-06-03-registry-construct-pressure-plan]]"
---

# Re-run construct-pressure corpus headroom audit

## Scope

- `.vault/audit`

## Description

- Measure line counts for every registry TOML file under
  `src/aeat/_data/registry/aeat/modelos`.
- Measure maximum row width across the same TOML corpus.
- Record the post-split headroom audit and remaining soft-band edge.
- Re-run the registry loader, reviewability, and committed registry checks after
  the branch-level `pyproject.toml` duplicate-key blocker was fixed.

## Outcome

- No registry TOML file is over 1,500 lines.
- No registry TOML row is over 600 characters.
- The largest file is now `M123` 2024-and-later `revision.toml` at 1,218 lines.
- The M200 records directory now tops out at 900 lines, with the S02 split parts
  at 753 and 716 lines.
- Verification passed for the construct merge regression, committed registry
  TOML reviewability, registry fragment reviewability, reviewability baseline,
  committed registry load, plan check, and construct-pressure annotation check.

## Notes

- The S02 split landed in a concurrent shared-worktree commit with other agents'
  changes. It was not rewritten or separated after landing.
- A committed duplicate-key parse error in `pyproject.toml` blocked pytest and
  vault CLI execution after S02 landed; it was fixed in a separate config commit
  before S03 verification continued.
