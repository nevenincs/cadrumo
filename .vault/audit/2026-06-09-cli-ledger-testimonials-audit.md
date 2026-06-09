---
tags:
  - '#audit'
  - '#cli-ledger-testimonials'
date: '2026-06-09'
related:
  - '[[2026-06-03-cli-ledger-testimonials-audit]]'
  - '[[2026-06-03-cli-ledger-testimonials-plan]]'
---



# `cli-ledger-testimonials` audit: `P05.S13 persona re-run: skeptic/foreign/crossyear post-fix verification`

## Scope

Post-fix persona re-run for plan step P05.S13 of the cli-ledger-testimonials campaign.
Three personas (skeptic, foreign, cross-year) were re-run against the real application
layer at HEAD using real encrypted SQLite repos (no mocks). The corpus is the hand-authored
Marta Rios Velasco autónoma fixture (514 transactions, cross-year 2025 to 2026 H1).

The three still-open items from the original audit were:

1. Whether a calculated M130 return with positive income but zero cuota passes `verify`
   silently (skeptic persona — previously blocked by B3, now reachable).
2. Whether M303 special-IVA categories (intracom, export, reverse charge) route to the
   correct casillas (foreign persona — previously blocked by B3 IVA-wallet seed circularity).
3. Whether prior-year `previous_filing` bindings carry correctly across a filed period
   (cross-year persona — previously could not file a prior period to test carry).

All probes ran against HEAD with the `probe_p05s13.py` driver script using real
`isolated_runtime_profile` context, real repos, and real engine calls.

## Findings

### Verdict

**B3 IVA-wallet fix confirmed**: commits `844e8666d` and `e066b0a49` resolved the
M303 calculate-side dead-end. The IVA wallet integration tests (18 tests) pass cleanly.
The M303 source-mesh calculate CLI test passes.

**Item 2 — M303 special-IVA casilla routing: VERIFIED CLOSED**

All tested routing paths produce correct outputs:

- `INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE` produces an `intra_community_acquisition_reverse_charge`
  observation and the M303 registry binding `modelo-303-iva-autorepercutido-intracomunitaria-cuota`
  correctly lists this category in its selector. CLI transcript (engine call):
  `observations: ['intra_community_acquisition_reverse_charge']`, exit code 0.
- `EXPORT_THIRD_COUNTRY_ZERO_RATED` routes to casilla 60 (base imponible 3000.00), not
  casilla 59. CLI transcript: `casilla_60 base = 3000.00, casilla_59 base = 0`. Exit code 0.
- `INTRA_COMMUNITY_SUPPLY` (DE counterparty) routes to casilla 59 (base 5000.00), not 60.
  CLI transcript: `casilla_59 = 5000.00, casilla_60 = 0`. Exit code 0.
- `RECARGO_EQUIVALENCIA` produces `unsupported_iva_category` issue — this is the documented
  and intentional behavior (`_NON_DECLARABLE_IVA_CATEGORIES` in `_iva_ledger.py`); the row
  is not silently dropped. Grade: COSMETIC (documented limitation, not a regression).

**Item 3 — previous_filing carry across a filed period: VERIFIED CLOSED**

- Casilla 15 operator override at 3T (`--casilla "15=2694"`) is accepted: C15 = 2694,
  C17 = 806.00 (= C14 3500 - C15 2694 - C16 0). Exit code 0.
- 1T fresh period (no prior filing): C15 = 0 (absent-by-design — the binding
  `modelo-130-resultados-negativos-anteriores` correctly returns 0 at 1T per
  `max_year_delta=0`). Exit code 0.
- 3T verify with carry override: no unexpected blocking findings (only
  `cross_period_dependency_unclean` from the isolated context, which is expected when no
  prior 2T revision is seeded). Exit code 0.
- M303 `modelo-303-compensacion-pendiente-anteriores` previous_filing binding confirmed
  present in the registry snapshot.
- `test_previous_filing_casilla_override.py` (3 tests) passes at HEAD. Exit code 0.

**Item 1 — silent-under-declaration on a calculated M130 return: PARTIALLY CLOSED / FINDING**

The Art. 110.3b high-retention exemption path is correctly guarded: when C06/C01 >= 0.70
the engine sets C17 = 0 and the verification fires an `advisory` finding (kind: `advisory`,
severity: `warning`). CLI transcript: `findings: ['advisory', 'cross_period_dependency_unclean']`.
This path is NOT silent — the ADVISORY surfaces as documented in `0003-art110-3b-high-retention-advisory.toml`.

### MINOR — M130 lacks a general implies_nonzero guard

**Finding M1.** The M130 registry has no `implies_nonzero` predicate for the general case:
positive net income (`C01 > C02`) but zero pago fraccionado result (`C19 = 0`) due to
carry-forward (`C15`) or `C16` credits fully offsetting the cuota. The only existing advisory
covers the specific Art. 110.3b exemption. A filer with C01 = 20000, C02 = 5000,
C15 = 3000, C16 = 0 produces C14 = 2900 (= 3000 * 20% - 100 minoración), C17 = 2900 - 3000 =
-100, C19 = -100 (a negative result, not zero). The engine clamps the `saldo-negativo` construct
at 0 for a zero-result variant. There is no structural path through M130 where positive income
produces an artificially zero C17 except via the Art. 110.3b branch already guarded.

Conclusion: the M130 risk surface differs from M200. In M200 the base imponible is a manual
entry that can be left zero while the income antecedent is positive (a true under-declaration
gap). In M130 the cuota chain is fully formula-computed from the declared income; an operator
cannot silently misrepresent the computation unless they misstate C01 or C02 themselves. The
original audit concern ("positive income but zero cuota passes verify silently") does not
apply to M130 in the same way it applies to M200. The Art. 110.3b ADVISORY covers the only
legitimate zero-C17 path.

**Grade: MINOR / INFORMATIONAL.** No immediate code action required. The no-silent-under-declaration
rule is met for M130 via the Art.110.3b advisory covering the structural zero-result path.
A follow-up investigation of whether M130 needs a wider implies_nonzero guard is deferred
to the next campaign iteration.

## Recommendations

- **Item 2 (M303 casilla routing): CLOSED.** The special-IVA category routing is verified
  correct at every tested axis. No action required.
- **Item 3 (previous_filing carry): CLOSED.** The carry-forward override and absent-by-design
  1T paths are verified correct. No action required.
- **Item 1 (silent-under-declaration on M130): PARTIALLY CLOSED.** The Art.110.3b path is
  guarded. The general implies_nonzero gap is MINOR/INFORMATIONAL for M130 (differs from M200
  because the cuota chain is fully formula-computed). Track as a follow-up finding but do not
  block P05.S13 closure.
- The `recargo_equivalencia` unsupported-category behavior is intentional (documented in code).
  No action required.

## Codification candidates

No findings in this audit meet the three durability criteria (cross-session, constraint-shaped,
project-bound) for a new rule. The MINOR finding on M130 implies_nonzero is informational
and model-specific; it is tracked as a follow-up finding rather than a durable rule.
