---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W09.P01.S03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-securestorage-repair-policy-adr-coverage-audit]]'
  - '[[2026-05-26-securestorage-repair-policy-adr-adjudication-research]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
---

# `live-iva-compensation-wallet` `W09.P01.S03`

Added an executable SecureStorage namespace-policy map.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`RepairNamespacePolicy` now records the executable policy fields required by
W09.P01.S03: owner domain, bucket scope, sensitivity class, repair policy,
recovery policy, mutation authority, export behavior, import behavior,
retention/legal note, and calculation-confidence impact.

`build_repair_namespace_policy` derives this policy from the existing namespace
classification layer. The first tests cover wallet observations, unknown
namespaces, and justificante receipt metadata so the policy distinguishes
remote-state recovery, unregistered preserve-first handling, and statutory
receipt preservation.

This is the first backend step toward centralizing repair/recovery policy. It
does not add mutation behavior, live AEAT behavior, import execution, export
execution, quarantine, or deletion.

The widened repair/privacy gate exposed a stale test harness that pinned
`AEAT_DATABASE_URL` to a root test database. That bypassed the active-bucket
route contract now enforced by `SecureObjectRepository`. The privacy tests now
use a real CLI-created active bucket through `AEAT_LOCAL_STORAGE_ROOT`, the
unsecured backend is limited to the documented synthetic tax-id fixture, and
raw non-decrypting before/after snapshots open the active profile session rather
than reading secure objects sessionlessly.

The plan row was closed manually because the installed plan CLI accepts only
leaf `S##` ids and the expanded L3 plan repeats leaf identifiers.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py -q --disable-warnings` completed with 41 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py` passed.
- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 46 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` passed.
- `uv run vaultspec-core vault check frontmatter --feature live-iva-compensation-wallet` passed.
- `uv run vaultspec-core vault check body-links --feature live-iva-compensation-wallet` passed.
- `uv run vaultspec-core vault check links --feature live-iva-compensation-wallet` passed.
- `uv run vaultspec-core vault plan status .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md` reported 56 of 119 steps complete.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md` still fails on the known expanded-L3 identifier issue: repeated leaf `S##` and phase `P##` identifiers make the CLI recompute display paths against the final wave.
