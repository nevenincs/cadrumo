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
  - "[[2026-04-22-real-pdf-import-wave-70-exhaustive-audit]]"
  - "[[2026-04-22-citation-blocklist-adr]]"
---

# real-pdf-import — wave 72 exhaustive audit

## Scope

Tenth cycle of the exhaustive-audit pattern. Four parallel streams
verify wave 71 (commit `ca1f010`) + deliver a **convergence verdict**
on the recurring citation-error pattern that has now surfaced in
waves 59c/61a/63a/65a/67a/67g/68/70/72.

Commit audited: `ca1f010`.

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 wave 71 verification | PASS | 0 | 0 | 0 |
| 2 convergence + final re-audit | NOT CONVERGED | 1 | 0 | 0 |
| 3 blocklist hardening (L1/L2/L3) | RECOMMENDATION | — | — | — |
| 4 GH issues + ADR graph + audit-doc chain | PASS | 0 | 0 | 0 |

**Total open: 1 HIGH, 0 MEDIUM, 0 LOW.** Test suite 357 passing.

## HIGH findings

### H1 (stream 2) — Modelo 100 summary RIRPF "liquidación (art. 67-77)" miscite

`modelo_100_summary_2025.py:25` (module docstring) and `:60-61`
(REAL_DECRETO `_CITATIONS` entry) claim RIRPF art. 67-77 covers
"liquidación". Stream 2 WebSearch-verified against BOE-A-2007-6820:

- **RIRPF art. 67** = "Colaboración externa en la presentación y gestión de declaraciones"
- **RIRPF art. 68** = "Obligaciones formales, contables y registrales"

These are FORMAL/REGISTRAL obligations, NOT liquidación. The citation
author conflated LIRPF article numbering (where 67 IS Cuota líquida
estatal) with RIRPF's entirely different 67-77 range. This is the
same class of error that wave 61a–68 surfaced in the same file.

**Fix**: remove "liquidación (art. 67-77)" from the RIRPF citation's
quoted_text_es. Retenciones (art. 74-101) and pagos fraccionados
(art. 109-112) stay. Liquidación is covered by the adjacent LIRPF
citation at "arts. 66-80" (acceptable as a summary range).

**Closure**: wave 73a (`HEAD`).

## Stream 3 recommendation (blocklist hardening)

- **L1 (narrative false-positive)**: SKIP. `quoted_text_es` is
  intended to be a role-quote, not educational prose; the wave 69
  ADR docstring already warns contributors. Cost > benefit.
- **L2 (accent-naive)**: HARDEN (~6 LOC). Real-world risk —
  pdfplumber drops diacritics on some PDF fonts. `unicodedata.
  normalize("NFKD", ...)` + ASCII-fold.
  **Closure**: wave 73b (`HEAD`) + 3 new unit tests.
- **L3 (word-order-naive)**: SKIP. Fixing requires parser; real
  BOE text follows canonical word order. Revisit if a concrete
  miscite demonstrates the failure mode.

## Convergence verdict (stream 2)

**NOT CONVERGED.** The wave 72 audit surfaced one new citation
error (H1 above), in the same modelo_100_summary_2025 file that has
been the single most error-prone locus across waves 61a/63a/65a/67a.
Waves 73+ should keep citation-accuracy in scope, with particular
focus on cross-law (Ley vs Reglamento) narrative ranges where the
LIRPF/RIRPF numbering collision lives.

Other citations across the fleet (303/202/200/131/111/180/115/123/
130/390) re-verified clean this cycle — so the citation-error
surface is narrowing but not yet at zero. Estimated 2-3 additional
audit cycles before CONVERGED verdict is defensible.

## Closure status (wave 73)

| Finding | Status | Closing wave |
|---|---|---|
| H1 Modelo 100 RIRPF "liquidación (art. 67-77)" miscite | CLOSED | wave 73a (`HEAD`) |
| L2 accent-naive blocklist matching | CLOSED | wave 73b (`HEAD`) |
| L1 narrative false-positive | SKIP (documented rationale) | wave 72 stream 3 |
| L3 word-order-naive matching | SKIP (documented rationale) | wave 72 stream 3 |

Wave 74 audit loop follows.
