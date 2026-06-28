---
tags:
  - "#audit"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-22-real-pdf-import-wave-48-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-53-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-58-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-60-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-62-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-64-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-66-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-68-exhaustive-audit]]"
  - "[[2026-04-22-citation-blocklist-adr]]"
---

# real-pdf-import — wave 70 exhaustive audit

## Scope

Ninth cycle of the exhaustive-audit pattern. Four parallel streams
verify wave 69 (commit `4fa75da`) — the citation-blocklist
structural intervention — and probe for residuals.

Commit audited: `4fa75da`.

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 wave 69 blocklist verification | PASS (+3 cautions) | 0 | 0 | 3 |
| 2 cross-cutting citation drift | REVISION REQUIRED | 4 | 0 | 0 |
| 3 test suite + ADR compliance | PASS (+2 blockers) | 0 | 2 | 0 |
| 4 Modelo 200 + audit-trail integrity | REVISION REQUIRED | 2 | 1 | 0 |

**Total open: 6 HIGH, 3 MEDIUM, 3 LOW.** Test suite 2217 passing.

## HIGH findings

### H1 (stream 2) — Modelo 200 production `_CITATIONS` cites LIS art. 125

`modelo_200_2024.py:62-68` still cites LIS art. 125 for "líquido a
ingresar o devolver; incremento por pérdida de beneficios fiscales".
Stream 4 WebSearch-verified against BOE-A-2014-12328: LIS art. 125 is
"Autoliquidación e ingreso de la deuda tributaria" (procedural;
clauses 125.1-.2 cover declaration + payment-in-kind; 125.3 is a
narrow remedy for loss-of-benefit-conditions).

The production citation conflates art. 125.3's narrow remedy with a
broad "líquido a ingresar" scope it does not have. The actual scope
of Modelo 200 casilla 00611/00621 arithmetic maps to LIS art. 30
(cuota íntegra / cuota líquida) + art. 39.2 (abono deducciones) + a
scoped 125.3 reference.

The wave 69 blocklist doesn't catch this because its substring is
`"cuota líquida"` — the 200 citation uses `"líquido a ingresar"`.

**Fix**: replace the art. 125 citation with art. 30 + art. 39.2 (+
scoped 125.3 for incremento). Also extend blocklist with a
`(LEY, "125", "líquido a ingresar")` entry.

### H2 (stream 2) — Modelo 390 production cites LIVA art. 71 for resumen anual

`modelo_390_2025.py:62-69` cites LIVA (Ley 37/1992) art. 71 as
"obligación de presentar la declaración-resumen anual del IVA
(modelo 390)". LIVA art. 71 is actually "Lugar de realización de
las prestaciones de servicios" (place-of-supply rules). The
resumen-anual obligation lives in **RIVA (RD 1624/1992) art. 71.7**
— a different law + source type (REGLAMENTO, not LEY).

**Fix**: change source to `REGLAMENTO` and article to `71.7` citing
RIVA / RD 1624/1992; BOE URL → BOE-A-1992-28925.

### H3 (stream 2) — Modelo 111 module docstrings narrate stale miscites

`modelo_111_2024.py:4-5` and `modelo_111_2025.py:11,14` module-level
docstrings still narrate "premios (art. 105.1 Reglamento IRPF)" and
"arrendamientos… art. 100.3.c Reglamento". Wave 69a fixed the
`_CITATIONS` tuples but left the narrative docstring uncorrected,
creating drift between documentation and citations.

**Fix**: sweep docstrings to match the 69a citations (art. 99 for
premios via LIRPF 101.7; art. 100 single-paragraph for
arrendamientos).

### H4 (stream 4) — Wave 68 audit doc was never created

The wave 68 audit cycle ran (4 streams) but the consolidated audit
doc at `.vault/audit/2026-04-22-real-pdf-import-wave-68-exhaustive-audit.md`
was never written. Wave 68 shipped fixes (commit `fe8fa85`) but the
audit-trail contract requires an explicit doc per wave — without it,
the load-bearing rationale for exec-record deferral collapses.

**Fix**: reconstruct the wave 68 audit doc retroactively from the
four stream outputs (preserved in `C:\Users\hello\AppData\Local\Temp\
claude\...\tasks\*.output`). **Closed inline as wave 70 ships a new
`2026-04-22-real-pdf-import-wave-68-exhaustive-audit.md`.**

### H5+H6 (stream 4 + stream 3) — Wave 66 audit doc missing closure table; modelos.md provenance stale

- `.vault/audit/2026-04-22-real-pdf-import-wave-66-exhaustive-audit.md`
  has no `## Closure status` section (ironically, wave 66 H2 flagged
  this on wave 64 doc).
- `docs/coverage/modelos.md` provenance line cites waves "48/53/58/60/
  62/64" — does not mention wave 66/68/69.

## MEDIUM findings

- **M1 (stream 3)**: `.vault/adr/2026-04-22-ruleset-architecture-adr.md`
  `related:` frontmatter does NOT back-link the new
  `[[2026-04-22-citation-blocklist-adr]]`. Bidirectional graph broken.
- **M2 (stream 3)**: `docs/coverage/modelos.md` provenance doesn't
  mention wave 69's structural blocklist protection.
- **M3 (stream 4)**: Modelo 115 module docstring at line 16 says
  "art. 100.2 LIRPF" — art. 100 is in RIRPF, not LIRPF. Source
  mislabel. `_CITATIONS` tuple correctly has REGLAMENTO; only the
  narrative is wrong.

## LOW findings

- **L1 (stream 1)**: Blocklist role-substring `"cuota líquida"`
  for LIRPF art. 79 could false-positive on a correctly-authored
  educational narrative like
  `"art. 79 — cuota diferencial = cuota líquida - pagos a cuenta"`
  (both roles mentioned, one blocklisted). Recommend regex anchoring
  in a future wave (`art. 79.*cuota líquida`).
- **L2 (stream 1)**: Blocklist is accent-naive. `"cuota liquida"`
  (without diacritic) defeats a `"cuota líquida"` substring. Known
  limit per the ADR; future wave could add `unicodedata.normalize`.
- **L3 (stream 1)**: Blocklist is word-order-naive. `"líquida cuota"`
  defeats the substring. Known limit; blocklists are not parsers.

## Remediation plan — wave 71

- **Wave 71a**: write missing wave-68 audit doc retroactively (H4 — closed inline).
- **Wave 71b**: add wave-68/70 closure-status tables to wave 66 + 68 docs (H5).
- **Wave 71c**: Modelo 200 LIS art. 125 → art. 30 + 39.2 + scoped 125.3 (H1).
- **Wave 71d**: Modelo 390 LIVA art. 71 → RIVA art. 71.7 (H2).
- **Wave 71e**: Modelo 111 module docstrings swept (H3).
- **Wave 71f**: Modelo 115 docstring source mislabel LIRPF → RIRPF (M3).
- **Wave 71g**: ADR back-link + modelos.md provenance bump (M1 + M2 + H6).
- **Wave 71h**: extend blocklist with `(LEY, "125", "líquido a ingresar")` entry + `(LEY, "71", "resumen anual")` LIVA entry.

L1/L2/L3 cautions tracked for wave 72+ as non-blocking.

Wave 72 audit loop follows.
