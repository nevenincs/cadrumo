---
tags:
  - '#reference'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:772758275faa8c0e5488408fd40bcd68380e58b6ce69f2f9dd7008b47d558ed6'
related: []
---

# `dehu-notification-legal-effect` reference: `DEHu notification legal-effect grounding`

Grounds the gap between the DEHu buzón reader (complete, read-only) and the
absence of any legal-effect computation over a pulled notification. Read from
current `main` on 2026-08-07.

## The read-only DEHu surface

The buzón reader is `adapters/outbound/aeat/sede/_notifications.py`
(`RemoteNotification` row model), wrapped by
`application/live/_notifications.py` (`PersistedNotificationsSnapshot`,
`NotificationsService`), exposed via `aeat app live notifications
pull|list|view|latest`. No acuse is ever sent to AEAT — `leida` is a local
read-marker only, never round-tripped to the sede. This surface is
authoritative for row content and must not change shape.

`RemoteNotification` (`adapters/outbound/aeat/sede/_notifications.py:110`)
carries `tipo` (`notificacion` | `comunicacion` | `pendiente` | `unknown`),
`fecha_emision: date`, `fecha_notificacion: date | None`, and `leida: bool |
None`. Its own docstring resolves the field-semantics question the dispatch
brief flagged as open: `fecha_notificacion` is documented as "`Fecha de
notificación` when the row has been delivered, else `None`" — i.e. the date
AEAT made the item available in the DEHu mailbox (puesta a disposición), NOT
the date the taxpayer accessed it. Access/reading is the separate `leida`
boolean. This reading is consistent with DEHu/LGT electronic-notification
practice, where "notificación" denotes the delivery-to-mailbox act and
"acceso"/"leída" denotes the taxpayer's subsequent action. `fecha_notificacion
= None` therefore means "not yet delivered" (e.g. a `pendiente` row), and the
service-effect clock — whichever mechanism computes it — has not started.

## No legal-effect computation exists anywhere in the tree

- `calendar_events_from_notification_snapshots`
  (`application/overview/_calendar.py:398-449`) sets `event_date =
  row.fecha_notificacion or row.fecha_emision` and a free-string `status`
  (`"read"` / `"unread"` / the raw `tipo`). No date arithmetic, no window, no
  deemed-service state.
- `application/workflow/_engine.py:661-727` (`_stage_checking_inbox`) blocks
  submission when ANY row has `tipo == "notificacion"` and `leida is not
  True` — a blunt "any unread formal notificación blocks filing" guard,
  independent of how long the row has been sitting unread. It raises
  `WorkflowAbortSignalError(reason=WorkflowAbortReason.INBOX_BLOCKING_REQUERIMIENTO)`.
  This guard is unconditional on age; it is not a substitute for a
  legal-effect date and should stay as-is (it is stricter than the law
  requires, which is the safe direction).
- `core/_post_filing_event.py` (`PostFilingEventKind`, read in full) is a
  closed `StrEnum` of AEAT *procedural categories* — requerimiento,
  liquidación, sanción, embargo, etc. — classified from `concepto`/`tipo` text
  by `classify_post_filing_event_kind`. `ACTIONABLE_POST_FILING_EVENT_KINDS`
  (lines 98-108) is a `frozenset` excluding the plain `NOTIFICACION` fallback
  member (fired when no sharper concepto pattern matches). Consequence: an
  ordinary formal notificación classified only as `NOTIFICACION` never
  reaches `actionable_post_filing_events`
  (`application/overview/_calendar.py:565`) or the overview's post-filing
  `Notice` (`entrypoints/cli/_overview_rendering.py:108`), regardless of how
  long it sits unread. This is the concrete hole the dispatch brief names:
  service state and procedural kind are conflated in one enum, and the
  fallback kind is excluded from actionability by construction.

## Regulatory grounding — verified against primary BOE text, 2026-08-07

**Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común de las
Administraciones Públicas, art. 43.2** (régimen de las notificaciones a través
de medios electrónicos): "... se entenderá rechazada cuando hayan transcurrido
diez días naturales desde la puesta a disposición de la notificación sin que
se acceda a su contenido." Read directly from BOE's live consolidated-text PDF
on 2026-08-07 (not from the bundled corpus — see below).

- The window is **ten días naturales** (calendar days — weekends and
  holidays count), not días hábiles. It runs from **puesta a disposición**
  (delivery to the mailbox), matching `fecha_notificacion` above, not from
  any later access date.
- Lapse produces "rechazo tácito" — the notification is deemed legally
  served (its content is treated as accepted/known) even though the taxpayer
  never opened it. This is a service-effect state, not a new procedural
  category: a `REQUERIMIENTO` and a plain `NOTIFICACION` can each lapse into
  deemed-service the same way.

**Not the governing article, checked and ruled out:**

- **RD 1363/2010** (obligatoriedad de notificación electrónica para
  determinados sujetos, including most AEAT-obliged taxpayers) does not fix
  its own response window — its Disposición adicional primera remits to the
  general administrative-procedure regime, i.e. to art. 43.2 above (formerly
  art. 28.3 Ley 11/2007, now Ley 39/2015).
- **RD 1363/2010, Disposición adicional tercera** — "días de cortesía": a
  taxpayer may declare up to 30 non-consecutive calendar days per year during
  which AEAT may not *deposit* a new notification in the DEHu mailbox. This
  bars new deposits during the declared days; it does NOT pause a clock
  already running on a previously-delivered notification. It is a distinct
  profile-level fact (which days are blocked), not a term in the window
  computation.
- **LGT (Ley 58/2003) art. 112** (notificación por comparecencia) governs
  publication-based service after a FAILED physical-delivery attempt (two
  failed tries at the domicile). It is a different failure mode from DEHu
  deemed-service-by-non-access and does not apply here.

## Corpus and legal-catalogue state

`src/cadrumo/_data/corpus/normatives/html/` carries **zero** Ley 39/2015
files today — the provision is not bundled and not in the legal catalogue
(`src/cadrumo/_data/registry/aeat/legal/*.toml`). Per
`aeat-calculation-grounding`, the bundled corpus must be checked first when
present, but here nothing is bundled, so BOE's live consolidated text was the
only available source; it must still be fetched, anchored and committed as a
proper corpus file (never hand-authored from memory) before any
`legal_refs` can cite it — see the `no-silent-under-declaration` /
`aeat-calculation-grounding` "verify against the bundled corpus" and
"fetched-file can be unfit" cautions (take the LAST version in a
consolidated-legislation payload, confirm no truncation).

The legal catalogue already carries **topic-scoped, non-modelo-specific**
TOML files alongside per-modelo ones — e.g. `lgt-autoliquidacion.toml`,
`censo.toml`, `iva-flow.toml` — establishing precedent for a new
`ley-39-2015-notificaciones.toml` (or similarly named) general-procedure
topic file, rather than forcing this LGT/administrative-procedure grounding
into a modelo-scoped file.

## Value-storage precedent: `core/external_constants.py`

`core/external_constants.py` is the established home for named, single-value
regulatory constants that are NOT modelo/filing-year scoped — e.g.
`M347_THRESHOLD_EUR`, `MINIMO_DESCENDIENTE_MAX_AGE`,
`ART_81_1_ENTRY_WINDOW_YEARS`. Each constant carries a doc comment citing its
binding provision verbatim. `DeadlineWindowDefinition`
(`domain/calculations/registry/_schema.py:726`) was considered and rejected
as the home for the ten-day figure: it is filing-year/period/modelo scoped
(declares `filing_year`, `period`, `opens_on`/`closes_on` for a specific
obligation's filing window), while the DEHu response window is a generic,
year-stable, modelo-independent rule that applies to any notification
regardless of which obligation it relates to. `external_constants.py`'s
existing pattern of a `Final[int]` with a grounding docstring
(`MINIMO_DESCENDIENTE_MAX_AGE`, `ART_81_1_ENTRY_WINDOW_YEARS`) is the closer
fit.

## Notice channel and typed-axis precedent

- `core/json_contract.py` (`Notice`, `NoticeSeverity`, read in full) is the
  sole diagnostic channel; `entrypoints/cli/_overview_rendering.py:108`
  already projects `actionable_post_filing_events` onto one `warning`
  `Notice` with a per-event reference→kind map on `Notice.context`. A
  service-state signal (deemed-served) should ride the same pattern, not a
  bespoke result field.
- `core/_post_filing_event.py` is the worked example of "closed value sets
  live in `core/` as a `StrEnum`, hydrated at boundaries" — the pattern a new
  service-state axis should follow, declared as its own enum rather than
  added as members of `PostFilingEventKind` (kind and service-state are
  orthogonal: a `REQUERIMIENTO` can be accessed, unread-within-window, or
  deemed-served, independent of its procedural category).

## Naming — Spanish-stem rule vs. the existing English-named family

The existing family (`NotificationsService`, `RemoteNotification`,
`PersistedNotificationsSnapshot`, CLI group `notifications`) is English-named
and predates `aeat-naming`'s Spanish-stem mandate; per that rule's
"already-public pre-rule identifiers keep their names" carve-out, none of it
is renamed here. Any NEW symbol this reference's downstream ADR proposes
(a service-state enum, a window-computation module, a legal-catalogue key)
should take the Spanish stem (`notificacion`, not `notification`) per the
current rule, deliberately diverging from the sibling family's English
naming rather than matching it.
