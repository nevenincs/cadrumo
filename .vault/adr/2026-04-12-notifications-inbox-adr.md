---
tags:
  - "#adr"
  - "#notifications-inbox"
date: 2026-04-12
modified: '2026-04-12'
title: AEAT notifications inbox — ADR
related:
  - "[[2026-04-12-notifications-inbox-research]]"
  - "[[2026-04-12-submission-engine-adr]]"
issue: wgergely/aeat#46
---

# adr: aeat notifications inbox

## context

Spanish AEAT issues a small number of legally binding document kinds
— *requerimientos*, *propuestas de liquidación*, *acuerdos de
liquidación*, *notificaciones de embargo*, *acuses de recibo*,
*comunicaciones generales*. Each is published under the taxpayer's
*Mis notificaciones* surface on the Sede Electrónica and, in the
binding cases, mirrored through DEHú. Missing one can cost a
sanction, an undefended liquidación, or an enforced embargo. wgergely/aeat#46
is the local, typed, read-only inbox that fetches these,
classifies them, computes appeal deadlines, and surfaces them loudly
through the `aeat inbox` CLI. See
`[[2026-04-12-notifications-inbox-research]]` for the legal and
surface-level background.

## decisions

### D1: the inbox is read-only against AEAT; acknowledgement is local state

`aeat inbox ack` records `acknowledged_at` / `acknowledged_by` in the
**local** inbox file. It does **not** tell AEAT anything. AEAT's
legal-delivery clock runs on *fecha de notificación* regardless of
local state, and the Sede Electrónica has no "mark as read" API.

**Rationale:** any design that implied a two-way sync with AEAT would
create a false-equivalence between local acknowledgement and legal
response — the exact failure mode this issue exists to prevent. The
docstring on every ack-adjacent surface repeats this.

### D2: the classifier is a pure-function rule table over Spanish subject prefix

The classifier maps a raw notification payload to
`(NotificacionKind, NotificacionPriority)` via an ordered tuple of
`(prefix, kind, priority)` rules. It is deterministic, auditable, and
100% unit-tested.

**Rationale:** we considered an LLM classifier and rejected it. A
non-deterministic classifier on legally binding documents is a
silent-miss risk we cannot accept. The Spanish subject-prefix surface
is narrow, stable, and already Spanish-authoritative under the
trilingual contract. Rule additions are a one-line PR.

### D3: unclassified notifications default to (OTRO, HIGH), never (OTRO, NORMAL)

If the classifier does not recognise a subject prefix, the result is
`(NotificacionKind.OTRO, NotificacionPriority.HIGH)`. The fallback is
deliberately noisy: better a false-HIGH on a *comunicación general*
than a silent pass on a new-shape *requerimiento* AEAT invented last
quarter. This rule is enforced by a dedicated unit test and is
explicitly called out in the classifier docstring.

**Rationale:** the cost of a false-positive is a single extra line in
`aeat inbox list --unread`. The cost of a false-negative is a missed
appeal window. The asymmetry is extreme, so the fallback is extreme.

### D4: every record is strict, frozen pydantic v2

`Notificacion` and `Inbox` use
`ConfigDict(strict=True, frozen=True, extra="forbid")`.
`NotificacionKind` and `NotificacionPriority` are `enum.StrEnum`.
There are no dataclasses, no `TypedDict`s, no bare `dict[str, Any]`
in public signatures or on disk. The persisted inbox file is
`Inbox.model_dump_json()` and loaded via `Inbox.model_validate_json()`.

**Rationale:** the project-wide pydantic v2 mandate (issue #46 pinned
comment, plus project north-star memory) requires strict validation
at every boundary. The inbox crosses three boundaries — wire (from
#43), disk (JSON file), and CLI (user input) — so the model is the
validation gate for all three.

### D5: `received_at` vs `effective_at` are distinct

`Notificacion.received_at` is the moment the inbox first observed the
entry. `Notificacion.effective_at` is the legal *fecha de
notificación*. Appeal-deadline arithmetic uses `effective_at`
exclusively.

**Rationale:** Spanish administrative law (LGT / Ley 39/2015) is
explicit that the appeal clock runs from *fecha de notificación*,
which can lag the observed-by date by up to 10 days (the *regla de
los diez días*). Conflating the two would produce wrong deadlines on
notifications the user did not open promptly.

### D6: protocol stubs for cross-module dependencies

The inbox does not hard-import from:

- `aeat.status` (#43) — the notification source. Stubbed via a
  `NotificacionSource` Protocol matching
  `async fetch_notificaciones(*, since: date | None = None) ->
  tuple[RawNotificacion, ...]`.
- `aeat.adapters.outbound.aeat.auth.certificate` (#8) — the cert backend. Not consumed
  directly; #43 owns certificate preloading.
- `aeat.domain.normatives` (#45) — the normatives catalogue. Appeal-window
  rules cite LGT articles as bare strings (`"LGT art. 99"`), never
  as hard imports.

Rebase swap on merge is mechanical: replace the Protocol import with
the real one, delete the stub, done. The pattern mirrors #42
(submission engine).

### D7: non-goals are explicit

The inbox does **not**:

- Draft appeals or responses — separate future issue.
- Send email / SMS — structured log + CLI only.
- Persist to the storage layer (#10) — single JSON file under
  `AEAT_INBOX_DIR` for v1.
- Expose a web UI.
- Integrate DEHú — future.

These are documented in the package docstring so future contributors
know what is *deliberately* absent vs merely not-yet-built.

### D8: appeal-deadline windows are declared per kind in a typed table

`_classifier._APPEAL_WINDOWS` is an immutable mapping from
`NotificacionKind` to an `_AppealWindow` model
(`days: int`, `unit: Literal["calendar", "business"]`, `rule: str`).
v1 computes deadlines using **calendar-day** arithmetic even for
kinds whose legal rule is business-day, and carries a note in the
docstring pointing at #45. This is a deliberate accuracy/complexity
tradeoff for v1: calendar-day arithmetic is conservative (earlier
deadline), so the worst case is surfacing an alert a few days
early, not missing one.

## consequences

- Classifier rule additions are a one-line PR + one unit test.
- Rebase onto #43, #8, #45 is a one-file diff in
  `_protocols.py`.
- The inbox is self-contained, deterministic, and has zero
  hard-imports from in-flight sibling branches.
- The `OTRO → HIGH` fallback means occasional noise on general
  comunicaciones. Acceptable cost.
- The `effective_at` field requires upstream (#43) to parse *fecha
  de notificación* from the Sede HTML. If #43 returns
  `received_at == effective_at` as a first cut, the inbox is correct
  but deadlines may be up to 10 days early (conservative).

## out of scope

See D7.
