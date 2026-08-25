---
tags:
  - '#adr'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:cf37531e4cc5d9e728bc499591bb3b2d82161257b9c85b2c22205e0ef8c941ba'
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
- **`core/external_constants.py` is a DEFINITION home for this class of
  value, not a re-export layer.** Checked directly: none of its existing
  regulatory leaf constants (`M347_THRESHOLD_EUR`,
  `MINIMO_DESCENDIENTE_MAX_AGE`, `ART_7P_EXEMPTION_CAP_EUR`, and every
  sibling) are imported from `external_constants.toml` or from any registry
  TOML — each is a hand-authored `Final[Decimal]`/`Final[int]` literal in
  the `.py` file itself, with a doc comment citing its binding provision.
  `test_external_constants_centralisation_part1.py`'s own module docstring
  states the file's role in terms: "pins ... statutory threshold amounts to
  `core.external_constants`... AST scans catch bare ... threshold literals
  reintroduced OUTSIDE THE CANONICAL REGISTRY" — i.e. this file IS the
  canonical registry for exactly this value class, and the "one-line import
  from the curated `core.external_constants` re-export layer" language in
  `aeat-registry-authority-flow` describes how a *consuming feature module*
  should reference the value (import it, don't re-declare it), not a
  requirement that `external_constants.py` itself source values from
  elsewhere. `DEHU_RECHAZO_TACITO_DIAS_NATURALES` follows the identical
  shape as its neighbours: non-modelo-scoped, year-stable, statutory,
  doc-cited.
- **The legal catalogue entry is a precondition, not a side effect of this
  ADR.** No Ley 39/2015 corpus file or catalogue entry exists yet
  (`dehu-notification-legal-effect-reference`, "Corpus and legal-catalogue
  state"). An ADR ruling on code is not self-executing
  (`aeat-agent-orchestration`); the fetch, anchor, and catalogue entry are
  opened as their own Step in Implementation below, in the same action as
  this ADR, so the debt has an owner.
- **The human-review gate is enforced by the type system, not only by
  discipline.** `LegalReference.review_status` is typed
  `Literal["reviewed"]` (`domain/calculations/registry/_legal.py`'s own
  documented invariant), so no other value is representable on disk — an
  agent CANNOT write a "draft, pending review" entry without the written
  bytes themselves asserting a review that did not happen. The only
  compliant move is to draft the candidate entry outside the registry (in
  the executing Step's own record) and let the operator commit the real
  file. This is a structural guarantee, not merely a process rule the plan
  states.
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
- **Días de cortesía is excluded on its own terms, not merely deferred.**
  RD 1363/2010 DA tercera bars AEAT from *depositing* a new notification
  during declared courtesy days; it does not pause a clock already running
  on a notification that WAS deposited. Since this ADR's window anchors on
  the actual `fecha_notificacion` (a deposit that already happened), the
  window is legally unaffected by courtesy days regardless of whether they
  are ever modelled — this is a correct exclusion, not an unresolved gap.
  No profile schema currently captures declared courtesy days at all; if
  one is ever added, it would change WHEN a notification can be deposited,
  not this window's arithmetic once deposited.
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

1. Reuse the campaign's already-primary-sourced BOE consolidated PDF for
   Ley 39/2015 (`https://www.boe.es/buscar/pdf/2015/BOE-A-2015-10565-consolidado.pdf`,
   art. 43 at page 35) rather than re-deriving it; take the LAST version if
   the payload bundles historical redactions, never pass the text through a
   shell (a truncating heredoc silently loses text), and read the committed
   file back before trusting it. The consolidated PDF does NOT annotate
   which articles were amended (confirmed by positive control against art.
   28, amended by Ley Orgánica 3/2018 with no marker present) — the absence
   of a marker on art. 43 establishes only that this is TODAY's operative
   text, and no claim that art. 43 is unamended since 2015 may be made or
   implied anywhere downstream of this Step. Commit the HTML plus its
   `.extracted.json`/`.extracted.md` sidecars under
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

`core/external_constants.py` was independently confirmed as the correct
constant home (not `DeadlineWindowDefinition`, and not a re-export
requiring a registry-TOML-backed value elsewhere): every existing sibling
constant in that file is defined in place as a Python literal with a
citing doc comment, and the file's own centralisation-test docstring names
it the "canonical registry" for exactly this value class. No generic,
non-modelo-scoped registry TOML surface for arbitrary statutory figures
exists as an alternative.

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

## Amendment (2026-08-08): the review gate blocks catalogue resolution, not every later Phase

The executing plan's Phase P01 was formulated as "a hard blocking dependency
for every later Phase". Read against what each later row's gate actually
asserts, that is broader than this decision needs. Two rows resolve the
legal-catalogue entry **id** and genuinely cannot exist before the operator
commits it: the grounding test that asserts the constant's citation resolves
against the reviewed entry, and the operator-facing `Notice` that carries the
entry id in its context. The remaining rows - the constant itself, the
`NotificacionEstadoServicio` enum and its pure function, the typed calendar
field, and the widened actionability predicate - have gates that never touch
the catalogue. They depend on the **corpus** committed in P01.S01, which is a
separate artefact with a separate gate.

This amendment therefore rules that the corpus half of P01 is the hard
precondition for every later Step, while the catalogue-enrollment half blocks
only the entry-id-resolving set. The original row bundling the constant with
its catalogue-resolution grounding test is split: the constant lands on the
corpus, and the grounding test stays behind the review.

**The split's own constraint, which is load-bearing.** The constant's doc
comment MUST cite the provision - Ley 39/2015 art. 43.2 and document id
`BOE-A-2015-10565` - and MUST NOT name a legal-catalogue entry id. Citing an
entry id before the catalogue file exists would ship a dangling reference
into production source, which is the same hazard that keeps the `Notice` row
blocked. Citing the provision alone is also exactly the shape every sibling
leaf constant in `core/external_constants.py` already carries, so the
constant lands at parity with its neighbours rather than at a novel bar. If
the constant could not be written without naming the entry id, the split
would not separate the two halves and this amendment would be wrong.

**What the original formulation still asks for that this amendment
excludes.** The retired "blocks every later Phase" rule guaranteed that no
line of this feature's code existed until a human had personally adjudicated
its legal basis, as a single ordering rule requiring no per-row judgement.
This amendment accepts, in exchange for unblocking four rows, that a
`Final[int] = 10` ships in `core/` before any human signs the provision
behind it, and that the reviewer arrives to a constant already consumed by an
enum, a calendar field and an actionability predicate - so a review finding
the figure wrong now implies unwinding four rows rather than writing none.
The figure was cross-checked against live BOE independently of the bundled
corpus before the split was taken, which narrows that exposure without
removing it. The human review remains required and remains unperformed; only
its blast radius changed.

**Implementing rows opened in the same change as this amendment**, per the
standing rule that an amendment ruling on code is not self-executing: the
constant row rewritten to the provision-citation-only contract, a new row
carrying the catalogue-resolution grounding test behind the gate, and a new
row scaffolding the human gate's own Step Record so a checked gate and an
unrecorded one do not wear the same checkbox.
