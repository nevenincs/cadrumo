---
tags:
  - '#audit'
  - '#runtime-without-service-manager'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:d638b8b8b5dc023b0dcb4e68f021f304215f8f9ac2fcef9b2b3543c7861a1dd7'
related:
  - "[[2026-10-03-runtime-without-service-manager-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
---

# `runtime-without-service-manager` audit: scope removal

## Scope

Reviewed the MCP runtime and profile-access ADRs, the runtime-without-service-manager ADR, their open implementation scope, and the live runtime, CLI, TUI, locale, test and documentation surfaces on 2026-10-03. The worktree contains concurrent changes. The operator authorized removal of runtime management and preservation of the runtime; external machine registrations were not changed.

## Findings

### SCOPE-001 | high | Runtime management was included in runtime authority

The accepted runtime ADR required OS service registration, health/start/stop controls and CLI/TUI management parity. The operator explicitly withdrew those requirements on 2026-10-03 and deferred management to application bundling, building and provisioning. Focused amendments remove those commitments from both MCP ADRs; the runtime-without-service-manager ADR records the accepted boundary. Runtime authentication, custody, safe shutdown and worker containment remain required.

Resolution: decision wording amended. Source removal and verification are in progress and were not certified by the initial finding.

### COVERAGE-001 | low | Semantic discovery and hosted coverage are bounded

Code semantic discovery returned rebuild_required because the existing sparse-vector index is incompatible with configured embeddings. Targeted source inspection and paged ADR inventory were used instead. Vault semantic search returned the relevant runtime records. The three-source hosted crossref pass returned ok with no conflict verdict; it reported source/candidate truncation, 116 requests and 368744 input tokens. The relevant complete ADRs were read locally. This is a scoped runtime-decision review, not corpus-wide certification.

### REMOVAL-001 | low | Management removal preserves the runtime boundary

Resolved: removed all platform service-manager adapters, managed bootstrap arguments/branches, runtime owner-stop and health request/reply protocols, CLI administration commands, TUI health/lifecycle controls and their dedicated tests. Removed 180 retired locale leaves through the catalogue authority, retaining the four translated profile-recovery uncertainty values under their owning access key. Generated CLI references and the command tree were rebuilt; retired command pages and sequence artifacts were removed. Source and product-document scans found no residual removed APIs or registrations.

Clients now connect to an explicitly started runtime and return typed unavailability otherwise. Native peer/cohort handshake, profile/session/grant administration, operation control, internal shutdown and descendant containment remain. The retired installed MCP recovery test exercised Task Scheduler supervision and automatic restart, both excluded; existing installed authentication and native transport tests remain.

### CLEANUP-001 | medium | Closed session calls retried a retained cleanup owner

The surviving session API exposed a cleanup difference when transport tests were moved from the retired health request. A closed call entered the exchange failure handler and retried native release. Resolved by checking the closed state before that handler, preserving explicit cleanup ownership. The subsequent focused framing/TUI/MCP run passed all 75 tests.

### VALIDATION-001 | low | Integrated acceptance remains pending concurrent imports and native coverage

The initial focused transport run had 75 passes and three cleanup failures; those failures were fixed and the relevant framing tests passed in the subsequent 75-test run. Launch-door, server, connection serialization and submission streaming cases passed in that initial run. Native endpoint/installed-client checks had 14 passes and 26 platform skips; installed runtime convergence failed to reach readiness within its existing bound. TUI admission and documentation sequence collection subsequently failed on the concurrent activity-asset refactor: first ActivityAssetOperationPorts, then ActivityAssetClaimProjection imports. These modules were not edited by this change. They also prevent installed runtime composition from being established reliably. Do not infer that the startup failure is fully diagnosed or claim installed acceptance.

Changed production surfaces passed targeted type checking; the inspected runtime/frontend surfaces passed lint. CLI graph inspection confirmed that the runtime administration family is absent. Detailed command outputs are in the task's temporary check reports and the repository test-run logs. Native macOS/Linux behavior is unproven on this Windows host. Review verdict: PENDING until integration gates can run against a stable composition and installed startup passes.

### VALIDATION-002 | low | Final validation update

Independent login/access tests passed 60 cases; runtime opener cleanup tests passed 15 cases after removing a stale monkeypatch of the deleted manager factory. A surviving login form selector still referenced the removed status button; that selector was removed. The subsequent admission run could not collect because activity_asset_contracts.py raised NameError for dataclass. Documentation coherence failed importing WorkflowObligationSnapshot from the concurrently edited workflow package. These external modules were not changed here.

Installed-runtime logs show isolated imports consuming about 12 seconds, then registry_prepare entry without completion before the existing 20-second readiness bound. The cause is not established; the bound was preserved. Full import-gate verification failed with a changing source snapshot, stale target metadata and 68 reported findings. Locale audit reports unrelated missing modelo.schema.131 revision.2026-late labels and extra workbench.grid.row_boxes keys across all four locales. Feature vault checks found no errors; the older MCP feature retains unrelated whitespace warnings and in-flight ledger notices.

Final targeted inspection found no remaining service registration, runtime health APIs or management UI/CLI controls. The remaining systemctl/systemd-run adapter supports transient worker containment. Review remains PENDING for installed startup and integrated gates; implementation removal is recorded, not full acceptance.

### FIXTURES-001 | medium | Development and test-owned lifetimes clarified and corrected

The operator requested complete runtime test execution, timing and automatic fixture startup/teardown. The ADR now explicitly permits test-owned runtime lifetimes while excluding product management. The developer test guide distinguishes unit tests, isolated native integration fixtures and manually started runtimes for interactive clients.

Execution found and corrected a fixture that installed an immutable ProfileWorkerCustody binding in the pytest process: test_approval_task_authority now runs its body in a disposable child, preserving the production no-reset rule. The corrected test followed by six enrollment tests passed (7 tests, 132.23 seconds), proving subsequent tests can use different profiles. A PID readiness file was visible before its contents were written; worker_approval_fixture now publishes it atomically. Its owning channel test passed in the focused native rerun. The cancellation fault client now yields the typed WorkerAuthorizationLease expected by provenance capture; registry setup precedes the journal pause timer. Both cancellation scenarios subsequently passed (30.83 and 26.91 seconds).

Two explicit teardown proofs passed: the launch-door fixture reaps its running child after an assertion failure, and installed-launch ExitStack teardown releases its process tree when the test body fails. Launch-door teardown now also closes the endpoint when child cleanup raises. Forty native fixture files now prepare their registry before starting transport, matching installed startup rather than charging registry construction to a login request. The prepared fixtures pass lint and type checking; integrated execution remains in progress.

### TIMING-001 | low | Cold-start setup exceeded the inherited test budget

The installed-entrypoint check failed at 20.007 seconds with ENDPOINT_NOT_READY. A separate bounded diagnostic using the real installed executable reached a verified handshake in 27.186 seconds: main import took 11.186902 seconds, registry preparation 14.063851 seconds, and listener setup 0.024525 seconds. This demonstrates successful cold startup exceeding the inherited 20-second fixture allowance. The installed fixture now gives bootstrap and competing launchers a shared 60-second setup allowance, separate from unchanged three-second request deadlines. A later run reached a shared boot identity but showed one losing launcher still completing bootstrap after the old three-second convergence window; that window now uses the original startup deadline. This does not certify a production startup performance target. Measurements were on this Windows host amid concurrent work.

### VALIDATION-003 | low | Broad runtime execution found remaining native failures

Initial combined collection stopped on the concurrently moved M145CommunicationOperationRecordNotFoundError error-code registration (39 collection errors, 47.87 seconds); later runs collected successfully after that external change settled. The full application/runtime plus local_runtime boundary run had 714 passes, 71 skips and six failures in 701.98 seconds. Failures were native shutdown/startup/descendant readiness plus the corrected PID publication race. The frontend run had 114 passes and one native login timeout in 146.48 seconds. The first full runtime-entrypoint run had 141 passes, one skip, 63 failures and five errors in 629.04 seconds; 61 conflict errors were downstream of the process-pinning fixture defect. Its corrected broad rerun ended with recorded exit 3 during native automation approval before completing; do not interpret that as a passing integration run. Focused fixes and prepared-fixture/MCP runs are being recorded separately. Review remains PENDING until outstanding native and installed acceptance checks pass.

### VALIDATION-004 | low | Startup, teardown and containment corrections verified

The installed convergence/restart test now passes in 58.64 seconds total (55.67-second test body, covering competing launchers and a second cold start). Installed mismatch and assertion-failure teardown checks passed separately; Linux endpoint coverage is skipped on this Windows host. The cancellation scenarios pass after registry setup was moved outside the journal pause timer. All eight launch-door cases passed after teardown correction. The PID publication fix passed its native channel test.

Windows job inheritance/process tests initially timed out because finite probe/tree children imported the full profile-worker fixture stack before publishing their process records. Owner-only imports were moved into the owning fixture branches. All 11 owning containment tests subsequently passed in 48.97 seconds with their original deadlines. No production containment code was changed.

The selected installed MCP and frontend-parity acceptance run completed with 9 passes, 3 skips and 7 failures in 711.55 seconds. Every failure reports AutomationCustodyError UNAVAILABLE from native credential custody; those tests do not certify native credential-store behavior on this host. The passing parity cases exercise fixture-owned runtime startup, client authentication and teardown.

### VALIDATION-005 | low | Concurrent ledger refactor blocks isolated worker startup

A repeated native profile-worker test still failed with CONNECTION_CLOSED (24.16 seconds total). Running the real isolated worker import directly with `uv run --no-sync python -I -m cadrumo.entrypoints.runtime.worker --help` exposed the cause: ledger/update_contracts.py imports the removed cadrumo.application.actions_common module, raising ModuleNotFoundError before the worker opens IPC. That ledger file was not modified by this task. Current prepared-fixture tests therefore cannot establish worker integration, regardless of a running parent runtime. Complete their acceptance after the application refactor restores a coherent isolated import graph. Do not widen request deadlines or mock the worker to conceal this failure.

### CONFIG-001 | low | Operator-requested local setting has an in-flight polarity mismatch

The operator reported a concurrent session-policy override implementation and explicitly requested value 0 in the local .env. Set and verified CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE=0 in env/.env without exposing other entries. At inspection, env/.env.example and core/config.py still defined literal 1 as enabling the development override, with 0/unset retaining strict checks. That implementation is owned by the other session; this task did not invert it. The local value is as requested, but development-mode behavior cannot be inferred until the polarity is aligned. Product Settings intentionally does not read dotenv files; manual development commands must load env/.env explicitly. Tests retain explicit policy isolation rather than blanket inheritance of a local development override.

### VALIDATION-006 | low | Import repair does not yet establish worker acceptance

The concurrent ledger import was subsequently corrected. A fresh isolated worker --help invocation passed, so VALIDATION-005's specific missing-module observation is historical, not a claim about the latest tree. The focused concurrent-profile worker test still failed after startup while installing the first lease (CONNECTION_CLOSED; 47.76 seconds total). That remaining failure is unresolved and cannot be attributed solely to the earlier import error. The final prepared-fixture batch remains the broader acceptance check. Preserve strict custody and transport assertions; do not call these failures passing based on the session-policy override work.

### VALIDATION-007 | low | Final prepared-fixture batch completed; acceptance remains pending

The changed native fixture test modules were executed with `uv run --no-sync pytest -q -n2 --dist=loadfile -m 'unit or integration' <changed test modules> --durations=20 --tb=short`. The complete run returned 25 passed, 39 failed and 4 errors in 1591.74 seconds (26m31s), exit 1. Full evidence: C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-10-03/20261003T094255.332961Z-pytest-54984-1aeb917d/run.log. The execution ledger enumerates the changed fixture modules. Do not combine overlapping reruns into a fabricated single pass total.

The fixture updates, installed convergence/restart, assertion-failure cleanup, cancellation and native containment have applicable focused evidence. The whole runtime suite is not green: worker connection/admission failures, native request deadlines, enrollment assertions and four teardown errors remain in the broad run against the concurrently changing tree. Native MCP custody capability failures are reported separately in VALIDATION-004. The test plan's integration acceptance remains open. No product service manager or health API was introduced, and no security/custody assertion was weakened. Local env/.env was set to the operator's explicit value 0, with the in-flight polarity discrepancy documented in CONFIG-001. Final review verdict: PENDING.

## Recommendations

Preserve the accepted management exclusion. Complete the pending integration checks after the concurrent activity-asset import migration settles; investigate installed startup if it still fails. Design runtime management only with application bundling, building and provisioning. Do not recreate registration or health APIs to satisfy retired tests.
