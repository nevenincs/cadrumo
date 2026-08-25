---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:84509f30c6a8f352142c7f9090fa31f79043f9e7c08cd5ebe145b26b074f15b6'
step_id: 'S55'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Relocate credential, login, registration, and passphrase projections while keeping secrets ephemeral

## Scope

- `src/cadrumo/entrypoints/tui/secret`

## Description

- Move the credential, login, registration, and secret-free passphrase-assessment projections to their canonical direct modules.
- Keep the canonical secret namespace inert, delete legacy secret modules and exports, and rewrite the affected presentation consumers and tests to direct canonical imports.
- Retain recovery confirmation solely within registration's short-lived handoff path; do not add persistence, logging, envelopes, backend validation, or orchestration policy.

## Outcome

- Independent review approved S55.
- The canonical secret surface is now the only presentation authority for these projections; legacy definitions and imports are absent.
- The implementation landed in `ca544edcae`; the locale-prefix inventory hunk landed in `04ea7186d0`.

## Verification

- Focused Textual integration suite passed: 31 tests.
- Focused no-generated-secret-display unit gate passed: 5 tests.
- Scoped Ruff and ty checks passed.
- Scoped legacy secret path, definition, and import census passed; the retention census found only the ephemeral recovery handoff, with no persistence, logging, envelope, or write sink.
- `git diff --check ca544edcae^ ca544edcae` passed.

## Notes

- Two wrong-password login nodes were excluded from the focused presentation run because the pre-existing CLI refusal mapper does not catch `ProfileAuthenticationRefusedError`. The S55 login diff is import and module relocation only; no authentication classification policy changed.
- The global migration-identity digest remains external integration debt owned by its census owner and was not refreshed by S55.
