---
tags:
  - '#adr'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3cee1b6307c4ff8547f40dc09c8fdcba6e057b492b4f31f43c94de8dad2412e8'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-reference]]"
---

# `dehu-notification-legal-effect` adr: `DEHu notification legal-effect and service state` | (**status:** `accepted`)

## Problem Statement

The DEHu buzón reader pulls formal notificaciones read-only
(`2026-08-07-dehu-notification-legal-effect-reference`), but nothing in the
tree computes whether a pulled, unaccessed notificación has become legally
served. `calendar_events_from_notification_snapshots` copies the raw date and
a free-text read/unread status with no window arithmetic; the workflow
inbox guard blocks on any unread formal notificación regardless of age
(deliberately stricter than the law, out of scope to change); and
`PostFilingEventKind`'s plain `NOTIFICACION` fallback is excluded from
`ACTIONABLE_POST_FILING_EVENT_KINDS`, so an ordinary formal notification
whose concepto matches no sharper pattern never reaches the operator's
attention at all — not on day 1, not on day 30. A taxpayer can be legally
deemed to have accepted a notification's contents (rechazo tácito, Ley
39/2015 art. 43.2) with the application never having said so. This decision
fixes the legal window, its typed representation, and where it surfaces —
not a filing action, since the buzón stays read-only.

## Considerations

- **Días naturales, not hábiles.** Art. 43.2 fixes ten *días naturales*;
  weekends, holidays and August count. A días-hábiles implementation
  understates urgency by computing a later lapse date than the law allows —
  the wrong-direction error `no-silent-under-declaration` exists to prevent
  (`dehu-notification-legal-effect-reference`, "Regulatory grounding").
- **The clock runs from `fecha_notificacion` (puesta a disposición), never
  from access.** Confirmed against `RemoteNotification`'s own field
  docstring; access is the separate `leida` boolean
  (`dehu-notification-legal-effect-reference`, "The read-only DEHu surface").
- **The value is a regulatory leaf constant, not a literal.** Per
  `aeat-registry-authority-flow`, regulatory values live in the central
  config or the registry authoring tree, never inlined; `external_constants.py`
  is the established home for a year-stable, non-modelo-scoped figure like
  this one (`dehu-notification-legal-effect-reference`, "Value-storage
  precedent").
- **The legal catalogue entry is a precondition, not a side effect of this
  ADR.** No Ley 39/2015 corpus file or catalogue entry exists yet
  (`dehu-notification-legal-effect-reference`, "Corpus and legal-catalogue
  state"). An ADR ruling on code is not self-executing
  (`aeat-agent-orchestration`); the fetch, anchor, and catalogue entry are
  opened as their own Step in Implementation below, in the same action as
  this ADR, so the debt has an owner.
- **Service state and procedural kind are orthogonal axes.**
  `PostFilingEventKind` already closes the procedural-category axis
  (`dehu-notification-legal-effect-reference`, "No legal-effect computation
  exists anywhere in the tree"); overloading it with service-state members
  would let one enum answer two unrelated questions and make a future
  "what changed" diff ambiguous between kind and state.
- **The `NOTIFICACION`-fallback actionability gap must close for deemed-served
  items specifically**, not by making every plain notificación actionable —
  that would regress the overview to flagging every read receipt.
- **Diagnostics ride the typed `Notice` channel** (`aeat-cli-contract`); no
  bespoke result field.
- **Días de cortesía is a separate profile-fact axis**, gating new AEAT
  *deposits*, not pausing a clock already running on a delivered
  notification (`dehu-notification-legal-effect-reference`, "Regulatory
  grounding"). No profile schema currently captures declared courtesy days;
  folding an unbuilt axis into this window computation would be
  speculative, so it is explicitly out of scope (see Constraints).
- **Direction of error this design protects, and what it does not catch:**
  every existing gate in this codebase watches under-declaration; nothing
  watches a taxpayer being misled about urgency. Rendering a served
  notification as merely "unread" understates consequence — that is the gap
  this ADR closes. It does NOT catch: a wrong or missing
  `fecha_notificacion` from AEAT's own portal data (garbage in, garbage
  out); días de cortesía (deferred, above); or a procedure-specific
  notification-window rule narrower than the general Ley 39/2015 regime,
  which was not exhaustively searched — only RD 1363/2010 (remits to the
  general regime) and LGT art. 112 (a different failure mode, ruled out)
  were checked against this concrete gap.

## Considered options

- **A: New `NotificacionEstadoServicio` `StrEnum` in `core/`, computed by a
  pure function, surfaced as a new typed field on the calendar event and a
  widened actionability predicate (chosen).** Keeps kind and state
  orthogonal; follows the exact `core/_post_filing_event.py` pattern
  already established for this domain.
- **B: Add service-state members directly to `PostFilingEventKind`
  (e.g. `NOTIFICACION_RECHAZO_TACITO`).** Rejected: conflates two axes into
  one enum — a `REQUERIMIENTO` can independently be accessed,
  within-window, or deemed-served, so cross-producting kind × state into
  enum members multiplies membership combinatorially and breaks the
  existing `ACTIONABLE_POST_FILING_EVENT_KINDS` frozenset's single-axis
  contract.
- **C: Compute the window inline in `_stage_checking_inbox` /
  `calendar_events_from_notification_snapshots` with no typed enum, just a
  boolean or free-text status.** Rejected: repeats the existing free-text
  `status` mistake this ADR exists to fix, and gives no typed surface for a
  future consumer (export, MCP resource) to depend on without re-deriving
  the rule.
- **D: Model the ten-day figure as a `DeadlineWindowDefinition` registry
  binding.** Rejected: that schema is `filing_year`/`period`/modelo scoped
  for a specific obligation's filing window
  (`dehu-notification-legal-effect-reference`, "Value-storage precedent");
  the DEHu response window is generic and modelo-independent, so forcing it
  into that shape would require a synthetic modelo/period pairing with no
  filing behind it.
- **E: Leave the workflow inbox guard as the sole safeguard and do nothing
  else.** Rejected: the guard only fires during a submission attempt and
  only for the current obligation's own filing; it does not tell an
  operator, on any other day, that a specific notification has already
  lapsed into deemed service.

## Constraints

## Implementation

## Rationale

## Consequences
