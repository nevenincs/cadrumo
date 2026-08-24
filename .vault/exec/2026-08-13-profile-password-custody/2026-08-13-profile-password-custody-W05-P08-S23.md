---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ac7ed030dae0a1f869cc99b86b490976313d6cc734886ede5526247279ba69f6'
step_id: 'S23'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh run and codify real CLI, TUI, recovery-isolation, artifact, and live read-only DEHu routes without remote writes

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Description

Codify the real CLI recovery-isolation, live-notification pull, and TUI restored-profile routes while retaining the live credential gate and avoiding duplicate coverage.

## Outcome

Three route modules codified (implementation commit `a144d627b82`, execution-record commit `d98865f99a8`, 5 cases green + one clean live-gated deselection): `test_recovery_isolation_cli_matrix.py` — A's archive restores into a B-active root as A's own capsule without switching the active profile (the archive contract held at the operator surface), and B's passphrase refuses at A's login through the real verb; `test_live_notifications_pull_route.py` — the `aeat_live`-marked pull route driving the real CLI with the in-body live gate, proving the preflight/persistence/grounding wiring when the live lane runs and deselecting cleanly without credentials; `test_login_screen_restored_and_legacy_members.py` — the full-screen login presents and unlocks a restore-fed profile through the real Pilot-driven door, and a retired-manifest member refuses at the login surface. The routes already covered (local notifications reads, local subgroups, archive roundtrip, restore CLI, the eight Pilot login cases) were inventoried and not duplicated.

## Notes

The live pull route is codified, not executed here: it runs only in the live lane with `CADRUMO_LIVE_TESTS_ENABLED=1`; its deselection under the normal lanes is the property asserted today. The route's grounding fields assert envelope shape, never operator data.
