---
tags:
  - '#plan'
  - '#type-check-fixes'
date: '2026-10-15'
tier: L1
related:
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-09-02-gate-integrity-adjudication-negative-test-typing-adr]]'
modified: '2026-10-14'
body_schema: body-v2
body_hash: 'sha256:4b4631d73a0dbd41f08da6375cefa1739426e4a4b6e1e4b1ff815c1333ebf5b2'
---

# `type-check-fixes` plan

## Description

Approved 2026-10-15

The user explicitly requested a fresh type-check run and fixes for all findings, using Luna at maximum reasoning and Sol 6.1 at medium reasoning. The current exact-scope baseline reports 350 folded diagnostics; .tmp/type-findings-current.json records their owning files and platforms. Preserve concurrent refactoring and update callers to canonical definitions rather than restoring retired paths.

The accepted import-centralization decision governs canonical modules, inert packages and dependency direction for every Step. The accepted negative-test typing decision governs payload and annotation repairs without changing refusal assertions. This work implements existing contracts and introduces no new costly decision. Existing refactor plans remain independent; this plan closes only the type-finding repairs it verifies.

## Steps

- [x] `S01` - Repair canonical runtime client service and harness imports and typed contracts; `src/cadrumo_client, src/cadrumo_runtime except host/tests/frontend/cli, src/cadrumo_agent_service, src/cadrumo_harness`.
- [x] `S02` - Repair tax CLI consumers and fixture invocation contracts; `src/cadrumo/entrypoints, src/cadrumo_runtime/host/tests/frontend/cli, src/cadrumo/tests/cli_fixture_ports.py, conftest.py fixture imports`.
- [x] `S03` - Repair developer consumers and calculation rendering inference; `dev, src/cadrumo/domain/modelos/calculation_revision_rendering.py, src/cadrumo/entrypoints/cli/tests/live_command_validation.py, src/cadrumo_agent_service/admin.py`.
- [x] `S04` - Verify all configured type scopes and review integrated repairs; `conftest.py, src/cadrumo/core/config.py, src/cadrumo/domain/transactions/classification_origin.py, pyproject.toml, affected source and type-check evidence`.

## Parallelization

S01, S02 and S03 may run concurrently after the baseline finishes. Luna max owns S01 production under src/cadrumo_client, src/cadrumo_runtime, src/cadrumo_agent_service and src/cadrumo_harness plus their tests except the following transferred scopes. After S03 focused checks pass, its Sol 6.1 medium worker owns runtime adapters/tests, application/tests, commands/tests and host/tests except host/tests/frontend/cli. The S02 Sol 6.1 medium worker owns src/cadrumo/entrypoints, the runtime-host frontend CLI test subtree, and the relocated client commands/tests/test_login_session_not_persisted_notice.py. That worker also owns test-only support extraction and consumer relocations needed to preserve private production ownership. S03 initially owns dev and the specifically diagnosed domain calculation file. Root owns conftest.py, src/cadrumo/core/config.py, src/cadrumo/domain/transactions/classification_origin.py, pyproject.toml, all shared configuration, plan and ledger mutations, and the full verification runner. Workers request ownership transfers before editing another worker's files and preserve external edits. No worker commits shared in-flight changes. Root serializes checkpoints and commits only independently reviewable changes.

## Verification

Retain configured ty discovery and the strict pyrefly and basedpyright scopes across Linux, Windows and macOS. Never add suppressions, type-erasing casts, compatibility aliases, dropped tests or broader exclusions to obtain a pass. Preserve fixture scope, teardown and refusal assertions when repairing moved test consumers. The session's check scope remains type checks; run no test suite. Use focused type checks during repairs, local Ruff checks for edited files, and finish with just check-types and an integrated code review. Record actual outcomes and any concurrent changes that limit evidence.
