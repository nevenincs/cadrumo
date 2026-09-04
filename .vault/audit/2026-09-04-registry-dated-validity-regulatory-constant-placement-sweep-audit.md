---
tags:
  - '#audit'
  - '#registry-dated-validity'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:8fff638250fed37da6d2f176590a3faa1a3c8f7e3f3b39d62c3b54fec9e4a22d'
related:
  - "[[2026-08-27-registry-dated-validity-frozen-constant-hunt-audit]]"
---

# `registry-dated-validity` audit: `regulatory constant placement across code and registry`

## Scope

Where the numbers that Spanish tax law fixes actually live in this product, and
whether each one sits somewhere the calculation can resolve.

In scope: every filing-affecting rate, ceiling, threshold, bracket, coefficient,
window and reduction reachable from `src/cadrumo/domain/` and
`src/cadrumo/application/`, plus the registry data under
`src/cadrumo/_data/registry/aeat/`. Out of scope: values whose governing
provision is not in the bundled corpus, which are recorded as unmeasurable
rather than cleared.

This extends the frozen-constant hunt rather than repeating it. That audit asked
whether a registry value MATCHED its provision. This one asks a prior question:
is the value somewhere a consumer can read at all?

## Method

Six shapes were swept, each recorded even when clean:

1. Python `Decimal` digit literals in domain and application, excluding tests
   and excluding zero, one and one hundred. Population 62.
2. Module-level upper-case numeric constants in the same trees.
3. Names matching percentage, rate, limit, maximum, minimum, threshold, ceiling,
   quota, and deadline suffixes.
4. Numeric literals inside registry formula expression strings.
5. Regulatory values encoded in registry parameter identifiers and filenames.
6. Comparison-expression literals, date and window boundaries, and enum members
   carrying numeric legal meaning.

Every candidate was checked against the registry parameter and legal-catalogue
trees BEFORE concluding no declaration existed. Where a test appeared to gate a
constant, the test was read rather than trusted.

The inherited discipline is a single question asked of each provision: does it
fix A NUMBER, or A REFERENCE to a number somebody else re-fixes? The phrases
`en cada ejercicio economico`, `que este establecida`,
`reglamentariamente se establezcan`,
`con los limites cuantitativos establecidos reglamentariamente`,
`el que se fije en la Ley de Presupuestos` and `vigente en cada momento` all
mean the value MOVES and must never be a constant.

The largest measurement is reproduced by counting `literal` assignments in the
formula TOML under the modelo revision tree, discarding zero, one, minus one and
one hundred.

## Findings

### constant-authority-ladder | high | the defect is not location but whether the literal can lose to the registry

Ranking every finding by how the Python literal relates to registry authority
produces four tiers, and the product already contains its own best answer.

Tier one, registry-resolved at runtime and fails closed. The rental tier
resolver in `src/cadrumo/domain/fincas/tier_resolver.py` reads the per-year
reduccion-rate parameter and overrides its own documented constant whenever the
registry differs; a missing parameter raises a validation error rather than
falling back. The literals there are commentary that cannot win.

Tier two, registry-gated by a real test. The general IVA rate constant is
asserted equal to the value the dated IVA registry resolves. The constant still
executes, but divergence is caught.

Tier three, ungated constant. Most of `src/cadrumo/core/external_constants.py`.
Nothing detects divergence. Some have a registry parameter that already exists;
several have none.

Tier four, constant that REFUSES the registry. The Modelo 303 annual-Orden
cluster. This is the only actively dangerous tier and should be remediated
first despite being the smallest.

### orden-constants-refuse-new-law | critical | the comparison direction makes correct new law indistinguishable from a corrupt extraction

`src/cadrumo/domain/calculations/registry/_m303_orden_constants.py` pins the
seasonal correction coefficients and their day bands, the difficult-justification
percentage, and the 2022 Lorca reduction of twenty per cent. Every one of those
values is ALREADY carried as registry data in the annual-Orden census, each with
a required-text field quoting the Orden verbatim.

The code compares manifest against constant and refuses on inequality. So when a
future Orden changes a coefficient, the census will faithfully carry the new
figure with its new official text, and the constant will reject the manifest.
The gate fails closed against the law rather than against a defect. The Lorca
figure is declared five times across three modules.

The same module pins corpus shape counts, including a per-ejercicio dictionary
of agricultural axis counts maintained by hand each year. That dictionary is
direct evidence that legal change is currently absorbed by editing Python.

### inline-formula-literals | high | 160 regulatory figures sit inside registry formulas where nothing can resolve them

Measured across modelos 100, 130, 131, 200, 202, 210, 303 and 714: 452 inline
literals in formula expressions, of which 160 are non-trivial. The most frequent
are fifty with fifty-five occurrences, twenty-five with nineteen, and the
one-million and ten-million pair.

An inline literal carries no data type, no unit, no dated validity and no legal
references of its own. It is invisible to a Python sweep and to a parameter
inventory alike. This ranks above most Python findings precisely because a
Python constant is at least greppable by name and reachable by the
import-boundary gates.

### rate-band-thresholds-unresolvable | high | Modelo 200 declares its rates as data and the thresholds that select them as strings

The Impuesto sobre Sociedades rate bands are split. The RATES are proper typed
parameters carrying legal references to LIS art. 29, art. 101 and DT 44a. The
THRESHOLDS that select between them, one million euros for the microempresa
scale and ten million for the ERD limb, are inline literals inside the formula
expression.

This is not hypothetical. While authoring a Modelo 200 conformance vector
earlier in this same campaign, the ten-million ERD ceiling was missed and a net
turnover of two million was declared with a comment asserting it exercised the
general art. 29 rate. It did not; it exercised the art. 101 ERD limb at
twenty-four per cent. An independent reviewer caught it. The value was missable
because it was not discoverable as registry data. The defect class has a
measured cost inside this repository.

### article-81-split | high | one article is treated two ways in the same product

The guarderia increment cap of art. 81.2 was given its own resolvable parameter,
and that parameter's header comment states the defect class in the project's own
words: the figure previously existed only as an inline literal, which is
legitimate registry data but unreadable from the application layer.

Art. 81.1 remains six Python literals: the monthly accrual, the annual cap, the
post-birth alta increment, the raised cap, and two filing-year boundaries. The
raised cap is stored as an independent literal rather than derived from the two
figures that compose it, so if either moved it would not follow.

### tautological-drift-gate | high | the centralisation gate protects exactly one constant while appearing to protect several

`src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`
contains two kinds of assertion. One resolves the dated IVA registry and
compares it to the constant: a real gate. The other asserts constants against
hardcoded copies of themselves, which detects an edit to the constant but can
never detect divergence from the registry, because the registry is never read.

The amortizacion rate and the maritime exemption fraction sit behind the second
kind.

CORRECTED DURING REMEDIATION: the amortizacion rate is nevertheless NOT tier
three. The rental amortisation ledger already resolves its dated Modelo 100
parameter at runtime and raises on a missing one, and the arithmetic multiplies
by that resolved value rather than by the constant, which is a documented alias
the computation never touches. It was already tier one. The original assessment
was reached by reading the test and not the runtime path. The maritime exemption
fraction has no registry parameter at all, so it cannot be bound to one.

### provision-grounded-figure-absent | high | the cleanest form of the defect, where the registry knows the article but not the number

Recurring shape: the legal catalogue registers the provision, sometimes a
binding even cites it, and no typed parameter carries its figure.

LIVA arts. 107, 108 and 109 are all catalogued, yet the bien-de-inversion
regularisation windows, the ten-point regularisation threshold, and the two
divisors live only in Python. Ley 44/2015 art. 14 is catalogued AND cited by a
Modelo 200 binding, yet the endowment rate and the double-capital multiple live
only in Python. LIVA art. 103 is catalogued, yet both prorrata especial margins
live only in Python.

The prorrata especial pair is the sharpest instance: one provision with two
values, each with its own validity window AND its own comparison operator,
versioned by hand as two differently named constants. Dated registry parameters
exist precisely to express this.

### values-in-identifiers | medium | a narrow family where the figure is in the filename and not in any field

Of 370 parameter files, most embedded numerics are innocent labels or revision
suffixes and were cleared. The genuine case is twelve age-band files. The amount
is typed and dated; the age band that selects it exists only in the identifier
and in the grounding text. A consumer must parse an identifier or restate the
ages in Python, which is exactly what the minimo age ceilings do. The disability
grade threshold shows the same shape from the opposite direction.

### generic-python-tree | low | the wider codebase is NOT riddled with regulatory constants

Swept for upper-case numerics, regulatory-sounding names and comparison literals
outside the two known modules. The overwhelming majority are correctly
structural: label and payload length caps, byte ceilings, timeouts and cache
lifetimes, display widths, diagnostic sample limits. Three genuine finds only:
the disability grade threshold, the four-year expense carry-forward of LIRPF
art. 23.1.a, and a Madrid autonomic filing-year boundary.

This is a real result and it bounds the problem. The concentration is in two
modules and in the registry's own formula expressions, not spread through the
tree.

### deliberate-non-sharing-is-correct | low | three sites refuse to merge values that agree today, and they are right

The transitional-rescate boundaries decline to be merged with each other because
they are independent rules that happened to change in the same reform. The
art. 81.1 entry window declines to borrow the art. 58.2 window because the two
read alike and count differently. The disability module declines to borrow an
age ceiling of the same value from another article.

This discipline is correct and must survive any remediation. Consolidating by
VALUE rather than by PROVISION would introduce defects, and it is the naive
reading of this audit.

### closed-window-constants-are-defensible | low | some legal values provably cannot move

The transitional-rescate cluster fixes a reduccion rate and windows keyed on
contingencia years that have passed, with a cliff date now in the past. The
module argues these are boundaries fixed once by an amendment rather than
figures the law re-sets, so year-versioning them would duplicate an invariant
across every revision to vary nothing. Assessed against the method above, that
argument is SOUND. These are not defects and a blanket relocation would be
wrong.

## Recommendations

Remediate tier four first, despite it being smallest. REMEDIATED: the
annual-Orden validators now assert shape rather than the legal figures, so a
future Orden changing a coefficient is accepted while a garbled extraction is
still refused. Both directions were proved by execution.

Extend the real drift-gate pattern rather than claiming one exists. Every
constant that has a corresponding registry parameter should be bound by a test
that RESOLVES the parameter, on the model of the IVA rate assertion. Retire or
rename the literal-restating cases so they cannot be mistaken for protection.
REMEDIATED: the amortizacion rate now has such a gate, and the literal-restating
test is renamed and documented as not being a drift gate.

The promotion recommendation below has a smaller scope than it first appears.
Only two constants have a registry parameter at all, and both already sit at
tier one or tier two. The bottleneck is not promotion but ABSENCE: the remaining
values have no parameter to resolve, so authoring one is the prerequisite for
every other fix. Rank that authoring by consumer count and filing impact.

Prefer promotion to tier one over tier two wherever a consumer already runs
inside a period context. Reading the parameter at runtime and failing closed on
absence is strictly stronger than testing agreement, and it is already
implemented in the rental tier resolver.

Give inline formula literals a home. This is the largest population and the
least discoverable. Adjudicating all 160 individually is a campaign in itself.
REMEDIATED for the Modelo 200 rate-band thresholds, which had the demonstrated
cost: both turnover ceilings are now typed money parameters carrying their own
legal references and dated validity, and all ten inline occurrences across both
revisions were replaced by parameter references. All three rate bands were
re-measured and still select the same tipo.

Apply a selective test, never blanket relocation. For each value ask whether the
provision fixes a number or a reference to a number somebody else re-fixes.
Preserve deliberate non-sharing between provisions. Leave provably closed
windows as leaf constants.

An architecturally significant decision remains open and belongs in a follow-on
ADR: whether registry parameters should gain a typed applicability facet, so an
age band, a turnover threshold or a comparison margin can be declared as data
beside the amount it selects. Every finding in the identifiers and
inline-literals groups reduces to the absence of that facet. This audit does not
make that decision.

## Measured versus assumed

Measured by execution: the literal counts and their per-modelo spread; the 370
parameter files and the twelve age-band family; the existence and content of
every parameter cited; the two kinds of assertion in the centralisation test;
the runtime registry resolution and fail-closed behaviour in the rental tier
resolver; the Modelo 200 rate-band misclassification and its correction.

Assumed and NOT verified: that each of the 160 inline literals is regulatory. It
is a POPULATION, not a defect count. Some are certainly structural, including
twenty-four occurrences of a hundredth that are rounding steps. The audit
reports the population and the means to reproduce it.

Unadjudicated: the 160 inline literals individually, beyond the confirmed
exemplars. Nothing was classified unmeasurable, because every provision reached
in this sweep was present in the bundled corpus.
