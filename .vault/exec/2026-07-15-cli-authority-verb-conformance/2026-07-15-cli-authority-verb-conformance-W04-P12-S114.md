---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S114'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Align bootstrap and repair-policy inventories with the recovery family and flat recover exception

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`

## Description

The repair-policy coverage gate had to be aligned with the recovery family and the flat
`recover` exception: every leaf under `config recovery` (status/create/rotate/verify) and
`config passphrase` (change), plus the flat `recover`/`export`/`import`/`restore` leaves,
must be discovered and carry a registered namespace policy.

## Outcome

`_requires_policy_coverage` in
`src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py:182-201` treats any
command path rooted at `["config", "recovery"]` or `["config", "passphrase"]` as
policy-relevant in full (lines 190-194), and separately treats a bare `recover` leaf (along
with `export`/`import`/`restore`) as policy-relevant (`recovery_leaves`, lines 184-189).
`_POLICY_COMMAND_MODULES` (lines 17-33) includes `_custody_secret.py` as one of the
AST-scanned source modules, so `config passphrase change`, `config recovery
status/create/rotate/verify`, and `config recover` are all discovered command paths.
`test_policy_command_surface_catalog_covers_cli_repair_import_export_and_profile_history_commands`
(line 36) asserts the discovered path set equals the catalogued path set exactly, and
`test_policy_command_surfaces_are_owned_and_namespace_policies_are_registered` (line 43)
asserts every namespace policy on every surface carries a real (non-`unknown`) repair
policy, recovery policy, and mutation authority.

## Notes

File matches the step's declared scope exactly. Cited the coordinator's gate run rather
than re-executing (serial `-n0` lane 27 passed/1 failed, unrelated S112 gap). This is an
AST-based structural gate reading the live source tree, not a hand-maintained inventory.
