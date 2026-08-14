---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:8d216081a763aa3705a8ff6b38d60e0fda064a81f5ec33a98c2567d0246eec28'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-load-closure-census-audit]]"
---

# `registry-temporal-coverage` audit: `drift census`

## Scope

Every production Python module under `src/cadrumo` and under `dev`, scanned for
regulatory data living outside the sanctioned channels. Closes the second of the
two enumeration denominators the coverage decision left open; the import-closure
axis is closed by the load-closure census beside this record.

The instrument is `dev/quality/regulatory_drift_census.py`, reconciled against
the reviewed ledger `dev/quality/regulatory_drift_dispositions.toml` and gated by
`src/cadrumo/tests/test_regulatory_drift_census.py`. It quantifies over the
SOURCE, never over a list of known offenders, because a census that iterates a
known-offender list cannot see an offender nobody listed and being unlisted is
exactly the question.

Eight detectors, each present because a real instance of it exists in this tree:
a bare integer in the filing-year span; a name carrying AEAT tax vocabulary bound
to a number; a `Decimal` literal that is not a scale or rounding quantum; a
collection of two or more filing years; one entry of a mapping keyed by a
`Modelo` member; a comparison or match on a concrete `Modelo` member; a regular
expression that parses Spanish AEAT design prose to derive a filing wire fact;
and filing wire facts checked into `dev` as data files.

**625 findings** across **243 files and directories**, every one adjudicated:
**254 enrolled** to a plan row, **337 deferred** with a reference, **34
allowlisted** as not regulatory data. Zero unadjudicated, zero stale ledger rows,
zero ambiguous matches. A re-run reproduces the finding set exactly, byte for
byte, and a gate asserts it.

Sanctioned channels are excluded structurally rather than by allowlist:
`src/cadrumo/core/external_constants.py` is the curated leaf home the
authority-flow rule grants, and the registry authoring tree is data by design.

Two scope decisions are stated rather than assumed. **The test surface is
measured and not adjudicated**: it carries **14,995 findings**, overwhelmingly
expected values a test takes from an external authority, which the quality-gates
rule requires it to carry. The census reaches that scope on demand and a gate
keeps the exclusion from becoming silent. **The plan row this census executes is
wider than the version quoted in its dispatch**: the live row also scopes `dev/`
and names the export-tree design-prose grammar as an in-scope instance, and this
census executes the live row.

## Findings

### drift-census | high | one regulatory value has two independent homes, which is the defect the one-canonical-home rule exists to prevent

`_MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR` is declared twice: at
`src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py:70` and again at
`src/cadrumo/application/modelo/_profile_binding.py:897`. Two modules hold the
same regulatory year independently, so a change to one leaves the other stating
the old year and nothing detects the disagreement.

This is the clearest single defect the census found and the only one where the
harm is already realised rather than latent. Remediation is one canonical home --
the registry declaration the supported-year row lands, or the curated
external-constants channel if it is a true leaf -- and deletion of the second
copy in the same change, per the no-legacy rule's delete-not-bridge direction.

### drift-census | high | the applicability rule table is 27 entries, not the 28 the plan states

The plan's Description carries "28 `ModeloApplicabilityRule` literals across 27
modelos". The census derives **27** constructions across 27 modelos. The
difference is a grep artefact: a search for the constructor also matches the
`class ModeloApplicabilityRule(BaseModel):` definition line at
`src/cadrumo/domain/calculations/registry/_applicability.py:210`.

Nothing about the migration changes, but the figure is quoted in a deletion
inventory that a later reader will reconcile against. A count derived by
mechanical enumeration should replace the grep-derived one, and the mismatch is
worth recording because "28 literals" reads as a fact rather than as a search
result.

### drift-census | high | the export-tree generator encodes the interpretation of official AEAT design prose as a Python grammar

`dev/registry/_export_tree.py` carries five regular expressions that read Spanish
AEAT design prose and derive filing wire facts from it: field width and decimal
places from a "N enteros y M decimales" clause at `:70` and `:75`, a fixed wire
value from a `Constante` clause at `:79` and `:118`, and a trailing `Nota N`
reference at `:89` and `:93` whose presence decides whether a slot is a closed
wire fact at all -- the module's own comment at `:84` records that Nota 8 and 9
carry a filing period and Nota 10 gates whether a slot may be filled.

What is encoded here is not a value but a reading of official text, and a reading
is exactly the kind of regulatory semantics the authority-flow rule places in the
registry. No row in the plan moves it. The census recommends one and records the
deferral in the meantime.

### drift-census | high | the named-constant detector was blind to every value written as a Decimal, and the miss was found by checking a case the plan named

The first build of this census missed
`EXPECTED_DIFFICULT_JUSTIFICATION_PCT` at
`src/cadrumo/domain/calculations/registry/_m303_orden_constants.py:18`, one of the
four values the plan names in that module. Two independent exclusions coincided:
the value-shape detector skipped `Decimal("1")` because `1` is a scale literal,
and the name-driven detector skipped it because the assigned value is a call
rather than a bare number. The constant is written `Decimal("1")` and carries a
`_PCT` suffix, so both signals were present and neither fired.

The name-driven detector could therefore not see ANY constant written
`NAME = Decimal(...)`, which is how this repository writes every regulatory
quantity. It was fixed by teaching the value test to look through a `Decimal`
call, which raised the census from 614 findings to **625** and surfaced eleven
constants nothing had reported, including a de minimis reconciliation tolerance
and a set of zero-valued field defaults.

Two things are worth carrying forward. First, the miss was found only because the
plan named a specific case to check against, which is what a
known-instance control is for; without it the census would have reported a clean
residue over a detector with a hole in it. Second, the residual limitation is
the same shape and is stated rather than fixed: the name-driven detector is
vocabulary-driven, so a regulatory constant named in English outside the
vocabulary is still invisible -- `EXPECTED_MODULE_DISTRIBUTION_VECTOR` in the
same module is the worked example, caught here only because the whole file
carries a file-level decision.

### drift-census | medium | 219 filing-year literals live in Python, dominated by a validation span repeated across the tree

The census finds filing-year integers in **219 file-and-symbol positions** under
`src/cadrumo`. The bulk are the 2000-to-2099 and 2000-to-2100 bounds repeated on
pydantic fields, CLI options and repository filters; the remainder are concrete
transitional years individual surfaces pin, such as the censo foundation year at
`src/cadrumo/domain/calculations/registry/_censo_modelos.py:90`, the M100 letter
casilla first year at `_export_parse.py:43`, and the registry minimum filing year
at `_validate_previous_filing_year_coverage.py:64`.

All 219 are enrolled to the supported-filing-years row, which the plan already
charges with replacing every Python-resident year set. The census gives that row
its denominator: it is not one declaration replacing one constant but one
declaration replacing a bound restated in over two hundred places, and the row
should expect to sweep files rather than edit a single site.

### drift-census | medium | 142 modelo-conditional branches sit outside the registry package and no row covers them

Behaviour conditioned on a concrete `Modelo` member appears in **142
file-and-symbol positions**, of which the majority are in the application layer:
which modelo folds into which, which export shape applies, which reconciliation
runs. The coverage decision rules that no modelo may carry its own schema
divergence, and the structural gate it installs is scoped to generic registry
schema types and generic authority construction, so none of these branches is
covered.

They are not all defects. Routing a workflow by modelo is legitimate application
logic; deciding a modelo's regulatory treatment in a Python branch is not, and
nothing in the syntax separates them. The census recommends a row that classifies
each site on that axis, and defers the group until one exists rather than
excusing it.

### drift-census | medium | per-modelo regulatory tables live in core, keyed by modelo, with their legal grounding in comments

Three core modules hold modelo-keyed tables the registry could hold instead.
`src/cadrumo/core/_amendment_kind_regime.py:146` declares the date from which
each modelo's autoliquidacion rectificativa mechanism applies, and each entry
carries its own orden or manual citation in a comment beside it -- the citations
are the tell that these are dates the law fixes.
`src/cadrumo/core/_result_disposition.py` declares which result dispositions each
modelo admits, which is a property of that modelo's official design.
`src/cadrumo/core/_modelo.py:265` and `:279` carry Spanish operator-facing prose
explaining, per modelo, why the application does not model an obligation, fusing
a scope decision that is registry data with an explanation that is a locale
string.

The `Modelo` enum is the sanctioned core home for the identifier. The tables
beside it are not the identifier.

### drift-census | medium | the foreign-asset thresholds module is half migrated, and the half that remains is the regulatory half

`src/cadrumo/application/_foreign_asset_thresholds.py:21` and `:25` map each
modelo to a registry parameter id, so the threshold amounts themselves are
already registry-resident and only the routing is in Python. `:29` declares which
obligation groups each modelo covers, and that scope is registry-resident
nowhere.

This is worth naming because a reader scanning the file sees parameter ids and
concludes the module was migrated. It was migrated on the amount axis and not on
the scope axis, and the unmigrated half is the one that decides what a taxpayer
is obliged to declare.

### drift-census | medium | reduction coefficients and transitional windows sit as Decimal and int literals in the domain

`src/cadrumo/domain/fincas/_tier_resolver.py` carries the reduction coefficients
0.05, 0.50, 0.60, 0.70 and 0.90 as `Decimal` literals at the resolver, beside a
default ejercicio amendment year and a rehabilitation lookback window.
`src/cadrumo/domain/modelos/_dt12_reduccion.py:30-34` carries five constants
encoding the DT12 transitional window. `src/cadrumo/application/modelo/_art109_activity_income.py`
carries the article 109 coefficient 0.70, and `_dt12_advisory.py` the 20000
threshold.

Each is a number a provision fixes, held outside both the registry and the
curated external-constants channel. No row moves them.

### drift-census | low | the dev registry tooling holds per-epoch filing data whose growth rate is already measured

The census counts **10 epoch directories** of filing wire facts under
`dev/registry/mappings` and `dev/registry/render_profiles`, across Modelos 200,
303 and 390. These are enrolled to the collapse row, which already carries the
measured cost of the pattern; the census contributes the current denominator so
that row can be proven by property rather than by tally.

### drift-census | low | the detector finds itself, and that is recorded rather than special-cased

`dev/quality/regulatory_drift_census.py` names the filing-year span it searches
for, so it appears in its own census. The finding is allowlisted with that
reason rather than excluded by a rule in the scanner, because a scanner that
quietly skips itself is one edit away from quietly skipping something else.

## Recommendations

Every finding above carries a disposition in the committed ledger; none is left
unclassified. Four recommendations ask for new plan rows, and the census defers
the corresponding findings against this record until those rows exist.

Collapse the duplicated Madrid autonomic deduccion filing year onto one home and
delete the second copy in the same change. This is the one finding where the
harm is already realised, and it is small enough to land inside an existing
row's sweep rather than needing its own.

Open a row for the export-tree design-prose grammar that decides where the
reading of official design text belongs. The two honest options are moving the
derived wire facts into the registry authoring tree so the grammar becomes a
one-shot import, or keeping the grammar and declaring it a sanctioned channel
with its own gate. Leaving it undeclared is what the census objects to.

Open a row that classifies the 142 modelo-conditional branches on the
orchestration-versus-treatment axis, exhaustively and by derivation, in the shape
the embed classifier already uses inside the registry package. The census
supplies the derived set; what it cannot supply is the judgement, and a
classification row is where that belongs.

Open a row for the per-modelo regulatory tables in core and the unmigrated scope
half of the foreign-asset thresholds module. All four sites declare, per modelo,
something the modelo's own revision could declare, and they are small enough to
move together.

Correct the plan's Description figure from 28 applicability literals to 27, or
restate it as "one rule per modelo across 27 modelos", which is the fact the
number was reaching for and is immune to the grep artefact.

Treat the test surface's 14,995 findings as a separate question with its own
answer, not as a backlog. The quality-gates rule requires a test's expected value
to come from an external authority and to live in the test; the interesting
subset is tests whose expected values were derived from the registry formula
under test, which is a tautology question rather than a drift question and needs
a different instrument.
