---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P01.S05'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P01.S05`

Closed PERS-3: bucket manifests now fail closed when the TOML read path
lacks the lifecycle `status` key.

- Modified: `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Re-verified the audit finding against the current bucket manifest read
path: `read_manifest` parsed TOML and then injected
`status = "active"` when the key was absent. That could let a malformed
or pre-lifecycle manifest re-enter profile scans as active.

Changed the TOML read boundary to require an explicit `status` key and
raise `StorageValidationError` when it is missing. Normal writes already
emit `status`, so existing valid manifests still round-trip. Added a
real file mutation test that writes a manifest, removes the persisted
`status` line, and proves `read_manifest` refuses it.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/adapters/persistence/storage/bucket/_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py` passed after formatting the import block.

`uv run pytest -q src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest.py` passed with 18 tests in 0.72s.

`uv run ruff check src/aeat/adapters/persistence/storage/bucket/_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest.py src/aeat/application/workflow/test_profile_health.py` passed.

`uv run pytest -q src/aeat/application/workflow/test_profile_health.py` passed with 3 tests in 2.58s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S05` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P01-S05.md src/aeat/adapters/persistence/storage/bucket/_manifest_io.py src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py` passed.
