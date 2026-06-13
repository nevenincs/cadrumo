---
tags:
  - "#research"
  - "#notifications-inbox"
date: 2026-04-12
modified: '2026-04-12'
title: AEAT notifications inbox — research
related:
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-filing-draft-engine-adr]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
issue: wgergely/aeat#46
---

# research: aeat notifications inbox

## goal

Ground the design of `src/aeat/inbox/` for wgergely/aeat#46. The inbox
is the local, typed, read-only view of every formal communication AEAT
issues to a Spanish *autónomo* — *requerimientos*, *propuestas de
liquidación*, *acuerdos de liquidación*, *notificaciones de embargo*,
*acuses de recibo*, plus any other binding document the Sede
Electrónica surfaces. Missing one of these can mean a missed appeal
window, penalty escalation, or direct account seizure. The system
must catch every one and surface it loudly.

## aeat notification surface

### where they live

AEAT publishes formal notifications under three overlapping surfaces:

- **Mis notificaciones** (Sede Electrónica): the canonical list of
  every *notificación electrónica* the taxpayer has received. Each
  entry has a `numero de notificación` (AEAT-issued, stable),
  `fecha de puesta a disposición`, `fecha de notificación`, a subject
  prefix, and a link to the full PDF.
- **Dirección Electrónica Habilitada Única (DEHú)**: the central
  Spanish state electronic mailbox. AEAT mirrors its *notificaciones
  obligatorias* through DEHú; the DEHú entry carries its own UUID but
  points back to the AEAT record.
- **Mis expedientes**: for every expediente with an active
  *requerimiento*, the requerimiento document is attached to the
  expediente as well as surfaced in `Mis notificaciones`.

v1 of the inbox **only consumes the Sede Electrónica surface**, via
the `fetch_notificaciones` method that lives in `aeat.status` (#43).
DEHú is a downstream integration that will produce the same
`Notificacion` record shape.

### legal concept: *fecha de notificación*

Spanish administrative law (*Ley 39/2015, Procedimiento Administrativo
Común*, art. 43) defines two distinct timestamps:

1. **Fecha de puesta a disposición** — the moment AEAT publishes the
   notification to the taxpayer's electronic mailbox.
2. **Fecha de notificación** — the moment the notification is
   *legally deemed delivered*. This is one of:
   - the moment the taxpayer accesses the document, OR
   - **10 calendar days** after `puesta a disposición` if the taxpayer
     does not access it, whichever is earlier.

All appeal and response windows are counted from **fecha de
notificación**, not from `puesta a disposición`. This 10-day grace
window is known colloquially as the *regla de los diez días*.

**Design implication:** the `Notificacion` record carries
`received_at` (the moment the inbox first saw the entry, i.e. our
proxy for `puesta a disposición`) and `effective_at` (the legal
`fecha de notificación`). Appeal-window arithmetic uses `effective_at`
exclusively.

## notification kinds and appeal windows

The six kinds the classifier must cover (plus `OTRO` as a catch-all):

| Kind (`NotificacionKind`) | Spanish label prefix on the Sede | Appeal window from `effective_at` | Default priority |
|---|---|---|---|
| `REQUERIMIENTO` | `Requerimiento`, `Requerimiento de información`, `Requerimiento de subsanación` | **10 business days** to respond (general rule, LGT art. 99) | `CRITICAL` |
| `PROPUESTA_LIQUIDACION` | `Propuesta de liquidación`, `Propuesta de regularización` | **15 calendar days** to submit *alegaciones* (LGT art. 34.1.l) | `CRITICAL` |
| `ACUERDO_LIQUIDACION` | `Acuerdo de liquidación`, `Liquidación provisional`, `Liquidación definitiva` | **1 month** (recurso de reposición, LGT art. 223) or **1 month** (reclamación económico-administrativa, LGT art. 235) — legally identical deadlines | `CRITICAL` |
| `NOTIFICACION_EMBARGO` | `Diligencia de embargo`, `Notificación de embargo` | No appeal window as such — but **oposición al embargo** must be filed within **1 month** (LGT art. 170.3) | `CRITICAL` |
| `ACUSE_RECIBO` | `Acuse de recibo`, `Justificante de recepción` | No appeal — informational receipt | `INFO` |
| `COMUNICACION_GENERAL` | `Comunicación`, `Información general` | No appeal — informational | `NORMAL` |
| `OTRO` (catch-all) | any unrecognised subject prefix | Unknown — **assume CRITICAL-adjacent** | `HIGH` |

The `HIGH` fallback for `OTRO` is deliberate: the worst failure the
project can ship is silently downgrading a legally binding document.
Any unrecognised AEAT prefix gets surfaced at elevated priority so the
user sees it in the default `aeat inbox list --unread` view.

## requerimiento vs propuesta de liquidación

The two most frequently confused kinds:

- **Requerimiento**: AEAT is *asking for something* — information,
  a missing document, a correction to a filing. The taxpayer *must*
  respond, typically within 10 business days. Failure to respond is a
  tipified infraction (LGT art. 203) and can trigger a sanction even
  if the underlying substance is fine.
- **Propuesta de liquidación**: AEAT is *proposing an amount* — a
  draft of the tax they believe the taxpayer owes. The taxpayer has
  15 calendar days to file *alegaciones* (a legal rebuttal). If the
  taxpayer does nothing, the propuesta becomes an `ACUERDO_LIQUIDACION`
  and the amount is enforceable.

Both are `CRITICAL`. Both are time-bound. The classifier rules
disambiguate on subject prefix. The inbox does **not** draft an
appeal or a response — that is a separate future issue (out of scope
per wgergely/aeat#46).

## read-only against aeat; acknowledgement is local state

A key design constraint: `aeat inbox ack` **does not notify AEAT**.
AEAT's legal-delivery clock runs on `fecha de notificación` regardless
of what the taxpayer does in the local inbox. Acknowledgement is a
purely local bookkeeping act — the user marks "I have read this and
taken action" and the inbox record records `acknowledged_at` +
`acknowledged_by`. This matches the semantics AEAT itself uses: there
is no "mark as read" API on the Sede.

This is documented on every ack-adjacent surface (CLI, docstrings,
ADR) so the user never mistakes a local ack for a legal response.

## classifier strategy

v1 uses a **pure-function rule table** over the normalised Spanish
subject prefix. Rationale:

- Rules are auditable, deterministic, and testable against fixture
  payloads. Every rule has a `@pytest.mark.unit` test that asserts
  the mapping.
- An LLM classifier would be non-deterministic and would introduce a
  false-negative risk on exactly the high-stakes documents the inbox
  exists to catch.
- The Spanish subject prefix surface is narrow and stable: AEAT does
  not rename *Requerimiento* to something else between quarters.
- If a rule miss happens, the `OTRO` fallback already raises the
  priority to `HIGH`, so the worst case is a false-HIGH on an
  informational comunicación — never a silent miss on a
  requerimiento.

The rule table is declared in `_classifier.py` as an ordered tuple
of `(pattern_prefix, NotificacionKind, NotificacionPriority)` triples.
Ordering matters because some prefixes are more specific than others
(e.g. `Requerimiento de información` is more specific than
`Requerimiento`, but the general `Requerimiento` match is fine
because both map to the same kind/priority).

## protocol stubs: #43, #8, #45

Three sibling branches are in flight and cannot be hard-imported:

- **#43 (`aeat.status`)**: the status reader. Owns
  `async fetch_notificaciones(*, since: date | None = None) ->
  tuple[Notificacion, ...]`. We stub a `NotificacionSource` Protocol
  matching that surface. Rebase swap on merge is a one-line import
  change.
- **#8 (`aeat.adapters.outbound.aeat.auth.certificate`)**: the cert backend. We do **not**
  consume it directly — the source reader (#43) is responsible for
  preloading the cert into the browser context. We do not stub it.
- **#45 (`aeat.domain.normatives`)**: future normatives catalogue. Appeal
  deadlines reference LGT article numbers — we store them as bare
  strings (`"LGT art. 99"`), never as hard imports.

## settings

- `AEAT_INBOX_DIR` (Path, default `<repo>/var/inbox`) — where the
  persisted inbox file lives. v1 writes a single JSON index.
- `AEAT_INBOX_PDF_DIR` (Path, default `<repo>/var/inbox/pdfs`) — where
  attached notification PDFs are downloaded.
- `AEAT_INBOX_ALERT_LEAD_DAYS` (int, default 7) — `next-deadline`
  surfaces CRITICAL notifications whose `appeal_deadline` is within
  N days.

## tests

- **Unit** (`@pytest.mark.unit`, colocated under `src/aeat/inbox/`):
  - Every classifier rule against fixture payloads.
  - `UNCLASSIFIED → (OTRO, HIGH)` rigorously tested — exhaustive
    "this prefix matches nothing" cases.
  - Appeal-deadline arithmetic per kind (`effective_at + window`).
  - Pydantic round-trip on `Notificacion` and `Inbox`.
  - Acknowledge round-trip.
  - `next_appeal_deadline` picks the earliest `CRITICAL` record with a
    non-None deadline within the alert lead window.
- **Live** (`@pytest.mark.live`, opt-in via `AEAT_LIVE_TESTS_ENABLED=1`):
  one fetch + acknowledge round-trip against the real AEAT portal,
  wired through the #43 status reader. Flags the #41 bot-detection
  bug if it trips.

Unit-test doubles for the `NotificacionSource` Protocol are
**concrete classes** — real Python classes that structurally satisfy
the Protocol. No `unittest.mock`, no patches, no stubs, no fakes.

## out of scope (confirmed from the issue and this research)

- Drafting an appeal in response — separate future issue.
- Web UI.
- Email / SMS notification routing — structured log + CLI only.
- Persisting to the storage layer (#10) — files only for v1.
- Hard imports from `aeat.status` (#43), `aeat.adapters.outbound.aeat.auth.certificate`
  (#8), `aeat.domain.normatives` (#45).
- DEHú integration (future).

## open questions

- **Timezone of `effective_at`**: AEAT renders Madrid-local timestamps
  (Europe/Madrid). v1 stores UTC-normalised `datetime` and documents
  that the legal clock is Europe/Madrid. The classifier does not
  read wall-clock time — the 10-day grace rule is implemented only
  when the source reader (#43) gives us a `puesta a disposición`
  timestamp; until then, the inbox trusts the `effective_at` it is
  handed.
- **Business-day math for `REQUERIMIENTO`**: 10 *business days* is
  Spain-specific (excludes weekends + *festivos nacionales*). v1 uses
  calendar-day arithmetic **with a note** — the exact business-day
  calendar is a #45 normatives concern.
