---
tags:
  - '#research'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:4ce49126b8cedabe7f30866ff0dc76c4803da779129d5c9438ded9e1daa66361'
related:
  - "[[2026-09-02-unreachable-capability-tui-root-composition-research]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---

# `unreachable-capability` research: `tui homepage product design`

The TUI needs a user-facing workbench, not a menu of implementation areas. Evidence favors a due-driven Home that answers what needs attention, which declaration can be resumed, and what is due next. Account utilities remain in the header; Declarations, Ledger, Calendar and Messages become routed destinations only when their composition is genuinely available. This is target information architecture: Home has the strongest existing application authority, while several destination factories and public composition seams remain missing.

## Findings

### Navigation must describe operator concepts

Profile, Secret, Flows, Operations and Modelo are not symmetric destinations. Login, password rotation and logout are account journeys; flows begin from the task they accomplish; operation modals are contextual; and Modelo already owns six local workspace destinations in `src/cadrumo/entrypoints/tui/modelo/routes.py:44`. The candidate shell instead names Home, Declarations, Ledger, Calendar and Messages, with Profile, Change user, Change password, Settings and Sign out under account identity. The ADR must settle this vocabulary and must not expose `WorkUnit`; “Declaration” is the candidate term for one local Modelo, year and period case, while “Filing” remains reserved for submission evidence.

Equal Profile/Ledger/Modelo tabs were rejected because they imply peer workflows. An implementation-area launcher was rejected because it gives no filing priority. HMRC documents account utilities separately from its home tax tasks; AEAT separately exposes Modelo declarations, notifications and a deadline calendar. https://www.gov.uk/government/publications/use-hmrcs-business-tax-account/use-hmrcs-business-tax-account, https://sede.agenciatributaria.gob.es/Sede/presentar-consultar-declaraciones-modelo.html, https://sede.agenciatributaria.gob.es/Sede/notificaciones-cotejo-documentos/notificaciones.html

### The strongest Home is a due-driven triage and resume surface

`build_overview_status_report()` and `build_overview_status_next_steps()` already provide application-owned status and actions in `src/cadrumo/application/overview/status_report.py:127` and `src/cadrumo/application/overview/next_actions.py:129`. The favored candidate leads with at most three Next actions, then a stable declaration-resume list and filing agenda. Each action needs Modelo and period context, a reason and one verb. Ranking belongs to the application projection, not the frontend. GOV.UK's multi-task pattern supports a status-bearing return point for long transactions. https://design-system.service.gov.uk/patterns/complete-multiple-tasks/

A lower-density task launcher hides deadline state, so it is better retained as Textual's fuzzy `Ctrl+P` command palette. https://textual.textualize.io/guide/command_palette/ Recent activity was rejected because Filing history, Messages and operation status own different facts and no application-owned redacted activity projection exists.

### Calendar should be a chronological agenda, not a month grid

The application distinguishes schedule, local filing readiness, AEAT-observed submission and justificante evidence in `src/cadrumo/application/overview/calendar.py:874`; agenda and backlog builders live at `src/cadrumo/application/overview/agenda.py:97` and `src/cadrumo/application/overview/backlog.py:88`. Home should preview three rows with date/window, Modelo, period and textual evidence state. A month grid wastes terminal cells and collapses poorly. The missing frontend-neutral evidence loader currently lives as a CLI-private join at `src/cadrumo/entrypoints/cli/app/_overview_evidence.py:61` and must be promoted or recomposed, never imported or duplicated by TUI. AEAT's official calendar is explicitly Modelo- and deadline-based. https://sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/calendario-contribuyente-2026/calendario-anual.html

### Unknown and unavailable are first-class states

Status pieces exist in `src/cadrumo/application/user_profile/status_projection.py:50`, but the root accepts only operation services in `src/cadrumo/entrypoints/tui/app.py:39`. A Home projection must distinguish no profile, locked, unlocked, expired, never captured, stale and unavailable. It must not render protected counts as zero or say there are no messages when none were captured. Initial Home is local-only; network refresh is explicit.

Notifications have encrypted snapshot reads in `src/cadrumo/application/live/notifications.py:153`, but no Inbox projection or TUI screen. Ledger has canonical summaries in `src/cadrumo/application/ledger/actions_manual.py:567`, but no TUI area. Both may appear as unavailable or stale in a synthetic prototype, but neither should be callable production navigation yet. A general Settings screen is also absent.

### Existing screens should be routed, not reproduced

Profile editing exists at `src/cadrumo/entrypoints/tui/profile/overview.py:291`; password rotation at `src/cadrumo/entrypoints/tui/secret/passphrase.py:88`; Modelo route and action catalogues at `src/cadrumo/entrypoints/tui/modelo/routes.py:44` and `src/cadrumo/entrypoints/tui/modelo/actions.py:123`. Home should deep-link into these owners and contain no inline editing or calculation.

The route is not end-to-end mountable: the declaration picker requires its standalone host at `src/cadrumo/entrypoints/tui/modelo/view/work_select.py:97`; workspace destinations call `app.exit()` rather than dismissing to a parent, for example `src/cadrumo/entrypoints/tui/modelo/view/overview.py:157`; and the launcher composes only operation services at `src/cadrumo/entrypoints/tui/launcher.py:156`. This contradicts the accepted record's ready-made-root premise, so its amendment remains prerequisite.

### Responsive behavior requires routed screens and semantic focus

Wide layout uses a two-thirds main column for Next actions and Declarations plus a one-third agenda. At the `80x24` floor in `src/cadrumo/entrypoints/tui/tests/terminal_sizes.py:21`, it becomes one scroll column ordered Actions, Declarations, Agenda; account utilities collapse; localized navigation uses a tested two-row or overflow treatment. The existing ordinary wide gate is `120x40`, so requested `120x35` is an additional snapshot.

Destinations are routed screens, not mounted `TabbedContent` bodies. Each list is one Tab stop; arrows move; Enter opens; Escape returns; F3 retains appearance; `Ctrl+P` opens the palette. Focus restoration uses semantic identity rather than row index. Active, focused, missing and refused states require words plus glyphs, never colour alone. https://textual.textualize.io/guide/screens/, https://textual.textualize.io/widgets/data_table/

### The minimum prototype tests layout, not business behavior

The thinnest experiment is a devtool shell backed by immutable synthetic, non-sensitive `HomeProjectionV1`-shaped fixtures. Render account posture, Next actions, three resumable Declarations, an agenda and explicit Ledger/Messages unavailable states, but perform no repository reads, network calls, execution or calculation. Reuse widgets at `src/cadrumo/entrypoints/tui/components/widgets.py:19`.

Smoke due-driven and task-launcher candidates through the real compositor at `80x24`, `100x30`, `120x40` and `200x50`, both themes and all locales. Measure clipping, scroll ownership, focus reachability, restoration and keystrokes. No real-operator or assistive-technology test was performed, so no usability or accessibility compliance claim follows.

The ADR amendment must settle vocabulary, authenticated visibility, Home projection and refresh, destination admission, account composition, calendar evidence join, Messages/Ledger readiness, the Declaration enclosing journey and unavailable-destination policy. Only then can the existing plan be widened through its owning verbs.

## Sources

- `src/cadrumo/application/ledger/actions_manual.py:567`
- `src/cadrumo/application/live/notifications.py:153`
- `src/cadrumo/application/overview/agenda.py:97`
- `src/cadrumo/application/overview/backlog.py:88`
- `src/cadrumo/application/overview/calendar.py:874`
- `src/cadrumo/application/overview/next_actions.py:129`
- `src/cadrumo/application/overview/status_report.py:127`
- `src/cadrumo/application/user_profile/status_projection.py:50`
- `src/cadrumo/entrypoints/cli/app/_overview_evidence.py:61`
- `src/cadrumo/entrypoints/tui/app.py:39`
- `src/cadrumo/entrypoints/tui/components/widgets.py:19`
- `src/cadrumo/entrypoints/tui/launcher.py:156`
- `src/cadrumo/entrypoints/tui/modelo/actions.py:123`
- `src/cadrumo/entrypoints/tui/modelo/routes.py:44`
- `src/cadrumo/entrypoints/tui/modelo/view/overview.py:157`
- `src/cadrumo/entrypoints/tui/modelo/view/work_select.py:97`
- `src/cadrumo/entrypoints/tui/profile/overview.py:291`
- `src/cadrumo/entrypoints/tui/secret/passphrase.py:88`
- `src/cadrumo/entrypoints/tui/tests/terminal_sizes.py:21`
- https://design-system.service.gov.uk/patterns/complete-multiple-tasks/
- https://sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/calendario-contribuyente-2026/calendario-anual.html
- https://sede.agenciatributaria.gob.es/Sede/notificaciones-cotejo-documentos/notificaciones.html
- https://sede.agenciatributaria.gob.es/Sede/presentar-consultar-declaraciones-modelo.html
- https://textual.textualize.io/guide/command_palette/
- https://textual.textualize.io/guide/screens/
- https://textual.textualize.io/widgets/data_table/
- https://www.gov.uk/government/publications/use-hmrcs-business-tax-account/use-hmrcs-business-tax-account
