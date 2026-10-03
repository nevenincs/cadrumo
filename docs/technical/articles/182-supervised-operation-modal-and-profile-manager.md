# Supervised operation modal and profile manager

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-182` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and limits

This report covers 22 assigned files: 5,068 lines, 228,485 bytes, and 46,804 measured `o200k_base` proxy tokens. All declared lines were read in nine bounded pages. This is static analysis only; the runtime, encrypted store, UI, auth provider and operations were not exercised. Screens render application/runtime projections and invoke injected doors; this chunk alone cannot certify their underlying policy or persistence.

## Operator capabilities

The generic operation modal observes one already-submitted TUI operation, displays its public status, phase, deadlines, diagnostic/receipt references and translated event codes, and offers only controls permitted by the projection. It polls at a 200 ms interval through the bound controller, folds public event pages into an append-only log capped at 500 rows, and clears old history when the replay contract requires resynchronization. Terminal status, cancellation and detach affordances are derived from a validated view model that checks they still match the public projection. Only registered safe `REVIEW` interactions are rendered; public `INPUT` and `CHOICE` interactions are deliberately represented as unsupported in this UI (modal flow (`src/cadrumo/entrypoints/tui/operations/modal.py`), public event log folding (`src/cadrumo/entrypoints/tui/operations/logs.py`), projection-derived view model (`src/cadrumo/entrypoints/tui/operations/projection.py`)).

For a pending review, the modal resolves the exact registered review projection and binds its response control once for that interaction and revision. It re-inspects permission while polling without consuming or reconstructing the response bearer, and sends apply/reject with the operation, interaction, revision, actor and response time. Cancel and detach likewise include the current expected revision. Refused controls retain and display an explanation instead of silently doing nothing. Closing a live operation requests detach when allowed and waits for the poll worker to stop before dismissing (review interaction binding (`src/cadrumo/entrypoints/tui/operations/interactions.py`), response and lifecycle controls (`src/cadrumo/entrypoints/tui/operations/modal.py`)).

The profile manager presents schema-defined sections and current profile facts, supports search and required-only filtering, and guides an unfinished profile through overview, data acquisition, required answers, review and ready stages. The wizard stores answers as each field is saved; only the explicit completion action asks the application to mark setup complete. Repeatable facts have add/update/remove actions keyed by stable row identities, and removal requires confirmation. Operators can declare average-workforce values by year, with decimal precision preserved as `Decimal`; the dialog delegates domain range/relationship decisions to its application door (profile screen and injected write doors (`src/cadrumo/entrypoints/tui/profile/overview.py`), setup transition (`src/cadrumo/entrypoints/tui/profile/overview_setup.py`), annual workforce editor (`src/cadrumo/entrypoints/tui/profile/plantilla_media.py`)).

Field editors keep masked values hidden. A blank submission on a hidden masked field means retain the existing value; clearing is offered only for an existing optional masked field. Required empty values and invalid values stay in the dialog with a refusal. Choice controls restore only an exact current choice, and a repeatable-row editor omits blank fields instead of interpreting them as clears (field editor handling (`src/cadrumo/entrypoints/tui/profile/edit_screens.py`)). The profile view also shows acquisition-source cards with credential-posture badges where supplied, offers profile-bound AEAT authentication configuration, and provides a runtime-backed automation inventory for grants, keys and pending review requests. The inventory details expose scope, expiry, unattended status and identifiers, but not secret key material; approve/decline controls are limited to a currently selected request in the still-bound inventory (automation inventory access and lifecycle (`src/cadrumo/entrypoints/tui/profile/automation_inventory.py`), selected-request check (`src/cadrumo/entrypoints/tui/profile/automation_inventory_decisions.py`)).

## Runtime and persistence boundaries

`RuntimeOperationController` pins the TUI frontend and exact session for a submitted operation, admits the registered contract before submit, refuses contracts requiring an uncomposed ephemeral-secret handoff, applies per-call deadlines, and rechecks session identity around exchanges. Terminal result reads are checked against operation, definition, subject, request/result schema and contract digest. The higher-level profile session additionally pins profile identity and confirms the live account binding before operations, after results, and when converting an access refusal to an expired-session result (submission and result checks (`src/cadrumo/entrypoints/tui/operations/runtime_controller.py`), profile/session binding (`src/cadrumo/entrypoints/tui/operations/runtime_profile_session.py`)).

Response controls remain runtime-owned: the TUI holds coordinates and an adapter, while the actual bearer stays in the runtime. `RuntimeResponseControl` checks apply/reject requests against the exact bound operation/interaction/revision/actor tuple. Result and error-detail projections are parsed under exact registered schema identities; operation refusal detail is shown only when the registry declares a public message or recorded public registered error. This limits the modal to public DTOs and prevents it from reading journals or private supervisor state (runtime response binding (`src/cadrumo/entrypoints/tui/operations/runtime_controller.py`), refusal explanation policy (`src/cadrumo/entrypoints/tui/operations/refusal_explanation.py`)). The separate auth-configuration adapter submits the shared registered configure operation and accepts the result only when profile/provider/effect and session agree with the request (auth configure settlement (`src/cadrumo/entrypoints/tui/profile/runtime_auth_configuration.py`)).

Profile writes run on worker threads with copied context so profile selection survives thread transfer. Field and repeatable-row writes carry the revision and content digest displayed when the dialog opened; writes are serialized because they merge into the whole fact set. The returned projection is checked against the active profile and prior revision before the screen updates, and rendering uses the store's returned view rather than an optimistic guess. A structural diff enables cell-level updates when rows are unchanged and falls back to a full redraw when repeatable rows or filters change layout (serialized writes and reloaded state (`src/cadrumo/entrypoints/tui/profile/overview_writes.py`), incremental profile rendering (`src/cadrumo/entrypoints/tui/profile/overview_rendering.py`)).

The automation inventory checks its borrowed session before and after reading, clears displayed facts and disables decisions on access loss or known expiry, and drains the worker on unmount. The profile manager likewise prevents overlapping writes and refuses to quit while a thread-backed write/completion is still landing. Credential posture can disable a configured source action, but an unknown posture is left unknown rather than mislabeled as a missing credential (inventory lifetime and refresh (`src/cadrumo/entrypoints/tui/profile/automation_inventory.py`), quit/write exclusion (`src/cadrumo/entrypoints/tui/profile/overview.py`)).

## Implementation assessment and follow-up

Strong controls in this chunk include exact operation/session bindings, schema/digest validation, revision-bound mutations, safe projection-only rendering, retained review controls, explicit confirmation for row deletion and profile completion, masking, and UI-side serialization of whole-record writes. The operation log enforces monotonic event sequence and operation identity, and a resynchronizing page discards historical rows instead of mixing stale history with the restarted stream. Profile rendering verifies profile identity and rejects a same-revision/different-digest result before replacing the current view.

No confirmed defect is established here. Dynamic behavior remains unverified, especially race handling among poll, cancel and detach; Textual worker cancellation; layout/focus under narrow terminals; read-modify-write conflict behavior; and the exact scope of automation decisions. Operation error and profile worker paths surface registered or generic messages, but no test suite is assigned in these files. Traceback/logging privacy and whether any profile/acquisition fields are sensitive must be checked with the actual configured logging and model policies. Synthesis should inspect composition wiring, local runtime session invalidation, encrypted-store conflict handling, automation approval operations, auth secret storage and schema-generated profile projections before making end-to-end claims.

## Complete assigned-file coverage

All 22 manifest files and their complete declared line ranges were read.

- operations/interactions.py (`src/cadrumo/entrypoints/tui/operations/interactions.py`) — 163 lines
- operations/logs.py (`src/cadrumo/entrypoints/tui/operations/logs.py`) — 147 lines
- operations/modal.py (`src/cadrumo/entrypoints/tui/operations/modal.py`) — 476 lines
- operations/projection.py (`src/cadrumo/entrypoints/tui/operations/projection.py`) — 235 lines
- operations/refusal_explanation.py (`src/cadrumo/entrypoints/tui/operations/refusal_explanation.py`) — 40 lines
- operations/runtime_controller.py (`src/cadrumo/entrypoints/tui/operations/runtime_controller.py`) — 532 lines
- operations/runtime_profile_session.py (`src/cadrumo/entrypoints/tui/operations/runtime_profile_session.py`) — 184 lines
- profile/__init__.py (`src/cadrumo/entrypoints/tui/profile/__init__.py`) — 5 lines
- profile/automation_inventory.py (`src/cadrumo/entrypoints/tui/profile/automation_inventory.py`) — 171 lines
- profile/automation_inventory_decisions.py (`src/cadrumo/entrypoints/tui/profile/automation_inventory_decisions.py`) — 93 lines
- profile/automation_inventory_details.py (`src/cadrumo/entrypoints/tui/profile/automation_inventory_details.py`) — 94 lines
- profile/automation_inventory_view.py (`src/cadrumo/entrypoints/tui/profile/automation_inventory_view.py`) — 101 lines
- profile/edit_screens.py (`src/cadrumo/entrypoints/tui/profile/edit_screens.py`) — 325 lines
- profile/overview.py (`src/cadrumo/entrypoints/tui/profile/overview.py`) — 437 lines
- profile/overview_contracts.py (`src/cadrumo/entrypoints/tui/profile/overview_contracts.py`) — 154 lines
- profile/overview_interactions.py (`src/cadrumo/entrypoints/tui/profile/overview_interactions.py`) — 398 lines
- profile/overview_rendering.py (`src/cadrumo/entrypoints/tui/profile/overview_rendering.py`) — 520 lines
- profile/overview_setup.py (`src/cadrumo/entrypoints/tui/profile/overview_setup.py`) — 373 lines
- profile/overview_writes.py (`src/cadrumo/entrypoints/tui/profile/overview_writes.py`) — 301 lines
- profile/plantilla_media.py (`src/cadrumo/entrypoints/tui/profile/plantilla_media.py`) — 205 lines
- profile/runtime_auth_configuration.py (`src/cadrumo/entrypoints/tui/profile/runtime_auth_configuration.py`) — 94 lines
- profile/runtime_errors.py (`src/cadrumo/entrypoints/tui/profile/runtime_errors.py`) — 20 lines
<!-- /preserved:article -->
