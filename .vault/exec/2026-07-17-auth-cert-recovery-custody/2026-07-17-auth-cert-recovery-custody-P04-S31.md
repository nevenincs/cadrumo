---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:5c724e5279c7c9001e6b780b659cc1420563309e5f4020476ed05ce31f6a8213'
step_id: 'S31'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Align bootstrap and repair-policy inventories with the recovery family and flat recover exception

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`

## Description

- Align `_bootstrap_exempt.py` with the recovery family: the `config recovery` prefix and flat `config recover` replace the retired `show-recovery`/`verify-recovery` entries.
- Extend the repair-policy catalog with `config recovery status/create/rotate/verify` surfaces and update `test_repair_policy_coverage.py` so the custody subgroups (`config recovery`, `config passphrase`) are policy-relevant in full.
- Teach the coverage gate's AST walker to resolve `add_typer(child)` mounts through the child's `typer.Typer(name=...)` constructor, closing the latent gap that hid the passphrase subgroup from discovery.

## Outcome

Bootstrap and repair-policy inventories match the live custody grammar; the discovery-vs-catalog equality gate is green including the passphrase family.

## Notes

None.
