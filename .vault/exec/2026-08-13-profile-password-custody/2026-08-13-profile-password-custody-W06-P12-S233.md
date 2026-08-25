---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7af974493dd1e98c6d3be1d290279f400a445e51b1c02d2d32e092ac70f8cab4'
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
- Ran the full harness integration lane in its authoritative split: non-serial integration under xdist and process-global watchdog tests serially under `-n 0`.
- Ran Spanish, Catalan, and Hungarian localized nitpicky builds plus the main full-scope nitpicky build.
- Ran feature-scoped Vaultspec checks and Ruff/ty over the relevant proof surfaces.

## Outcome

S233 remains open because multiple substantive current-HEAD gates are red. Green current evidence includes no-skip at 25 passes, native and WSL KDF supervision at 19 passes each, and Ruff plus ty across the exact 41-file campaign surface. Current red evidence includes sequence/custody composition, production catalogue and registry moves, every required nitpicky build, documentation dash ratchet, both harness lanes, native root-descriptor refusal, and feature/full Vaultspec warning-free closure. The WSL machine-secret result is recorded with the fresh 2026-08-25 evidence below; the following 2026-08-24 section is retained only as historical comparison.

## Notes

Fresh strict rerun on current shared HEAD, 2026-08-25:

- `python -m pytest -q -n 0 -m integration` over documented-command conformance, sequence contracts/goldens/page coherence, catalogue drift, docs localization, no-skip, and distribution evidence exited 1 after 232.77 seconds: 371 passed, 6 failed, 3 errors, 59 deselected. Every real sequence failed before dispatch because `publish_test_profile_capsule` reached recovery enrollment without a composed `profile_custody_port`; catalogue extraction failed because Modelo 038's 2025 revision key `x-chim6r1ecll6asj3d5hmiro.label` is absent from Spanish.
- `python -m pytest -q -n 0` over documentation localization, dash ratchet, orphan-page removal, and production locale audit exited 1 after 65.30 seconds: 16 passed, 2 failed. `docs/reference/environment-overrides.md` has five new em dashes against a zero baseline, and the production catalogue audit is red.
- `python -m dev.locales audit` exited 1 after approximately 60 seconds: every locale reports 48 missing keys, 20 extra keys, and two registry moves. The moves are Modelo 220 `2025-y-siguientes` to `2025` and Modelo 763 `2011-y-siguientes` to six published eras; representative missing keys include calc-sheet metadata refusals, filed-pull factual refusals, the Modelo 210 deadline, LLM diagnostics, and current Modelo schema labels.
- `python -m pytest -q -n 0 -m unit dev/docs/tests/test_docs_build_localized.py dev/docs/tests/test_docs_build_full_scope.py` exited 1 after 177.73 seconds: 2 passed and all four required builds failed. Spanish, Catalan, Hungarian, and main full-scope builds stop at the same missing Modelo 038 Spanish casilla label.
- `python -m pytest -q -n auto src/cadrumo-harness/src/cadrumo_harness -m "integration and not serial and not os_keychain"` exited 1 after 89.00 seconds: 317 passed, 9 failed. Three delivery and three warm-runtime tests lack composed custody infrastructure; installed `cadrumo-mcp` is unavailable to handshake/refusal subprocesses; `overview.calendar` emits an 18,819-character schema over the 18,000-character budget.
- `python -m pytest -q -n 0 src/cadrumo-harness/src/cadrumo_harness -m "integration and serial and not perf and not os_keychain"` exited 1 after 84.28 seconds: 18 passed, 1 failed, 379 deselected. The real leaked-stdin watchdog proof cannot launch `cadrumo-mcp`.
- `python -m pytest -q -n 0 dev/tests/test_no_skip_xfail.py` exited 0: 25 passed in 30.60 seconds.
- Native Windows supervised KDF exited 0: 19 passed in 30.20 seconds. Native machine-secret subprocess proof exited 1: 68 passed, 2 failed in 516.77 seconds; unusable root descriptors for `config.profile.history` are laundered into `INTERNAL_CLI_UNEXPECTED_BOUNDARY` with exit 6 instead of the typed exit-2 refusal.
- WSL supervised KDF exited 0: 19 passed in 40.43 seconds. WSL machine-secret subprocess proof exited 1 after 1,150.47 seconds: 69 passed and the fd-leaf passphrase-change case failed with `INTERNAL_CLI_UNEXPECTED_BOUNDARY`, exit 6, while its descriptor remained open.
- The corrected 41-file campaign surface exited 0 under both Ruff and ty in 1.2 seconds. No diagnostic remains on that bounded campaign surface.
- `vaultspec-core vault check all -f profile-password-custody --no-hints` exited 0 in 5.17 seconds but reported 26 warnings: 17 scaffold-annotation documents, one stale feature index, and eight stale body attestations. The unfiltered full check exited 0 in 10.26 seconds with 1,505 warnings across annotations, markdown hygiene, orphan audits, stale/missing feature indexes, historical body sections, references, schema grounding, and modified stamps.

Derived owner steps were appended through the plan CLI and S233 remains open: S261 owns custody composition in profile capsules, sequences, and harness fixtures; S262 owns catalogue/revision reconciliation and all nitpicky builds; S263 owns the documentation em-dash regression; S264 owns hermetic `cadrumo-mcp` delivery to installed subprocess proofs; S265 owns the `overview.calendar` schema budget; S266 owns both Windows typed root descriptor refusal and WSL fd-leaf passphrase change; S267 owns feature/full Vaultspec hygiene by exact document owner.

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
