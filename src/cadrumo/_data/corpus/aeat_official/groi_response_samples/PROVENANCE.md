# GROI response samples — provenance

Verbatim text fragments captured from live AEAT GROI servlet responses during
cl@ve-móvil authenticated probing. These samples are the external authority for
the GROI verdict parser; this document is their audit trail.

## Source

- **Surface**: Consulta de Operadores Intracomunitarios (GROI), AEAT Sede Electrónica
- **Endpoint**: `https://www2.agenciatributaria.gob.es/wlpl/GROI-JDIT/ConsultaOperadorSedeGroiServlet`
- **Access**: authenticated (cl@ve-móvil); the surface is not reachable anonymously
- **Capture method**: project BrowserSession probe, responses copied verbatim
- **Raw capture artefacts**: `.tmp/nif_iva_capture/groi_response_{NIF}.html` (not committed)

The AEAT page carries no published last-updated timestamp — the servlet renders a
per-request certification. The response *phrasing* is the versioned surface this
corpus tracks, so the corpus-capture date below is the authoritative freshness
signal.

## Corpus capture date

- **Captured**: 2026-05-07
- **Last re-verified**: 2026-05-07

Re-capture is a live operation: it requires cl@ve-móvil credentials and network
access to AEAT. There is no automated refresh. When a re-probe confirms the
phrasing is unchanged, bump *Last re-verified* without rewriting the samples.

## Documents

| File | Verdict | Subject NIF | Captured | Bytes | SHA-256 |
|------|---------|-------------|----------|-------|---------|
| `valid_telefonica_a28015865.txt` | `valid` | `A28015865` — Telefónica SA, publicly ROI-registered | 2026-05-07 | 280 | `3df47d9665ac7abfc67dd2e7eb4d41b7e11afcfcc7d7c2cf9f6ad4c2768f563b` |
| `invalid_format_b00000001.txt` | `invalid` | `B00000001` — syntactically invalid Spanish NIF | 2026-05-07 | 155 | `a330302b66e69ed8453587352e5d5b6412e26a02f76e7edc4cf9ebe9a6fbb0a0` |

Captures are stripped of AEAT page chrome before commit. The header and
área-personal dropdown leak the authenticated operator's own NIF; only the
verdict-bearing block is retained. No sample contains personal data: both
subject NIFs are a public company registration and a synthetic invalid value.

## Naming contract

Filenames follow `{verdict}_{descriptor}.txt`, where `{verdict}` is one of
`valid`, `invalid`, `unknown`. **The filename is the assertion** — the
parametrised gate in
`src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check.py` derives the
expected verdict from the prefix. A file that does not match the contract fails
the gate rather than being skipped.

## Known coverage gaps

These verdict classes are reachable in production but have **no captured
sample**. They are declared here so the absence stays visible rather than
reading as completed coverage.

| Missing sample | Verdict | Why it matters |
|----------------|---------|----------------|
| Valid-format NIF that is not ROI-registered (`NO CONSTA`) | `invalid` | The single most operationally important case for modelo 349. Currently covered only by a reconstructed inline string in the test module, which is not captured evidence. |
| Structurally unanswerable response (service error / interstitial) | `unknown` | The discovery gate accepts an `unknown_` prefix, but no sample exercises it end to end. |

Closing a gap requires a live authenticated probe. To add a sample: capture the
response, strip the chrome, save it as `{verdict}_{descriptor}.txt`, add a row to
the Documents table above, and delete the corresponding row here. The gate picks
the file up automatically.
