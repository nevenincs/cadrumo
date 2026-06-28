---
tags:
  - '#exec'
  - '#cli-ledger-testimonials'
date: '2026-06-09'
modified: '2026-06-09'
step_id: P05.S13
related:
  - '[[2026-06-03-cli-ledger-testimonials-plan]]'
  - '[[2026-06-09-cli-ledger-testimonials-audit]]'
  - '[[2026-06-03-cli-ledger-testimonials-audit]]'
---

# `cli-ledger-testimonials` `P05.S13` step record

## Step

P05.S13 — Re-run skeptic/foreign/crossyear personas post-fix to close still-open:
silent-under-declaration on calculated return, M303 special-IVA casilla routing,
prior-year previous_filing carry across a filed period.

## Execution

Probe script `probe_p05s13.py` ran three persona scenarios against the real
application layer using `isolated_runtime_profile` context (real encrypted SQLite
repos, no mocks). All engine calls used real `calculate_modelo_revision` and
`verify_modelo_revision` with real binding resolution and formula evaluation.

### Persona 1 — Skeptic: silent-under-declaration on M130

**Scenario A — Art. 110.3b high-retention exemption path:**

The engine correctly sets C17 = 0.00 when C06/C01 = 0.75 >= 0.70. The verification
report fires an `advisory` finding (kind `advisory`, severity `warning`). The path
is NOT silent. Registry predicate: `0003-art110-3b-high-retention-advisory.toml`.

**Scenario B — General implies_nonzero guard:**

M130 has no `implies_nonzero` predicate beyond the Art. 110.3b case. Analysis shows
this is structurally different from M200: M130's cuota chain is fully formula-computed
from the declared income (C01-C02), so there is no structural path for "positive income
produces artificially zero cuota" except the Art. 110.3b branch already guarded.

Finding M1 (MINOR/INFORMATIONAL): M130 lacks a general implies_nonzero guard. Deferred
to follow-up campaign iteration. Does NOT block P05.S13 closure.

**Verdict: PARTIALLY CLOSED** — Art. 110.3b path guarded; general case MINOR/INFORMATIONAL.

### Persona 2 — Foreign: M303 special-IVA casilla routing

All routing paths verified correct via `aggregate_iva_ledger_observations` and registry
snapshot inspection:

- `INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE` produces correct observation; M303 binding
  `modelo-303-iva-autorepercutido-intracomunitaria-cuota` selector lists this category.
  Output: `observations: ['intra_community_acquisition_reverse_charge']`.
- `EXPORT_THIRD_COUNTRY_ZERO_RATED` routes to casilla 60 (base 3000.00), not casilla 59.
- `INTRA_COMMUNITY_SUPPLY` (DE counterparty) routes to casilla 59 (base 5000.00), not 60.
- `RECARGO_EQUIVALENCIA` produces `unsupported_iva_category` issue (intentional — classified
  as `_NON_DECLARABLE_IVA_CATEGORIES` in `_iva_ledger.py`). Not silently dropped. COSMETIC.

**Verdict: VERIFIED CLOSED.**

### Persona 3 — Cross-year: previous_filing carry across a filed period

All carry-forward paths verified correct:

- Casilla 15 operator override at 3T (`2694`) accepted: C15 = 2694, C17 = 806.00
  (C14 3500 - C15 2694 - C16 0). No unexpected blocking findings.
- 1T fresh period: C15 = 0 (absent-by-design, `max_year_delta=0` binding constraint).
- M303 `modelo-303-compensacion-pendiente-anteriores` previous_filing binding present
  in registry snapshot.
- `test_previous_filing_casilla_override.py` (3 tests) passes at HEAD.

**Verdict: VERIFIED CLOSED.**

## Status

P05.S13 closed. Two of three still-open items verified fully closed (M303 routing,
previous_filing carry). Item 1 (silent-under-declaration) partially closed: Art. 110.3b
path guarded; general M130 implies_nonzero gap graded MINOR/INFORMATIONAL and deferred.

## Artefacts

- Probe script: `probe_p05s13.py` (root of worktree)
- Audit record: `2026-06-09-cli-ledger-testimonials-audit.md`
- Plan: `2026-06-03-cli-ledger-testimonials-plan.md` (P05.S13 checked)
