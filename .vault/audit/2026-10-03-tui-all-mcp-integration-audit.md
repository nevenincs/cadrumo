---
tags:
  - '#audit'
  - '#tui-all-mcp-integration'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:ae668c3017aaa6104fb4fc7cb20632319ef85aceafb9131e2a025334a6301a80'
related:
  - "[[2026-10-03-tui-all-mcp-integration-plan]]"
---
# `tui-all-mcp-integration` audit: MCP recovery and combined runtime behavior

## Scope

Review the original-base deltas of all six preserved MCP worktrees, the collision scratch lineage and conflict-stage evidence, and later relevant TUI work in the isolated integration branch. The user authorized implementation, routine conflict resolution, verification and safe landing. The original worktrees and their indexes remain untouched by the integration. Accepted runtime decisions require transient session-owned containment and preserve the current runtime-mediated CLI/TUI admission boundary.

The source inventory contains 3,069 original source/path deltas. The disposition corpus accounts for every pair and also records selected later TUI captures, excluded transaction locks, and unrelated active-writer paths preserved outside this MCP scope. A disposition is an intent assessment with an original base, source snapshot, source-delta hash, replacement and reason; mechanical equality alone is not the semantic decision. Integration commit mappings are finalized after coherent checkpoints.

## Findings

### stale-coalition | high | Orphan cleanup could lose custody when a transient launchd job disappeared

Resolved. `src/cadrumo/adapters/local_runtime/macos_worker_process.py` now reaps the saved coalition even when launchd no longer lists its job, and retains its marker/refuses replacement when verified termination fails. Independent orphan and failed-termination tests cover the custody invariant. Native Darwin containment exercises parent, guardian and worker loss, browser descendants, setsid/regroup escape, registration loss, churn and stale-job recovery: eleven tests passed. A final shared-process fixture rerun passed two tests; unchanged containment code permits reuse of that evidence.

### darwin-worker-admission | high | Native worker routing and explicit authority controls were missing

Resolved. Darwin now selects the POSIX worker endpoint. Worker and guardian environment construction preserves the declared storage, authority and temporary path controls while excluding ambient credentials and interpreter injection. Actual native startup diagnostics established the missing authority cause before the correction. The final native containment run passed after a verified source overlay; Windows portable checks were not substituted for Darwin behavior.

### historical-collision | high | Trial markers and obsolete resolutions cannot govern the recovered product

Resolved through per-path disposition. The collision trial, scratch parent and conflict-stage refs remain immutable evidence. Conflict-marker files were rejected; newer runtime, registry, typed authority and CLI owners supersede obsolete trial code where recorded. The earlier binding-consumer plan was recovered from its latest actual historical blob through the owning CLI, retaining its original twelve Steps and six completed Steps. Ten omitted historical purpose-authentication ledger rows were restored through the ledger CLI; those rows preserve history and do not reinstate runtime administration.

### canonical-imports | medium | Captured callers depended on removed forwarding and private defining surfaces

Resolved source changes use direct public defining imports, including the CLI parameter/shared contract modules, test enrollment recipient and codec/parser helpers. The root fixture owns the outward runtime composition dependency so the shipped harness remains inward-only. The configured import checker initially found two unresolved dynamic loops because a shared lexical variable accumulated all four bounded root sets; separate lexical bindings fix the actual resolver without changing its cap or contract scope. The subsequent configured run reported zero hard findings and loaded all 4,359 targets, but correctly refused a final verdict because test files changed during the run. A stable rerun remains required.

### native-keychain-context | medium | Protected verification requires an unlocked native login security session

Resolved verification dependency. The original locked native context correctly returned NEEDS_USER. With explicit user authorization, a masked askpass prompt on the Mac delivered the password directly to the native unlock API, without a credential in chat, arguments, environment, files or tool output. Unlock and tests ran in the same SSH security session. Three native namespace round trips passed, each replacing, reopening from a fresh process and deleting binary items; the mutually exclusive locked-context detector skipped. No Keychain provider or access policy was weakened.

### executor-scenario-coverage | medium | The combined registered-operation matrix lacked concrete scenarios

Open verification repair. The broad affected suite exposed 57 registered operations absent from its independent expectation families. Workers are adding actual registered-handler scenarios with concrete result, effect, phase and cleanup assertions; the matrix is not narrowed or suppressed. A human-facing private ledger refusal test also lacked runtime admission and was moved to its existing native CLI fixture while retaining its original assertions. Missing browser provisioning was an environment prerequisite; the public provisioning command installed the required Chromium build and the controlled category path is explicit for reruns.

### installed-withholding | medium | The new installed continuation failed during public CLI seeding

Open diagnosis. The recovered continuation keeps the current withholding capture route unavailable and uses public CLI input capture followed by actual installed runtime TUI calculation, verification, export, local recording and fresh-process reopen. Its independent export and admission assertions passed eleven focused tests. The first fresh-wheel native journey failed before reaching TUI and retained a failed receipt. The receipt initially discarded the typed CLI failure stage, so the owner is repairing the sanitized diagnostic evidence before identifying and fixing the concrete cause. This is not a demonstrated production defect until its cause is established, and no end-to-end success is claimed.

### current-registry-generation | medium | Later M190 and M390 changes alter real typed export geometry

The selected later TUI source and mapping deltas preserve typed perceptor rows, the complete M390 filing envelope, source pins and current public codec APIs. They are semantic data changes, unlike the earlier provenance-only digest edits. Canonical authority publication passed locally and on Darwin with the same logical identity `5375497a63086b77cb673bf468f370ea944af86f6892190132b5e67bc2bc3308`. Fresh bounded committed-render comparison and installed export behavior remain required to finalize that proof.

### active-destination | medium | The live TUI writer prevents an uncoordinated checkout update

Open landing dependency. Later committed calendar, filing-session and native application changes were reconciled alongside the selected dirty source deltas. Unrelated desktop and active documentation work is preserved separately. Before landing, inspect the destination's latest commits and relevant edits again and reconcile any new changes. Do not reset, clean, stash, switch or overwrite the writer's checkout. The isolated integration branch has not been described as landed.

### preview-projection | low | Framework sync preview did not fully describe adoption changes

Observed during canonical rule projection. The owning sync command's preview reported no file changes while describing adoption state; the applied isolated sync updated the rule projections and provider state. The rule prose now derives the public MCP tools from the typed protocol and names corpus/ranked discovery. No broad pending framework migration was applied.

## Recommendations

Finish the concrete conformance families, diagnose and complete the installed withholding continuation, corroborate generated registry reproduction, rerun the configured checks against frozen inputs, and obtain the final integrated code review. Preserve failed and unavailable runs beside passing evidence and retain their actual causes. Finish per-path integration commit mappings and coherent provenance-bearing checkpoints. Close only Steps whose required proof passes. Coordinate the final destination update if its writer remains active; the exact landing operation and dependency must stay explicit.

Current review status is PENDING. Static review has no unresolved critical or high defect; combined verification and landing remain open.


## Baseline checkpoint after user priority change

The user explicitly directed committing the complete reconciled MCP baseline before remaining verification. Product source and coupled public CLI consumers are committed in e977df5ac5; tooling, documentation, canonical configuration and historical records in68258c3539; native packaging and the independent application host in fb802220bb. Earlier discovery4e7392a2ee and containment01480b047a checkpoints remain separate. S03/S04/S05 remain open until their required proof and landing conditions are satisfied.

The interrupted affected cohort completed527 cases:466passed,61failed,41of568uncompleted. Fifty-seven failures used the previously loaded incomplete scenario matrix; its replacement scenarios exist. The remaining failures include completeness and browser/native fixture prerequisites plus one custody registration failure requiring replay. No complete suite pass is claimed. Verification replay and final combined gates are deferred until after this concrete baseline, as requested.

The installed CLI failure was a demonstrated production defect: generic materialization created the derived runtime namespace0755. The correction creates a new application-owned namespace0700 before its descendants while preserving existing and explicit insecure namespaces for refusal. Portable checks passed22tests with one host skip; fresh-wheel Darwin checks passed all3cases in1.06s, including real endpoint admission and both insecure namespace refusals. The wheel matched all3218shipping Python modules.

Canonical registry gates passed58modelos,160revisions and1502legal references. A fresh M3902022render comparison reproduced all14committed files with no semantic, source-pin or provenance drift. The published logical authority remains5375497a63086b77cb673bf468f370ea944af86f6892190132b5e67bc2bc3308.

Native installed withholding seeding now succeeds. Its lifecycle child failed before proving completion; the safe failure-receipt repair retains driver stage and sanitized public screen/widget identities, with17focusedtests passing. The full fresh native continuation is being replayed; no successful lifecycle or reopen is claimed. Native containment and unlocked Keychain passing evidence above remain valid for their unchanged owners.

The immutable later destination cut60c063bba1fc3d53f7d0c2522405a81966a6a0a8 will be reconciled only in the isolated branch. The active live checkout has4888observed status paths and cannot be overwritten. Review remains PENDING for combined verification and landing.
