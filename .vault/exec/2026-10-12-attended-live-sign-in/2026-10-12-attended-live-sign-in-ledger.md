---
tags:
  - '#exec'
  - '#attended-live-sign-in'
date: '2026-10-12'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:54713145daa51eb0db790fb03caf952818d7a09a364857062ee3522891354647'
related:
  - "[[2026-10-12-attended-live-sign-in-plan]]"
---

# `attended-live-sign-in` ledger

## Changes

- `S01` `A` `src/cadrumo/application/runtime/attendance.py`
- `S01` `M` `src/cadrumo/application/runtime/profile_access.py`
- `S01` `M` `src/cadrumo/application/user_profile/access_contracts.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_policy.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_core.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_access.py`
- `S01` `M` `src/cadrumo/application/user_profile/session_authority_admission.py`
- `S01` `A` `src/cadrumo/entrypoints/runtime/profile_connection_attendance.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/profile_connections.py`
- `S01` `M` `src/cadrumo/entrypoints/runtime/profile_connection_sessions.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/server_connection_handling.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/runtime_profile_transport.py`
- `S01` `M` `src/cadrumo/adapters/local_runtime/frontend_client.py`
- `S01` `A` `src/cadrumo/entrypoints/runtime/tests/test_attendance.py`
- `S01` `verify:` `pytest -m integration src/cadrumo/entrypoints/runtime/tests/test_attendance.py` -> `pass`
- `S01` `verify:` `mutation control (holder requirement disabled) fails test_attendance` -> `pass`
- `S01` `verify:` `pytest -m unit application/user_profile application/runtime custody/test_session_authority (1169)` -> `pass`
- `S01` `verify:` `pytest framing + session authority integration (100)` -> `pass`
- `S01` `verify:` `ruff check, ty check on changed modules` -> `pass`
- `S01` `by:` `claude`
- `S02` `A` `src/cadrumo/entrypoints/cli/config/sign_in_hold.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/_custody_command_specs.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/custody.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/custody_payloads.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/command_operation_table.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/command_frontend_counterparts.py`
- `S02` `M` `src/cadrumo_harness/_data/agent/reference/command-operations.md`
- `S02` `M` `src/cadrumo/locales/en/cli.yml`
- `S02` `M` `src/cadrumo/locales/es/cli.yml`
- `S02` `M` `src/cadrumo/locales/ca/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `verify:` `aeat config sign-in-hold --help (dev env)` -> `pass`
- `S02` `verify:` `aeat config logout --help lists --secrets-stdin/--secrets-fd` -> `pass`
- `S02` `verify:` `pytest test_command_frontend_parity, test_command_operation_reference, test_command_operation_join (61)` -> `pass`
- `S02` `verify:` `ruff check, ty check on sign_in_hold.py and custody.py` -> `pass`
- `S02` `by:` `claude`
- `S03` `M` `src/cadrumo_harness/mcp/runtime_adapter.py`
- `S03` `M` `src/cadrumo_harness/mcp/runtime_admission.py`
- `S03` `M` `src/cadrumo_harness/mcp/tests/test_sign_in_resume.py`
- `S03` `verify:` `pytest src/cadrumo_harness/mcp/tests/test_sign_in_resume.py (27)` -> `pass`
- `S03` `verify:` `ruff check, ty check on runtime_adapter.py and runtime_admission.py` -> `pass`
- `S03` `by:` `claude`
- `S04` `M` `docs/how-to/connect-an-agent.md`
- `S04` `M` `.vault/adr/2026-10-12-mcp-parity-attended-live-sign-in-adr.md`
- `S04` `M` `.vault/adr/2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr.md`
- `S04` `M` `.vault/adr/2026-10-10-mcp-parity-shared-sign-in-door-adr.md`
- `S04` `M` `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md`
- `S04` `M` `.vault/adr/2026-10-04-application-sign-in-adr.md`
- `S04` `verify:` `docs contract matches the dev-environment real-process run of dev.runtime_lifecycle.live_sign_in (all lifecycle steps held; expiry skipped)` -> `pass`
- `S04` `by:` `claude`
- `S05` `A` `dev/runtime_lifecycle/live_sign_in.py`
- `S05` `M` `dev/runtime_lifecycle/caller_owned_root.py`
- `S05` `M` `dev/runtime_lifecycle/README.md`
- `S05` `M` `justfile`
- `S05` `M` `src/cadrumo/application/user_profile/session_authority_core.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/config/sign_in_hold.py`
- `S05` `M` `src/cadrumo/entrypoints/runtime/tests/test_attendance.py`
- `S05` `verify:` `just verify-live-sign-in build/windows-x64/stage/Release/app (manifest sha256 24b8d3c3..., 18:29-18:48Z, expiry included): every lifecycle step held; exit 3 incomplete for the reviewed operation only` -> `pass`
- `S05` `verify:` `pytest -m integration test_attendance.py five consecutive runs` -> `pass`
- `S05` `verify:` `pytest application/user_profile + MCP test_sign_in_resume (1002)` -> `pass`
- `S05` `by:` `claude`
- `S05` `M` `dev/runtime_lifecycle/live_sign_in.py`
- `S05` `verify:` `just verify-live-sign-in build/windows-x64/stage/Release/app` -> `fail`
- `S05` `verify:` `just verify-live-sign-in build/windows-x64/stage/Release/app --skip-review` -> `fail`
- `S05` `verify:` `just verify-live-sign-in build/windows-x64/stage/Release/app` -> `pass`
- `S05` `M` `native/CONTRACT.md`
- `S05` `M` `native/package-layout.json`
- `S05` `M` `src/cadrumo/adapters/local_runtime/frontend_client.py`
- `S05` `M` `src/cadrumo_harness/mcp/runtime_adapter.py`
- `S06` `M` `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`
- `S06` `M` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_profile_worker_custody_lease_window.py`
- `S06` `M` `src/cadrumo/application/runtime/contracts.py`
- `S06` `M` `src/cadrumo/application/runtime/attendance.py`
- `S06` `M` `src/cadrumo/adapters/local_runtime/windows_channel.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/profile_connection_attendance.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/profile_connections.py`
- `S06` `M` `src/cadrumo/entrypoints/runtime/tests/test_attendance.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/config/sign_in_hold.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/config/custody.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/config/tests/test_runtime_logout.py`
- `S06` `M` `docs/how-to/connect-an-agent.md`
- `S06` `M` `.vault/audit/2026-10-13-attended-live-sign-in-audit.md`
- `S06` `M` `.vault/plan/2026-10-12-attended-live-sign-in-plan.md`
- `S06` `verify:` `pytest test_profile_worker_custody_lease_window.py` -> `pass`
- `S06` `verify:` `pytest test_attendance.py` -> `pass`
- `S06` `verify:` `pytest test_runtime_logout.py` -> `pass`
- `S06` `verify:` `ruff check, ruff format --check, ty check on touched files` -> `pass`
- `S06` `verify:` `just check-import-boundaries` -> `fail`

## Notes

- `S02` Code was swept into c7fbea9454 by another session's catch-all commit; the counterpart declaration and regenerated reference landed in 9790b9e63c. Command name is config sign-in-hold (ADR hypothesis config sign-in hold); password arrives as the first stdin line, not --secrets-fd; both reconciled in the ADR under S04. Other CLI suites showed 11 failures from `runtime_deadline_exceeded/KDF_RESOURCE_LIMIT` under 100% host CPU from concurrent sessions, not from this change.
- `S03` Adapter code was swept into c7fbea9454 by another session; test updates committed in 9790b9e63c. Packaged end-to-end proof is S05.
- `S04` ADR amendments reconcile: command named config sign-in-hold (hypothesis was config sign-in hold); password read as the first stdin line, not --secrets-fd; bounds 120s ask, 8 pending, 90s MCP wait; attended children judged by lineage without automation custody.
- `S05` Packaged proof found and fixed two defects: lease revalidation retired attended children where the automation store is unavailable (6521d4c2ca), and the holder could abort at shutdown with a daemon thread blocked on buffered stdin (6521d4c2ca).
- `S05` Unproven: a safe operation with a real review response. Every review-gated operation (ledger.classify.review, ledger.split.review, config.google.login, export.google-review, user-profile.censo-review) reaches a remote service, hands data to a model, or needs a censal document no parser accepts. S05 stays open for that item.
- `S05` Observed, not ours: the package redacts profile ids even with `CADRUMO_CLI_REVEAL_IDENTIFIERS=1` (dev env reveals them); MCP search failed on person-act describe refusals, fixed by another session in 07b729934c after this package was built.
- `S05` Package built from HEAD e11fb302f2 with 21 dirty paths from other sessions; packaged `runtime_adapter.py` predates a408f4b773.
- `S05` Package manifest 50301ff0bf9402f117e7e995cece9cef71d78ed5f3186f8fc568d16e752338ec. With --skip-review the run exits 3 (incomplete) and every attended lifecycle step passes: decline, wrong profile, approved read with search, sign-out, input close, logout, lock/resume, expiry, runtime stop, no stored sign-in, default root unchanged, no survivors. Reveal identifiers works in the package. The full run fails at review approval: the bundle is core-only with no llm extra, so ledger.classify.review refuses with `ERROR_OPTIONAL_EXTRA_MISSING` at ledger.llm.acquire, effect none, the absent-llm lane's tested contract. Bundling the llm extra awaits an operator decision. The driver now stops the model runner with its server; four orphaned llama-server runners were reaped.
- `S05` Package manifest ec2e4fac443201e94e0b4c714328b8214db3e3f8ec36053af18c5730311d4e38 bundles the llm extra (c77c8d074a, ruling e4124e5b53). The full run passed with expiry and review: ledger.classify.review classified BUSINESS by llm:local-text:qwen3:1.7b, reviewed, nothing written before the decision, read back by the CLI. No model runner survived.
- `S05` Rows for fa4f7dc9c5 appended after the plan-close review found them unlogged. The package-layout change admits `CADRUMO_CLI_REVEAL_IDENTIFIERS` to the installed overrides, which the operator asked for on 2026-10-12.
- `S06` Neighbouring tests: 205 passed, 3 failed in `test_config_custody_profile_lifecycle.py.` All three fail with `runtime_deadline_exceeded` because another session's uncommitted `holder_operation_id` field in `profile_connection_operations.py` fails RuntimeAccessRefusal validation; none of those files is in this Step.
- `S06` check-import-boundaries: all 15 contracts kept; its 188 hard findings are in test files outside this Step, and the tree changed during the run. ruff format flags `sign_in_hold.py:99,` unchanged since HEAD.
- `S06` Image path is read on Windows only; Linux and macOS report null (audit finding attendance-peer-facts-posix). The client-id restore on a refused approval has no direct test.
