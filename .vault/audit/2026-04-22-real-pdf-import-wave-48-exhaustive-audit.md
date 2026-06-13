---
tags:
  - "#audit"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-22-ruleset-architecture-adr]]"
  - "[[2026-04-21-real-pdf-import-execution-wave-910-audit]]"
---

# real-pdf-import — wave 48 exhaustive coverage audit

## Scope

Four parallel audit streams against branch `feature/271-pdf-import` at
`987422b` (wave 47 landing). No spot-check: every ruleset, every
extractor, every doc surface, every primitive & test walked line by
line.

- **Stream 1 — Ruleset calc verification.** Walk every formula in
  the 18 rulesets, compute the AEAT identity by hand, cross-check
  rates + citations. Agent: `vaultspec-code-reviewer`.
- **Stream 2 — Extractor casilla verification.** Every casilla_id,
  text_casilla_id, named_field_pattern cross-referenced against the
  cited BOE Orden per module.
- **Stream 3 — Docs + ADR + coverage-matrix integrity.** Every claim
  across `docs/coverage/*.md`, the wave-46 ADR, and module
  docstrings must be backed by live code.
- **Stream 4 — Test integrity + primitive correctness.**
  Tautological-fixture hunt, adversarial-PDF-text simulation on the
  three primitives, coverage gaps per ruleset.

## Findings summary

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 Ruleset calc | PASS | 0 | 0 | 5 |
| 2 Extractor casillas | REVISION REQUIRED | 3 | 4 | 3 |
| 3 Docs integrity | PASS | 0 | 0 | 2 |
| 4 Test + primitive | REVISION REQUIRED | 4 | 3 | 3 |

**Total: 7 HIGH, 7 MEDIUM, 13 LOW across 30 findings.**

## Closure status (updated 2026-04-22, wave 54)

| Finding | Status | Closing wave |
|---|---|---|
| H1 decimal whitespace | CLOSED | wave 51 (`3df1097`) |
| H2 soft-hyphen line-break | CLOSED | wave 51 (`3df1097`) |
| H3 tautological ruleset tests | PARTIAL | wave 57a/b (`a69623e`, `d8675ee`) + wave 59c (`c36f9b0`) anchored 11/14 rulesets; wave 61c (`d30c530`) closed 130_2025 + 100_summary_2025; 303_2024 thin-anchor surface remains (wave 63+) |
| H4 7 rulesets with zero tests | PARTIAL | wave 52 (`07232d6`) — closed 5/7; Modelo 130 2024/2025 gap tracked as wave 53 H3, wave 55 |
| H5 111/115 label drift | CLOSED | wave 49 (`6f9763b`) + wave 53 stream 1 LOW `78b4687` |
| H6 Modelo 202 casilla 34 | CLOSED | wave 50 (`d50b7a6`) — verified real |
| H7 Modelo 200 00582 label | CLOSED | wave 49 (`6f9763b`) |

See `.vault/audit/2026-04-22-real-pdf-import-wave-53-exhaustive-audit.md`
for the follow-up audit findings that remain open.

## HIGH findings (must-fix)

### H1 (stream 4) — Decimal primitive silently loses intra-number whitespace

`src/aeat/adapters/inbound/pdf/_label_regex.py:23` — `SPANISH_AMOUNT_GROUP`
does not tolerate thousands-separator whitespace (`1 234,56` collapses
to `234,56`, 1000× underreport). pdfplumber occasionally emits
kerned-glyph space-separated numerics on AEAT PDFs.

**Fix**: widen the capture group OR emit an "ambiguous numeric
context" warning when `\d{1,3}\s` precedes the matched amount.

### H2 (stream 4) — Hyphenated labels across line breaks silently drop

`_label_regex.py` has no soft-hyphen / `-\n` line-continuation
handling. Any AEAT PDF that reflows `Cuota reper-\ncutida:` drops
the casilla silently with `casilla-not-found`.

**Fix**: pre-normalise `full_text` by stripping `-\n` in
`GenericDeclaracionExtractor.extract` (before dispatch).

### H3 (stream 4) — Ruleset "happy-path" tests are tautological

Every `test_consistent_*_is_clean` fixture is hand-computed by
running the ruleset's own formulas. A swapped-operand formula bug
would be mirrored into the fixture and still pass.

**Fix**: seed at least one fixture per ruleset from an AEAT-published
worked example (instrucciones PDF), not from the ruleset itself.

### H4 (stream 4) — 7 rulesets have zero dedicated unit tests

Missing: `modelo_100_summary_2025`, `modelo_111_2024`,
`modelo_115_2024`, `modelo_123_2024`, `modelo_130_2024`,
`modelo_131_2024`, `modelo_180_2024`. The 2024 backfills rely on
registry-identity smoke tests only; any formula bug in a 2024
variant lands undetected.

**Fix**: add one-happy + one-mutation test per missing ruleset.

### H5 (stream 2) — Modelo 111/115 casilla label drift

`modelo_111_v2025.py:53` comments casilla 29 as "resultados negativos
de declaraciones anteriores" but the printed AEAT label is
"**A deducir**: exclusivamente en caso de declaración
complementaria". Similar drift on `modelo_115_v2025.py` casilla 05.

**Fix**: update comments to match the AEAT-printed label verbatim.

### H6 (stream 2) — Modelo 202 casilla "34" existence — RESOLVED (wave 50)

**Resolution**: Stream 2 was WRONG. Casilla 34 EXISTS on the 2025
Modelo 202 form. Verified against primary source:

- **BOE-A-2025-5407** Orden HAC/262/2025, Anexo I pág. 36465
  (liquidación block 4) prints:
  - `32` — Resultado
  - `33` — Mínimo a ingresar (para empresas CN ≥ 10M €)
  - `34` — **Cantidad a ingresar (mayor de claves [32] y [33])**
- The `Ingreso (8)` block on the same page references ``Importe
  (casilla [34] ó [03])``, confirming 34 is the terminal payable.

Current ruleset formula `34 = max(32, 33)` matches the printed form.
**No code changes; citation anchors added to Modelo 202 extractor +
ruleset docstrings** (wave 50) so the question cannot be re-litigated
without consulting the verdict.

Closed via wave 50.

### H7 (stream 2) — Modelo 200 casilla 00582 comment wrong

`modelo_200_v2025.py:53` labels 00582 as "cuota íntegra ajustada
positiva" but AEAT Manual Sociedades 2024 says 00582 is
"bonificaciones y deducciones doble imposición internacional".
The extractor still *finds* the casilla (regex matches the number)
but downstream ruleset authors reading the comment get misled.

**Fix**: correct the comment. The "cuota íntegra ajustada positiva"
casilla is `00592`, which is already correctly labelled on line 54.

## MEDIUM findings

- **M1 (stream 2)**: Modelo 232 regex `vinculadas` / `intangibles`
  / `paraísos` over-permissive — docstring already flags as
  speculative, but the form-title can leak into matches. Tighten
  when L2 fixtures land.
- **M2 (stream 2)**: Modelo 720 `clave [CVI]\b` regex may false-
  positive inside 720's per-line detail block. Docstring flags.
- **M3 (stream 2)**: Modelo 369 `soportado` negative-lookahead is
  per-line; AEAT's grid-wrap layout could split the phrase. Caveat
  documented.
- **M4 (stream 2)**: Modelo 036 `Causa presentación` multi-hit —
  mitigation exists via confidence downgrade; docstring should
  explain.
- **M5 (stream 4)**: `TEXT_VALUE_GROUP` collapses tab-separated
  multi-token values. Extractors with `text_casilla_ids` but no
  `text_labels` entry get no truncation warning.
- **M6 (stream 4)**: `test_modelo_180_2025.py` has only 3 tests
  (below the informal ≥5 bar).
- **M7 (stream 4)**: `test_modelo_303_*.py` declare
  `domain_local_state`; every other ruleset test uses
  `domain_financial_input`. Reclassify or document.

## LOW findings

- **L1 (stream 1)**: Modelo 100 docstring mentions 0721 without
  declaration.
- **L2 (stream 1)**: Modelo 130 uses `REAL_DECRETO` enum where
  others use `REGLAMENTO` for the same RIRPF.
- **L3 (stream 1)**: Modelo 303 double-declares rate in casilla
  02/05/08 literal AND in param table.
- **L4 (stream 1)**: Modelo 202 modalidad 40.2 out-of-scope
  (documented in docstring).
- **L5 (stream 1)**: Modelo 131 casilla 02 hardcoded rate
  (documented).
- **L6 (stream 2)**: Modelo 347 missing EPIC-#305-full reference in
  scope note.
- **L7 (stream 2)**: Modelo 190 missing deferral note for full-form
  per-perceptor detail.
- **L8 (stream 2)**: Modelo 303 v2024_09 docstring asserts superset
  but enumerates identical set.
- **L9 (stream 3)**: ADR §1 says variant-axis refactor "deferred"
  but wave 47 already implemented it. Update ADR status.
- **L10 (stream 3)**: ADR §4 names only 390+123 as empty-
  ParameterTable exemplars; 100/200/202 also apply (different
  rationale).
- **L11 (stream 4)**: `parse_spanish_decimal` accepts ambiguous
  US-format `1234.56`.
- **L12 (stream 4)**: `test_label_regex.py` has no adversarial
  cases for `€` suffix, nbsp, soft-hyphen.
- **L13 (stream 4)**: Synthetic round-trip gap for 180/190/200/202/
  232/347/349/369/390/720/840.

## Remediation plan — waves 49-52

- **Wave 49**: docs-level fixes — ADR L9/L10, extractor comment
  drift H5/H7, marker reclassification M7, scope-note L6/L7/L8.
  Quick wins, no primitive or formula changes.
- **Wave 50**: research Modelo 202 casilla 34 existence (H6) and
  resolve. If confirmed, migrate ruleset formula + extractor set.
- **Wave 51**: decimal-primitive whitespace tolerance (H1) and
  soft-hyphen handling (H2), plus adversarial primitive tests (L12).
- **Wave 52**: backfill unit tests for 7 untested rulesets (H4),
  expand Modelo 180 test coverage (M6).
- **Wave 53+**: independent-fixture refactor against AEAT worked
  examples (H3) — significant research work, staged per ruleset.

Waves 49-52 land as a contiguous block before any new extractor or
ruleset work is shipped.
