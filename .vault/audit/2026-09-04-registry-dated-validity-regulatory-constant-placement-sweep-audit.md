---
tags:
  - '#audit'
  - '#registry-dated-validity'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:cca71b1246644d3cfea77e9adea7fdb61992675165897c351515049104349e46'
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

### m390-regularizacion-has-two-computation-paths | high | UNADJUDICATED, a legal question

Surfaced while authoring the LIVA art-107/109 figures as registry parameters,
and deliberately NOT settled here: it is a question about what Modelo 390
casilla 63 legally IS, not about where a constant lives.

Every Modelo 390 revision declares `family_dispositions.parameters` NOT
APPLICABLE, and the declaration is reasoned and revision-verified rather than a
blanket assertion: it states that the resumen anual "restates their outcome and
applies nothing of its own", having checked that the revision declares zero
parameters and that its four formulas aggregate already-computed period figures.
The registry loader enforces that disposition, and it REFUSED an attempt to
author the art-107/109 figures onto those revisions.

The code disagrees. `application/calculations/bienes_inversion_regularizacion.py`
admits both Modelo 303 and Modelo 390 in the same resolver branch and calls
`compute_registro_regularizacion` for both, so casilla 63 RECOMPUTES the
regularisation from the capital-goods register rather than restating the Modelo
303 casilla 43 that already computed it for the same ejercicio. One legal figure,
two computation paths, with no parity check between them.

Either the disposition is wrong and Modelo 390 does apply figures of its own, or
the code is wrong and casilla 63 should carry the periodic outcome forward. Both
readings are defensible from the documents available in this tree, and the choice
decides what a filed annual summary contains. It is therefore left open for an
operator or reviewer with the authority to read AEAT's design intent for the
resumen anual.

What was done in the meantime, and why it is not a settlement: the parameter
resolver refuses a Modelo 390 revision, so the source resolver now returns an
unresolved binding with a classified diagnostic instead of projecting a
filing-bound figure computed from values the active revision never declared.
That is the no-silent-under-declaration answer to an ungrounded value, not an
answer to the legal question. It is a USER-VISIBLE behaviour change on a
non-blocking advisory path and was reported as such. Two resolver tests that
previously proved casilla 63 projected a value were rewritten to pin the refusal,
with their original claims preserved in their docstrings rather than deleted.

The constraint that forced this shape is worth recording for whoever adjudicates:
no validated registry authority handle reaches `calculation_actions.py` or
`_calculation_source_staging.py`, and the calculation source context carries a
single revision and no authority, so the application layer CANNOT select a Modelo
303 revision while serving Modelo 390. Resolving the figures cross-modelo — which
is what the "restates the periodic outcome" reading would require — needs an
authority threaded through several layers, and that is a change with its own
design cost, not a local fix.

## Recommendations

### What was remediated during this audit

Tier four is CLOSED. The annual-Orden validators assert shape rather than the
legal figures, so a future Orden that changes a coefficient is accepted while a
garbled extraction is still refused. Both directions were proved by execution.
The five duplicated Lorca comparisons are gone.

The drift-gate pattern was extended and made honest. The amortizacion rate is now
bound to its dated parameter by a test that RESOLVES the registry, and the
literal-restating test was renamed and documented as explicitly not a drift gate
so no future reader mistakes it for protection.

The Modelo 200 rate-band thresholds are typed money parameters in both revisions,
with all ten inline occurrences replaced by parameter references. All three bands
were re-measured and still select the same tipo.

The article eighty-one split is CLOSED. The maternidad figures are registry
parameters across all six Modelo 100 revisions, each grounded in that year's own
manual, and the consumer resolves them at runtime and fails closed. The raised cap
is now DERIVED from its two inputs rather than stored, and the reform year is
expressed as PARAMETER PRESENCE rather than an integer. The manual's own worked
example reproduces exactly.

The article fifty-eight and sixty-one qualifying conditions, and the article
twenty-three carry-forward window, are authored across all six revisions. The
conditions are bound by a drift gate rather than a runtime read, deliberately:
they are consumed at roughly twenty call sites inside per-descendant predicates,
and the ladder's second rung is the proportionate answer there.

### What is BLOCKED, and why it must not be forced

Three clusters cannot be authored without either misstating the law or breaking
calculations that work today, and each was measured rather than assumed.

The bienes de inversion figures key on the ACQUISITION year. Modelo 303 declares
revisions only from 2022 while acquisitions run from 2000 and the window lasts
nine years, so a runtime read would refuse for most of the register. Keying on the
regularisation year instead would apply current law retroactively, which inverts
the provision's purpose.

The prorrata especial margins are the same trap and sharper: one provision, two
values, two validity windows and two DIFFERENT comparison operators, with the
earlier value governing years no revision covers.

The SAL figures and the maritime exemption fraction have no period in their
consumer signatures at all, so promotion would require a signature change before
any registry work is meaningful.

### The decision this audit does not make

Every blocked item reduces to one missing capability: a registry parameter is
addressed by modelo, revision and filing period, and cannot express a value whose
validity keys on an EVENT DATE such as an acquisition. A follow-on ADR must decide
whether parameters gain that axis. Until it does, the blocked figures are
defensible leaf constants and should be given corpus drift gates rather than being
relocated.

### The standing rules for anyone continuing this work

Apply the selective test, never blanket relocation: does the provision fix a
number, or a reference to a number somebody else re-fixes? Preserve deliberate
non-sharing between provisions, because three sites correctly refuse to merge
values that agree today and consolidating by value rather than by provision would
introduce defects. Leave provably closed windows as leaf constants.

Never substitute a catalogued-but-wrong legal reference to make validation pass.
During this remediation an invented citation to an uncatalogued RIRPF article was
refused, and the parameter was WITHDRAWN rather than repointed: a false legal
claim inside filing-grade data is worse than an honestly labelled Python constant.

### A finding about the registry itself, which is positive

The grounding validation caught two authoring errors immediately and by exact
message: a legal reference cited outside its effective window, and a reference to
an uncatalogued article. Registry authoring is safe to attempt precisely because
these refusals are strong and specific. That strength is the argument for moving
more values in, not fewer.

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
