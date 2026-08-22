---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:b98bf6f99605801a8b439295efdfc4c73a6f0e7d5b453e34dcc9ab3002032e53'
step_id: 'S51'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Attach execution policy to live, diagnostics, maintenance, review, overview, registry, and quickfile callbacks

## Scope

- `src/cadrumo/entrypoints/cli/ remaining app modules`

## Description

- Add import-light execution-policy presets for the remaining application CLI.
- Add explicit `local-storage` and `subprocess` capability axes where the prior
  taxonomy could not truthfully describe telemetry or Playwright process control.
- Attach callback-local policies to every live, diagnostics, maintenance,
  review, overview, registry, and quickfile root, group, and leaf.
- Preserve executable and callbackless group behavior while classifying the
  maximum conditional effect of each callback.
- Add live-derived exact-partition, unclassified-node, downgrade, import-light,
  and help-behavior gates.
- Retain the keyed risk table unchanged for its mandatory complete S52 migration
  and deletion.

## Outcome

The exact live S51 partition contains no unclassified node. Local snapshot
reads no longer inherit network authority, portal metadata remains state-free,
telemetry uses application-local storage rather than false profile custody,
mutating live pulls declare network and profile-bound writes, and the IVA
evidence pull additionally declares browser and subprocess control. Maintenance
reconciliation remains destructive and quickfile remains a filing handoff.

Scoped Ruff and ty checks passed. Focused schema, census, CLI behavior, risk
parity, and representative family tests passed in separate runs of 19, 21, 17,
and 23 tests. The independent review found no severity-bearing issue and
re-attested the browser/subprocess correction.

## Notes

The shared-worktree writer captured the first production sweep in commit
`e61c2e9c75` while this Step was still running. Subsequent proportional-policy,
formatting, test, review, and Vaultspec changes remain attributed through exact
paths. No peer changes were reverted or staged.

S52 must remove `_risk_table.py` itself together with every row, export,
consumer, test, and obsolete prose dependency. An empty table, compatibility
re-export, shim, or dormant fallback is not completion.
