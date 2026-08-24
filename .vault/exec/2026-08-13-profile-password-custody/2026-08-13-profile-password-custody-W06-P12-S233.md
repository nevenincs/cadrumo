---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e3eb429d6298c36693b2200c620ad4e0d9f8688bd75ce74c09d0e709b2cd58a9'
step_id: 'S233'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Run the complete documented-command, catalogue-drift, locale-completeness, localized-build, no-skip, native Windows, and WSL proof suite and persist fresh global evidence

## Scope

- `dev/docs/tests/`
- `dev/tests/test_no_skip_xfail.py`
- `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

- Ran the combined documented-command, sequence contract/golden/page-coherence, catalogue drift, localization completeness, no-skip, and distribution-evidence modules on current HEAD.
- Ran native Windows and WSL/POSIX KDF-supervision and machine-secret subprocess suites serially.
- Ran the full harness integration lane serially, including its recovery-channel fixtures and process-global watchdog tests.
- Ran Spanish, Catalan, and Hungarian localized nitpicky builds plus the main full-scope nitpicky build.
- Ran feature-scoped Vaultspec checks and Ruff/ty over the relevant proof surfaces.

## Outcome

S233 remains open because multiple substantive global gates are red. Green evidence: combined global module run had 375 passes around three sequence failures; native KDF 19 passed and machine-secret 70 passed; WSL KDF 19 passed and machine-secret 70 passed. Catalogue drift, localization completeness, no-skip, documented-command, and distribution-evidence cases did not fail in the combined run.

## Notes

Exact commands and results on 2026-08-24:

- `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py dev/docs/tests/test_sequence_contract.py dev/docs/tests/test_sequence_goldens.py dev/docs/tests/test_golden_records_no_crash.py dev/docs/tests/test_docs_catalogue_drift.py dev/docs/tests/test_docs_localization.py dev/tests/test_no_skip_xfail.py dev/packaging/tests/test_distribution_evidence_emit.py` exited 1 after 758.56 seconds: 375 passed, 3 failed.
- `uv run --no-sync pytest -q -n 0 -m unit src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py` exited 0 after 29.28 seconds: 19 passed.
- `uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py` exited 0 after 582.28 seconds: 70 passed.
- `wsl.exe -d Ubuntu -- bash -lc "cd /mnt/y/code/aeat-worktrees/main && UV_PROJECT_ENVIRONMENT=/home/hello/.cache/cadrumo-s233-wsl uv sync --all-packages --group dev"` exited 0 and installed the locked WSL proof environment.
- `wsl.exe -d Ubuntu -- bash -lc "cd /mnt/y/code/aeat-worktrees/main && UV_PROJECT_ENVIRONMENT=/home/hello/.cache/cadrumo-s233-wsl uv run --no-sync pytest -q -n 0 -m unit src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py"` exited 0: 19 passed in 39.99 seconds.
- `wsl.exe -d Ubuntu -- bash -lc "cd /mnt/y/code/aeat-worktrees/main && UV_PROJECT_ENVIRONMENT=/home/hello/.cache/cadrumo-s233-wsl uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py"` exited 0: 70 passed in 1216.02 seconds.
- `uv run --no-sync pytest -q -n 0 -m integration src/cadrumo-harness/src/cadrumo_harness` exited 1 after 312.69 seconds: 335 passed, 4 failed, 53 deselected.
- `uv run --no-sync pytest -q -n 0 -m unit dev/docs/tests/test_docs_build_localized.py dev/docs/tests/test_docs_build_full_scope.py` exited 1 after 935.16 seconds: the Spanish, Catalan, Hungarian, and main nitpicky builds failed; two control tests passed.
- `vaultspec-core vault check body-sections -f profile-password-custody`, `frontmatter`, and `exec-mapping` each exited 0 after evidence population.
- `uv run --no-sync ruff check dev/docs src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py src/cadrumo/adapters/persistence/storage/custody src/cadrumo-harness/src/cadrumo_harness` exited 1 with one harness import-order error.
- `uv run --no-sync ty check dev/docs src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py src/cadrumo/adapters/persistence/storage/custody src/cadrumo-harness/src/cadrumo_harness` exited 1 with 200 diagnostics.

Derived work is required before this Step can close:

- S240: add result-payload expectations on `how-to/filing-spine`, `how-to/irpf-lifecycle`, `how-to/iva-lifecycle`, `how-to/modelo-100`, `how-to/modelo-303`, `how-to/profile-setup`, `how-to/protect-data-access`, `how-to/quickstart`, and `how-to/verification-reports`, then tighten only their baseline entries.
- S241: adjudicate recovery-secret enrollment and current export/registry/ledger behavior against live authority, then repair page coherence without refreshing unexplained output.
- S242: after that adjudication, use only the owning sequence CLI to refresh affected goldens and eliminate filing-spine, modelo-303, and verification-reports frame-count drift.
- S243: repair es/ca/hu reference-token mismatches and generated CLI toctree enrollment, then prove all three localized nitpicky builds.
- S244: repair the full-scope API cross-reference inventory and prove the main nitpicky build independently of localization work.
- S245: enroll a real recovery secret in the two warm-runtime profile-provision fixtures.
- S246: repair the independent serial kill-switch and disarm-event failures.
- S247: fix the one harness import-order error and partition the 200 ty diagnostics by their existing owning modules rather than treating S233 as a bulk type cleanup.

No product, documentation, golden, baseline, or test file was edited by S233. The WSL proof environment was synchronized from the committed lock into `/home/hello/.cache/cadrumo-s233-wsl` before execution.
