---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:fea9d38f2c8782bc7317a5af48104d4808ec27a0c5dba1ca54cc65e621e2be01'
related: []
---

# `tui-architecture` audit: calculation-correctness campaign handoff

Synthesis of a campaign that asked one question of every guard, default, total and
binding in the engine: **which direction does this fail in, and does anything
watch that direction?**

That question earned its place. It found the whole relief class, it settled the
casilla-18 dispute correctly, and it was arrived at independently by another
author in `test_statutory_cap_schedule.py`, whose docstring says of a flat
constant that under-stated an allowance: "Nothing in this repository watches
over-payment: it produces a valid return, no refusal, and no signal. A gate that
only watches under-declaration would never have found it."

## The asymmetry, stated once

Every gate, advisory and refusal in this engine watches under-declaration. That is
correct and load-bearing. But the opposite error — a relief not applied, a
threshold too low, a rate never reached — produces a **valid return, no refusal
and no signal**, and the taxpayer simply pays more than they owe. The findings
below are sorted on that axis because it is the axis with no coverage.

## Open, over-payment direction

1. **Modelo 360 refund minimums** (400 / 50 EUR) cite `orden-eha-789-2010:art-4`,
   which the catalogue's own note calls the *plazo de presentación* article. The
   establishing provision — the LIVA art. 119 minimum transposing Directive
   2008/9 — is neither catalogued nor bundled. Re-verified at HEAD: the citation
   is unchanged and art. 119 is still absent. These thresholds *refuse* a refund
   below them, so an error denies a taxpayer money they are owed.
2. **Ten parameters outside any orphan gate**, several of them reliefs whose
   non-application over-charges: the Modelo 200 ERD reduced corporate rate, the
   Modelo 303 simplified-regime difficult-justification forfait, and the RIRPF
   art. 95 reduced 7 % retención for specific collectives. The M200 ERD parameter
   is well grounded — a test pins its 23 % value, data type, unit and both
   `legal_refs` — it is *consumption* that nothing asserts.
3. **The received-invoice refusal direction**: a guard refuses a whole filing
   citing under-declaration over a population where the error direction is
   over-payment. The origin of this campaign's question.

## Open, under-declaration direction

4. **Recargo tabaco rung unreachable**: the 1,75 % rate has a validated parameter
   and boxes on Modelo 303 and Modelo 390, but no `IvaCategory` can route a supply
   to it.

## Open, correctness of record rather than of computation

5. **Verification power**: independent AEAT oracle grounding covers **12 of 128**
   registry revisions; 116 have none, and Modelo 100 peaks at 15.5 %. The oracle
   gate holds the relation at zero in both directions but asserts only
   non-emptiness on coverage, so verification power can fall silently. A raw count
   floor is forbidden by the no-tally rule, which makes the ratchet shape a design
   decision rather than an obvious fix.
6. **Citation defects over verified figures** — kept distinct from wrong numbers
   throughout: 90 autonomic scale tables cite the delegating article; Modelo 100's
   2024 savings scale cites a redaction stating a different rate, where two gates
   conflict and neither available citation satisfies both; the 2022 Madrid mínimos
   pin one `corpus_ref` across six years of differing amounts; Modelo 232's
   threshold cites the framework documentation article; and 99 parameters carry a
   `required_text` pinning no number.
7. **Modelo 303 to Modelo 390 handoff**: five tests across two modules need
   genuinely filed quarters. No production defect — the guards are right and the
   tests predate the filing contract.

## Swept clean, do not re-derive

Grounding is now swept **registry-wide**: structural integrity across all declared
parameters, and substance verified by numeric comparison against bundled corpus
text. The last families — IVA rates and their RDL 4/2024 transitional companions,
retención percentages, módulos coefficients, Modelo 714 tariffs, IRNR rates — are
clean, as are the `treaties/`, `iva/` and `categories/` subtrees.

Also swept and clean: the literal-zero restrictive-default class; all five
annual/quarterly reconciliation pairs; the tier and category completeness of every
IVA total; the undated-constant-for-an-annual-figure class (one historical
instance, already repaired); and the tautology hunt, which found no individually
bad calculation test.

Two reference shapes worth copying.
`test_modelo_202_cuota_base_ejercicio_anterior_continuity.py` derives its wiring
assertion from the live snapshot and pins the statutory rate separately, purely as
drift detection. `test_statutory_cap_schedule.py` declares its figures external
authority and names the failure direction in its own docstring.

## What this campaign got wrong

Recorded because the corrections are the most transferable part.

- **A deferral read as a regression.** Modelo 100 2025 casillas 0150, 0611 and
  0613 were characterised as lost reliefs and wired to compute on an operator
  directive. `test_modelo_100_2025_semantic_boundaries.py` declares those rows
  measured cross-revision divergences that must not acquire a producer until
  their evidence is accepted. 39 tests broke; reverted in `8258892c64`, audit
  corrected in `d35d2894ca`. One grep for the casilla id in the test tree would
  have prevented it. **A computed-to-manual diff is a question, not a finding.**
- **Fifteen filter bugs**, each caught by the same discipline: an implausible
  derived set is a filter bug until proven otherwise. The two costly ones were a
  string matcher that could not see "12.450,00" as `12450`, whose counts were
  published before correction, and a reachability probe that returned zero
  because unanchored f-string templates absorbed the entire declared set.
  Validating against a known answer caught the second.
- **A failure count reported from a fragment**: "two" when the log held 61.
- **Reachability inferred from a stem grep** that matched a `semantic_role`
  string rather than a parameter id.

## For an owner

The highest-leverage change is generalising the Modelo 100 orphan-parameter gate
and its `_PRE_STAGED_PARAMETERS` discipline to the other modelos: a parameter may
sit unconsumed provided it is *declared* as such, and the declaration is the gate
future work must clear. That converts the ten ungated parameters from unnoticed to
either consumed or explicitly deferred.

The second is deciding the verification-power ratchet, since coverage can
currently fall without any gate noticing.
