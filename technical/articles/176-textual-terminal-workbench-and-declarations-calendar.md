# Textual terminal workbench and Declarations calendar

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-176` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and limits

This report covers all 26 files in the TUI entrypoint manifest: 5,142 source lines and 218,763 bytes, measured at 46,983 `o200k_base` proxy tokens. All assigned ranges were read across nine bounded pages, including slices that cross files. This is static analysis of the supplied snapshot. The report does not run the app or certify Textual behavior, tests, deployment, external services, or the correctness of upstream projections and calendar rules.

## Operator capabilities

The TUI package provides a terminal workbench with an account-aware root, a searchable command palette, navigation into admitted work areas, and a shared presentation system. `__main__` configures Pydantic plugin behavior before importing the app and has guarded shutdown/error handling for the terminal lifecycle (launcher (`src/cadrumo/entrypoints/tui/__main__.py`)). The root app loads an injected root projection, binds available destinations, builds semantic navigation targets, and returns to Home while retaining meaningful focus (app (`src/cadrumo/entrypoints/tui/app.py`), navigation and Home refresh (`src/cadrumo/entrypoints/tui/app.py`)). Account controls are injected through host protocols; the account provider contributes search and discovery entries only when the current root exposes them (account (`src/cadrumo/entrypoints/tui/account.py`)).

The AEAT Sync workspace presents six projection zones: census, filed declarations, notifications, evidence comparison, reconciliation, and overview. Route resolution is an explicit mapping from typed targets to screens, and the controller checks that an offered action resolves to its canonical command and to a single matching public operation contract permitted for the TUI (controller (`src/cadrumo/entrypoints/tui/aeat_sync/controller.py`), routes (`src/cadrumo/entrypoints/tui/aeat_sync/routes.py`)). The screen renders zone status and navigation, then admits only paired action/operation requests through the runtime handoff. In the inspected implementation, concrete effect paths cover filed-history retrieval, notification listing and reading, and a census edit review; the comparison and reconciliation areas are projection surfaces rather than general-purpose mutation consoles (screens (`src/cadrumo/entrypoints/tui/aeat_sync/screens.py`), handoff composition (`src/cadrumo/entrypoints/tui/aeat_sync/runtime_handoff.py`)).

The Declarations calendar is an agenda over an injected immutable projection. Operators can search, choose a closed scope, inspect a row’s dates and legal/local/AEAT statuses, see source freshness and evidence-conflict indicators, and open an admissible declaration entry. When a row offers a recovery action, the screen first presents a decline-by-default confirmation; after approval it submits the saved action/row pair on a worker and prevents a second recovery from being submitted concurrently (calendar projection and search (`src/cadrumo/entrypoints/tui/declarations/calendar.py`), details (`src/cadrumo/entrypoints/tui/declarations/calendar.py`), recovery admission (`src/cadrumo/entrypoints/tui/declarations/calendar.py`)). Success, domain refusals, and unexpected failures receive separate operator-facing outcomes.

## How the TUI works

The root owns the Textual screen stack; feature workspaces resolve their own internal screens and rely on a small host protocol to replace the visible body. A one-screen host supports standalone surfaces without pretending to offer the root’s navigation stack (host (`src/cadrumo/entrypoints/tui/components/host.py`), workspace host seam (`src/cadrumo/entrypoints/tui/components/workspace_host.py`)). Root loaders run outside the UI event loop. Home refreshes are tied to a navigation revision, and return navigation re-admits destinations from the current projection rather than blindly restoring an old catalogue (app refresh and destination changes (`src/cadrumo/entrypoints/tui/app.py`), destination swaps (`src/cadrumo/entrypoints/tui/app.py`)).

AEAT Sync separates projection/controller/screen routing from effect execution. Its runtime handoff checks the currently registered public operation contract and the bound profile/session before admitting a typed request. Census review has an extra preparation stage: it performs the registered prepare operation, validates the returned projection, then forms and admits the review request. Notifications are read through a typed result controller. Operation screens own progress and outcome interaction; the workspace disables conflicting controls while an operation is active and refreshes the relevant projection after successful completion (handoff contracts and census preparation (`src/cadrumo/entrypoints/tui/aeat_sync/runtime_handoff.py`), notification result (`src/cadrumo/entrypoints/tui/aeat_sync/runtime_handoff.py`), operation UI (`src/cadrumo/entrypoints/tui/aeat_sync/screens.py`)).

The calendar’s rows use a semantic key assembled from model, year, and period. Search and scope changes preserve the selected identity when it remains visible, retain a hidden selection for later restoration, and show a distinct empty message for stale source data versus an empty/search-filtered agenda (calendar selection (`src/cadrumo/entrypoints/tui/declarations/calendar.py`), empty-state logic (`src/cadrumo/entrypoints/tui/declarations/calendar.py`)). The detail pane reports available observation timestamps or explicitly says when no timestamp was recorded; it does not manufacture one (source detail (`src/cadrumo/entrypoints/tui/declarations/calendar.py`)).

## Knowledge, trust, and safety

This layer displays application projections and typed operation results. Calendar dates, holiday coverage, shift reasons, declaration eligibility, evidence states, and notification state arrive through those contracts; this screen code does not establish their legal or external factual correctness. No LLM prompt or model use appears in the assigned TUI files. The source material includes no test files in this supplied code-only snapshot, so the analysis has no test execution evidence.

There are meaningful local boundaries. `BoundSession` pins the runtime client to a profile/session identity and asks the runtime for current status before accepting a session as live; unavailable status or identity mismatch fails closed (bound session (`src/cadrumo/entrypoints/tui/bound_session.py`)). The root periodically checks account status, severs profile-bound references before direct sign-out/change-user actions, and avoids keeping a private root bound after recompose (session watch (`src/cadrumo/entrypoints/tui/app.py`), direct session action (`src/cadrumo/entrypoints/tui/app.py`), root severing (`src/cadrumo/entrypoints/tui/app.py`)). The handoff also rechecks binding around effect admission and validates exact public contracts instead of treating a visible button as authorization. These are TUI-side safeguards; synthesis should trace their application/runtime callers to establish complete authorization and effect behavior.

At the interaction layer, irreversible recovery starts with a modal whose initial focus is the cancel button and whose escape action declines. A single pending tuple and in-flight flag serialize the recovery path; failures are surfaced with either a resolved domain refusal or generic copy (confirmation dialog (`src/cadrumo/entrypoints/tui/components/dialogs.py`), calendar submission (`src/cadrumo/entrypoints/tui/declarations/calendar.py`)). Root account refresh errors and unexpected operation errors are handled without exposing exception text in these paths. Notification rendering is limited to public metadata and the admitted document-read flow; the screen does not itself persist credentials or implement networking.

## Implementation assessment and follow-up

The strongest design feature is that navigation affordances and effect permissions are connected through explicit typed routes and public-operation contracts. The root/session boundary, standalone host seam, semantic focus restoration, and shared account chrome reduce duplicate policy in individual screens. Shared widgets also centralize responsive table width allocation, Unicode cell fitting, status tones, requirement badges that carry glyphs as well as color, and reusable source-action composition (shared table and widgets (`src/cadrumo/entrypoints/tui/components/widgets.py`), cell fitting (`src/cadrumo/entrypoints/tui/components/cell_text.py`), theme token resolution (`src/cadrumo/entrypoints/tui/components/theme.py`)).

One bounded review question is whether `ContentDataTable._natural_width` should use display-cell width rather than Python string length: that allocator measures labels and cell text with `len`, while the adjacent text helper explicitly measures terminal cells. If wide or combining characters reach table cells, confirm that Textual’s own rendering measurement prevents clipping or over-allocation (table natural width (`src/cadrumo/entrypoints/tui/components/widgets.py`), cell-width helper (`src/cadrumo/entrypoints/tui/components/cell_text.py`)). This is not established here as a user-visible defect. Theme comments state that selected colors meet AA contrast; this chunk contains no contrast-check implementation or test evidence, so the claim remains unverified (theme palettes (`src/cadrumo/entrypoints/tui/components/theme.py`)).

Synthesis should trace the `RuntimeFrontendClient` and `RuntimeOperationController` operations behind the AEAT handoff, verify that profile/session invalidation covers in-flight work, and follow calendar projection and recovery factories to their producers. It should also connect the Declarations canonical action guards to the route/controller construction paths (declarations action guards (`src/cadrumo/entrypoints/tui/declarations/action_guards.py`)). These questions are cross-module; this report does not infer a global limitation from their absence here.

## Complete assigned-file coverage

All assigned files and declared line counts are covered above. The detailed capability citations point into these same files.

- tui/__init__.py (`src/cadrumo/entrypoints/tui/__init__.py`) — 10 lines
- tui/__main__.py (`src/cadrumo/entrypoints/tui/__main__.py`) — 37 lines
- tui/account.py (`src/cadrumo/entrypoints/tui/account.py`) — 172 lines
- tui/action_target.py (`src/cadrumo/entrypoints/tui/action_target.py`) — 16 lines
- aeat_sync/__init__.py (`src/cadrumo/entrypoints/tui/aeat_sync/__init__.py`) — 1 line
- aeat_sync/controller.py (`src/cadrumo/entrypoints/tui/aeat_sync/controller.py`) — 177 lines
- aeat_sync/models.py (`src/cadrumo/entrypoints/tui/aeat_sync/models.py`) — 109 lines
- aeat_sync/routes.py (`src/cadrumo/entrypoints/tui/aeat_sync/routes.py`) — 113 lines
- aeat_sync/runtime_handoff.py (`src/cadrumo/entrypoints/tui/aeat_sync/runtime_handoff.py`) — 541 lines
- aeat_sync/screens.py (`src/cadrumo/entrypoints/tui/aeat_sync/screens.py`) — 822 lines
- tui/app.py (`src/cadrumo/entrypoints/tui/app.py`) — 931 lines
- tui/bound_session.py (`src/cadrumo/entrypoints/tui/bound_session.py`) — 70 lines
- components/__init__.py (`src/cadrumo/entrypoints/tui/components/__init__.py`) — 5 lines
- components/account_chrome.py (`src/cadrumo/entrypoints/tui/components/account_chrome.py`) — 236 lines
- components/app_access.py (`src/cadrumo/entrypoints/tui/components/app_access.py`) — 33 lines
- components/cell_text.py (`src/cadrumo/entrypoints/tui/components/cell_text.py`) — 60 lines
- components/dialogs.py (`src/cadrumo/entrypoints/tui/components/dialogs.py`) — 68 lines
- components/filing_year_route.py (`src/cadrumo/entrypoints/tui/components/filing_year_route.py`) — 46 lines
- components/host.py (`src/cadrumo/entrypoints/tui/components/host.py`) — 50 lines
- components/status.py (`src/cadrumo/entrypoints/tui/components/status.py`) — 143 lines
- components/theme.py (`src/cadrumo/entrypoints/tui/components/theme.py`) — 490 lines
- components/widgets.py (`src/cadrumo/entrypoints/tui/components/widgets.py`) — 473 lines
- components/workspace_host.py (`src/cadrumo/entrypoints/tui/components/workspace_host.py`) — 61 lines
- declarations/__init__.py (`src/cadrumo/entrypoints/tui/declarations/__init__.py`) — 1 line
- declarations/action_guards.py (`src/cadrumo/entrypoints/tui/declarations/action_guards.py`) — 61 lines
- declarations/calendar.py (`src/cadrumo/entrypoints/tui/declarations/calendar.py`) — 416 lines
<!-- /preserved:article -->
