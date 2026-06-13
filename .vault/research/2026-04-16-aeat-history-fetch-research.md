---
tags:
  - "#research"
  - "#aeat-history-fetch"
date: 2026-04-16
modified: '2026-04-16'
title: AEAT filing-history read surface research (#168)
related:
  - "[[2026-04-12-status-reader-adr]]"
  - "[[2026-04-12-notifications-inbox-adr]]"
  - "[[2026-04-12-cert-auth-adr]]"
issue: wgergely/aeat#168
epic: wgergely/aeat#166
---

# aeat filing-history read surface research

## purpose

Issue #168 delivers the *second* layer of the AEAT read surface: given
the list of submitted filings (`Expediente` rows produced by the #43
status reader), fetch the per-filing detail page and extract the full
calculations — the casilla→value mapping the taxpayer actually
submitted, plus any headline totals.

This is the foundational read for the double-entry verification
engine in EPIC #166: our locally computed draft must be compared
against what was actually filed. Without this layer we cannot detect
divergence between local state and AEAT's record of truth.

The reader is **strictly read-only**. No form submissions, no POSTs,
no cookie mutation beyond what a plain `page.goto()` performs. This
constraint is non-negotiable per the live-AEAT-write safety charter
(#116).

## context in the existing architecture

Two subpackages already fetch data from authenticated AEAT surfaces:

- `aeat.status` (#43) — returns `tuple[Expediente, ...]` for *Mis
  expedientes*. Each `Expediente` carries:
  `(expediente_id, modelo, period, status, presented_at, csv,
  justificante_url, source_page_url, fetched_at)`.
- `aeat.domain.justificante` (#44) — parses a locally-downloaded PDF
  receipt into `Justificante` with *only the headline totals*
  (`total_a_ingresar`, `total_a_devolver`, csv, tax_id, presented_at).

Neither surface exposes the **casilla-level calculations** we need
for double-entry verification. That is the gap #168 fills.

Relevant architectural reference:

- `aeat.inbox` — the read-only-plus-local-ack pattern. The inbox is
  the closest sibling to what #168 builds: a read-only fetcher that
  composes a Protocol-typed upstream source, persists typed records
  to a single JSON file under a dedicated config dir, and is
  entirely offline-testable via fixture HTML.
- `aeat.status._reader.StatusReader.fetch_expedientes` — already
  composes `BrowserSession` + `CertificateBackend` via Protocols;
  #168 reuses the same authenticated context indirectly (see D1
  below).
- `aeat.domain.casillas.CasillaRecord` — defines the canonical casilla
  catalogue shape (`casilla_id`, `label`, `data_type`, etc.).
  History records refer to casillas by `casilla_id` only — we
  deliberately do not re-embed the catalogue shape.

## data surfaces

All surfaces below live beneath `https://sede.agenciatributaria.gob.es`.

### surface 1 — *Consulta de presentaciones por modelo* (per-modelo filing history)

AEAT exposes a per-modelo history list (e.g. *Consulta de
presentaciones del modelo 303*) reachable from each model's portal
page. Response is a server-rendered HTML table mirroring the
structure of *Mis expedientes* but scoped to one modelo and usually
carrying more metadata per row: NRC (banking reference), period,
presentation date, whether a complementaria was filed, and a link to
a detail/duplicate-copy page.

Known entry URLs (drift across campaigns, accept as settings):

| Modelo | Spanish label                       | Likely path                                          |
| ------ | ----------------------------------- | ---------------------------------------------------- |
| 130    | Consulta de presentaciones — 130    | `/wlpl/BUGC-JDIT/ConsultaPresentaciones?modelo=130`  |
| 303    | Consulta de presentaciones — 303    | `/wlpl/BUGC-JDIT/ConsultaPresentaciones?modelo=303`  |
| 390    | Consulta de presentaciones — 390    | `/wlpl/BUGC-JDIT/ConsultaPresentaciones?modelo=390`  |

Because these paths drift, they are declared as *input parameters* to
the fetcher rather than hard-coded. The v1 deliverable wires a
settings-driven base-URL override and accepts a `modelo` + `year`
argument pair.

### surface 2 — *detalle de expediente / obtener copia* (per-filing detail)

Each row on surface 1 links to a *detalle* page that shows the
submitted values field-by-field. Two possible shapes observed from
AEAT documentation and the portal-manifest work on #11:

1. **HTML detail page** — a server-rendered form echoing every
   casilla with its submitted value. Selectable by casilla id via
   `<td id="casilla_XXX">` or `<label for="casilla_XXX">`
   conventions, depending on the campaign.
2. **PDF duplicate (*copia del impreso*)** — a printable version of
   the submitted form including all casillas stamped with their
   submitted values. Same PDF corpus as the justificante but with a
   "DUPLICADO" watermark.

v1 parses the HTML shape; PDF-duplicate extraction is a declared
follow-up (see non-goals).

### surface 3 — *Mis expedientes* (already covered)

The #43 status reader already extracts this. #168 consumes
`Expediente` rows as *input* (via a Protocol stub, per D5 below);
it does not re-implement the list surface.

## candidate architectures

### rejected — one pass, everything in one fetcher

A single `HistoryFetcher.fetch_all(modelo, year)` that lists + details
in one go. Rejected: couples listing to detail parsing, makes the
fetcher impossible to test with a fixture-only `ExpedienteSource`, and
duplicates the #43 list parser that already exists on main.

### accepted — two-step composition (list provider → detail fetcher)

The fetcher accepts two collaborators:

1. An `ExpedienteSource` Protocol returning `tuple[Expediente, ...]`
   for a given `(modelo, year)`. The real implementation wraps
   `aeat.status.StatusReader.fetch_expedientes()` with a
   `modelo` / `period` filter; the test implementation returns a
   fixture tuple directly — no `BrowserSession` required.
2. A `FilingDetailFetcher` Protocol returning raw HTML for an
   `Expediente` (routed through the #43 browser session). The test
   implementation returns a fixture HTML string keyed by
   `expediente_id` — again, no `BrowserSession`.

A pure-function `parse_filing_detail(raw_html, *, expediente, ...)`
converts HTML → `FiledModelo` without any I/O.

This mirrors the #46 inbox pattern exactly and makes the unit-test
path 100% offline.

## wire schema (proposed)

### FiledModeloMetadata

| Field               | Type                  | Notes                                                     |
| ------------------- | --------------------- | --------------------------------------------------------- |
| `expediente_id`     | `str (1..64)`         | Mirrors `Expediente.expediente_id`.                       |
| `modelo`            | `str (1..16)`         | AEAT modelo id (`"130"`, `"303"`, `"390"`).              |
| `period`            | `str (1..16)`         | Filing period (`"2025-1T"`, `"2025"`).                   |
| `status`            | `str (1..128)`        | AEAT-rendered status string (verbatim).                   |
| `presented_at`      | `AwareDatetime`       | UTC. Mirrors `Expediente.presented_at`.                  |
| `tax_id`            | `str (4..32)`         | NIF/NIE of the taxpayer.                                  |
| `csv`               | `str | None`          | Código Seguro de Verificación if printed.                 |
| `justificante_url`  | `AnyHttpUrl | None`   | Mirrors `Expediente.justificante_url`.                   |
| `complementaria_of` | `str | None`          | `expediente_id` of the filing this one amends.           |
| `source_page_url`   | `AnyHttpUrl`          | Detail page URL.                                          |
| `fetched_at`        | `AwareDatetime`       | UTC wall-clock when the HTML was captured.                |

### RawCalculationPayload

The casilla→value mapping keyed by `casilla_id`. Values are carried as
strings verbatim from the portal (see D3 below) to preserve AEAT's
printed formatting; downstream consumers (verification engine) convert
through `aeat.domain.casillas.CasillaRecord.data_type` rules.

| Field                    | Type                        | Notes                                                        |
| ------------------------ | --------------------------- | ------------------------------------------------------------ |
| `casillas`               | `dict[str, str]`            | `{"01": "1234,56", "02": "0,00", ...}`.                    |
| `total_a_ingresar`       | `Decimal | None`            | Parsed at extraction time when a labelled total is present.  |
| `total_a_devolver`       | `Decimal | None`            | Idem.                                                        |
| `resultado_a_compensar`  | `Decimal | None`            | Modelo 303-specific; optional.                               |
| `source_page_url`        | `AnyHttpUrl`                | Detail page URL.                                             |
| `fetched_at`             | `AwareDatetime`             | UTC.                                                         |

### FiledModelo (composition)

A single frozen pydantic record that bundles metadata + calculations
+ a reference to the originating `Expediente`.

| Field         | Type                     | Notes                                                |
| ------------- | ------------------------ | ---------------------------------------------------- |
| `metadata`    | `FiledModeloMetadata`    |                                                      |
| `calculations`| `RawCalculationPayload`  |                                                      |
| `parse_warnings` | `tuple[str, ...]`     | Non-fatal parser observations (missing totals, etc.).|

### FilingHistory (persistence container)

Mirrors the `Inbox` container pattern: a map of
`expediente_id → FiledModelo`, validated for uniqueness, with
`load_filing_history` / `save_filing_history` helpers.

## parser choice

BeautifulSoup4 (already on main, already a runtime dep via #43).
Rejected `lxml` (C build on Windows), `selectolax` (same), raw regex
(HTML drift). The pattern matches #43's existing
`parse_expedientes`.

Parser selects by label text, not brittle CSS paths:

```python
# Given a form row like:
# <tr><td class="casilla">01</td><td>1.234,56</td></tr>
for row in tbody.find_all("tr"):
    casilla_cell = row.find("td", class_="casilla")
    ...
```

Spanish decimal conventions (`1.234,56` → `1234.56`) are already
handled by `aeat.domain.justificante._extract._parse_decimal`; we reuse the
helper or lift its logic into a shared `aeat._decimal` module (plan
decision).

## fixture strategy

Every parser test runs against hand-curated fixture HTML under
`tests/fixtures/aeat-pages/filing-history/`. Procedure mirrors the
#43 ADR decision D9:

1. One fixture per supported modelo (`modelo_130_detail.html`,
   `modelo_303_detail.html`, `modelo_390_detail.html`).
2. Strip `<script>`, `<style>`, `<link>`, `<meta>`, and every `<div>`
   ancestor that is not required to reach the target form.
3. Scrub PII: NIF → `X1234567L`, amounts → round numbers, URLs →
   stable placeholders.
4. Each fixture round-trips through the parser and the pydantic model
   in a unit test.

The live opt-in test (`@pytest.mark.live_read` + domain markers)
skips by default and only runs when `AEAT_LIVE_TESTS_ENABLED=1`.
Because the live surface requires an authenticated certificate-backed
session, the test additionally documents the setup path and exits
early when no live session can be constructed.

## config surface

Two new `Settings` fields on `aeat.core.config.Settings`:

- `aeat_filing_history_dir: Path` — default
  `PROJECT_ROOT / "var" / "filing-history"`. Single JSON file
  (`history.json`) plus optional downloaded-detail-HTML archive
  under a `pages/` subdirectory.
- `aeat_filing_history_cache_ttl_s: int` — default `900` (15 min).
  Mirrors the #43 status-cache TTL default.

Both are regenerated in `.env.example` and covered by
`tests/test_config.py::test_env_example_alignment`.

## non-goals

- Double-entry verification logic. That is a separate issue that
  consumes `FiledModelo`; this issue produces it.
- PDF-duplicate (*copia del impreso*) extraction. The HTML detail
  surface covers v1 for every supported modelo. PDF-duplicate is a
  follow-up.
- Appeal filing, rectifying filings, or any write operation. The
  fetcher refuses to POST anywhere; enforced by the code-review
  checklist and the #116 safety charter.
- Typing casilla values. Values are carried as strings; the
  verification engine is responsible for coercing via
  `CasillaRecord.data_type`.
- Filtering by complementaria vs ordinaria. The fetcher surfaces the
  `complementaria_of` field and lets consumers decide.
- Persisting to the #10 storage layer. Single JSON under
  `AEAT_FILING_HISTORY_DIR` matches the inbox/status cadence.

## known risks

1. **Surface drift.** AEAT periodically reshapes portal URLs each
   campaign. Mitigation: parsers select by text label, URLs accepted
   as settings, live test is opt-in and only documents the current
   shape.
2. **Casilla labelling.** Not every modelo renders a visible
   `casilla_XX` tag; some use plain numeric labels adjacent to the
   value. Mitigation: per-modelo parser modules (`_parsers/modelo_130.py`,
   etc.), each validated against a fixture. Unsupported modelos raise
   `HistoryUnsupportedModeloError`.
3. **Certificate lifecycle.** #167 owns cert auth. We compose via
   Protocol stub; rebase-on-merge is a one-file change.
4. **Partial/rejected filings.** AEAT shows detail pages for
   `"Presentada"` rows and sometimes for `"Rechazada"` / `"En
   tramitación"` — but the casilla payload may be empty or
   partial. Mitigation: `FiledModelo` accepts empty
   `calculations.casillas`, records a `parse_warnings` entry, and
   never raises for a missing optional total.

## acceptance criteria

1. `aeat.history` subpackage ships under `src/aeat/history/` with
   public API exposed only via the package root.
2. `HistoryFetcher` composes an `ExpedienteSource` Protocol and a
   `FilingDetailFetcher` Protocol; both are injected.
3. v1 covers modelo 130, 303, 390 with real fixtures; other modelos
   raise `HistoryUnsupportedModeloError`.
4. Every boundary type is a strict+frozen pydantic v2 model; enums
   are `enum.StrEnum`.
5. 100% of unit tests run offline with fixture HTML; zero mocks,
   patches, fakes, or `unittest.mock` references.
6. A `@pytest.mark.live_read` opt-in test exists and is gated by
   `AEAT_LIVE_TESTS_ENABLED=1`; it is a no-op when not enabled.
7. Module imports inside `src/aeat/history/` are relative per the
   #162 mandate.
8. `tests/test_config.py` passes against the new settings fields;
   `.env.example` is aligned.
9. The fetcher has no write surface; `grep -R "page.goto\|page.click\|page.fill\|page.type\|form.submit"`
   over `src/aeat/history/` returns only `page.goto` calls, and
   every `page.goto` is asserted via a code-review note.
