---
tags:
  - '#research'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c95e0292676ec9a6ddce2155ce699c370dd4f48ea99b2976c35e126414ba222a'
related:
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---

# `unreachable-capability` research: `the real TUI root composition boundary`

The accepted home-screen intent remains sound, but its implementation premise is false in the live source: five ready-made, host-agnostic area roots do not exist. A truthful join needs two boundaries—a frontend-neutral root-session projection and refresh door, plus a TUI-local catalogue of admitted area factories—and several product choices must be amended into the existing ADR before `W06.P13.S73` can execute.

## Findings

### Leaf screens are not five mountable areas

The root receives only `OperationComposedServices` and has neither session posture nor area factories (`src/cadrumo/entrypoints/tui/app.py:39`). Profile and secret expose multiple task screens with different prerequisites; `FlowScreen` requires a selected definition and mode; `OperationModal` requires an existing submitted controller; and Modelo has route/action catalogues but no enclosing journey (`src/cadrumo/entrypoints/tui/profile/app.py:58`, `src/cadrumo/entrypoints/tui/secret/login.py:35`, `src/cadrumo/entrypoints/tui/flows/app.py:306`, `src/cadrumo/entrypoints/tui/operations/modal.py:87`, `src/cadrumo/entrypoints/tui/modelo/routes.py:35`). The current `app.py`-only Step scope cannot implement a real join.

### The minimal boundary splits application facts from Textual factories

The frontend-neutral half needs an immutable session projection: committed profile choices, selected profile identity, live-session posture, and any typed resume refusal. Existing authorities already distinguish committed choices, selected pointer, and live session (`src/cadrumo/application/user_profile/login_interaction.py:10`, `src/cadrumo/application/user_profile/login_session.py:623`, `src/cadrumo/application/user_profile/login_session.py:698`).

The TUI-local half can then hold a fixed catalogue of area ID, locale key, live admission result, and a factory returning a host-agnostic `Screen`. Textual types must not enter the frontend-neutral contract. Per-area factories should close over only their required public doors rather than giving the root repositories or a universal service bag.

### Session posture must refresh after credential transitions

Forcing authentication before home hides valid pre-login journeys; showing every destination and allowing deep refusal presents broken-looking surfaces. The evidence favors a visible fixed inventory whose unavailable entries carry localized reasons and whose credential-recovery journey remains reachable. The ADR must choose this policy. In every option, registration, login, logout, expiry, passphrase change, and profile handover must cause a fresh authoritative session projection rather than trusting a screen outcome.

### Profile and secret require production journey composition

Concrete registration, login, manager, and status builders currently live only in devtools and construct repositories directly (`src/cadrumo/entrypoints/tui/devtools/surfaces.py:51`, `src/cadrumo/entrypoints/tui/devtools/fixture.py:115`). They are references, not production dependencies. The ADR must choose the profile landing and the secret journey by posture: registration with no profiles, login without a live session, and custody/passphrase actions with a live session.

### Flows and operations lack navigable denominators

The wizard catalogue exposes only `SETUP_FLOW`; Modelo work flows are built from a selected work and held runtime context (`src/cadrumo/application/wizard/catalogue.py:1198`, `src/cadrumo/entrypoints/tui/devtools/modelo_work_wizard.py:102`). The ADR must choose whether the home offers setup only, a TUI-local offer catalogue, or an application-owned runnable-flow catalogue.

Operations currently provides cross-cutting services and a modal for an already-submitted operation, but no definition or instance discovery surface (`src/cadrumo/application/operations/composition.py:88`, `src/cadrumo/entrypoints/tui/operations/controller.py:49`). The ADR must decide whether Operations is omitted as a home area, becomes definition discovery, or gains a fail-closed instance-list/reattachment contract.

### Modelo needs an enclosing journey and host-neutral exits

The picker obtains units from a specialized `ModeloWorkSelectApp`, review has the same host assumption, and routed workspace screens exit the whole application instead of dismissing to a parent (`src/cadrumo/entrypoints/tui/modelo/view/work_select.py:42`, `src/cadrumo/entrypoints/tui/modelo/view/work_review.py:277`, `src/cadrumo/entrypoints/tui/modelo/view/overview.py:157`). A joinable area root must receive state and doors through construction, avoid concrete-host narrowing, and dismiss back home. The ADR must specify admission mode, work selection, destination navigation, exposed actions, and post-action settlement.

### Composition belongs in launcher; governance receipts do not

The launcher currently composes only operation services (`src/cadrumo/entrypoints/tui/launcher.py:61`). Production composition should enter the normal profile-adapter scope, resume fail closed, build the session projection, compose operations once, build per-area factories, inject those into the app, and settle all scopes after exit. The CLI remains out of process through `python -m cadrumo.entrypoints.tui` (`src/cadrumo/entrypoints/cli/_tui_session.py:1`, `src/cadrumo/entrypoints/tui/__main__.py:1`).

The accepted ADR's runtime cohort-receipt membership is not implementable: that receipt mechanism was retired and no runtime service exists. Static area membership belongs to build/test conformance; runtime admission uses live session and capability facts.

### The existing ADR needs amendment before execution

The amendment must replace “five existing screens” and “nothing in the areas changes shape,” distinguish static conformance from runtime admission, expand launcher composition, define authentication visibility and refresh, choose Profile/Secret entry journeys and the flow denominator, decide the Operations meaning, specify the Modelo enclosing journey, and widen `W06.P13.S73` beyond `app.py`. Unresolved product choices are the operations-area meaning, runnable-flow population, profile landing, logout/expiry behavior, actor identity for operation actions, and whether unavailable entries are hidden or visibly disabled.

### Modelo edit admission bypasses its canonical capability projection

The exact reachability findings for `application/modelo/edit_session.py` and `_edit_facade.py` are not removable debt. The session is used by the complete C3 TUI editor chain, but `open_modelo_edit_session()` reaches `admit_modelo_edit()` without consulting the mutation-capability projection. The dormant facade is the only implementation of the accepted D5 projection and can classify that same target as `UNMEASURED`; no production consumer reads it. The empty root currently masks this disagreement. The ADR amendment must require one public canonical capability home and one admission path that refuses session creation unless the projection is available, before the editor becomes a root-reachable route (`src/cadrumo/application/modelo/edit_session.py`, `src/cadrumo/application/modelo/_edit_facade.py`, `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`, `src/cadrumo/entrypoints/tui/modelo/routes.py:35`).

## Sources

- `src/cadrumo/entrypoints/tui/app.py:39`
- `src/cadrumo/entrypoints/tui/launcher.py:61`
- `src/cadrumo/application/user_profile/login_interaction.py:10`
- `src/cadrumo/application/user_profile/login_session.py:623`
- `src/cadrumo/application/user_profile/login_session.py:698`
- `src/cadrumo/entrypoints/tui/devtools/surfaces.py:51`
- `src/cadrumo/entrypoints/tui/flows/app.py:306`
- `src/cadrumo/application/wizard/catalogue.py:1198`
- `src/cadrumo/application/operations/composition.py:88`
- `src/cadrumo/entrypoints/tui/operations/modal.py:87`
- `src/cadrumo/entrypoints/tui/modelo/routes.py:35`
- `src/cadrumo/entrypoints/tui/modelo/view/work_select.py:42`
- `src/cadrumo/entrypoints/tui/modelo/view/work_review.py:277`
- `src/cadrumo/entrypoints/tui/modelo/view/overview.py:157`
- `src/cadrumo/entrypoints/cli/_tui_session.py:1`
- `src/cadrumo/entrypoints/tui/__main__.py:1`

- `src/cadrumo/application/modelo/edit_session.py`
- `src/cadrumo/application/modelo/_edit_facade.py`
- `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`
