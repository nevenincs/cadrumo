# modelo coverage matrix

Per-modelo implementation state. Refreshed every month via audit [#241](https://github.com/wgergely/aeat/issues/241).

Legend: ✅ shipped · 🚧 in progress · ⏳ scheduled · ❌ not yet scoped · N/A · *(named-field MVP)* = document recognised + header + a curated set of named-field values captured via regex (non-numbered summary blocks, see wave 27). *(text-value MVP)* = numbered casillas with text payloads (see wave 24).

| Modelo | In registry | Schema | Formula ruleset | Filing builder | Export (fichero BOE) | Amendment (complementaria) | Amendment (rectificativa) | Tests | Live-read detail | CLI coverage | `justificante` import | `declaración` import | `borrador` import | `predeclaración` import |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 036 | ✅ | 🚧 | ❌ | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (named-field MVP) | ❌ | ❌ |
| 037 | ✅ | 🚧 | ❌ | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (named-field MVP) | ❌ | ❌ |
| 100 | ✅ | 🚧 (summary 27 casillas) | 🚧 (summary 12 casillas) | ❌ | ❌ | ❌ | N/A | partial | ❌ | ✅ (`--from-borrador`) | ✅ | ✅ (summary MVP) | ✅ (summary MVP) | ✅ (summary MVP) |
| 111 | ✅ | ✅ (9 casillas) | ✅ (2024 + 2025 sum/resultado) | ❌ | ❌ | ⏳ #235 | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 115 | ✅ | ✅ (6 casillas) | ✅ (2024 + 2025) | ❌ | ❌ | ⏳ #235 | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 123 | ✅ | ✅ (11 casillas) | ✅ (2024 + 2025 aggregation) | ❌ | ❌ | ❌ | N/A | partial | ❌ | ❌ | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| **130** | ✅ | ✅ (19 casillas) | ✅ (2024 + 2025 + 2026, calc-verify Tier-L #321) | ✅ | ✅ (2024 + 2025, golden SHA pinned, verify round-trip) | ✅ (pre-Q3-2024) | ⏳ #234 | ✅ | ⏳ #272 | ✅ | ✅ | ✅ (2024 + 2025 + 2026, 19-casilla full liquidación block #321) | ❌ | ❌ |
| 131 | ✅ | ✅ (15 casillas) | ✅ (2024 + 2025 módulos) | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 180 | ✅ | ✅ (4 casillas) | ✅ (2024 + 2025 resumen arrendamientos) | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 190 | ✅ | 🚧 | ❌ | ❌ | ❌ | ⏳ #235 | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 193 | ✅ | 🚧 | ❌ | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 200 | ✅ | ✅ (16 casillas p14) | ✅ (2024 liquidación) | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP p14) | ❌ | ❌ |
| 202 | ✅ | ✅ (9 casillas) | ✅ (2025 liquidación) | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 232 | ✅ | 🚧 | ❌ | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (named-field MVP) | ❌ | ❌ |
| **303** | ✅ | ✅ (8-segment envelope, 393 fields, DR303e24.xlsx auto-generated) | ✅ (2024 + 2025 + 2026, calc-verify Tier-L #326) | ✅ | ✅ (2024 + 2025, 7994-byte envelope, golden SHA pinned, verify round-trip) | ✅ (pre-Q3-2024) | ⏳ #234 | ✅ | ⏳ #272 | ✅ | ✅ | ✅ (2024.09 + 2025 + 2026, 33-casilla full liquidación block #326) | ❌ | ❌ |
| 347 | ✅ | 🚧 | ❌ | ❌ | ❌ | ⏳ #235 | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 349 | ✅ | 🚧 | ❌ | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 369 | ✅ | 🚧 | ❌ | ❌ | ❌ | ❌ | N/A | partial | ❌ | partial | 🚧 | ✅ (named-field MVP) | ❌ | ❌ |
| **390** | ✅ | ✅ | ✅ (2025 resumen IVA anual) | ✅ | ⏳ #201 | ✅ (SUSTITUTIVA) | N/A | partial | ⏳ #272 | ✅ | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
| 720 | ✅ | 🚧 | ❌ | ❌ | ❌ | ❌ | N/A | partial | ❌ | ❌ | 🚧 | ✅ (named-field MVP) | ❌ | ❌ |
| 840 | ✅ | 🚧 | ❌ | ❌ | ❌ | ❌ | N/A | partial | ❌ | ❌ | 🚧 | ✅ (text-value MVP) | ❌ | ❌ |

**Bold** = primary autónomo forms (130, 303, 390). These are the minimum-viable modelo set for Kent.

## kent CLI integration coverage

`tests/integration/test_kent_workflows.py` exercises `aeat filing import` end-to-end via Typer's CliRunner against synthetic PDFs for every Tier-L modelo. As of #340 (2026-04-25), the file ships dedicated `TestKentImports*` classes covering Modelos 100 (summary, via `--from-borrador`), 111, 115, 123, 130 (template), 131, 180, 200 (locks in the current UNVERIFIABLE verdict — 2024-only ruleset against the 2025 extractor), 202, 303, 390. Each class asserts `Extraction status:` / `Verification status:` plus the per-modelo `cause=CORRECTNESS_DIVERGENCE` discrepancy classifier where a ruleset is available. Spanish-default and explicit English (`AEAT_OUTPUT_LANGUAGE=en`) paths are exercised for every modelo.

## provenance

This matrix was last updated on **2026-04-27** (#326 — Modelo 303 calc-verify-roundtrip Tier-L bar reached for 2024/2025/2026: 2026 ruleset registered as a scoped régimen-general clone of 2024/2025 per the rule-delta manifest at `.vault/reference/2026-303-rule-delta.md`, declaración extractor registry extended with `Modelo303V2026Extractor`, 33-casilla liquidación round-trip preserved, and Kent integration extended with a 2026 happy path while keeping the discrepancy-classifier case; #321 — Modelo 130 calc-verify-roundtrip Tier-L bar reached for 2024/2025/2026: 2026 ruleset registered as a structural clone of 2024/2025 per `.vault/reference/2026-130-rule-delta.md`; previous refresh **2026-04-25** — #340 Kent CLI integration coverage extended to all 10 remaining Tier-L modelos in `tests/integration/test_kent_workflows.py`). Future updates land via [#241](https://github.com/wgergely/aeat/issues/241) monthly-audit PRs. Do not edit this file out-of-band except for per-modelo DoD updates that explicitly require this matrix.
