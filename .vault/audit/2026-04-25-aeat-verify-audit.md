---
tags:
  - '#audit'
  - '#aeat-verify'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-24-aeat-verify-reference]]"
  - "[[2026-04-24-aeat-verify-adr]]"
---



# `aeat-verify` audit: `modelo-coverage-matrix-and-rewrite-status`

## Scope

End-of-day audit of the `aeat-verify` feature after the discovery-driven
rewrite. Captures (a) the post-demolition codebase state, (b) the
modelo coverage matrix as of 2026-04-24/25, and (c) the open follow-ups
for continuous expansion.

## Demolition record

The following speculative subpackages were deleted wholesale during this
PR. None were ever validated against live AEAT — they were Protocol
stubs and synthetic-fixture-only logic gated behind never-merging
collaborator branches. Total: roughly 11700 lines removed across the
rewrite.

| Subpackage | Lines | Status |
| --- | --- | --- |
| `aeat.remote/` | ~2000 | deleted in 474cceb |
| `aeat.status/` | 4093 | deleted in 8df3733 |
| `aeat.history/` | 2341 | deleted in 8df3733 |
| `aeat.inbox/` | ~1456 | deleted in 8df3733 |
| `aeat.entrypoints.cli.status/` | ~120 | deleted in 8df3733 |
| `aeat.entrypoints.cli.inbox/` | 607 | deleted in 8df3733 |
| `aeat.entrypoints.cli._live_reader.py` | ~80 | deleted in 8df3733 |

Salvaged: the site-health detection records and parsers (which were
genuinely useful, not speculation) moved from `aeat.status._site_health`
to `aeat.adapters.outbound.aeat.browser._site_health`.

Downstream cleanup (handled by the dependent agent in 8df3733):
`aeat.application.review` lost its inbox adapter; `aeat.application.workflow` had its
`SiteHealthAlert` import retargeted; `aeat.entrypoints.cli.filing.import_` lost the
`--from-aeat` flag and its supporting `_handle_aeat_import` /
`_fetch_filed_modelos` helpers.

## What replaced the deleted code

| New surface | Status | Live-validated? |
| --- | --- | --- |
| `aeat.adapters.outbound.aeat.sede` (walker, expediente schema, justificante refs) | shipped | yes (Kent's 3 IRPF expedientes captured live) |
| `aeat.adapters.outbound.aeat.sede._notifications` (parsers + live fetchers) | shipped | yes (2 unread + 1 pending row captured live) |
| `aeat.domain.justificante` (annual-modelo regex set) | extended | yes (3 IRPF justificantes parse end-to-end) |
| `aeat.adapters.inbound.declaracion` Modelo 100 extractors (2021/2022/2023) | shipped | yes (83-86 casillas/year extracted from real PDFs) |
| `aeat.application.filing.reconciliation` | shipped | yes (verified against captured Justificantes) |
| `aeat sede list-expedientes` CLI | shipped | yes (returns Kent's 3 IRPF rows live) |
| `aeat sede discover` CLI | shipped | smoke-tested, full live PDF capture loop |
| `aeat sede notifications` CLI | shipped | parser verified against live HTML; live fetch yet to run |
| `aeat filing reconcile` CLI | shipped | wires draft to sede to reconcile end-to-end |

## Modelo coverage matrix

The aeat catalogue lists 21 modelos. Coverage is per the four sub-stages
of the verify loop: justificante parse, declaracion deep parse, sede
walker discovery (fold modelo by category), reconciliation hookup.

| Modelo | Justificante parse | Declaracion deep parse | Sede walker | Reconcile | Notes |
| --- | --- | --- | --- | --- | --- |
| 100 (IRPF) | OK (live) | OK (live, 2021/2022/2023) | OK (live, 3 expedientes captured) | OK | Kent's primary corpus. |
| 130 (IRPF fraccionado) | OK (synthetic fixture) | not implemented | OK (catalogue branch resolves) | meta-only | No live filings yet. |
| 303 (IVA) | OK (synthetic fixture) | not implemented | OK | meta-only | No live filings yet. |
| 390 (IVA anual) | not yet | not implemented | OK | meta-only | No live captures. |
| 111, 115, 131, 180, 190, 193 | not yet | not implemented | catalogue resolves | not wired | Rulesets exist; no fixtures or live captures. |
| 200, 202, 232 | not yet | not implemented | catalogue resolves | not wired | Sociedades; rulesets exist; no live work. |
| 347, 349, 369, 720, 840 | not yet | not implemented | catalogue resolves | not wired | Informativa / IVA-OSS / patrimonio / IAE. |
| 036, 037 | not yet | not implemented | n/a | n/a | Census forms — out of scope for verify. |

Live-validated: only Modelo 100 (Kent's account). Every other modelo is
synthetic-fixture-only or pure catalogue metadata.

## Continuous-expansion levers

For each non-Modelo-100 row above to become "live-validated", the
project needs one of:

- A real Justificante PDF for that modelo, captured by Kent or a
  collaborator with that filing on file. Drop into
  `tests/fixtures/justificantes/` and the matching extractor regression
  test enforces shape stability.
- An attempt to call `aeat sede discover --modelo <N>` against an
  account that has filed it — the discovery script writes the captured
  PDF + parsed metadata under `scratch/sede-discovery/<ts>/`, which
  feeds the next regression-test capture.
- A new Modelo-100-style deep extractor (in
  `src/aeat/adapters/inbound/declaracion/_parsers/<modelo>/`) once a real PDF is in hand.

The continuous-discovery loop is intentionally bounded by Kent's actual
filings; speculative shape work is explicitly out of scope per the
ground-truth-first mandate.

## Open audit items

- 4 transient failures observed in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`
  during the cleanup wave were verified to pass cleanly on a fresh run
  (b7wcbw5ww and byzys6epr completion notices); not pre-existing as the
  earlier executor surmised.
- Modelo 100 extractor's casilla 70 (CCAA) returns `int` for the legacy
  2021 layout (where AEAT prints the numeric code) and `str` for
  2022/2023 (where AEAT prints the name). Downstream consumers must
  not assume a single typed shape.
- Modelo 100 extractor's casilla 0069 (Dirección del inmueble) is
  reliably truncated by the value-walk; bbox-anchored extraction is
  the long-term fix.
- `aeat sede notifications` CLI live-fetch remains unverified end-to-end
  (parser is verified against captured HTML; the wrapper is mechanical).
- The Mis-Alertas page has the "1 unread" counter on Kent's account.
  Its content is JS-rendered and was not captured in any unit fixture.
  Treated as out of scope; the canonical surface is the
  `ResumenInteresados` / `SvInteresadosQuery` pair that was captured
  cleanly.

## Recommendations

- Capture and add `Modelo 100` synthetic test fixtures for the deep
  extractor so CI doesn't depend on `scratch/recon-corpus/` being
  populated. Track as a follow-up; tests skip cleanly when the live
  capture is missing.
- Run `aeat sede discover` whenever Kent files a new modelo so the
  parser corpus grows organically.
- Cache the Cl@ve session aggressively — `aeat auth whoami` resets the
  18-min idle TTL on disk, so a periodic ping during long discovery
  runs avoids fresh 2FA prompts.
- Track `Modelo 100` casilla 70 + 0069 oddities in the next cleanup
  pass; bbox-anchored value extraction is the right structural answer.
