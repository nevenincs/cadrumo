---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-15'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c2ad142f1551e7307e5ed7c34f4035126029957ac03411124043492df2fd85fe'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# `distribution-installation-readiness` ledger

## Changes

- `S01` `T` `pyproject.toml`
- `S02` `T` `uv.lock`
- `S03` `T` `dev/packaging/release_cohort.py`
- `S04` `T` `dev/packaging/cohort_manifest.py`
- `S05` `T` `dev/packaging/tests/test_release_cohort.py`
- `S06` `T` `dev/packaging/installed_tax_oracle.py`
- `S07` `T` `dev/packaging/installed_mcp_oracle.py`
- `S08` `T` `src/cadrumo/entrypoints/mcp/_server.py`
- `S09` `T` `src/cadrumo/entrypoints/mcp/tests/test_installed_cli_resolution.py`
- `S10` `T` `dev/packaging/tests/test_installed_oracles.py`
- `S11` `T` `dev/packaging/smoke_core.py`
- `S11` `T` `dev/packaging/tests/test_smoke_core_payload.py`
- `S11` `T` `justfile`
- `S12` `T` `dev/packaging/smoke_pip_core.py`
- `S13` `T` `dev/packaging/smoke_sdist_core.py`
- `S14` `T` `dev/packaging/smoke_split_install.py`
- `S15` `T` `dev/packaging/smoke_extras.py`
- `S16` `T` `dev/packaging/tests/test_installed_oracles.py`
- `S16` `T` `.github/workflows/packaging-smoke.yml`
- `S17` `T` `packaging/scoop/generate.py`
- `S18` `T` `packaging/scoop/tests/test_generate.py`
- `S21` `T` `packaging/homebrew/generate.py`
- `S22` `T` `packaging/homebrew/tests/test_generate.py`
- `S23` `T` `dev/packaging/smoke_homebrew.py`
- `S25` `T` `src/cadrumo/agent/_workspace.py`
- `S26` `T` `src/cadrumo/agent/tests/test_marketplace_generation.py`
- `S27` `T` `dev/packaging/smoke_plugin_install.py`
- `S28` `T` `packaging/mcpb/manifest.json`
- `S30` `T` `packaging/mcpb/tests/test_client_install.py`
- `S31` `T` `dev/packaging/evidence.py`
- `S32` `T` `dev/release/readiness.py`
- `S33` `T` `dev/release/tests/test_distribution_readiness.py`
- `S42` `T` `dev/release/promote_python_cohort.py`
- `S43` `T` `justfile`
- `S44` `T` `dev/release/tests/test_publish_workflow.py`
- `S51` `T` `.vault/reference/2026-07-15-distribution-installation-readiness-reference.md`
- `S56` `T` `dev/docs/tests/test_distribution_claims.py`
- `S57` `T` `.vault/exec/2026-07-15-distribution-installation-readiness`
- `S58` `T` `.vault/audit/2026-07-15-distribution-installation-readiness-code-review-audit.md`
- `S60` `T` `.vault/index/distribution-installation-readiness.index.md`
- `S61` `T` `src/cadrumo`
- `S62` `T` `src/cadrumo/application/workflow`
- `S63` `T` `dev/packaging`
- `S63` `T` `src/cadrumo/entrypoints/mcp`
- `S64` `T` `src/cadrumo/entrypoints/mcp/tests/test_installed_cli_resolution.py`
- `S65` `T` `dev/packaging/installed_mcp_oracle.py`
- `S65` `T` `dev/packaging/tests/test_installed_oracles.py`
- `S65` `T` `.github/workflows/packaging-smoke.yml`
- `S65` `T` `pyproject.toml`
- `S66` `T` `src/cadrumo/entrypoints/mcp`
- `S67` `T` `dev/packaging/verify_distribution_identity.py`
- `S67` `T` `src/cadrumo/_data/agent`
- `S67` `T` `src/cadrumo/agent`
- `S67` `T` `src/cadrumo/entrypoints/mcp`
- `S68` `T` `dev/packaging/verify_distribution_identity.py`
- `S68` `T` `src/cadrumo/agent/_workspace.py`
- `S68` `T` `packaging/mcpb/manifest.json`
- `S71` `T` `leave noncompliant artifacts open`
- `S71` `T` `.vault/audit/2026-07-15-distribution-installation-readiness-close-audit.md`
