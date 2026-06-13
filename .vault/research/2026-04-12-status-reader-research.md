---
tags:
  - "#research"
  - "#status-reader"
id: 2026-04-12-status-reader-research
title: AEAT status reader research (#43)
date: 2026-04-12
modified: '2026-04-12'
status: draft
type: research
---

# AEAT live status reader research (#43)

## Purpose

Document the URL structure, DOM shapes, and pydantic-v2 wire schemas
required by the read-only AEAT status reader. The reader is the
*fetch* half of the tax loop: it authenticates against
**Sede Electrónica**, navigates to the user's status pages, and
returns typed records for the rest of the project.

## In-scope surfaces

All surfaces below live beneath the AEAT *Sede Electrónica* base
URL `https://sede.agenciatributaria.gob.es`. Final URLs require an
authenticated session (certificate preload handled by #8), therefore
they are verified from published AEAT documentation and the portal
link manifest that #16 / #11 have already established, not by live
fetch inside this research pass.

| Surface             | Spanish label                       | Known entry URL (portal page)                                                                                      |
| ------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| EXPEDIENTE          | Mis expedientes                     | `/wlpl/TC-UTIL/Expediente?COPT=Y`                                                                                  |
| NOTIFICACION        | Mis notificaciones                  | `/wlpl/TC-UTIL/Notificaciones?COPT=Y`                                                                              |
| DEVOLUCION          | Mis devoluciones                    | `/wlpl/BUGC-JDIT/ConsultaEstadoDevol`                                                                              |
| BORRADOR_IRPF       | Estado de borrador IRPF             | `/wlpl/RENT-WEB/login` + campaign-scoped landing                                                                   |
| DATOS_FISCALES      | Datos fiscales                      | `/wlpl/RENT-R8R1/datosFiscales`                                                                                    |
| CALENDARIO          | Calendario fiscal personalizado     | `/wlpl/CALW-UPCF/CalendarioFiscalPersonalizado`                                                                    |

The exact URLs drift across AEAT campaigns; the reader therefore
accepts them as configuration/fixture rather than hard-coding. A
future follow-up can fold them into the #11 portal manifest.

## DOM shapes

AEAT status pages are server-rendered HTML tables with deeply nested
`<div>`, `<table>`, and `<span class="…">` chains. Two stable
invariants:

1. Every tabular surface exposes a single `<table>` element carrying
   the rows of interest, with `<th>` headers whose text is the
   authoritative Spanish label.
2. Each row's first cell carries a canonical identifier
   (`expediente_id`, `notificacion_id`, etc.), either as visible text
   or as the target of an anchor link (`<a href="…justificante…">`).

The parsers therefore select by header-text match rather than
brittle CSS paths. This survives minor layout tweaks between
campaigns.

## Pydantic v2 wire schemas

All status records are strict, frozen pydantic v2 models:

- `Expediente`, `Notificacion`, `Devolucion`, `BorradorIrpf`,
  `DatosFiscales`, `CalendarioEntry`, `Payor`.
- Closed-set enumerations (`AeatStatusKind`, `PayorKind`) are
  `enum.StrEnum`.
- Fetch metadata (`fetched_at`, `source_page_url`) is carried on
  every record so consumers can audit provenance.

Schema field lists are authoritative in `src/aeat/status/_models.py`
and mirrored in the ADR.

## Parser choice

Candidates:

1. **BeautifulSoup4** — pure-Python, lenient, well-known; can select
   by header text trivially. No compiled dependency.
2. **selectolax / lxml** — faster, stricter, requires a C build.
3. **Playwright DOM extraction** — route through `page.locator`. Ties
   parsing to a live browser, hurts test fixtures.

The reader caches raw HTML and parses it offline, so speed is not a
concern. BeautifulSoup4 wins on lenient parsing and fixture
simplicity. Decision recorded in the ADR.

## Cache policy

Short-lived file cache keyed by
`(tax_id, surface, query_params_hash)` under
`AEAT_STATUS_CACHE_DIR`. TTL defaults to 900 s (15 min) and is
configurable via `AEAT_STATUS_CACHE_TTL_S`. On hit, the cached
pydantic model JSON is loaded and revalidated before return — the
cache never trusts its own payload.

## Fixture collection

Fixtures under `tests/fixtures/aeat-pages/<surface>/` are
hand-curated snapshots of the minimum HTML required to exercise each
parser. The trimming rule: retain the outermost container, the
single `<table>` containing the rows of interest, and any inline
`<a>` anchors the parser needs to resolve (justificante, CSV). No
AEAT session cookies or PII leak into fixtures — they are scrubbed
to the user `X1234567L` / `A12345678` test identifiers.

## Coordination with in-flight branches

- **#8 (cert auth)** — cert backend accessed through a Protocol stub
  matching the planned `LoadedCertificate` + `preload_into_browser_context`
  surface. No hard import from `aeat.adapters.outbound.aeat.auth`.
- **#42 (submission engine)** — no overlap. Both compose
  `aeat.adapters.outbound.aeat.browser.BrowserSession` and both add fields to
  `src/aeat/config.py`; we therefore keep additions grouped under a
  single, clearly named block at the bottom.
- **#11 (sync)** — the sync runner's `WireFilingEntry` etc. are
  stub-shaped predecessors of our real records; replacing them is a
  follow-up outside this issue.
- **#41 (live bot-detection probe)** — known `playwright_stealth`
  failure in the live test path. We do not attempt a fix; live tests
  are opt-in and skip by default.

## Out of scope

- Mutating anything on AEAT (reader is strictly read-only).
- Persisting records to the storage layer (#10 follow-up).
- Notification triage / inbox UI (#46).
- Narrowing free-form `status` strings into enums (follow-up once a
  full dataset is observed).
