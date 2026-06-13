---
tags:
  - '#audit'
  - '#r7-state-scale'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-29-cross-domain-continuity-audit]]"
---

# R7 cluster-T M100 2024 state-scale grounding verdict

## Scope

Read-only grounding investigation triggered by Eva round-10 testimonial
(commit `e002d17d3`): salary €52k → 0500 = 52000 → 0532/0533 = 0.00.
Compares commit `c47211b03` (2024 wiring) against `6eda54425` (2025)
and `d64dfb7ff` (2023). Determines whether S361 coder1 dispatch can
proceed or must be paused pending R7 fix.

## Chain anatomy (2024 registry)

The general-base tarifa chain runs:

```
0500 (base liquidable general, manual/bound input)
  → 0505 = max(0, 0500 - 0527)   [formula 0168]
  → 0528 = lookup_bracket(0505, renta-2024-escala-estatal-base-general)  [formula 0148]
  → 0530 = lookup_bracket(0521, renta-2024-escala-estatal-base-general)  [formula 0149]
  → 0532 = 0528 - 0530            [formula 0152]
  → 0545 = 0532 + 0540            [formula 0154]
  → 0570 = 0545 - deducciones     [formula 0156]
  → 0585 = sum(0570, 0568, ...)   [formula 0158]
```

All formula TOML files exist in
`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/`.
All target casillas are marked `input_kind = "computed"` with the
correct `formula` id. The bracket parameter
`renta-2024-escala-estatal-base-general` (file `parameters/0016-...toml`)
carries six brackets with `valid_from = 2024-01-01, valid_to =
2024-12-31`, matching the engine's default `filing_period =
date(2024, 12, 31)` (line 149 of `_formula_runtime.py`).

The `renta-cuota-chain` construct (`constructs/0001-renta-cuota-chain.toml`)
lists all these formula IDs. More importantly, `formula_evaluation_order`
in `_runtime_graph.py` evaluates ALL `revision.formulas` in topological
order — constructs are metadata only. The loader (`_loader.py`) merges
every fragment TOML under `revisions/2024/` via `_REVISION_APPEND_ARRAYS`
which includes `"formulas"`.

Unit test `test_renta_escala_estatal_bracket_resolution.py` parametrises
over `_BACKPORTED_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)` and
asserts BOE-published cuota íntegra breakpoints for 2024, confirming
the bracket table resolves correctly at the parameter level.

Contract test `test_renta_cuota_chain_contract.py::test_renta_cuota_chain_present_in_all_supported_revisions`
checks that 2024 formula targets include 0532 and 0533. This passes.

## Commit comparison

| Year | Commit | Method | Status |
|------|--------|--------|--------|
| 2022 | `fbe9b1525` | fragment TOML | confirmed present |
| 2023 | `d64dfb7ff` | fragment TOML | confirmed present |
| 2024 | `c47211b03` | fragment TOML (landed May 8 2026) | confirmed present |
| 2025 | `6eda54425` | fragment TOML | confirmed present |

The 2024 commit `c47211b03` was titled "Wire IRPF state-scale formulas
for 2024 (Phase 5)" and added formulas 0148/0149/0150/0151/0152/0153
plus the bracket parameter `renta-2024-escala-estatal-base-general`.
The diff also shows 0532/0533 casilla entries being given `input_kind =
"computed"` via the casilla fragment files.

## Root cause of Eva's 0532/0533 = 0

The registry wiring is structurally complete and correct. Eva's
testimonial observation must arise from one of:

1. **Missing 0500 input.** If 0500 was zero (no salary input supplied
   as a direct casilla override to 0500), 0505 = max(0, 0 - 0) = 0,
   and the lookup_bracket on 0 returns the base-tier fixed_addition = 0
   plus 0.095 * (0 - 0) = 0. Eva reports "0500 = 52000 correctly
   populated" but this was likely populated via a rendimientos binding
   that flows to 0435 (base imponible general) and then 0500 (base
   liquidable general). If the binding chain to 0500 was incomplete or
   if 0527 (anualidades alimentos hijos) carried a spurious value equal
   to 0500, then 0505 = 0.

2. **Engine version mismatch.** If Eva's testimonial ran against a
   cached registry snapshot that predates `c47211b03` (landed May 8
   2026), the fragment formulas would be absent. The LRU-cached loader
   invalidates on `(path, byte_count, mtime_ns)` fingerprints; a warm
   process with a stale cache would compute with the pre-wire registry.

3. **CCAA binding absent causing silent abort.** The autonomic formula
   `lookup_bracket_by_ccaa` (formula 0150 targeting 0529) raises
   `RegistryValidationError` if the CCAA binding is not supplied. This
   would abort calculation before 0529/0533 evaluate. The estatal path
   (0528/0532) uses plain `lookup_bracket` with no CCAA dependency and
   would still execute — unless an abort propagates before 0528 is
   reached in topological order. If 0529 sorts before 0528 and the
   engine does not catch per-formula errors, the entire run could abort
   with 0532 left at its initial (zero) value.

Root cause 3 is most likely given the asymmetry: the report says both
0532 (estatal) AND 0533 (autonomic) = 0. If it were merely a missing
CCAA binding aborting 0529, only 0533 would be zero; 0532 should
still compute. The fact that BOTH are zero points to a zero 0505
(causes both to compute to 0), or a formula ordering abort that
zeroes both.

**Recommended diagnostic:** run with `--casilla "0505=52000"` instead
of relying on the binding chain, and supply `--binding
renta-2024-profile-tax-residence-ccaa=madrid`. If 0532 becomes
non-zero, the issue is upstream in the 0500 binding path (root cause 1
or binding chain for 0500 itself). If still zero, suspect cache or
engine-version mismatch.

## Verdict

**Verdict (A): S361 is structurally independent of R7's root cause.**

The 2024 registry has the complete 0500 → 0532 → 0585 chain. The
formula TOML files, bracket parameters, and casilla `input_kind`
declarations are all correct and present (committed `c47211b03`, May 8
2026). Unit and contract tests pass for 2024. The S361 settlement tail
(0587→0670) is a separate missing-formulas gap confirmed by the
5daaaac83 triage — those six casillas have no 2024 formula regardless
of whether 0532 computes.

However, R7's operational root cause (why Eva sees 0532 = 0 at
runtime) is UNCONFIRMED at the registry level. The registry is
correct; the runtime failure is either upstream binding chain (0500
not reaching 0505), a CCAA-binding absence causing formula order
abort, or a stale cached loader.

## Recommendation for coder1 (S361)

**PROCEED with S361 dispatch.** S361 authors 0587/0595/0598/0609/
0610/0670 formula TOMLs and casilla input_kind flips — a completely
disjoint file set from anything R7 touches. S361's correctness does
not depend on 0532 resolving; it depends on 0585/0586, which the
registry already wires. When R7's runtime root cause is diagnosed
(binding chain gap or CCAA missing), that fix will be a separate
dispatch.

**Additionally dispatch an R7 runtime diagnosis step** to determine
which of the three root causes above applies, with the diagnostic
invocation above as the first action. This is independent of S361
and can run in parallel.

The S361 triage oracle expectation (0587 = 15,141 from Roberto
scenario base liquidable €55.5k) was stated as an oracle target
for the completed chain — it implicitly assumes 0585/0586 receive
real values. Once S361 lands, the oracle test MUST be run with
explicit `--casilla "0500=55500"` and `--binding
renta-2024-profile-tax-residence-ccaa=madrid` to bypass any upstream
binding chain gap, producing a clean end-to-end registry computation
that validates the new settlement tail formulas independently of R7.
