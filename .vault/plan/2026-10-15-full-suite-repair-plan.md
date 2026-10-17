---
tags:
  - '#plan'
  - '#full-suite-repair'
date: '2026-10-15'
tier: L1
related:
  - '[[2026-10-04-google-app-identity-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-07-01-verification-reconcile-when-present-adr]]'
  - '[[2026-10-05-google-outbound-review-adr]]'
  - '[[2026-10-11-mcp-parity-full-parity-adr]]'
  - '[[2026-10-13-startup-performance-operation-contract-manifest-adr]]'
modified: '2026-10-16'
body_schema: body-v2
body_hash: 'sha256:1417613c9ebdd85f2bc92aa229d6d611abb106e007038956bb9643671b0a41ae'
---
# `full-suite-repair` plan

## Description

Approved 2026-10-15. The user explicitly requested running the complete justfile test populations including live tests and fixing all failures. The user further required the publisher Google OAuth client to be a fixed, bundled, non-overridable application identity inherited by every native image.

Repair existing behavior under the accepted verification-reconcile-when-present, application-sign-in, MCP signed-in-profile, provider-settings, Google application identity and canonical environment decisions. No test exclusion, suppression, weakened assertion or increased timeout is authorized. Preserve unrelated edits in this shared worktree.

Current evidence and full command logs are in `.logs/test-repair/`. Read the actual logs and process status before resuming commands. The latest user instruction forbids full-lane runs and limits test execution to previously known failures; do not represent these moving-tree observations as an immutable all-green checkpoint.

## Steps

- [x] `S01` - Enroll computed casillas and validate published authority; `verification declarations for modelos 303, 308, 322, 369 and 390`.
- [x] `S02` - Compile fixed Google publisher identity into every package launch environment; `native environment contract, build provisioning, runtime settings and identity tests`.
- [ ] `S03` - Repair behavior, fixture and tooling contracts exposed by the full suite; `fixtures, CLI ownership, registry migrations and reconciliation, actor contract compatibility, import isolation and packaging guards`.
- [ ] `S04` - Verify targeted repairs using only previously known failing test cases and final review; `recorded failures, scoped static checks and final review`.

## Parallelization

Authorized 2026-10-16 by the user: use GPT-6.1 Sol medium agents. S03 assignments may run concurrently with disjoint write ownership: frontend worker owns native/desktop/frontend, typing worker owns the six files from the recorded type diagnostics, calculation worker owns the recorded Modelo 322/353 calculation failures, and supervisor owns remaining runtime/TUI repairs. The supervisor serializes shared metadata and commits. Reuse applicable passing repair evidence. No full-lane tests may run; select only previously known failing cases.

Next slices authorized 2026-10-16: remeasure unused code, establish real orphan status and remove confirmed orphans; a separate Sol agent repairs import failures. The supervisor owns reachability measurement, orphan decisions and edits in `application/operations/access_facts.py`, `core/storage_environment.py`, `entrypoints/cli/_profile_session_gate.py`, `entrypoints/cli/config/_spec_policies.py`, `entrypoints/cli/main.py`, and their directly affected tests and tooling. The import agent owns import diagnostics and import repairs outside those reserved files, preserving existing edits and governing package responsibility. Import changes needed inside reserved files are sent to the supervisor. Shared import target metadata, governance and commits remain serialized by the supervisor. Existing checks stay strict; test execution remains limited to known failing cases.

The newly requested orphan/import repairs include focused verification of affected code and retargeted tests. This authorizes their necessary regression checks while preserving the prohibition on full test-population reruns.

Other-unreconciled follow-up authorized 2026-10-16: source-file-disjoint exact failure batches A/B/C are recorded in var/verification-resume/remaining-offline-batches.json (30/29/29 originally failing selectors). The calculation, typing and frontend agents respectively own those batch source files if a failure reproduces; shared helper changes route through the supervisor. The frontend agent additionally owns the two keychain test fixture repairs. The supervisor owns the four malformed target-string correction in profile_command_specs.py, live prerequisite adjudication, shared evidence and governance. Preserve ongoing import/orphan work and reuse its applicable evidence. No full test lanes or sibling test expansion is authorized.


Additional targeted S03 ownership under the user's other-unreconciled follow-up: the Sol calculation worker owns installed IVA/income-tax acceptance helpers, session_authority_activity.py, runtime_workbench.py, the new runtime_ledger_classification.py and their directly connected TUI Ledger models/controller/classification/injection/routes and legacy type-narrowing assertions. The precise fourteen-file snapshot is recorded in var/verification-resume/reconcile-iva-tui-final-review.json. The Sol typing worker owns the bounded backend_probe.py record annotation and the per-node historical inventory. The Sol frontend worker performs independent read-only integrated review of those repairs. The supervisor owns command target-string, keychain and Rust fixture reconciliation, canonical import-load metadata generation, final configured type/import checks and serialized vault evidence. These routine repairs preserve existing registered-operation, registry authority, profile/session custody and immutable projection contracts; no new authority or timeout policy is introduced. Test selection remains exact known failures only.

## Verification

User instruction of 2026-10-16 supersedes the earlier full-lane verification requirement: run only exact previously known failing test selectors. Use scoped lint, formatting and type checks for changed files; reuse applicable passing receipts. Preserve real prerequisites and explicit failures rather than skipping them. Do not increase deadlines, weaken assertions or fabricate credentials or authority evidence. Final review must distinguish repaired failures, already-fixed cases and unresolved prerequisites.

Supervisor follow-up ownership: neutral command graph/compiler resolver injection, actual tax/runtime composition loaders and their consumers, unused lazy-loader variants, active refusal-projection contract relocation, and finite-comprehension target evaluation. The Sol import worker owns the receiver/source provenance repair in the subordinate checker after canonical module/test ownership moves; the supervisor owns the subsequent stable-source import metadata compilation, final import gate, unused remeasurement and governance.
