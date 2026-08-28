---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:02b8e5cb43454b22fc7cffd26d27918bed8ba71fa5a11fd6f035ce75d3185708'
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

**The Modelo 303 [158]/[170] allocation, re-verified — and a second worked
example of why ids must never be joined across years.** Tracing the binding
`modelo-303-recargo-equivalencia-super-reducido-cuota` through every revision:

| revision | box carrying it |
|---|---|
| 2022 | none — the rung is not declared that year |
| 2023, 2024 | casilla **18** |
| 2025, 2026 | casilla **170** |

Modelo 303 was renumbered between 2024 and 2025 and the registry follows the
*concept*, not the box: no binding is attached to more than one casilla in any
revision, so nothing is double counted. Casilla 18 still exists in 2025 and 2026
carrying something else entirely.

That is the same hazard as Modelo 123's 8-to-14-box renumbering, now confirmed in
a second modelo — and in one this campaign actively edited, since the aggregation
fixture's casilla-18 override was written against the 2024 numbering. Anyone
comparing Modelo 303 casilla 18 across the 2024/2025 boundary compares unrelated
boxes.

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

## Re-verification of the Madrid finding at HEAD, and a correction to how it was read

The Madrid finding above was briefly withdrawn in a working note and is
**re-instated**. The withdrawal checked the wrong artefact. Both facts below are
true at once, and confusing them is the trap:

- The **parameter's** `source_citations` are year-correct. The 2022 mínimos cite
  `aeat-renta-2022-manual-parte1` → `corpus/manuals/renta/2022/part1/`, and all
  three figures (2.498,40 / 2.810,70 / 2.914,80) appear verbatim in that year's
  extracted text under "Mínimo por descendientes". Their `required_text` pins the
  digits and matches exactly. **The figures are grounded.**
- The **legal catalogue entry's** `corpus_ref` is the defect, and it is unchanged:

| entry | `evidence_tier` / `kind` | `corpus_ref` | `effective_from` | review |
|---|---|---|---|---|
| `madrid-dl-1-2010:art-2` | `legal_authority` / `real_decreto_legislativo` | `corpus/manuals/renta/**2025**/part1/source.pdf.extracted.md#madrid-minimo-descendientes` | 2020-01-01 | `agent_reviewed` |
| `:art-4` | same | `corpus/manuals/renta/**2025**/part2-deducciones-autonomicas/...#madrid-nacimiento-adopcion` | 2023-01-01 | `agent_reviewed` |
| `:art-18` | same | `corpus/manuals/renta/**2025**/part2-deducciones-autonomicas/...#madrid-nacimiento-adopcion-limites` | 2023-01-01 | `agent_reviewed` |

Each declares itself the regional *real decreto legislativo* while pointing at an
AEAT **manual** extraction, and `art-2` spans from 2020 on a single corpus stating
only the latest figures. That is the "one `corpus_ref` across six years of
differing amounts" claim, confirmed concretely rather than asserted.

An authenticity note worth keeping, since this audit distinguishes transcribed
from authored excerpts: the 2022 `required_text` reproduces the manual's own
grammatical slip, "por el primer descendient**es**". A fabricated excerpt would
carry correct Spanish, so the slip is positive evidence of transcription.

### A probe caveat that qualifies this audit's grounding tally

The `numeric_match` sweep behind the "every encoded number is stated" count
resolves **only** `legal_refs` → legal-catalogue `corpus_ref`. Parameters grounded
through `source_refs` → source-catalogue `corpus_path` (the AEAT manuals tree) are
never opened, so they report as "number not stated" regardless of truth.

The verified-stated figure therefore stands as a **lower bound**, and the
some-absent set is **not** evidence of ungroundedness — it mixes genuine gaps with
manual-grounded parameters the probe cannot see. The Madrid 2022 entries are the
worked example: flagged by the probe, verbatim in the manual. Findings established
by reading corpus files directly — Modelo 347, Modelo 232, Modelo 360 — are
unaffected.

## The campaign's origin finding is RESOLVED at HEAD

This campaign was opened by a guard that refused an entire filing citing
under-declaration while firing on a population — `InvoiceKind.RECEIVED`, purchase
invoices — where a ledger shortfall makes the taxpayer **over-pay**. The stated
criterion and the real direction disagreed, and nothing said so.

Re-verified at HEAD: **that disagreement is gone.**
`_raise_if_screened_invoice_iva_would_be_silent`
(`application/aggregation/_modelo_bindings.py`) now states the distinction in its
own comment and implements it:

> Withholding an unauthorised input row is unconditional; REFUSING the whole
> filing over it is not. This guard's criterion… is invoice IVA that would EXCEED
> the transaction-ledger cuota — that is the under-declaration. An unlinked
> purchase invoice whose cuota the ledger already carries is corroborating
> evidence of an operation that IS declared, so refusing there blocks a filing
> whose totals are correct. It stays withheld (no invented deduction family
> reaches a casilla) and the operator is told through the diagnostic channel
> instead.

The refusal is now gated on `_uncovered_withheld_invoice_cuota(...) > 0` — invoice
IVA in excess of the ledger cuota. Criterion and population agree: it fires only
where the direction genuinely is under-declaration, and the corroborating-purchase
case is withheld with an operator diagnostic rather than refused.

Confirmed committed, not a working-tree edit: the symbol is present in
`git show HEAD:…` and the file is unmodified in `git status`. (`git log -S` does
not trace it, presumably across a rename; HEAD content is the authority.) The
behaviour is exercised by `test_invoice_declared_category_survives.py` and
`test_terminal_preconditions.py`.

**The organising question survives its origin case.** It kept earning findings
after this one was fixed — the M390 fourth recargo tier, the M360 refund
thresholds, the RIC 80 % concept — so the question, not the instance, is what the
handoff should carry forward.

### The two direction probes, re-run at HEAD

Both are stable and neither surfaces a new candidate:

- `direction_audit` — 66 refusing functions scanned, **one** hit, and it is this
  now-resolved guard. Its detector matches the old prose that survives in the
  comment explaining the fix, so the hit is a residue of the explanation, not a
  live defect.
- `restrictive_defaults` — the relief-side zero fallbacks remain the reviewed
  DANA / recargo / suplido set; the nine liability-side ones are all
  `recargo_amount or Decimal("0")`, legitimately zero where no recargo applies.

Re-run both after any change that adds a relief or a guard.

## Citation dilution: one measured outlier, and it compounds with a blind cross-check

The grounding rule requires a value's `legal_refs` to name **the specific binding
provision that establishes that value**. Omission defeats that; so does citing
everything. The second failure mode has one instance, and it is measured rather
than asserted.

Across the 382 parameters under `modelos/*/revisions/*/parameters/` that carry
`legal_refs`:

| refs | parameters |
|---|---|
| 1 | 311 |
| 2 | 53 |
| 3 | 9 |
| 4 | 7 |
| 5 | 1 |
| **18** | **1** — `is.modelo-200.tipo-gravamen-general` |

One provision per parameter is the overwhelming norm, at 81 %. The four- and
five-ref rows are legitimate multi-provision values — transitional IVA rates
carrying an RD-Ley plus the base article, fractional-payment rates. The next
highest after the outlier is 5, so the gap to it is 3.6×.

`is.modelo-200.tipo-gravamen-general` cites LIS arts. 40, 29, 30, 39, 19, 36, 100,
12, 15, 21, 22, 31, 32, 13, 16, 25, 26 and `rd-634-2015:art-3`. Exactly one — art.
29 — establishes the rate, verbatim in the bundled corpus: *"El tipo general de
gravamen para los contribuyentes de este Impuesto será el 25 por ciento…"*. The
other seventeen are amortisation, provisions, exemptions, consolidation and CFC
rules that have nothing to do with the rate.

**The value is correct, so there is no error direction today.** The defect is
auditability: a reviewer cannot tell which of eighteen provisions to check, the
evidence gate is satisfied by any of them, and were art. 29 amended the other
seventeen would remain, still plausible-looking. Its siblings are clean —
`new-entity-first-2-years` and `cooperative-protected` cite art. 29 alone, and
`non-profit-special-regime` cites art. 29 plus `ley-49-2002:art-10`, which is
where its 10 % actually lives. The isolation and the distribution together suggest
refs accumulated onto this row rather than being authored.

This row is also the worked example of the two citation defects compounding: its
`required_text` is the bare phrase `"tipo de gravamen"`, which pins no value. So
nothing in the record identifies which provision governs, and nothing would fail
if the 25 were wrong.

## Sharpening: the evidence gate is an auditability device, never an enforcement one

This audit's `required_text` finding, and the remediation proposed for Modelo 360,
both need refining. The gate does less than either assumed.

`registry/_validate_evidence.py` performs exactly one comparison:

```python
for required in citation.required_text:
    if _normalise_required_text(required) not in source_text:
        failures.append(... missing text ...)
```

It asks whether the **declared phrase appears in the cited source**. It never
reads the parameter's `value`. The two are never compared.

The consequence changes the shape of the finding:

- A `required_text` that states no value — `"modelo 303"`, `"operaciones
  vinculadas"`, `"tipo de gravamen"` — tells a reader nothing about the number.
- But a `required_text` that **does** state the value is not enforced either.
  `m303-modulos-iva-dificil-justificacion-forfait` carries the best phrase in the
  registry: *"será deducible el 1 por ciento del importe de la cuota devengada por
  operaciones corrientes, en concepto de cuotas soportadas de difícil
  justificación"* — value, base and concept all named. Change its `value` from `1`
  to `2` and the phrase still says "el 1 por ciento", still appears verbatim in the
  Orden, and the gate stays green.

So `required_text` buys **auditability, not enforcement**, in both cases. The
difference between a phrase that states the value and one that does not is whether
a human reading the row could see the mismatch — never whether the build would
fail.

This corrects the Modelo 360 remediation step that proposed replacing its
`required_text` with a phrase pinning the digits "so the cross-check can fail".
That step is still worth doing — it makes the row reviewable, and it is what
distinguishes the M303 forfait row from the M360 one — but it does **not** create a
bite. Stated plainly so no one implements it expecting one.

Enforcement would need a different mechanism: extracting the figure from the
cited source text and comparing it as a `Decimal` against the encoded value. That
is a design decision, not a wording fix, and it is not adjudicated here. Note that
it would have to handle values spelled in words, since the corpus writes "ochenta
por ciento" and "el 1 por ciento" as readily as digits.

**Reference shape.** `m303-modulos-iva-dificil-justificacion-forfait` is the model
for a discriminating citation: one `legal_ref` (`ley-37-1992:art-123`), one
source, and a `required_text` naming the value, the base it applies to, and the
concept. Copy this shape.

### Correction and the healthy direction: value-vs-corpus enforcement DOES exist, on a spine

The section above says the evidence gate audits rather than enforces. That is true
of `_validate_evidence.py`, and it was the wrong place to stop looking.

`domain/iva/tests/test_legal_basis_rate_grounding.py` is a purpose-built gate
that does exactly the comparison declared missing. Its own docstring:

> This test module is the canonical gate that every rate value used by the IVA /
> IRPF substrate and modelo registry matches its BOE legal authority. For each
> rate, the chain of references is checked end-to-end: 1. The BOE corpus excerpt
> contains the operative percentage string (e.g., "21 por ciento" in LIVA art 90).
> 2. The registry parameter / IVA_RATE_TABLE entry stores the matching numeric
> value (Decimal "0.21" = 21 %). 3. The substrate's typed enum … 4. The
> pydantic-typed Python wrapper … returns the same value.

27 tests carry it, and it is bidirectional: `test_liva_art_161_missing_recargo_
parameter_raises_iva_catalogue_error` deletes `liva-art-161:recargo-rate-tabaco`
from the catalogue and asserts `IvaCatalogueError`, so the chain is proven to bite
rather than assumed to.

**Its scope is a spine, not the population.** It covers LIVA art. 90 (21 %), art.
91 (10 % and 4 %), art. 161 (all four recargo tiers including tabaco at 1,75 %),
art. 103 (the two prorrata-margin redactions), and LIRPF art. 85 (imputación),
plus the rate-slot/kind mapping and the zero-rate statutory window — on the order
of a dozen distinct values, each hand-authored.

So the accurate statement is: **enforcement exists and is exemplary where it
reaches, and it reaches the IVA rate spine.** It does not reach the IS
tipo-gravamen family, IRNR rates, the patrimonio scales, the M720/M721 thresholds,
módulos coefficients, the M360 refund minimums, the autonomic scales, or RIC. For
those, `required_text` is the only evidence artefact, and it audits without
enforcing.

That reframes the remediation. The question is not "how do we build value-vs-corpus
enforcement" — it exists, with a proven anti-tautology test. It is "which further
rate families earn a chain in this file", which is a prioritisation the owner
should make on liability exposure. `test_legal_basis_rate_grounding.py` is the
reference shape for parameter enforcement, as
`m303-modulos-iva-dificil-justificacion-forfait` is for a discriminating citation.

#### Correction to the gap list above: the IS family is covered, and there are two tiers of coverage

The section above lists "the IS tipo-gravamen family" among the families
value-vs-corpus enforcement does not reach. **That is wrong**, and it was asserted
from a search scoped to the wrong packages — the same error the section's own
closing method note warns against, committed in the same change.

`domain/calculations/registry/tests/test_modelo_200_tipo_gravamen_dispatch.py`
covers it:

- `test_scalar_tipo_gravamen_parameters_carry_the_lis_art_29_rates` pins each
  parameter to its rate — general 25, cooperative-protected 20,
  non-profit-special-regime 10, new-entity 15.
- `test_ley_49_2002_art_10_nonprofit_rate_links_to_bundled_corpus` asserts the
  reference's `corpus_ref` is `corpus/normatives/html/ley-49-2002-art-10.html#a10`
  and checks its `required_text`.
- Further tests pin the micro-empresa two-bracket scale, the ERD rate against Ley
  31/2022, and that dispatch raises on an unsupplied or unrecognised legal-entity
  form.

The IRNR side likewise has `test_catalogue_verification_normatives.py`,
"article-level normative corpus verification", which resolves `required_text`
through `verify_source_file`.

**What survives is a real distinction, and it is more useful than the gap list
was.** There are two tiers of coverage:

- **Corpus-text verified** — the IVA spine. The test reads the bundled BOE text
  and asserts the operative percentage string is present, then follows the value
  through registry, substrate and wrapper. This catches a *wrong reading of the
  law*, because the authority is the text.
- **Literal-pinned** — the IS family, mostly. The expected rate is a `Decimal`
  written in the test. This catches *registry drift* — someone changing 25 to 24
  reds immediately — but it cannot catch an error shared between the test author
  and the registry author, because both encode the same belief.

Neither tier is absent, and the second is not worthless; it is the difference
between "the registry still says what we decided" and "what we decided matches the
BOE". The prioritisation question for the owner is therefore narrower than stated
above: **which literal-pinned families should be promoted to corpus-text
verification**, given that the mechanism and its anti-tautology proof already
exist in `test_legal_basis_rate_grounding.py`.

#### The verified coverage map, replacing the asserted gap list

Searched by concept across `src` and `dev` — not by owning package, and not by
parameter id alone — for every family the earlier list named. The result retires
the list and identifies one priority.

| family | coverage | tier |
|---|---|---|
| IVA rates (LIVA 90, 91, 161, 103; LIRPF 85) | `test_legal_basis_rate_grounding.py`, 27 tests | corpus-text verified |
| M714 patrimonio escala | `test_modelo_714_cuota_integra_escala_matches_boe_table`, parametrised | BOE-table verified |
| IS tipo-gravamen | `test_modelo_200_tipo_gravamen_dispatch.py` | literal-pinned + one corpus link |
| Autonomic escalas | 9 tests incl. `test_m100_2021_cuotas_integras_escala_aragon_manual_worked_example.py` | manual worked example |
| Módulos coefficients | 4 tests incl. the 2024 engine backfill | scenario/engine |
| M720 / M721 thresholds | 1 test each, prior-year baseline fidelity | scenario |
| RIC 80 % | `test_modelo_100_drift_detection.py` only | drift detection; parameter unconsumed |
| **M360 refund minimums 400 / 50** | **none** | **none** |

**M714 was wrongly listed as a gap.** Its escala is verified against the BOE
table, at the strongest tier available. The earlier "zero tests" reading came from
grepping the *parameter id*; the test reaches the escala through its formula and a
parametrised base-liquidable → expected-cuota table. **Grepping a parameter id is
a weak proxy for coverage** — a parameter exercised through its formula shows as
uncovered.

Worth recording as good practice: `test_modelo_714_patrimonio_baseline_fidelity.py`
prevents exactly that misreading, stating in its own docstring that its cuota
figure "is a roundtrip-fidelity input, not an oracle for the art. 30 escala; the
escala is verified by the dedicated M714 registry calculation tests." A fixture
that declares what it is *not* evidence of, and points at what is.

**M360 is the one family uncovered on both axes**, and that convergence is the
finding. Its citation points at the plazo article, which states no threshold, and
the Orden states neither 400 nor 50 anywhere (see the dedicated M360 audit); and
no test asserts either value — the only near-matches are unrelated row amounts.
So nothing in the record establishes these figures, and nothing would notice if
they changed. Direction is over-payment: a wrong refund threshold suppresses a
legitimate claim.

That makes M360 the priority for the promotion question posed above, ahead of the
literal-pinned families, because those at least fail on drift.

### Scope qualification: the evidence for a value may live on the BINDING, not the parameter

Every `required_text` measurement in this audit — the recorded count, and the
value-aware re-measurement that replaced it — scanned **parameters**. Bindings
carry `source_citations` too, and they are instrumented differently:

| artefact | carrying a `required_text` | of those, pinning a digit |
|---|---|---|
| parameters (under `modelos/*/revisions/*/parameters/`) | 382 | ~22 % |
| bindings (under `modelos/*/revisions/*/bindings/`) | 1.222 of 9.230 | **1.005 (82 %)** |

The ratio is inverted. Where a binding declares evidence at all it almost always
pins a number, which is the opposite of the parameter population this audit
measured.

**Worked example, the Ley 12/2023 rental reduction.** The four tier parameters
`renta-2024-rental-reduccion-rate-tier-{50,60,70,90}` each cite
`ley-35-2006:art-23` with no `required_text` naming any tier. The binding that
selects among them, `renta-2024-rental-reduccion-art-23-2-tier`, declares:

```toml
required_text = ("90 por 100", "70 por 100", "60 por 100", "50 por 100")
```

against the AEAT Renta 2024 manual. So all four values *are* anchored in the
evidence record — on the binding, where a parameter-scoped sweep never looks.

### What this does and does not change

It does **not** rehabilitate the parameter population: most bindings (8.008 of
9.230) declare no `required_text` at all, and not every parameter has a binding
that grounds it. A parameter with a blind citation and no binding evidence is
still unanchored, and the Modelo 360 case remains exactly that.

What it changes is the unit of the question. "Is this value anchored?" cannot be
answered by looking at the parameter alone; it needs the parameter *and* any
binding that carries it. Every count in this audit is therefore a **parameter-side
count**, not a per-value verdict, and should be read as such.

That also explains a healthy pattern worth naming: the registry tends to put the
legal reference on the parameter and the *operator-facing evidence* on the
binding — the binding is where a figure meets a declared taxpayer fact, and it is
where the AEAT manual, rather than the BOE, is the natural source. The rental-tier
binding cites the manual with `"90 por 100"` in the manual's own idiom, while its
parameters cite the law.

#### Measured: how much of the parameter-side gap the binding evidence closes

Widening the question from the parameter to its **revision** — does any
`required_text` anywhere in that revision, on a parameter, binding, casilla or
construct, state the value? — gives the split the parameter-only sweep could not:

| of 437 value-bearing parameter rows | count |
|---|---|
| pinned by the parameter's **own** `required_text` | 101 |
| pinned only **elsewhere** in the revision's evidence | 132 |
| pinned **nowhere** in the revision | **204** |

So roughly a third of what a parameter-scoped sweep calls unanchored is in fact
named somewhere a reader can reach — which is the rental-tier pattern generalised,
and the reason the earlier counts overstated the gap.

**The 132 is an upper bound on anchoring, not a clearance.** A phrase pinning
"50" somewhere in a revision may be about an entirely different quantity; this
test cannot tell. Its value is to shrink the candidate list from 336 to 204, not
to certify any row.

**The 204 is the solid set**: nothing in the whole revision's evidence names those
values. It is the list worth reading, and it is dominated by two families already
recorded here — the Modelo 200 `tipo-gravamen` rows, whose cited LIS art. 29
states the steady-state rates rather than the phased ones, and the Modelo 131
módulos coefficient tables. `irpf.urban_rental_withholding_rate` sits there too.

Both families are the same shape and neither is a wrong value: the figures are
correct and the evidence record simply does not carry them. That is consistent
with everything this campaign found — the weakness is in what the record says
about a value, not in the values.

#### Refinement: the 204 includes large keyed tables where per-value pinning is impractical

Reading the second family in that list — the Modelo 131 módulos coefficients —
changes how the number should be read again.

`m131-modulos-coeficientes-2025` is a **273-entry** keyed table mapping
`<epígrafe IAE>:<módulo>` to the rendimiento anual per unit, from Orden
HAC/1347/2024 Anexo II. Pinning 273 values in a `required_text` is not a thing
anyone would do; the row's declared phrase is necessarily generic. So its
appearance in the pinned-nowhere set reflects the **shape of the artefact**, not
neglect — a scalar rate and a 273-row tariff table cannot be held to the same
evidence convention.

The file states its own grounding discipline instead:

> Incrementally authored dataset: only activities grounded and cross-checked
> against the bundled corpus are tabled here; the ~80+-activity Orden Anexo II is
> authored over time.

**And the incompleteness is watched, in the right direction.** The same comment:

> An epígrafe absent from this table is NOT computed by the engine; casilla 01
> stays reachable as a manual operator input and the
> `modelo-131-2025-modulos-computed-diverges-de-c01` advisory fires instead of a
> silent zero.

That advisory is real, not aspirational — a declared verification predicate,
`advisory_when_computed_diverges(["01", "modulos-rendimiento-neto-actividad"])`,
`finding_kind = "ADVISORY"`, grounded on LIRPF art. 31 and the Orden. It compares
the operator's manual casilla 01 against the engine's computed rendimiento and
flags divergence **either way**, so it watches the over- and under-declaration
sides alike. Its own note explains the choice not to block:

> This is deliberately a note and not a gate — refusing the binding outright would
> also refuse it once the inputs are per-activity, which is the state we want to
> reach.

So an un-tabled epígrafe cannot silently zero a rendimiento: the manual value
stands and divergence is surfaced. **Add to checked and sound.**

The general point for the count: **204 is a mixed set.** It contains scalar rates
whose evidence genuinely says nothing (the Modelo 200 tipo-gravamen rows), and
large tariff tables where per-value pinning was never the convention. Only the
first kind is a candidate for repair, and separating them is the next step for
anyone acting on this list.

#### Correction: 204 was inflated four-fold — the legal catalogue was never read

The measurement above swept `source_citations` across each **revision** —
parameters, bindings, casillas, constructs. It never read
`registry/aeat/legal/*.toml`, which sits outside `modelos/*/revisions/` and is
**where the BOE-side evidence lives**. Including it changes the result
substantially:

| of 437 value-bearing parameter rows | before | corrected |
|---|---|---|
| pinned by the parameter's own `required_text` | 101 | 101 |
| pinned elsewhere in the evidence | 132 | **288** |
| pinned nowhere | **204** | **48** |

The mínimo personal y familiar rows, which dominated the previous repair list, are
the clearest example of what was missed. `ley-35-2006:art-57` resolves to a
**874-byte per-article excerpt** whose `required_text` pins `"5.550 euros
anuales"` and `"1.150 euros anuales"`; art. 58 pins `"2.400 euros"` and `"2.700
euros"`; art. 59 pins `"1.150 euros"`. Those are exemplary citations — tight
corpus, digits pinned — and the sweep called their parameters unanchored purely
because it looked in the wrong file.

Verified independently: LIRPF art. 57 reads *"El mínimo del contribuyente será,
con carácter general, de 5.550 euros anuales. 2. Cuando el contribuyente tenga una
edad superior a 65 años, el mínimo se aumentará en 1.150 euros anuales. Si la edad
es superior a 75 años… adicionalmente en 1.400 euros anuales."* The registry's
5550 is right.

### What the surviving 48 actually are

Mostly **specific tranches whose article's citation pins only the leading
figures**. `art-57`'s `required_text` names 5.550 and 1.150 but not the 1.400 for
over-75s; `art-58` names 2.400 and 2.700 but not the 4.000, 4.500 or 2.800. So the
parameters for those tranches — `minimo-contribuyente-edad-75`,
`minimo-descendientes-tercer-hijo`, `-cuarto-y-siguientes`, `-menor-tres-anos`,
and their ascendientes counterparts — are the ones nothing names, in 2020 and 2021
revisions.

That is a real and small gap with a cheap fix: extend the existing catalogue
entries' `required_text` to cover the remaining tranches of the article they
already cite tightly. No new corpus, no new citation.

### The lesson about these counts

This is the fourth time a count in this audit moved because the sweep's **scope**
was wrong rather than its question. Parameter-only missed bindings; revision-only
missed the legal catalogue; digit-matching missed words; row-counting
double-counted revisions. The question — "is this value named in evidence a reader
can reach" — has been right throughout. **Treat every count here as scoped until
its scope is stated, and state it.**

#### And the 48 is not a grounding gap either: the excerpts state every figure

Reading the excerpts settles it. Each mínimo article's per-article corpus file
contains **every** tranche, not just the ones its `required_text` names:

| excerpt | figures present |
|---|---|
| `ley-35-2006-art-57.html` (874 B) | 5.550, 1.150, **1.400** |
| `ley-35-2006-art-58.html` (1.101 B) | 2.400, 2.700, **4.000**, **4.500**, **2.800** |
| `ley-35-2006-art-59.html` (1.028 B) | 1.150, **1.400** |

So `renta-2025-minimo-contribuyente-edad-75-2025` and its siblings are grounded on
every axis that matters: the **right article**, a **tight excerpt**, and the
**figure stated verbatim** in it. Nothing about them is unanchored.

### What this means for the whole "pinned" line of work

`required_text` is a **bundling spot-check** — evidence that the right document is
present and is the document the author read — not an exhaustive manifest of every
value an article establishes. Naming two of an article's five tranches is a
reasonable authoring choice, not an omission, and for a multi-tranche article
enumerating all of them adds length without adding enforcement, since the gate
compares phrases to the source and never to the encoded value.

So the sequence of counts in this audit — 99, then 300, then 204, then 48 — was
measuring `required_text` **enumeration completeness**, and calling it grounding.
It is not the same thing. Grounding is *(right provision) + (corpus that states
the figure) + (value matching it)*, and on that test the mínimo family passes
completely.

**This does not dissolve the real findings; it sharpens why they are real.**
Modelo 360 is not a thin `required_text` over a good citation — its cited article
is the *plazo* article, which states no threshold, and the whole Orden states
neither 400 nor 50 anywhere. The M200 pyme row cites an article stating different
rates than it encodes. Those are grounding defects in the strict sense: no
document in the chain states the value. The mínimo rows never were.

The residual `required_text` observation stands as what it is — a reviewability
nicety, cheap to improve where an article's leading figures are named and its
later tranches are not — and should not be carried forward as a grounding count.

## Re-verified at HEAD: the liability-critical aggregates still hold

A "checked and sound" verdict decays — this is a shared tree and the checks in
this audit were made across many days of concurrent commits. The two aggregates
whose failure would most directly misstate a liability were re-run against
current HEAD.

**Modelo 303 `cuota-devengada-total`, recargo rung enumeration per design year:**

| revision | recargo rungs summed |
|---|---|
| 2022 | 3 — `18`, `21`, `24` |
| 2023 | 4 — plus `158` |
| 2024-hasta-08-y-2t | 4 |
| **2024-desde-09-y-3t** | **5** — plus `170` |
| 2025 | 5 |
| 2026-y-siguientes | 5 |

3/4/4/5/5/5, exactly as recorded. And the growth lands where the official design
grows: casilla `170` enters with the September 2024 design change, which is the
same boundary that splits the two 2024 revisions. The total enumerates each year's
actual rungs and no more.

**Modelo 111 casilla 28:** sums nine casillas — `03`, `06`, `09`, `12`, `15`,
`18`, `21`, `24`, `27`. The revision carries ten casillas with a retención
semantic role; the tenth is `28` itself, the total. So every contributing box is
summed and none is dropped, as recorded.

Both verdicts stand. Recording the re-check rather than the verdict alone is the
point: a handoff list that says "sound" without saying *when* invites the next
reader to trust a measurement taken against a tree that has since moved.
