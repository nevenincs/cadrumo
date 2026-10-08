# Home, Declarations portfolio, and Ledger TUI flows

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-177` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and limits

This report covers the 25 files assigned under the TUI Declarations, Home, installed-session, launcher, and Ledger packages: 5,112 lines, 228,380 bytes, and 47,378 measured `o200k_base` proxy tokens. All assigned source ranges were read in nine bounded pages. Static inspection only: no application code was imported or run, and no runtime, terminal, persistence, or external-service behavior was exercised. The supplied snapshot omits tests and build material.

## Product capabilities

The installed TUI session boundary discovers profiles, registers the first profile through a bootstrap screen when the inventory is empty, and authenticates existing profiles through an installed runtime client. Human credential sessions enter the full workbench; API key/reference sessions are routed to a restricted session app. Profile change ends the current owned runtime session before the loop reads a fresh inventory. Headless mode without an explicit autopilot exits without waiting for credentials (session orchestration (`src/cadrumo/entrypoints/tui/installed_session.py`), session loop (`src/cadrumo/entrypoints/tui/installed_session.py`), launcher (`src/cadrumo/entrypoints/tui/launcher.py`)).

Home is a display-only projection of next actions, resumable declarations, agenda items, source/evidence freshness, ledger counts, and messages needing attention. It uses stable semantic identities rather than table positions and sends selected targets to the owning app for admission and dispatch (Home projection rendering (`src/cadrumo/entrypoints/tui/home.py`), selection message (`src/cadrumo/entrypoints/tui/home.py`)). Availability includes available, locked, stale, never-captured, and unavailable states; stale timestamps are shown explicitly and empty measured zones can be distinguished from unavailable sources (availability copy (`src/cadrumo/entrypoints/tui/home.py`)).

The Declarations workspace offers a searchable, filterable, sortable, foldable filing portfolio with status/result/next-action wording. Operators can open local work, choose an admitted Modelo and registry-backed period to create or reopen a work unit, inspect an AEAT filing without implying it reconciles local work, or open the calculation-revision, filing-history, and calendar routes (portfolio actions (`src/cadrumo/entrypoints/tui/declarations/grouped.py`), creation flow (`src/cadrumo/entrypoints/tui/declarations/grouped.py`), picker (`src/cadrumo/entrypoints/tui/declarations/picker.py`), external details (`src/cadrumo/entrypoints/tui/declarations/external_details.py`)). Filing history presents lifecycle and filing records in chronological order while keeping local record status distinct from AEAT confirmation and evidence. Calculation revisions display current/filed flags with stable focus IDs (filing history (`src/cadrumo/entrypoints/tui/declarations/filing_history.py`), revisions (`src/cadrumo/entrypoints/tui/declarations/revisions.py`)).

The Ledger controller exposes seven areas and the assigned screens implement entry browsing, a per-transaction classification flow, activity-asset actions, and evidence queue/document review. Classification is an explicit choose/edit/confirm operation that builds a typed patch; import preview/apply, evidence registration/extraction/confirmation, invoice entry, and reconciliation-link submission are exposed as typed injected controller doors, though their screens or route implementations are outside this chunk (Ledger controller doors (`src/cadrumo/entrypoints/tui/ledger/controller.py`), link admission (`src/cadrumo/entrypoints/tui/ledger/controller.py`)). Activity-asset controls delegate create, inspect, correct, forecast, claim, and filing projection requests through one injected action interface; screen code parses dates and public request shapes but leaves asset arithmetic to application services (activity-asset actions (`src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`), dispatch (`src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`)).

## How data and effects move

Controllers hold injected application projections and typed handoffs. Declarations validates the workbench context, projection contract version, and canonical action references; refresh accepts a replacement only when the profile bucket remains the same. Its closed route catalogue admits only available/stale zones with a concrete screen/factory and otherwise displays an explicit unavailable screen (Declarations controller (`src/cadrumo/entrypoints/tui/declarations/controller.py`), bucket-bound refresh (`src/cadrumo/entrypoints/tui/declarations/controller.py`), route admission (`src/cadrumo/entrypoints/tui/declarations/routes.py`)). Calendar recovery rows are checked against the canonical work-create command and their declared Modelo/year/period bindings before UI selection (recovery validation (`src/cadrumo/entrypoints/tui/declarations/controller.py`)). Creation/recovery calls run off the UI thread, and screen state prevents duplicate work while a request is active.

Ledger similarly checks projection version and carries selection in a validated semantic focus object. Classification target identities must exist in the visible projection; result identities are checked against submitted transaction IDs. Link submission is allowed only for a pair present in the displayed reconciliation projection, and returned identities must match the admitted pair (Ledger controller (`src/cadrumo/entrypoints/tui/ledger/controller.py`), classification identity (`src/cadrumo/entrypoints/tui/ledger/controller.py`), link identity (`src/cadrumo/entrypoints/tui/ledger/controller.py`)). Refresh runs off the event loop and coalesces a second refresh request behind the running one (refresh (`src/cadrumo/entrypoints/tui/ledger/controller.py`)). Entry tables adapt columns to terminal width while retaining complete records in the projection and preserving the selected transaction identity across resize (entries screen (`src/cadrumo/entrypoints/tui/ledger/entries.py`)).

Evidence views distinguish an application-supplied review queue from registered local documents. The queue shows safe metadata and stable attachment identities; local records can be extracted into a draft and then explicitly confirmed as an invoice. Draft wording preserves unread values as “unread,” presents discrepancies and field provenance, and includes competing candidates rather than silently choosing one (evidence screen (`src/cadrumo/entrypoints/tui/ledger/evidence.py`), draft rendering (`src/cadrumo/entrypoints/tui/ledger/evidence_draft.py`)). The full draft can contain supplier/customer names, tax identifiers, postal details, invoice values, and source metadata, so this is a sensitive operator-facing surface even though the renderer itself does not persist it.

## Security and safety

The installed-session module explicitly confines local bootstrap custody to profile discovery and first-profile registration, releases active local profile/key sessions, and opens existing-profile clients against the verified runtime. It does not give the TUI ambient registration custody for ordinary login (module boundary (`src/cadrumo/entrypoints/tui/installed_session.py`), bootstrap release (`src/cadrumo/entrypoints/tui/installed_session.py`)). The launcher owns cleanup after Textual exits and releases bundled registry authority only after an orderly session return (cleanup and orderly exit (`src/cadrumo/entrypoints/tui/launcher.py`), main (`src/cadrumo/entrypoints/tui/launcher.py`)). These local properties still need synthesis to trace through runtime admission and persistence implementations.

Mutation flows require explicit operator choices, validated typed inputs, and injected command doors. The classification UI does not infer a business classification, treats blanks as absent rather than zero, validates the business-percentage coupling and IVA fraction convention, then disables cancel and confirm while submission is in flight (classification validation (`src/cadrumo/entrypoints/tui/ledger/classification.py`), confirm and submit (`src/cadrumo/entrypoints/tui/ledger/classification.py`)). Activity-asset flows require a forecast before claim and carry the forecast’s superseded-claim identity into the claim request. On an expired session, the screen clears private form values, forecast state, and displayed revision identity (activity-asset expiry handling (`src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`)).

Canonical action guards bind offered Declarations and Ledger references to expected command keys; optional Ledger doors are checked when present, with absence treated as an unoffered area (Ledger action guard (`src/cadrumo/entrypoints/tui/ledger/action_guards.py`)). However, two query destinations remain explicitly incomplete in this layer: selecting a Ledger review row or evidence-review row posts a request that the shared screen answers with “destination pending”; the comments state that no production consumer executes the query yet (pending query response (`src/cadrumo/entrypoints/tui/ledger/controller.py`)). This is an observed capability gap in the assigned UI path, not a claim that the underlying application queries are absent.

## Assessment and follow-up

The clearest strengths are truthful separation of local and external filing evidence, stable semantic identity through filtering/resizing, typed operation boundaries, bucket-preserving projection refresh, and explicit refusal states. The UI retains provenance and uncertainty for document extraction and gives operators visible controls for confirming writes. No test sources were included in this code-only snapshot, so these behaviors are not verified dynamically.

For synthesis, trace installed login and API-restricted admission to runtime permissions and secret custody; trace Declarations creation, refresh, and filing handoffs to the application layer; and resolve Ledger review/evidence query messages against the route catalogue to document the currently pending path. Also follow activity-asset and invoice-evidence operations into their application and domain validation. The assigned screens show sensitive invoice data, but do not establish logging, storage, or terminal-session privacy outside their own rendering paths.

## Complete assigned-file coverage

All 25 manifest files and their complete declared line ranges were read.

- declarations/controller.py (`src/cadrumo/entrypoints/tui/declarations/controller.py`) — 530 lines
- declarations/external_details.py (`src/cadrumo/entrypoints/tui/declarations/external_details.py`) — 74 lines
- declarations/filing_history.py (`src/cadrumo/entrypoints/tui/declarations/filing_history.py`) — 194 lines
- declarations/grouped.py (`src/cadrumo/entrypoints/tui/declarations/grouped.py`) — 327 lines
- declarations/models.py (`src/cadrumo/entrypoints/tui/declarations/models.py`) — 148 lines
- declarations/overview.py (`src/cadrumo/entrypoints/tui/declarations/overview.py`) — 25 lines
- declarations/picker.py (`src/cadrumo/entrypoints/tui/declarations/picker.py`) — 164 lines
- declarations/portfolio_interactions.py (`src/cadrumo/entrypoints/tui/declarations/portfolio_interactions.py`) — 38 lines
- declarations/portfolio_rendering.py (`src/cadrumo/entrypoints/tui/declarations/portfolio_rendering.py`) — 194 lines
- declarations/portfolio_rows.py (`src/cadrumo/entrypoints/tui/declarations/portfolio_rows.py`) — 97 lines
- declarations/revisions.py (`src/cadrumo/entrypoints/tui/declarations/revisions.py`) — 86 lines
- declarations/routes.py (`src/cadrumo/entrypoints/tui/declarations/routes.py`) — 193 lines
- declarations/row_words.py (`src/cadrumo/entrypoints/tui/declarations/row_words.py`) — 136 lines
- destination_alias.py (`src/cadrumo/entrypoints/tui/destination_alias.py`) — 14 lines
- home.py (`src/cadrumo/entrypoints/tui/home.py`) — 500 lines
- installed_session.py (`src/cadrumo/entrypoints/tui/installed_session.py`) — 267 lines
- launcher.py (`src/cadrumo/entrypoints/tui/launcher.py`) — 103 lines
- ledger/__init__.py (`src/cadrumo/entrypoints/tui/ledger/__init__.py`) — 1 line
- ledger/action_guards.py (`src/cadrumo/entrypoints/tui/ledger/action_guards.py`) — 74 lines
- ledger/actividad_asset.py (`src/cadrumo/entrypoints/tui/ledger/actividad_asset.py`) — 241 lines
- ledger/classification.py (`src/cadrumo/entrypoints/tui/ledger/classification.py`) — 262 lines
- ledger/controller.py (`src/cadrumo/entrypoints/tui/ledger/controller.py`) — 791 lines
- ledger/entries.py (`src/cadrumo/entrypoints/tui/ledger/entries.py`) — 208 lines
- ledger/evidence.py (`src/cadrumo/entrypoints/tui/ledger/evidence.py`) — 153 lines
- ledger/evidence_draft.py (`src/cadrumo/entrypoints/tui/ledger/evidence_draft.py`) — 292 lines
<!-- /preserved:article -->
