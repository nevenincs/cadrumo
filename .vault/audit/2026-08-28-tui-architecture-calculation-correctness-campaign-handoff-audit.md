---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:c2396a0c3eef6f7ae0d9033685ab51ac4a5d02dd9a3485c981f937c806197650'
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
3. ~~**The received-invoice refusal direction**~~ — **RESOLVED at HEAD, closed.**
   The guard that started this campaign no longer refuses over the whole
   received-invoice population. `_raise_if_screened_invoice_iva_would_be_silent`
   now fires only when `uncovered_authority_evidence > 0`, i.e. when invoice IVA
   would EXCEED the transaction-ledger cuota — which is genuinely the
   under-declaration direction. Its comment states the reasoning: "An unlinked
   purchase invoice whose cuota the ledger already carries is corroborating
   evidence of an operation that IS declared, so refusing there blocks a filing
   whose totals are correct. It stays withheld ... and the operator is told
   through the diagnostic channel instead."

   Fixed by another author, not this campaign. Re-verified by reading the site at
   HEAD rather than trusting the probe: `tmp/direction_audit.py` STILL flags this
   function, because it keyword-matches under-declaration language beside
   input-side markers. That is now a known false positive — do not re-open the
   finding on the probe's say-so.

## Open, under-declaration direction

4. **Recargo tabaco rung unreachable** — re-verified at HEAD, still open, but the
   state has improved and the description is updated accordingly.

   The domain plumbing now exists and is self-documenting: `domain/iva/
   _recargo_equivalencia.py` loads all four LIVA art. 161 rates through the
   validated registry catalogue into a typed `LivaArt161RecargoRates`, with
   `tabaco_rate` covered by its own tests. Both the rate table and the lookup
   function declare *why* tabaco sits outside the rate-keyed axis — "it attaches
   to a product rather than to an accompanying IVA rate, and is read from
   `LIVA_ART_161_RECARGO.tabaco_rate`" — which is the honest form.

   What is still missing is the routing. `IvaCategory` has 21 members and none is
   tabaco, and no production caller reads `.tabaco_rate`; only tests do. So a
   supply of labores del tabaco cannot be classified into the rung, and the
   1,75 % recargo can never be charged.

   **Correction to my own earlier statement of this finding.** I recorded that the
   rate "has a validated parameter and boxes on Modelo 303 and Modelo 390". The
   boxes half is FALSE. Checked at HEAD: neither modelo declares any tabaco
   casilla or binding. Modelo 303 carries three recargo bindings (general,
   reducido, super-reducido); Modelo 390 carries nine (those three plus six
   rate-specific ones at 0,26 / 0,5 / 0,62 / 1 / 1,4 / 5,2). 1,75 appears in none
   of them.

   The true picture is simpler and more coherent than I described: the registry
   holds the legal rate — correctly, art. 161.4.º exists — and models no box for
   it anywhere. What I cannot establish from the bundled material is whether
   AEAT's own record designs for these modelos provide such a box. That is the
   question an owner needs to answer, and it decides whether this is an
   unreachable rung or simply a rate the forms do not collect.

   Direction unchanged: a recargo not charged is under-declaration.

5. **The RIC 80 % is named for a different operation than its article states** —
   latent, and the risk is created by the deferral rather than removed by it.

   `renta-2025-ric-reduccion-rate-maximo` carries `value = 80`, `unit = percent`,
   and a `required_text` pinning "rendimiento neto". Ley 19/1994 art. 27.15 says
   something else: the deducción "se calculará aplicando el tipo medio de gravamen
   a las dotaciones anuales a la reserva y tendrá como límite **el ochenta por
   ciento de la parte de la cuota íntegra** que proporcionalmente corresponda" to
   the Canarias rendimientos netos. The 80 % is a CAP ON THE DEDUCCIÓN in the
   cuota íntegra, not a reduction rate applied to rendimiento neto.

   The figure is right; the framing is wrong. Re-verified at HEAD: the parameter is
   unchanged, and it is consumed by nothing — it sits in the drift gate's
   `_PRE_STAGED_PARAMETERS` allow-list, so the unconsumed half is a *declared
   deferral*, not an orphan.

   That is precisely why the naming matters. Whoever later wires this parameter
   will read its name. Applying 80 % as a reduction to rendimiento neto would cut
   the taxable base by four fifths of net income — a large **under-declaration**.
   Nothing watches a parameter's name, and the deferral guarantees the misreading
   happens later, when the reasoning is no longer to hand.

   **Is this a class? Not demonstrated.** With this instance and the Modelo 232
   one below, an attempt was made to detect the shape mechanically by comparing
   the operation word in a parameter's id against the operation words in its
   cited provision's note. It reported 130 mismatches across 468 parameters,
   which is an artefact, not a finding: `escala` and `tipo` name the same thing,
   `tarifa` is a synonym of `escala`, a provision note describes a whole article
   and so mentions several operations at once, and — the decisive flaw — the
   notes are written in mixed Spanish and English, so LIRPF art. 23's "deductible
   expenses and **reductions**" failed to match an id saying `reduccion`. The
   probe measures language mixture.

   Both real instances were found by reading the article text against what the
   parameter's name and unit claim. That is a semantic judgement, and keyword
   intersection does not approximate it. Treat the two as verified individual
   findings, not as evidence of a population.

### Downgraded on re-verification: the Modelo 100 2024 savings scale

Originally recorded as a two-gate conflict with no citation satisfying both. Both
halves still hold mechanically — the 2024 parameters encode a 0.14 top tranche
while citing `ley-35-2006:art-66` / `:art-76`, whose corpus states 15, and the
redaction that states 14 closes 2024-12-21, nine days before the IRPF devengo, so
the revision-scoped window check refuses it.

But the registry is not silent about this, and my original entry implied it was.
Both cited entries carry the explanation in their own notes, verbatim at HEAD:
"The selected BOE redaction is published 2024-12-21 and in force from 2024-12-22;
**the source note states effects from 2025-01-01 for the Ley 7/2024 change**."

So a reader who follows the citation finds why the encoded 14 differs from the
article's current 15. What is missing is only the mechanical link: nothing
connects "this parameter encodes 14" to "the cited corpus says 15, and the cited
entry's note says why". Ley 7/2024 itself has no catalogued entry — it appears
only in prose in three files — so there is still nothing to cite as the
effect-date provision.

Downgrade this from a contradiction to a documented-but-unmechanised divergence.

## One root cause behind two of the citation findings

The 90 autonomic scale tables citing the delegating LIRPF art. 74, and the 2022
Madrid mínimos pinned to a single corpus_ref, are not two problems. They are one:

**The registry bundles no autonomous-community normative text at all.**

Every autonomic value is grounded one of two ways. The scale tables cite the
*state* article that delegates the scale to the Comunidad rather than the regional
norm that sets it. The Madrid entries — `madrid-dl-1-2010:art-2`, `:art-4`,
`:art-18`, which are **all three** of the autonomous-community entries in the
catalogue — carry `evidence_tier = legal_authority` and
`kind = real_decreto_legislativo`, yet their `corpus_ref` points at an AEAT
*manual* PDF extraction rather than the BOCM text of the DL. All three are
honestly marked `agent_reviewed`, not operator-reviewed.

`madrid-dl-1-2010:art-2`'s own note documents three distinct amount regimes —
2020-2021, 2022 under Ley 8/2022, and 2023 onward under Ley 13/2023 — while the
entry itself is a single undated provision whose corpus states only the latest
figures. Neither amending law is catalogued; both appear only in that prose.

This is why neither finding is repairable the way Modelo 347's and Modelo 232's
were: there, the establishing article was already catalogued and merely uncited.
Here there is no regional corpus to point at, for any region.

What is NOT wrong: the figures. Each affected parameter carries
`source_citations` against the correct filing year's AEAT manual, so the amounts
are cross-checked even where the legal chain is not. The defect is the chain.

## Open, correctness of record rather than of computation

6. **Verification power**: independent AEAT oracle grounding covers **12 of 128**
   registry revisions; 116 have none, and Modelo 100 peaks at 15.5 %. The oracle
   gate holds the relation at zero in both directions but asserts only
   non-emptiness on coverage, so verification power can fall silently. A raw count
   floor is forbidden by the no-tally rule, which makes the ratchet shape a design
   decision rather than an obvious fix.
7. **Citation defects over verified figures** — kept distinct from wrong numbers
   throughout: 90 autonomic scale tables cite the delegating article; the 2022
   Madrid mínimos
   pin one `corpus_ref` across six years of differing amounts.

   **99 parameters carry a `required_text` pinning no number** — re-verified at
   HEAD, and sharper than first recorded. The mechanism is real and *enforced*:
   `registry/_validate_evidence.py` requires every `required_text` phrase to
   appear verbatim in the bundled source, failing registry validation otherwise,
   and the bundled authority threads a `source_root` so the check runs on the
   standard load path. Coverage is total — 0 of 458 numeric parameters lack a
   `required_text`, and 359 pin at least one digit.

   The gap is strength, not absence. For those 99, the check confirms the cited
   source *discusses the topic* without constraining the *figure*: a wrong number
   would pass validation untouched. One structural caveat worth knowing — the
   text check is skipped entirely when the validator is built without a
   `source_root`, so any caller constructing one that way gets no verification at
   all.

   ~~Modelo 232's threshold cites the framework documentation article~~ —
   **FIXED in `accd590f4e`.** Orden HFP/816/2017 art. 2 was already catalogued,
   corpus-backed and operator-reviewed, its note saying it "Define los umbrales
   de operaciones vinculadas" and its excerpt reading "Operaciones específicas
   ... supere los 100.000 euros". Added as the establishing provision; 28 Modelo
   232 registry tests pass.

   Re-verifying it surfaced a **separate, still-open** observation. Art. 2 sets
   TWO thresholds: 250.000 EUR for operaciones with the same related party, and
   100.000 EUR for operaciones específicas. The registry declares ONE parameter,
   `modelo-232-related-party-threshold-eur`, carrying 100.000 — the *específicas*
   figure under a *related-party* name — and does not model the 250.000 general
   threshold at all. Latent today, because the parameter is one of the ten nothing
   consumes; the same trap as the RIC naming, and it will be sprung by whoever
   wires it.
8. **Modelo 303 to Modelo 390 handoff**: five tests across two modules need
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

**Modelo 390's recargo exclusion, re-verified with a mechanical proof.** The
annual devengada total sums the three tier bindings and excludes the
rate-specific ones. That is correct, and the reason is visible in the selectors:
`...-reducido-cuota` carries `applied_rates = None` — rate-blind, so it sums
every reducido-tier recargo — while `...-tipo-1-4-cuota` and
`...-tipo-0-62-cuota` carry byte-identical selectors narrowed to `0.10` and
`0.05`. The tier binding is a strict superset of both, so including all three
would double count, and the 2023-2024 transitional 5 % recargo IS captured by the
tier row. Verified 2023, 2024 and 2025.

One correction to how this was recorded: the excluded set is **not always six**.
2024 and 2025 exclude six; 2023 excludes four, because that revision declares
seven recargo casillas rather than nine. The invariant is the superset relation,
not the count.

**The five annual/quarterly reconciliation pairs, re-verified at HEAD.** All five
declare `annual_summary` relations from the quarterly modelo, and every pair
reconciles both an amount measure and a tax measure:

| pair | relations |
|---|---|
| M190 ← M111 | 10: nine per-block *importe* boxes (02, 05, 08, 11, 14, 17, 20, 23, 26) plus the retenciones aggregate 28 |
| M180 ← M115 | 2: base 02, retenciones 03 |
| M193 ← M123 | 2: base 06, retenciones 09 |
| M296 ← M216 | 2: base 10, retenciones 13 |
| M390 ← M303 | 3: cuota devengada total, cuota deducible total, resultado régimen general |

Two wording refinements, neither a substantive change. The pairs were recorded as
reconciling "base and retenciones": true for four of them, but M390 ← M303
reconciles the IVA-appropriate measures instead — devengada, deducible and
resultado — since an IVA return has no retenciones. And the M190 shape settles an
earlier confusion of mine: the nine per-block rows are *importe* boxes, while the
retenciones side reconciles at the aggregate casilla 28, exactly as recorded.

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
