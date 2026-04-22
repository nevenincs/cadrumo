**Kent success moment:** Kent drops a declaración PDF for any modelo in scope and `aeat filing import --from-declaracion` returns `VERIFIED` with every printed casilla re-derived from its inputs to within 0.01 €. Works for 2024, 2025, and 2026 filings. When a discrepancy appears, the classifier tells Kent exactly which casilla drifted, what the PDF printed, what the engine computed, and a suggested cause (extraction / formula / un-modelled rule / rounding).

## Why this EPIC exists

EPIC #305 shipped the PDF-import + calc-verify scaffolding and proved it end-to-end for Modelo 130. That work drifted in scope and now covers the full casilla → modelo → PDF ingestion + calculation universe.

This EPIC is the **completeness umbrella** for that universe — a per-modelo, per-year bar that says "Kent can compute, verify, and round-trip this form."

It is deliberately scoped *outside* PR #271 so that PR can land without further creep. Every child issue here is independently pickable.

## Architectural ground-truth (from 2026-04-22 audit)

The ruleset engine operates on casilla-level primitives, not raw transactions. The T6 transaction-to-casilla aggregator (Kent capability #218) is NOT in scope here — that's upstream. This EPIC's scope starts at `inputs.json` and ends at `VERIFIED` on the exported-or-extracted PDF.

Tier split (audit-validated, non-negotiable):

| Tier | Modelos | Semantic |
|---|---|---|
| **L — Liquidation** | 100, 111, 115, 123, 130, 131, 180, 200, 202, 303, 390 | Full calc + round-trip + per-annum rule coverage |
| **S — Summary/informative** | 190, 193, 347, 349 | Per-counterparty records + resumen-totals parity; no formula ruleset |
| **R — Registration** | 036, 037, 232, 369, 720, 840 | Named-field / text extraction; no calc semantic |

## Child issues

Filed as children of this EPIC:

- **11× Tier-L** — per-modelo calc-verify completeness (2024/2025/2026)
- **4× Tier-S** — per-modelo summary extraction + totals parity
- **6× Tier-R** — per-modelo registration-form extraction + L2 fixture
- **3× codebase chores** — mutation-harness extension (`percent` + `brackets`), mandatory `LegalCitation` enforcement, integration-test expansion for all Tier-L modelos
- **4× RENTA hardening** (1 umbrella + 2024/2025/2026) — Modelo 100 deep dive: anexos, CCAA deductions, LIRPF minimums
- **6× IVA complexity** (1 umbrella + 5 scoped) — tipos/exento, prorrata, ISP+intracomunitarias, bienes de inversión, 2026 franquicia IVA

Total: 34 children.

## Relationship to other EPICs

- **Child of / parallels #305** (real-PDF calc-verified import). This EPIC turns #305's MVP into universal coverage.
- **Blocked-by nothing** — formula engine, declaración extractor, and `verify_declaracion()` are all already landed.
- **Does not overlap with #201** (fichero-BOE export) — export serialisation is a separate workstream.
- **Does not overlap with #218 / T6** (transaction-to-casilla aggregation) — aggregation is upstream.

## Kent-observable acceptance

- Every Tier-L modelo round-trips `VERIFIED` on a 2024/2025/2026 synthetic fixture + (where available) an L1 or L2 real-PDF fixture
- Every Tier-S modelo round-trips `VERIFIED` on per-counterparty records with resumen totals matching within 0.01 €
- Every Tier-R modelo round-trips the extractor against a real L2 fixture (consent-logged)
- `docs/coverage/modelos.md` shows ✅ in every applicable column for every supported modelo

## Labels

`epic`, `type:feature`, `area:submission`, `health:coverage`, `priority:P1-high`, `effort:XL`, `parallel-safe`, `kent-journey`
