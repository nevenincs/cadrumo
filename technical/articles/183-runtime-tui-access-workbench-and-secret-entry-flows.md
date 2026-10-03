# Runtime TUI access, workbench and secret-entry flows

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-183` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope

This implementation chunk covers 21 TUI modules: profile/runtime composition, account and session management, access recovery, runtime shell and workbench navigation, palette search, automation request/decision screens, shared credential handling, and passphrase rotation. The manifest measures 44,002 `o200k_base` proxy tokens, 4,912 lines, and 217,697 bytes. All declared ranges were read across eight bounded pages; the combined output for pages 5–8 exceeded the tool display cap, so those ranges were reread as individual files or contiguous line slices. No source range remains unread. This is static inspection only: no modules or application were executed and no tests were assigned to this chunk.

## Product capabilities and how they work

The TUI can manage a runtime-backed profile without becoming a second source of profile truth. `RuntimeProfileManagerComposition` pins the originating client/profile/session and builds edit, row, setup-completion, authentication-configuration, and template-media doors from runtime operations. Each mutation re-reads current state and uses the registered operation path; overview reconstruction consumes the runtime’s paginated profile view and validates page identity/cursor progression before creating the presentation projection (runtime profile composition (`src/cadrumo/entrypoints/tui/profile/runtime_manager.py`), runtime profile overview reader (`src/cadrumo/entrypoints/tui/profile/runtime_overview.py`)). Setup state is carried into the workbench as a profile fact, not inferred by the screen.

Account and session surfaces distinguish viewing status, changing credentials, and ending authority. Factories require the exact TUI profile/session binding; password rotation opens a fresh recovery client and closes it after the attempt, while language/profile completion use their composed runtime doors (runtime account factories (`src/cadrumo/entrypoints/tui/runtime_account.py`)). Session reads are bound to the pinned profile/session and can return a receipt-backed expiry outcome, preserving an operation ID and unknown effect where the terminal result is not known (account-session reader (`src/cadrumo/entrypoints/tui/runtime_account_session.py`)). The login admission app owns a newly accepted client for the resulting screen lifetime and rejects reuse after handoff (runtime login admission (`src/cadrumo/entrypoints/tui/runtime_admission.py`)).

Runtime access management exposes refresh, deny, lock, and recovery actions over the user’s current runtime grants. Selected grant/session identifiers are checked against the displayed inventory; recovery uses a separately opened, owned client, validates the receipt against the requested identity and authority, and fences an uncertain dispatch rather than blindly retrying. A denied or locked access result can be reported separately from cleanup still pending (access action handlers (`src/cadrumo/entrypoints/tui/runtime_access_actions.py`), access-management recovery (`src/cadrumo/entrypoints/tui/runtime_access_management.py`)). The projection surface displays public session/grant facts and omits credential material. A restricted session shell reports only the pinned API grant’s bounded scope and expiry, supports current-session lock/sign-out, and disables its actions when its binding expires; it does not provide human-administrator controls (restricted-session UI (`src/cadrumo/entrypoints/tui/runtime_session.py`), safe access projection (`src/cadrumo/entrypoints/tui/runtime_access_projection.py`)).

The runtime manager offers explicit start, enable, disable, refresh, and stop controls. Stop is gated by a separate global-scope confirmation; cleanup code retains stop consent and resource ownership when release fails so another screen or swallowed host error cannot silently discard pending cleanup (runtime management UI (`src/cadrumo/entrypoints/tui/runtime_management.py`), stop confirmation and release (`src/cadrumo/entrypoints/tui/runtime_management.py`), retained cleanup ownership (`src/cadrumo/entrypoints/tui/runtime_management_cleanup.py`)).

`RuntimeWorkbenchRoot` joins a runtime generation with a profile overview under one exact TUI client. Home and profile are admitted, ledger/declarations/AEAT-sync routes depend on the generation’s admissions, and withholding is explicitly unavailable in this runtime composition. Factories are created only for admitted routes. Declaration refresh captures a new generation; opening a calendar item requires one matching declaration semantic key and rejects unreadable or ambiguous matches. Mutations are wired individually, so a missing door remains unavailable (runtime workbench capture and binding (`src/cadrumo/entrypoints/tui/runtime_workbench.py`), admitted route construction (`src/cadrumo/entrypoints/tui/runtime_workbench.py`)).

Palette search adapts two application-owned authorities: the search service provides ranked bounded results, while the current destination catalogue decides whether a result can navigate. Search refusals become localized no-op hits; unknown refusal/action identifiers are worded as unknown rather than exposed as internal tokens. The command provider offers admitted destinations and registered action candidates, but each hit only asks the root to navigate to a validated target; it does not invoke the business action itself (search result provider (`src/cadrumo/entrypoints/tui/search.py`), command discovery and navigation binding (`src/cadrumo/entrypoints/tui/search.py`)). Labels, sources, statuses, action names, and destination descriptions are localized projections of stable identifiers (localized result/action rendering (`src/cadrumo/entrypoints/tui/search.py`)).

The automation requester makes enrollment or grant changes explicit: the operator selects permitted operations, action scopes, schema/category disclosures, periods, expiry, delegation, unattended behavior, OS-lock policy, and the relevant grant/key/credential references. Choices originate from public TUI operation contracts, start unselected, and are checked against those choices before the proposal is built with the destination ID minted by the protected enrollment channel (request scope model (`src/cadrumo/entrypoints/tui/secret/automation_requester.py`), draft validation (`src/cadrumo/entrypoints/tui/secret/automation_requester.py`)). The workflow distinguishes initial enrollment from rotation/renewal/scope change, pins exact profile/session bindings, settles blocking work off the UI loop, and retains cleanup owners. Grant changes reconcile through a fresh credential client using the remaining deadline and close that client in `finally`; uncertain delivery retains request identity rather than implying success (request execution and reconciliation (`src/cadrumo/entrypoints/tui/secret/automation_requester.py`), settlement outcomes (`src/cadrumo/entrypoints/tui/secret/automation_requester.py`)). A separate review screen submits one approve/decline decision for the exact displayed review; approval takes fresh password proof, and outcomes retain only operation facts (decision screen (`src/cadrumo/entrypoints/tui/secret/automation_decision.py`), safe outcome projection (`src/cadrumo/entrypoints/tui/secret/automation_decision_outcome.py`)).

Credential screens share a one-attempt, thread-backed lifecycle, localized safe refusals, progress state, and live password assessment. The passphrase screen collects current/new/confirmation values, performs local usability checks, and leaves policy enforcement to the injected application door. It clears inputs before dispatch and on unmount, wipes temporary bytearrays after use, and waits for the rotation thread to settle before releasing the borrowed client (shared credential attempt lifecycle (`src/cadrumo/entrypoints/tui/secret/credentials.py`), passphrase submission and settlement (`src/cadrumo/entrypoints/tui/secret/passphrase.py`)).

## Knowledge, data and trust boundaries

This chunk consumes runtime-generated profile/workbench projections, runtime session and grant facts, registered operation definitions, server-minted enrollment destinations, and explicit human scope choices. The TUI translates identifiers and states into localized operator copy; it does not establish legal meaning for those data or authoritatively decide automation permissions. The protected runtime/application services remain the mutation and authorization boundaries. No model/LLM use or bundled legal-reference data appears in these modules.

## Security and implementation assessment

Concrete controls include exact profile/session/frontend checks, route admission before factory creation, selected-grant validation, separate owned recovery connections, explicit global-stop confirmation, no blind retry after uncertain delivery, clearing of visible credential fields, and cancellation-complete settlement before borrowed resources are released. Cleanup retention is a notable lifecycle safeguard: an error does not necessarily mean the underlying runtime stop or close has finished.

The workbench capture explicitly says its generation and profile reads are individually guarded and do not claim a shared storage revision. It checks the session after both reads, which catches loss of the originating authority, but does not itself prove that those two snapshots describe one atomic storage state. This is a consistency boundary for synthesis to compare with runtime generation/version semantics, not a demonstrated user-visible defect. Likewise, the root binding sets search/catalogue refresh callbacks to `None`; whether navigation recomposes those projections after state changes depends on the host root outside this chunk (capture semantics (`src/cadrumo/entrypoints/tui/runtime_workbench.py`), read and root binding (`src/cadrumo/entrypoints/tui/runtime_workbench.py`), binding refresh slots (`src/cadrumo/entrypoints/tui/runtime_workbench.py`)).

Secret handling is careful but not a guarantee of memory erasure. The passphrase screen copies the entered strings into mutable buffers and zeroes those buffers, but decodes them back into immutable Python strings for the injected callback; the UI clears its fields, while Python/runtime copies cannot be proven erased by this module. Runtime decision/requester adapters and the host’s authorization checks need cross-layer review before claiming end-to-end credential or scope guarantees. Unexpected credential worker failures are rendered through registered error messages or generic internal guidance, but diagnostic logging behavior is outside this chunk. No runtime race, Textual lifecycle, authorization, or filesystem behavior was tested here.

## Dependencies and follow-up

Synthesis should connect these doors to runtime operation contracts, profile projection/version semantics, root navigation/recomposition, native enrollment and receipt validation, session invalidation, recovery-client ownership, credential rotation policy, and logging/error redaction. In particular, check whether profile/workbench snapshots have a common revision, whether catalogue/search captures refresh after admissions change, and whether automation scope constraints are repeated authoritatively below the UI. These are bounded cross-module questions; this chunk alone does not establish failures in those paths.

## Complete assigned-file coverage

All 21 manifest files and their full declared ranges were read (4,912 lines; 44,002 measured proxy tokens). The page-5 and page-6 combined outputs exceeded the tool’s display cap; their affected source ranges were reread in smaller contiguous file/line units. Page 7 and page 8 ranges were also verified individually where the combined page output clipped. No unread slices remain.

- profile/runtime_manager.py (`src/cadrumo/entrypoints/tui/profile/runtime_manager.py`) — 367 lines
- profile/runtime_overview.py (`src/cadrumo/entrypoints/tui/profile/runtime_overview.py`) — 179 lines
- profile/setup_journey.py (`src/cadrumo/entrypoints/tui/profile/setup_journey.py`) — 16 lines
- runtime_access_actions.py (`src/cadrumo/entrypoints/tui/runtime_access_actions.py`) — 270 lines
- runtime_access_management.py (`src/cadrumo/entrypoints/tui/runtime_access_management.py`) — 373 lines
- runtime_access_projection.py (`src/cadrumo/entrypoints/tui/runtime_access_projection.py`) — 86 lines
- runtime_account.py (`src/cadrumo/entrypoints/tui/runtime_account.py`) — 118 lines
- runtime_account_session.py (`src/cadrumo/entrypoints/tui/runtime_account_session.py`) — 97 lines
- runtime_admission.py (`src/cadrumo/entrypoints/tui/runtime_admission.py`) — 117 lines
- runtime_management.py (`src/cadrumo/entrypoints/tui/runtime_management.py`) — 385 lines
- runtime_management_cleanup.py (`src/cadrumo/entrypoints/tui/runtime_management_cleanup.py`) — 201 lines
- runtime_session.py (`src/cadrumo/entrypoints/tui/runtime_session.py`) — 306 lines
- runtime_workbench.py (`src/cadrumo/entrypoints/tui/runtime_workbench.py`) — 336 lines
- search.py (`src/cadrumo/entrypoints/tui/search.py`) — 386 lines
- secret/__init__.py (`src/cadrumo/entrypoints/tui/secret/__init__.py`) — 10 lines
- secret/automation_decision.py (`src/cadrumo/entrypoints/tui/secret/automation_decision.py`) — 235 lines
- secret/automation_decision_outcome.py (`src/cadrumo/entrypoints/tui/secret/automation_decision_outcome.py`) — 37 lines
- secret/automation_decision_view.py (`src/cadrumo/entrypoints/tui/secret/automation_decision_view.py`) — 65 lines
- secret/automation_requester.py (`src/cadrumo/entrypoints/tui/secret/automation_requester.py`) — 689 lines
- secret/credentials.py (`src/cadrumo/entrypoints/tui/secret/credentials.py`) — 312 lines
- secret/passphrase.py (`src/cadrumo/entrypoints/tui/secret/passphrase.py`) — 327 lines
<!-- /preserved:article -->
