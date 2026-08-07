---
tags:
  - '#adr'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:89da3c62d83e8cdfa0994c7fcedef02b8861bdf60ae61b7af135ebd0c6b16d58'
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

- **No Ley 39/2015 corpus exists yet.** The corpus fetch/anchor/commit is a
  hard precondition of any `legal_refs` citing art. 43.2; it must be sourced
  from BOE's live consolidated text (never hand-authored), taking the LAST
  version if the fetched payload bundles historical redactions, per
  `aeat-calculation-grounding`.
- **Días de cortesía is explicitly out of scope.** No profile schema
  currently models declared courtesy days; the window computation this ADR
  authorises does not pause for them. A later feature adding courtesy-day
  capture must revisit the window function, not bolt an unmodelled
  parameter onto this one now.
- **Exhaustive procedure-specific notification-window review is out of
  scope.** Only the general Ley 39/2015 regime, RD 1363/2010, and LGT art.
  112 were checked (Considerations, "Direction of error"). A narrower
  regime for a specific AEAT procedure, if one exists, is not ruled out.
- **The workflow inbox guard (`_stage_checking_inbox`) is unchanged.** It
  stays a blunt "any unread formal notificación blocks filing" check,
  which is stricter than art. 43.2 requires and therefore safe to leave as
  is; this ADR does not loosen it to key off the new service-state
  computation.

## Implementation

**Precondition — legal grounding (opened as its own implementing row, same
action as this ADR, not deferred):**

1. Fetch BOE's live consolidated text for Ley 39/2015 art. 43.2, taking the
   LAST version if the payload bundles historical redactions; commit the
   HTML plus its `.extracted.json`/`.extracted.md` sidecars under
   `src/cadrumo/_data/corpus/normatives/html/` following the existing
   `ley-*` naming convention (e.g. `ley-39-2015-art-43.html`).
2. Add a new topic-scoped legal-catalogue file
   `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml`
   (following the `lgt-autoliquidacion.toml` / `censo.toml` non-modelo-scoped
   precedent) with one reviewed `LegalReference` (`kind = "ley"`,
   `corpus_ref` anchored to the committed file, `required_text` carrying the
   "diez días naturales desde la puesta a disposición" phrase verbatim).
3. Run `verify_legal_reference` / the catalogue's existing build-time
   verification to confirm the entry is filing-grade before anything
   downstream cites it.

**Core typed axis:**

4. Add `DEHU_RECHAZO_TACITO_DIAS_NATURALES: Final[int] = 10` to
   `core/external_constants.py`, doc-commented with the art. 43.2 citation
   in the same style as the file's existing entries
   (`MINIMO_DESCENDIENTE_MAX_AGE`, `ART_81_1_ENTRY_WINDOW_YEARS`).
5. Add a new `core` module declaring `NotificacionEstadoServicio` (`StrEnum`:
   `NO_ENTREGADA`, `ACCEDIDA`, `EN_PLAZO`, `RECHAZO_TACITO`) and a pure
   function computing it from `(fecha_notificacion: date | None, leida: bool
   | None, as_of: date)` against `DEHU_RECHAZO_TACITO_DIAS_NATURALES`,
   following `core/_post_filing_event.py`'s module shape (docstring,
   `__all__`, no I/O). Spanish-stemmed module and symbol names throughout,
   per the naming decision above.

**Wiring:**

6. Add a typed `notificacion_estado_servicio:
   NotificacionEstadoServicio | None` field to `OverviewCalendarEvent`,
   populated only for `MESSAGE`-type events sourced from notification
   snapshots; `calendar_events_from_notification_snapshots` computes it per
   row from the function in (5).
7. Widen the actionability predicate consumed by
   `actionable_post_filing_events`: an event is actionable when its
   `post_filing_kind` is in `ACTIONABLE_POST_FILING_EVENT_KINDS` **or** its
   `notificacion_estado_servicio` is `RECHAZO_TACITO` — independent of
   kind, so a plain `NOTIFICACION` that lapses into deemed service becomes
   actionable without making every notificación actionable.
8. Extend the CLI overview `Notice` composer
   (`entrypoints/cli/_overview_rendering.py`) to include deemed-served
   notifications in its existing `warning`-severity `Notice`, or a sibling
   `Notice`, carrying the art. 43.2 `legal_refs` id and the affected
   certificado ids on `Notice.context` — no bespoke result field.

**Tests:** a roundtrip/boundary test for the pure function (day 9 →
`EN_PLAZO`, day 10 → `RECHAZO_TACITO`, `fecha_notificacion is None` →
`NO_ENTREGADA`, `leida is True` → `ACCEDIDA` regardless of elapsed days) —
a structural boundary test, not a tautological value-from-formula test; a
grounding test asserting the legal catalogue entry's `required_text`
resolves against the committed corpus (the existing
`test_legal_anchor_verification_ratchet.py` / catalogue-verification
machinery, not a bespoke check); and an overview-projection test proving a
synthetic lapsed notification reaches `actionable_post_filing_events` and
the rendered `Notice`.

## Rationale

Option A wins on a knockout criterion: it is the only option that keeps
`PostFilingEventKind` a single-axis enum (per `aeat-architecture-boundaries`'
typed-constant-axis discipline) while still closing the concrete
actionability gap the reference and dispatch brief both name. Option B fails
that discipline directly. Option C reproduces the exact free-text-status
anti-pattern already present in `_calendar.py` that this feature exists to
replace. Option D is a shape mismatch — `DeadlineWindowDefinition` is
inherently `filing_year`/`period`/modelo scoped and every existing consumer
assumes that scoping; forcing a generic rule through it would be the
"one canonical mechanism per calculation type" violation `aeat-calculation-
aggregation` forbids in the adjacent domain. Option E leaves the actual gap
(a lapsed notification never surfacing outside a live submission attempt)
unaddressed.

## Consequences

- **Gain:** a taxpayer can no longer be deemed to have accepted a
  notification's contents without the application having said so
  somewhere an operator will see it — the overview `Notice` and the typed
  calendar event.
- **Gain:** the service-state/kind separation gives a clean extension point
  — a future `EN_PLAZO`-approaching-lapse advisory (e.g. "3 days left") can
  reuse the same pure function without touching `PostFilingEventKind`.
- **Difficulty:** the precondition row (corpus fetch + catalogue entry) is
  real work with its own failure mode — a truncated or wrong-version BOE
  fetch would ground the whole feature on bad text; it must be verified
  independently before the constant's docstring can cite it as settled.
- **Pitfall carried forward:** días de cortesía and procedure-specific
  narrower windows remain unmodelled; a future filer who has declared
  courtesy days, or who is inside a procedure with its own notification
  article, could see a `RECHAZO_TACITO` flag that is technically premature
  or inapplicable. This is the honest boundary of this decision, not a
  silent gap — Constraints states it explicitly so it is not mistaken for
  exhaustive coverage.
- **Pathway opened:** the Spanish-stemmed `core` module and its pure
  function are also the natural home for a future recaudación-side deadline
  (providencia de apremio response windows use a similar días-naturales
  shape) should that need arise.
