---
tags:
  - '#audit'
  - '#workbook-parity-charter'
date: '2026-05-15'
modified: '2026-05-15'
related:
  - "[[2026-05-04-calculation-truth-registry-legal-grounding-review-audit]]"
  - "[[2026-05-14-legal-grounding-audit-reference]]"
---

# `workbook-parity-charter` audit: `workbook-parity oracles are universally inert across all AEAT modelos`

## Scope

Surveyed every `[[revisions."*".workbook_parity_refs]]` block across
`registry/aeat/modelos/` to determine whether any modelo runs an
executable parity oracle against AEAT-published XLS workbooks. The
mandate at `.claude/rules/no-tautological-calculation-tests.md`
explicitly names workbook-parity replay as the primary form of
external verification — calculations are not legally grounded if no
authoritative cross-check confirms registry output against AEAT's
own published computation.

## Findings

### Universal `runner_required = false`

Every `workbook_parity_refs` block in the entire registry — across
M036, M100/2020-2025, M111, M115, M123, M130, M131, M180, M190, M193,
M200, M202, M232, M303, M308, M309, M322, M347, M349, M353, M360,
M369, M390, M720, M840 — is declared with `runner_required = false`
and `formula_coverage = "record_design_layout"`. No modelo runs an
executable XLS oracle.

### What this actually verifies

The `formula_coverage = "record_design_layout"` annotation means
parity tests verify the field-layout of the AEAT-published Diseño
de Registro file (positions, lengths, encoding, padding) — not the
arithmetic. A registry whose formula produces a wrong number against
AEAT's truth will pass every parity test currently in place, because
no test feeds inputs to the AEAT XLS and compares the result to the
registry.

### Why this matters

This is the largest single attack surface for silent calculation
drift in the entire codebase. Every refactor, every retention-rate
update, every legal-grounding pass, every per-section semantic
cleanup runs the risk of nudging a formula's arithmetic without
detection. The legal-grounding audit may green-light a citation
graph, but the underlying number can still be wrong against AEAT.

### Concrete examples surfaced during the broader audit

- M100/2025 casilla 0585 `renta-2025-cuota-liquida-estatal-incrementada`
  was flagged for possible sign-semantics error: the formula uses
  `op = "sum"` for what LIRPF art. 67 prescribes as cuota íntegra
  MINUS deducciones. Manual inspection confirmed the upstream casilla
  0570 applies `negate()` to each deduction component, so 0585's
  additive sum over the post-negation result is correct. No executable
  oracle could verify this without manual inspection.
- M130 minoración thresholds at registry/aeat/modelos/130.toml lines
  430–458 (step-function 100/75/50/25/0€ at income ranges
  9000/10000/11000/12000€) are stated correctly per RIRPF art. 110.3
  but unvalidated against any AEAT numerical fixture.
- M115 retention rate parameter `irpf.urban_rental_withholding_rate
  = 19` matches LIRPF art. 101.8 textually but is not arithmetically
  cross-checked.

## Recommendations

### Why the gap exists

Workbook parity requires the AEAT-published XLS / xlsm files to be
available in the corpus, a runner that can load and evaluate them,
and a per-modelo bridge that maps registry casillas to workbook
cells. None of these are in place today; the `workbook_parity_refs`
declarations describe an intent without an implementation.

### Path to closure (multi-step)

1. Inventory the AEAT-published Diseño de Registro and Manual XLS
   files already in `corpus/aeat_official/disenos_registro/` and
   compare to the per-modelo `aeat-dr-{id}-{year}` source_ref
   declarations. Identify modelos where the XLS is corpus-present
   but the parity wiring is missing.
2. Pick one self-contained modelo for the first executable oracle —
   M115 is a strong candidate: 5 casillas, single retention-rate
   parameter, formula chain is `casilla-03 = 02 × rate; casilla-05 =
   03 − 04`. The AEAT XLS has both casillas computed natively.
3. Stand up a workbook-runner contract that takes synthetic inputs,
   feeds them to the AEAT XLS via openpyxl or LibreOffice headless,
   and returns the result. Compare to the registry output. The
   xlsm calc-engine choice is the architectural unknown.
4. Generalise to the retention-modelo family (M111, M115, M123,
   M180, M190, M193) — they share the same simple chain.
5. The annual-summary modelos (M180, M190, M193, M347, M349) are
   harder because their inputs are aggregated multi-period
   observations; per-section parity may be more tractable than
   full-form parity.
6. M200 (132k lines, 9770 legal_refs blocks) is the largest single
   target and the most reward; defer until the simpler families
   are working.

### Per-case mitigation in lieu of parity oracles

Until oracles are wired, the registry relies on:

- Textual cross-check of `required_text` against the BOE excerpt
  (catalogue verification handles this).
- Manual review of formula structure against BOE article prescription
  (e.g. the 0585 sign-semantics inspection done in this audit cycle).
- Per-casilla legal grounding cleanup (~280 casillas in this audit
  cycle had over-broad citations stripped to surface the actual
  substantive law each formula implements).

These mitigations close the citation graph but cannot catch
arithmetic drift on a correctly-cited formula. Workbook parity
remains the only external authority that catches that class of bug,
and no modelo runs one today.

### Risk classification

This is the highest-severity un-mitigated finding from the audit
cycle. All other findings have been resolved (over-broad citations,
tautological tests, code duplication, schema drift, corpus integrity
false-positives). Workbook parity is the last structural gap and the
one most likely to manifest as silently-wrong tax filings.

## Conclusion

The codebase's calculation correctness story currently rests on
legal-grounding completeness and manual formula review — both of
which the audit cycle materially improved. Neither catches
arithmetic drift on a correctly-cited formula against AEAT's truth.
The path forward requires a workbook runner contract and per-modelo
oracle wiring, starting with M115 as the simplest viable target.
