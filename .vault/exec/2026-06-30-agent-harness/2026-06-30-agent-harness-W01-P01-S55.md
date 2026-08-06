---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:abf91a1083e32a97b4ed6f1f9b51c6e937668f02b216e4fe75af5ea9b7526691'
step_id: 'S55'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# Complete the OperatorSurfaceContract to cover every mounted family and sub-verb, and add a live-Typer-tree drift gate so the agent manifest source can never silently drift

## Scope

- `src/aeat/application/operator_surface/_contract.py`

## Description

- Resolve the live Typer tree two levels deep under both pinned roots and capture ground truth for every `config`/`app` family and its direct sub-verbs.
- Add presentation domains `GOOGLE` and `CONTRACT` to `MountedCommandDomain`.
- Add the three families the CLI mounted but the contract omitted: `config check` (read-only provisioning readiness), `config google` (Google auth/Drive/export mirror), `config reset` (config-scope reset); keep each root's `required_children` in lockstep order with its families.
- Add the `app contract` family so the manifest is self-describing.
- Complete the stale `commands` tuples for `profile` (+capabilities/preflight/validate), `auth` (+login), `repair` (+profile), `overview` (+agenda/backlog/calendar/explain), `ledger` (+categories/doclink/evidence/inventory/invoice/participation/providers/restore/rule), `live` (all eight children, `filed` kept as `FilingStatus.FILED`), `modelo` (+12 sub-verbs), `registry` (+citations/manuals).
- Extend the `SERVICE_OWNERS` inventory for the new provisioning/google/config-reset capabilities.
- Add `test_operator_surface_contract_drift.py`: an integration-tier gate that force-loads every lazy subtree, walks the two pinned roots, and asserts an empty symmetric difference between the live family/sub-verb surface and the contract — no allowlist.

## Outcome

The `aeat app contract` manifest now emits a contract that matches the live CLI tree exactly, and the drift gate makes any future family/sub-verb that lands without a contract update a red integration gate (co-commit by construction). Verified: the new drift gate plus `test_contract.py` (15 unit) and `test_app_contract.py` (7 integration) pass; an anti-tautology check (transiently dropping `config google sync`) reds the gate with a precise diagnostic, confirming it resolves the live tree rather than restating the contract; ruff clean on all touched files.

## Notes

- Brief framed this as a precondition "before the manifest command is mounted", but W01 (and W02) had already landed — the manifest was already emitting from the stale contract. Recorded honestly as an appended correction Step (`S55`), not inserted before the already-done mount.
- Scope crosses two files beyond the single scope clause: `src/aeat/application/operator_surface/_models.py` (two enum members) and `src/aeat/entrypoints/cli/tests/test_operator_surface_contract_drift.py` (the gate). The gate lives in `entrypoints/cli/tests/` rather than the operator-surface tests so it can import the live Typer tree without inverting the application→entrypoints layering, and to mirror/sit beside the leaf-schema gate whose loader it reuses.
- Did NOT run `apidocs scaffold`: the change adds no new `src/aeat` module (only edits + a test file), so it carries zero apidocs obligation; the working tree's `aeat.agent`/`docs/api` drift is peer-owned WIP from the concurrent W02/W03 harness work and must not be swept into this commit.
