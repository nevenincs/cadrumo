---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S208]]"
---

# cross-domain-continuity Code Review

## Commit

`71398c709` -- #209 Plan de empleo Art. 52 LIRPF reduccion not applied (Aitor G4)

## Status: PASS

---

## Critical-Question Answers

**Q1 -- Casilla 0468 flip + formula wiring**

0468 was correctly flipped from untyped (no `input_kind`, no `formula`) to `input_kind = "computed"` with `formula = "renta-2024/2025-reduccion-prevision-social-total"` in both revision casilla files. The new formula targets 0468. Both base-liquidable-general formulas were extended to subtract 0468 from 0500. The renta-cuota-chain constructs for both years insert the two new formulas before `base-liquidable-general`, ensuring correct topological order. All four wiring points are correct.

**Q2 -- Cap formula: min(0467, 10000, 30% x 0432)**

Both new formula files (`0182-renta-2024-reduccion-prevision-social-total.toml` and `0196-renta-2025-reduccion-prevision-social-total.toml`) implement `op = "min"` with three args: `{ casilla = "0467" }`, `{ literal = "10000" }`, and `{ op = "percent", args = [{ casilla = "0432" }, { literal = "30" }] }`. Both statutory caps are wired. Casilla 0432 is the `saldo neto de los rendimientos a integrar en la base imponible general` -- the correct base for the 30% Art. 52 cap. Correct.

**Q3 -- Art. 51 individual cap (EUR 1,500) -- separation**

Casilla 0463 (`aportaciones individuales y contribuciones empresariales`) is the Art. 51 path. It flows into 0467 as a separate summand alongside 0426 (plan de empleo worker contribution). Formula `importe-derecho-reduccion-pension-suma` sums them independently; 0468 then applies the Art. 52 aggregate cap on the combined 0467. The Art. 51 individual EUR 1,500 cap is not enforced by a distinct formula in either revision -- this is pre-existing scope, not regressed by this commit. No commingling introduced.

**Q4 -- legal_refs provenance**

`ley-35-2006:art-52` is correctly registered in `irpf.toml` with `evidence_tier = "legal_authority"`, `corpus_ref`, `permalink`, and `required_text`. Both new formula files carry `legal_refs = ["ley-35-2006:art-52"]`. Both base-liquidable-general formulas now reference both `art-50` and `art-52`. The chain constructs add `art-52` to their `legal_refs` lists. The 0468 casilla files carry only `["ley-35-2006:art-52"]`, dropping the broader Art. 49/17-32 cluster -- that cluster belongs to upstream input casillas, not the aggregate-cap casilla. The narrowing is architecturally correct.

**Q5 -- Wizard parity (#228/#239 family)**

No wizard changes in this commit. Casilla 0426 is a direct form-input; no wizard flag is required. `_SETUP_OPTION_INFOS` is not implicated. No regression.

**Q6 -- Locale parity es/en/ca/hu**

No locale `.yml` changes in this commit. New formula identifiers are internal registry IDs, not user-facing strings. Locale parity is N/A for this commit.

**Q7 -- Oracle test: 0426 = 4,200, trabajos = 56,500 -> 0500 = 52,300**

`test_plan_de_empleo_reduccion_below_caps_full_amount` covers this shape on the 2025 revision. Oracle derivation is documented inline in the test docstring. Asserts `0467 = 4200.00`, `0468 = 4200.00`, `0500 = 52300.00`. Real-behavior test, no mocks, not tautological: a missing 0468 subtraction from 0500 would yield 56500 and fail.

**Q8 -- Anti-tautology: aportacion = 15,000 -> reduccion capped at EUR 10,000**

`test_plan_de_empleo_reduccion_capped_at_10000` covers the absolute cap scenario: `0003 = 80000`, `0426 = 15000`; `min(15000, 10000, 24000) = 10000 -> 0468 = 10000`; `0500 = 70000`. Asserts both. Would fail if the `literal = "10000"` cap were absent (would yield 15000) or if the 0468 subtraction were missing from 0500 (would yield 80000). Correct anti-tautology proof.

**Q9 -- Both 2024 + 2025 revisions**

Registry changes are symmetric across both years: casilla flip, new formula file, base-liquidable-general extension, chain construct update. Oracle tests exercise the 2025 revision only; flagged LOW in findings.

---

## Standing Gate Sweep (G1-G6)

- G1 -- No naked env reads: No production Python changed. PASS.
- G2 -- Typed pydantic at boundaries: No new boundary types introduced. PASS.
- G3 -- tr() for user messages: No user-facing strings changed. PASS.
- G4 -- No locale yml hand-edits: No yml changes. PASS.
- G5 -- No shims/re-exports/duplication: No shims. Pre-existing pension-suma formula reused correctly via chain ordering. PASS.
- G6 -- No tautological tests: Expected values derived from Art. 52 statutory rules; both tests would catch formula regression. PASS.

---

## Findings

CHAIN-001 | LOW | 2024 revision lacks a dedicated oracle test for the plan-de-empleo reduccion path.

Both formula sets are symmetric but the oracle tests only exercise the 2025 revision. A mirrored 2024 test using `_scenario_2024` would close the coverage gap. No immediate risk; the registry change is symmetric and formula logic identical.

LEGAL-001 | LOW | 0468 casilla legal_refs narrowed to art-52 only.

Prior definition carried a broad Art. 49/17-32 cluster inherited from neighbouring placeholder casillas. Narrowing to art-52 is architecturally correct -- Art. 52 is the sole authority for the aggregate cap casilla. Noted for awareness; no action required.

---

## Summary

Root cause resolved cleanly. 0468 flipped to computed with the correct `min(0467, 10000, 30% x 0432)` formula. 0500 now subtracts 0468. Chain topological order correct for both 2024 and 2025. Both statutory caps wired. Art. 51 individual path (0463) separate and unaffected. Legal provenance complete end-to-end. Oracle tests cover the nominal shape from the Aitor brief and the EUR 10k cap anti-tautology. No safety, concurrency, or architectural violations. No shims. All G1-G6 gates pass.

**Verdict: PASS -- safe to merge.**
