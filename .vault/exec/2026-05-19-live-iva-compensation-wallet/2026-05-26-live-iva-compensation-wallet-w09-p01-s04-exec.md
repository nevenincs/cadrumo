---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W09.P01.S04'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-securestorage-repair-policy-adr-coverage-audit]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
---

# `live-iva-compensation-wallet` `W09.P01.S04`

Added the SecureStorage repair policy coverage gate.

- Modified: `src/aeat/application/repair_integrity.py`
- Created: `src/aeat/entrypoints/cli/test_repair_policy_coverage.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Modified: `.vault/audit/2026-05-26-securestorage-repair-policy-adr-coverage-audit.md`

## Description

`RepairPolicyCommandSurface` now records ADR-linked policy coverage for each
repair, recovery, import, export, or bucket command surface. The catalog records
the command path, family, owner domains, governed secure-object namespaces,
mutation policy, redaction policy, and accepted ADR links.

The CLI coverage test parses the real command-source modules with Python AST,
walks Typer command/mount declarations, and compares every discovered
repair/import/export/recover/recovery/restore/bucket command to the backend
catalog. If a future command is added without an ADR-linked policy entry, the
test fails. Namespace-linked entries also materialise their executable namespace
policies and fail when a listed namespace is unregistered or unknown.

The plan row was closed manually. The installed plan CLI rejected
`W09.P01.S04` with `Step 'W09.P01.S04' does not exist in this plan` because the
expanded L3 plan still repeats leaf `S##` identifiers.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/entrypoints/cli/test_repair_policy_coverage.py -q --disable-warnings` completed with 48 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/entrypoints/cli/test_repair_policy_coverage.py` passed.
- `uv run vaultspec-core vault check frontmatter --feature live-iva-compensation-wallet` passed.
- `uv run vaultspec-core vault check body-links --feature live-iva-compensation-wallet` passed.
- `uv run vaultspec-core vault check links --feature live-iva-compensation-wallet` passed.
- `uv run vaultspec-core vault plan status .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md` reported 57 of 119 steps complete.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md` still fails on the known expanded-L3 identifier issue: repeated leaf `S##` and phase `P##` identifiers make the CLI recompute display paths against the final wave.
