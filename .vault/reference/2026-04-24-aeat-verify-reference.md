---
tags:
  - '#reference'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-verify-adr]]"
  - "[[2026-04-24-aeat-verify-research]]"
---



# `aeat-verify` reference: `post-auth-sede-ground-truth`

Canonical record of what AEAT's post-authentication sede electrónica
actually looks like, captured live on 2026-04-24 against Kent's
production account using Cl@ve-móvil authentication. **This document
supersedes the shape assumptions baked into the earlier speculative
ADR.** Every URL, selector, field, and enum member listed here has at
least one live observation backing it.

## Why this document exists

The pre-discovery ADR and plan proposed an `aeat.remote` subpackage
with invented records — `RemoteFiling`, closed `RemoteFilingStatus`
StrEnum, per-modelo `FilingDetail{130,303,390}`, Protocol-stubbed
fetchers. None of those shapes survived the first live run because:

1. AEAT organises expedientes by **procedure category**, not modelo
   code. The tree's top-level nodes are "Impuestos", "Certificados",
   "Sanciones", etc.
2. The filing's canonical record is a **signed justificante PDF** that
   AEAT returns through a CSV-keyed verifier endpoint — not a typed
   row in a "filings" collection.
3. Per-year IRPF filings live at separate endpoint paths
   (`/wlpl/DASR-CORE/AccesoDR<YYYY>RVlt`), not a single per-modelo
   endpoint.
4. Filing status is a **free-text Spanish prose sentence**, not an
   enumerable set.

The speculative `aeat.remote` subpackage was deleted in commit
`474cceb`. This document replaces it as the source of truth for the
actual shape of Kent's sede.

## Authentication: Cl@ve-móvil flow

The flow captured 2026-04-24 against `sede.agenciatributaria.gob.es`:

1. CLI issues `aeat auth login --provider clave_movil`; the provider
   opens a headed Playwright browser and navigates to AEAT's
   `SelectorAccesos.html` with the target encoded in `ref=`.
2. The authenticator clicks `button[name="autoriza-P"]` (Cl@ve móvil
   button) which lands on `/wlpl/MOVI-P24H/ObtenerClaveMovil?qAA=2`.
3. In the non-QR flow, the authenticator fills `#NIF` with the NIE and
   `#SOPORTE` with the número de soporte, then clicks `#botonContinuar`.
4. AEAT issues a push notification to Kent's phone and renders a
   waiting-page. Kent approves the push in the Cl@ve app within
   ~5 minutes.
5. After approval, the browser redirects to AEAT's representation
   dispatcher at
   `/wlpl/OVCT-CXEW/DialogoRepresentacion?ref=<encoded-target>`. This
   page has a `<form id="repForm">` with a pre-selected
   `#propio` radio ("Actuar en nombre propio"). **Kent's real account
   requires the form to be submitted explicitly** — the speculative
   portal-reference doc assumed auto-forward, captured from a test
   account with no apoderamientos. Our authenticator now clicks
   `form#repForm button[type=submit]` when it sees DialogoRepresentacion
   on the current URL path.
6. After the representation submit, the browser lands at
   `/wlpl/TEWV-CORE/ResumenVlt` — *Mis expedientes*. Session cookies
   are persisted via Playwright `storage_state()`.

**Pending-request failure mode (captured)**: if a prior authentication
attempt left an un-acknowledged push alive server-side, AEAT returns
`ObtenerClaveMovil?qAA=2` in an error state with the message "No ha
sido posible generar una nueva petición de autenticación con Cl@ve
Móvil. Por su seguridad, acceda a la APP Cl@ve de su dispositivo
móvil y rechace la petición pendiente o espere a que caduque tras un
máximo de 5 minutos." The authenticator now raises
`ClaveMovilApprovalTimeoutError` with the same remediation text rather
than sitting on the page until the outer timeout fires.

**Idle TTL**: AEAT's 18-minute session timeout is **idle-based**.
Calling `aeat auth whoami` (or `probe_persisted_session()`
programmatically) hits a post-auth URL and resets the deadline — the
sidecar idle_deadline is updated on every successful probe.

## The *Mis expedientes* tree

Captured URL: `https://www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt`.

The page title is the `<h1>` "Mis Expedientes" — parsers should
fail-fast when this heading is missing (signals session expiry or
page drift).

The body is an **AJAX-expanded tree** of procedure categories. Kent's
snapshot contained 47 expedientes across roughly these branches (with
counts captured as rendered):

- Agencia Estatal de Administración Tributaria (47)
  - Impuestos, tasas y prestaciones patrimoniales (5)
    - Impuesto sobre la Renta de las Personas Físicas (3)
      - Modelo 100- Modelo 102. IRPF. Declaración y documento de
        ingreso o devolución. (3)
    - IVA (1)
      - IVA. Regularización por falta de presentación. (1)
    - Declaraciones Informativas (1)
      - Control de la presentación de Declaraciones Informativas. (1)
  - Certificados (11) with Censales / Situación Tributaria /
    Contratistas y subcontratistas sub-trees
  - Comprobaciones fiscales y procedimiento sancionador (18)
  - Recursos, reclamaciones (3)
  - Otros procedimientos tributarios (10)

**Category-to-modelo mapping**: the modelo code is embedded in the
deepest category label — e.g. "Modelo 100- Modelo 102. IRPF." yields
modelo `"100"` for every expediente under it. The parser in
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/_parse.py` pulls modelo via a `\bModelo\s+(\d{2,4})\b`
regex against the reversed category path.

**Tree expansion**: each category anchor fires
`javascript:mostrarListado(<ids>)`. Anchors are CSS-hidden by default
(parent collapsed) — the walker invokes them via
`page.evaluate('... a.click() ...')` which bypasses Playwright's
visibility check because the onclick handler only needs the DOM click
event, not focus or pixel visibility.

**Leaf anchors** carry:

- `onclick="javascript:lanzarTewvForm(this,12);return false;"` — the
  marker handler that distinguishes expediente leaves from grouping
  anchors (`mostrarListado` / `desplegar`).
- `href=<per-year-endpoint>` — e.g.
  `/wlpl/DASR-CORE/AccesoDR2023RVlt?exp=<expediente-id>` for IRPF.
- Text content is the expediente id itself (no whitespace), e.g.
  `202310013522456T`.

**Expediente id shape**: `<4-digit-year><sequence><checksum-letter>`,
16 characters for IRPF. The year prefix lets us infer `ejercicio`
without HTTP round-trip.

## Per-filing-family endpoints

Different filing families live at different endpoint paths. Captured
so far:

- IRPF Modelo 100: `/wlpl/DASR-CORE/AccesoDR<YYYY>RVlt?exp=<id>` —
  one endpoint per tax year (AccesoDR2021RVlt, AccesoDR2022RVlt,
  AccesoDR2023RVlt, ...).

Other filing families (certificados, sanciones, recursos) use
different dispatchers and are out of scope for the reconciliation MVP.

## The expediente detail page

Captured for IRPF 2023 at
`https://www6.agenciatributaria.gob.es/wlpl/DASR-CORE/AccesoDR2023RVlt?exp=<id>`.

Contents:

- `<h1>Servicios Renta <YYYY> (Detalle)`
- Identity block: NIF, Nombre, `Primer declarante` / `Representante`
- `Expediente <id>`
- `Órgano gestor: Administración de <OFICINA>`
- `Estado de Tramitación` — **free-text Spanish prose**, e.g.
  "Su declaración ha sido tramitada por los órganos de Gestión
  Tributaria, estimándose conforme, sin perjuicio de las
  comprobaciones que pudieran realizarse posteriormente por la
  Administración Tributaria." No closed enum surfaced by AEAT —
  parsing status as an enum with UNKNOWN fallback (as the speculative
  ADR proposed) is wrong; surface it as-is.
- `Servicios Disponibles` block with a mix of read links and a WRITE
  link ("**Modificar declaración**"). The write-guard's verb list
  now bans `modificar` in any public surface name.
- `Historia del Expediente` — timeline with "Grabación de la
  declaración <id> (Consulta / Copia)" linking to the justificante
  verifier.

## The justificante verifier

Two endpoints per CSV:

- `/wlpl/KATA-APLI/cotejo/CotejoIdSv?CSV=<csv>` — HTML viewer stub
  with an embedded `<iframe>`. Not directly useful for parsing.
- `/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=<csv>` — raw PDF bytes.
  **Must be fetched via `APIRequestContext` (`context.request.get`),
  not `page.goto`**, because Chrome wraps PDF responses in its
  PDF-viewer stub HTML when navigated.

The CSV code appears in three places on the detail page — as the
`ref` token of a `CotejoIdSv` link, in plaintext at the bottom
"authenticity footer", and in the `pdf.metadata['Title']` field of the
downloaded PDF (for 2022+ layouts; 2021-era PDFs have no title
metadata).

## Justificante PDF shapes

Captured from live IRPF receipts (2021, 2022, 2023). All PDFs are
AEAT-issued with `Creator: AEAT`, `Producer: AEAT OVCT-IPDF/OVCT-XPDF`,
and `Keywords: 'AEAT, Justificante, Declaracion, Predeclaracion,
Vista Previa'`.

**2022+ layout** (IRPF 2022, 2023 captured):

- Labels on left, values on right; pdfplumber reads top-down,
  left-right, giving natural label-then-value order.
- Key fields and their regex anchors:
  - `Modelo <NNN> Ejercicio <YYYY>` — modelo + tax year on one line
  - `Presentación realizada el: DD-MM-YYYY a las HH:MM:SS`
  - `Expediente/Referencia (nº registro asignado): <id>`
  - `Código Seguro de Verificación: <CSV>`
  - `Número de justificante: <13-digit>`
  - `NIF Presentador: <NIF>`
  - `Apellidos y Nombre / Razón social: <name>`
  - `INGRESAR` section with `NRC: <nrc-code> IMPORTE: <amount>`

**2021 layout** (IRPF 2021 captured):

- Column-split layout: pdfplumber reads the VALUE first and the LABEL
  after. Regex needs to accept both orderings.
- No PDF `Title` metadata — falls back entirely to text extraction.
- `DOMICILIACIÓN DEL IMPORTE A INGRESAR` block when payment was by
  direct debit; no explicit IMPORTE line, so `total_a_ingresar` is
  legitimately `None`.

**Authenticity footer** (every layout):
"La autenticidad de este documento puede ser comprobada mediante el
Código Seguro [N] de Verificación <CSV> en
https://sede.agenciatributaria.gob.es". The optional `[N]` is a
page-number interstitial pdfplumber occasionally lifts into the text
stream. This footer is the most reliable CSV fallback.

## Module boundaries

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py` — Cl@ve-móvil authentication,
  including the DialogoRepresentacion handshake and idle-TTL refresh.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/` — read-only sede walker: `Expediente`,
  `JustificanteRef`, `SedeCapture` records; pure-function HTML
  parsers; Playwright walker
  (`walk_expedientes_tree`, `resolve_justificante_ref`,
  `capture_justificante`, `find_expediente`).
- `src/aeat/domain/justificante/` — PDF parser, now handles both layouts.
- `src/aeat/application/filing/reconciliation/` — `FilingDraft` ↔ `Justificante`
  comparator emitting `ReconciliationReport`.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/` — session management (unchanged besides the Clave
  patches above).

## Open questions for follow-ups

- Modelo 303 / 130 / 390 filings — Kent's account has none on capture
  day, so these remain covered only by the synthetic fixture corpus
  under `tests/fixtures/justificantes/`. First real quarterly filing
  by Kent should re-exercise this whole stack.
- Per-modelo total derivation on the draft side: `reconcile()` skips
  total compare when draft totals are `None` (the MVP). A per-modelo
  projection map from casilla values to `(total_a_ingresar,
  total_a_devolver)` is the next logical addition.
- Notifications inbox (`/wlpl/IIIC-ALER/SvObtAlertas`) — separate
  surface from expedientes; future follow-up.
- Non-IRPF filing families (certificados, sanciones) each use a
  distinct dispatcher path — to be captured when Kent's corpus grows.
