---
tags:
  - '#adr'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c9b687e263692cb078e81d1dad5f7c65fd2cc3d1ed04790318b92b921e6e1644'
related:
  - "[[2026-09-02-unreachable-capability-research]]"
  - '[[2026-09-02-unreachable-capability-fincas-unblock-research]]'
  - '[[2026-09-02-unreachable-capability-tui-root-composition-research]]'
  - '[[2026-09-02-unreachable-capability-tui-homepage-product-design-research]]'
---
# `unreachable-capability` adr: `one tui entrypoint and a home-screen navigation join` | (**status:** `accepted`)

## Problem Statement

The installed TUI has one reachable process but no product navigation model. The prior form of this decision assumed five host-neutral implementation areas could be listed unchanged. `2026-09-02-unreachable-capability-tui-root-composition-research` disproves that premise; `2026-09-02-unreachable-capability-tui-homepage-product-design-research` grounds the replacement product model. The decision must define the operator-facing workspaces, their composition boundary, Home's role, truthful availability, and the relationship between local data, Modelo calculation and AEAT evidence without creating frontend-owned business behavior.

The entrypoint question is already settled: bare `aeat --tui` starts the out-of-process TUI module, and the parallel `aeat-tui` spelling remains retired.

## Considerations

- Ledger facts are a principal input to Modelo calculations, not a secondary utility.
- Profile facts identify the filer and affect applicability, while profile editing and credential journeys already have dedicated owners.
- Declarations own Modelo calculation, revisions, verification, filing preparation and filing history.
- AEAT retrieval and reconciliation span profile, declarations, notifications and evidence, so they cannot be hidden inside Profile.
- Local state, AEAT-observed state, missing evidence, stale evidence and a proven zero or empty result remain distinct.
- Existing application projections and screens must be composed, never reimplemented in Home.
- The CLI-to-TUI boundary remains out of process; TUI must not import CLI-private evidence joins.

## Considered options

- **Five implementation areas.** Rejected: Profile, Secret, Flows, Operations and Modelo are internal asymmetries, not an operator information architecture, and several are not joinable roots.
- **Profile, Ledger and Modelo as equal tabs.** Rejected: Profile is identity-bound and infrequently edited, while Ledger and Declarations are continuous workspaces; AEAT reconciliation also crosses all three.
- **Modelo-first shell with hidden utilities.** Rejected: it understates Ledger's role as the input layer and obscures evidence reconciliation.
- **Task launcher as Home.** Rejected as the default because it hides portfolio, blocker and deadline state; retained as the global command palette.
- **Joined Home plus Ledger, Declarations and AEAT Sync workspaces, with Profile under account identity.** Chosen.

## Constraints

- The public navigation vocabulary is Home, Ledger, Declarations and AEAT Sync. Profile is always reachable through the account identity control. Implementation terms such as Secret, Flow, Operation and WorkUnit are not navigation labels.
- “Declaration” is the human-facing term for a local Modelo/year/period case. “Filing” is reserved for submission or filing evidence.
- Home is local-only on initial load. AEAT network activity is always an explicit action with visible progress, result and failure state.
- “Sync” means explicit pull, compare, reconcile and supported push or filing actions. It must not imply automatic two-way convergence or silently choose which side wins.
- Every Home zone and destination admission carries an explicit state such as available, locked, stale, never captured or unavailable. Unavailable destinations remain understandable rather than masquerading as empty data.
- Only the active destination body is mounted. Navigation uses routed screens, not a tab container retaining inactive workspaces.
- Focus, active destination, blockers and statuses have textual non-colour cues. Focus restoration uses semantic identity rather than row position.
- Profile, Ledger, Declarations and AEAT evidence remain behind their owning secure-storage, application-service and capability boundaries.

## Implementation

The root receives a frontend-neutral immutable Home projection, a refresh door and a closed destination catalogue. The projection composes account/session posture, application-owned next actions, resumable declarations, Ledger readiness and a short filing agenda. It preserves authority and freshness per zone and performs no calculation, classification or reconciliation itself. Registration, login, logout, password rotation, profile handover and session expiry rebuild the projection through the refresh door.

Home is the joined operational overview. It leads with status and no more than three application-ranked next actions, then resumable declarations and a compact chronological filing agenda. It contains no editor, calculation, profile form or month-grid calendar. Global search and `Ctrl+P` route to owning destinations and actions.

Ledger is a principal workspace for overview, entries, review, imports, classification, evidence and reconciliation. Its landing view prioritises data quality, unresolved classification and affected declarations over decorative financial totals.

Declarations owns in-progress, needs-attention, ready, filed and history views; the full operational calendar belongs here. A declaration workspace owns Modelo inputs, results, provenance, verification, filing and revisions. Existing Modelo screens become genuinely host-neutral and dismiss back to their parent route before production admission.

AEAT Sync owns explicit profile/census retrieval, filed-declaration observation, notifications, evidence comparison and reconciliation. It distinguishes local data from AEAT-observed evidence and provides no generic write path: each push or filing action requires its own registered operation and capability.

Profile editing, user switching, password management, settings and sign-out are account utilities. Existing Profile and secret screens remain their owners; the shell supplies production factories rather than reproducing their forms.

The responsive shell uses a two-column Home when space permits and one ordered scroll column at the supported floor. The full calendar is an agenda/filter/search workbench with optional broader visualisations, not a mandatory month grid. Search spans Ledger entries and evidence, Modelo declarations and revisions, filing records, reconciliation findings and notifications while preserving each result's type, source and status.

The already-landed entrypoint layer remains unchanged: `aeat --tui` starts one child interpreter against the TUI module, and the retired `aeat-tui` console script does not return.

## Rationale

This option matches the application's causal structure: Profile and Ledger facts feed Modelo calculations; Declarations turn them into revisioned filing work; AEAT Sync observes and reconciles external evidence; Home joins their actionable state. It gives Ledger equal operational weight without making account configuration a permanent peer workspace, and it keeps the calendar with the declarations whose legal windows it represents. The command palette preserves task-launcher speed without sacrificing glanceable status.

It also removes the false assumption that finished modules are automatically joinable destinations. A projection plus admitted factory catalogue makes availability explicit and keeps persistence, network, calculation and mutation authority out of the root frontend.

## Consequences

Operators gain one coherent workbench, a first-class Ledger, a declaration lifecycle with calendar and history, explicit AEAT reconciliation, account-bound Profile access and global search. Missing, stale and conflicting evidence remains visible.

The architecture and interface plans must be reconciled before execution. Work now includes a Home projection and refresh contract, production area factories, host-neutral declaration navigation, a Ledger TUI, a public calendar/evidence composition provider, AEAT Sync and notification projections, global search, localization, responsive behavior and accessibility gates. These capabilities may land incrementally, but unavailable destinations cannot claim completion.

The earlier “five existing areas, no shape changes” implementation text is retired by this amendment. The entrypoint retirement and out-of-process CLI boundary remain in force.
