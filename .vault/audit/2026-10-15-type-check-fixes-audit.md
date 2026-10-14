---
tags:
  - '#audit'
  - '#type-check-fixes'
date: '2026-10-15'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:8a9390d0848b5c33a49c6b3323b4e94e83bd3f11b98b9ceb203340973dd6d916'
related:
  - "[[2026-10-15-type-check-fixes-plan]]"
---
# `type-check-fixes` audit: configured type repairs and shared-boundary behavior

## Scope

Review the repairs recorded by the 2026-10-15 type-check-fixes plan and its worker manifests, including uncommitted changes in the shared worktree. The initial exact-scope sweep recorded 350 folded findings. Independent Luna review assesses current defining-module ownership, exception and refusal behavior, typed CLI execution, registry rendering, shared test support and actual worker/service authority boundaries. The root owns the full type-check gate and audit; no test suite is executed under the user's type-check-only scope. Source attribution uses worker handoffs and current file evidence because the full HEAD diff includes pre-existing and concurrent refactoring.

## Findings

### verdict-attachment | high | Generic attachment must support recorded errors with a property

The generic attachment helper in `src/cadrumo_client/commands/errors.py` initially assigned a getter-only terminal verdict property when the recorded error path in `src/cadrumo_runtime/commands/runtime_auth_login.py` requested a diagnostic follow-up. That would replace the intended refusal with AttributeError. The root added a typed setter backed by the existing verdict field. The helper retains the same exception object and type, and the caller still refuses to replace an already recorded verdict. Focused ty and Ruff checks passed; independent source re-review confirmed the correction.

### command-type-boundary | high | Command introspection must use the actual Typer command type

During concurrent editing, `dev/agent_eval/tests/_real_cli_support.py` cast a Typer-vendored command to the distinct upstream Click command class. This hid a concrete class boundary and contradicted the plan's typing policy. The assigned Sol worker is correcting the command annotation, its development consumers and the owning option-inspection helper without a cast. Final verification and re-review remain pending.

### command-type-resolution | low | Actual command classes now preserve both caller families

The Sol follow-up removed the nominal command cast and uses the actual Typer-vendored command class. Conformance traversal narrows the actual group with TypeIs. The owning option inspector accepts the two real command families and checks their corresponding option classes. Independent source review found no remaining high or critical issue in this correction; focused ty checks across all three platforms and Ruff passed.

### cleanup-follow-up | low | Optional cleanup handles preserve the concurrent async owner

Concurrent refactoring replaced the original service-record fixture teardown with NativeRuntimeFixtureOwner and close_async_resources. The final typing repair in `src/cadrumo_runtime/host/tests/test_service_records.py` collects optional completed connections through a precisely typed owning helper. Both partial-setup guards remain, service clients precede the human connection, and native ownership follows them in async cleanup. Independent review confirmed that early setup failures and the existing retry/drain path retain cleanup. Focused type checks on all three platforms and Ruff passed.

### ingress-json-boundary | high | Fresh service-test response extraction must retain real JSON types

The late provider-ingress test edits exposed an object-valued response at nested extraction. The first bare-dictionary narrowing admitted untyped nested values. S03 was reopened and replaced frame decoding with strict TypeAdapter validation into dict[str, JsonValue], with explicit nested provider list, object, identity, revision and availability checks. Existing bearer, lease, refusal, revision-conflict and secrecy comparisons remain. Focused ty across all three platforms and Ruff passed on the final recorded source hash. Independent review confirmed the correction. A subsequent concern about narrowing the already typed JsonValue union was withdrawn after actual checker inference showed dict[str, JsonValue] and JsonValue, without Any; no redundant validation was added.

### integrated-verification | low | Final review passes with platform and freshness evidence

PASS: the independent Luna max reviewer found no unresolved high or critical issue in S01 through S04. The literal just check-types command exited zero, covering ty, pyrefly and basedpyright across Linux, Windows and macOS; its log is `.logs/check-types-clean-20261015.log`. Before/after fingerprints each contained 11349 inputs, with three concurrent test-file changes rather than an immutable full-gate snapshot. Later external edits were covered by a new complete project ty sweep across all three platforms, recorded in `.logs/type-gate-project-linux.log`, `.logs/type-gate-project-win32.log` and `.logs/type-gate-project-darwin.log`. The strict production scopes and gate configuration remained unchanged from the passing full gate. The one attendance test changed during that later sweep received fresh all-platform checks with an unchanged hash. The final ingress JSON correction likewise received all-platform focused ty and Ruff checks, recorded in `.tmp/dev-type-fixes-evidence.json`. No test suite was run. These results apply to the recorded shared-worktree inputs; concurrent refactoring continues independently.

## Recommendations

All recorded high findings are resolved and every plan Step is complete. Reuse the passing evidence while its inputs remain applicable, and recheck affected scopes when concurrent refactoring changes them. Preserve the uncommitted shared refactor; no isolated commit was possible without staging another writer's changes.
