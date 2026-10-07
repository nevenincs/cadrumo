---
tags:
  - '#audit'
  - '#desktop-environment-readiness'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:d4812817aa67fe74f61e117e17fec2e8d42f23ca43777d914a0a792a6e5d8f65'
related:
  - "[[2026-10-07-desktop-environment-readiness-plan]]"
  - "[[2026-10-04-desktop-shell-adr]]"
---

# Desktop environment readiness audit

## Scope

Canonical environment projection and working directory for desktop Console, Python and TUI terminals; bundled command resolution; existing runtime admission and development storage inheritance. Independent integrated reviewer found no blocking code defects. Platform/session acceptance is distinguished from isolated automated evidence.

## Findings

### console-workspace | medium | Terminals lack a consistent CADRUMO operator workspace

Resolved by declaring a fixed console workspace in the core storage taxonomy, creating it through both native and Python projections, and selecting it for all terminal kinds. The workspace is separate from encrypted profile custody. Standalone invocations retain caller cwd. The desktop shell ADR amendment records the user's requested change from home cwd.

### bundled-python-path | medium | Windows console may select a system interpreter

Resolved by putting both bundled native entrypoints and the bundled interpreter directory ahead of inherited PATH for every terminal kind. Preparation removes Windows PATH aliases and remains idempotent. User shell startup profiles remain enabled and may deliberately customize the environment.

### runtime-attachment | low | Environment contract needs explicit attachment and development guidance

Existing interactive CLI and TUI receipt admission already resumes selected signed-in profiles through verified native IPC. No authentication environment variable or client runtime supervisor is introduced. Existing desktop manager startup dispatch and account-status readiness polling are implemented. Added subprocess regression coverage for source development commands preserving inherited storage and authority pins from an unrelated cwd. Updated native contract describes noninteractive credentials and source/runtime version and authority compatibility.

## Verification

Initial evidence: 33 focused CLI/TUI/runtime admission unit tests and seven storage inheritance integration tests passed. Python workspace projection and native terminal checks are being finalized by the implementation owner. Repository formatting passed for 11914 files; repository lint found a concurrent unrelated SIM117 in dev/ci/modelo_runtime_benchmark.py. Configured type and import checks pending.

Final source verification: 208 desktop Rust unit tests passed (build/desktop-windows-x64/environment-unit-tests.log); 33 unique S01 Python tests and 40 S02 Python tests passed. The fixed-taxonomy fingerprint regression also passed in the six-test fingerprint suite. Scoped Ruff, formatting and diff checks passed. Independent integrated source review passed with no blocking findings; the temporary-directory portability observation was resolved. Full configured types reported one concurrent authority-migration unresolved import in native/desktop/tests/packaged/runtime_fixture.py:31. Direct import-gate invocation failed because its child lint-imports executable was outside PATH and metadata is stale; rerunning through the configured uv environment. Live authenticated packaged GUI acceptance remains unrun.

Review status: source PASS with no unresolved findings; repository verification remains PENDING because configured lint/types have unrelated shared-worktree failures. S01 and S02 are complete; S03 remains open for a clean repository verification checkpoint. Scope-specific tests and documentation are complete. No authenticated desktop session or rebuilt full package was exercised.

Configured uv import-gate rerun completed: dependency graph contracts passed (10648 files, 80198 dependencies), but overall gate failed because the shared import-load target metadata is stale. Full log: build/desktop-windows-x64/environment-import-gate.log. This is retained as an open repository verification limitation, not a passing check.

The same import-gate snapshot also reports six subordinate findings outside this patch: one noncanonical CalculationRevisionCatalogue import in dev/ci/tests/test_modelo_runtime_benchmark.py and five unresolved custody_payloads imports in CLI custody and tests during concurrent edits. These prevent a clean integrated repository verdict; no source review or runtime availability claim overrides them.

## Recommendations

Run live packaged desktop sign-in followed by Console CLI and TUI receipt attachment in an interactive desktop session. That acceptance has not been performed; isolated tests do not establish it.
