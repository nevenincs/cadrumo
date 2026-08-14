---
tags:
  - '#research'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e99a4cfaf7063ce368ad27d9c3f161d189253f077438a9b50212a3eeffaba118'
related: []
---

# `registry-temporal-coverage` research: explicit support horizons and schema-family coverage

The registry cannot safely enforce one literal calendar interval for every modelo:
forms have different legal inception dates, annual ejercicio designs are published on
a different clock from monthly and quarterly forms, and some mid-year revisions split
one filing year by period. The current corpus nevertheless has a real consistency
defect: one `PeriodSelector` simultaneously implies legal applicability, grounded
source coverage, and runtime support. Open-ended selectors therefore make unsupported
future coverage indistinguishable from reviewed authority. The evidence favors a
shared coverage contract with identical dimensions and gates for every revision, while
allowing the legally supported interval and applicable schema families to differ only
through explicit, grounded dispositions. An ADR must decide that contract and whether
the 94-revision governance backlog is a hard production cut or a staged refusal.

## Findings

### The loaded corpus has no single honest common calendar horizon

A fresh loaded-authority inventory contains 73 modelos and 94 revisions. Modelo
coverage rises from 27 in 2015 to 56 in 2023, 64 in 2024, and 72 in 2025, then falls
to 67 in 2026. The six selectors that cover 2025 but not 2026 are M100, M189, M280,
M289, M345, and M714; M136 begins in 2026. These are not automatically defects:
annual modelo coverage is keyed to ejercicio and official publication, while M136 is
a newly enrolled quarterly form. `select_revision` correctly treats
`(modelo, filing_year, period)` as the natural key and refuses zero or multiple
matches; it cannot determine whether a declared selector is grounded in an official
design. See `src/cadrumo/domain/calculations/registry/_temporal.py:18` and the accepted
period-resolution decision `2026-06-10-period-revision-resolution-adr`.

The rejected alternative is forcing every modelo to a shared start year or extending
all six 2025-bounded forms into 2026 mechanically. That would turn missing evidence
into fabricated authority. The viable shared invariant is identical coverage axes for
every modelo, not identical legal history.

### Open-ended selectors dominate and conflate support with extrapolation

Of 94 revisions, 67 use an open `year_from` range, 12 use a bounded range, and 15
enumerate explicit years. Seventy-four revision validity windows also omit
`valid_to`. A single old revision consequently claims every future year until someone
authors a replacement, even when its layout, filing schedule, extraction surface, or
legal parameter evidence has not been rechecked for that year. The current bracket
coverage validator explicitly does not validate the tail of an open revision beyond
its last bounded bracket window, so it cannot serve as a general future-year gate.
See `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py:171` and
`src/cadrumo/domain/calculations/registry/_schema_references.py:106`.

Three selector/date pairs already demonstrate semantic ambiguity: M200 declares
selector start 2024 but `valid_from=2025-01-01`; M309 declares 2004 but starts
`2003-12-31`; M720 declares selector start 2012 but starts `2013-02-01`. M309 may be a
legitimate publication/effectivity boundary, while M200 and M720 require
adjudication. A mechanical equality rewrite would be unsafe; a gate needs an explicit
date-axis relationship or exception reason.

### Section presence is consistent only for the structural core

Across active revisions in 2025, casillas, application links, and workbook parity
references are present in all 74 revisions. Other families vary sharply: parameters
15/74, formulas 30/74, bindings 29/74, relations 9/74, export layouts 6/74,
extraction profiles 19/74, filing schedules 31/74, completeness manifests 36/74, and
verification predicates 10/74. Some absence is legitimate—informative modelos must
not carry calculation formulas or relations—but absence currently says neither
“not applicable” nor “not implemented.” The informative-model invariant proves that
schema-family applicability is domain-dependent, not globally uniform. See
`src/cadrumo/domain/calculations/registry/_validate_revision_rules.py:45` and
`src/cadrumo/domain/calculations/registry/_schema.py:1009`.

The favored option is a revision-owned coverage manifest derived against the real
schema field set. Every family receives one typed disposition such as populated,
not_applicable, or blocked_pending_evidence, with a reason and source/legal references
where the claim is substantive. A handwritten list of current families would drift;
the gate should derive enrollment from `ModeloRevision` field metadata, as the
existing manifest-only and governance field sets already do.

### Revision governance is declared but not enforced at the production boundary

All 94 loaded revisions currently resolve to `pending_review`. The schema makes that
the honest fail-closed default and already defines agent-reviewed and operator-reviewed
states, but snapshot construction checks only selected legal-reference review status;
it does not check the revision's own governance stamp. Thus an operator-reviewed legal
slice can still serve a wholly pending revision. See
`src/cadrumo/domain/calculations/registry/_schema_governance.py:1`,
`src/cadrumo/core/_revision_review.py:39`, and
`src/cadrumo/domain/calculations/registry/_snapshot.py:298`.

This is the largest dev-to-production state leak. Mechanically upgrading the 94 rows
is rejected because authorship and review cannot be derived. The ADR must choose
between an immediate snapshot refusal for every pending revision and a staged boundary
that preserves non-filing inspection while making production eligibility visibly red.
Either option must require genuine operator signoff for filing authority, matching the
legal-reference boundary.

### Backfill can be generated as candidates but authority cannot be generated

A safe program can enumerate every `(modelo, year, period, schema_family)` cell,
resolve its owning revision, attach source and legal evidence, and classify mechanical
gaps. It can also generate candidate files from a prior year's structurally identical
revision and prove compiled equality before human adjudication. It cannot assert that
an official design, deadline, rate, or legal window remains unchanged. Those claims
require AEAT/BOE evidence and operator review.

The strongest gate sequence is therefore: derive a complete matrix from loaded
authority; reject ambiguous or internally gapped selectors; require an explicit
disposition for every schema family; cap support at an evidence-backed
`coverage_through` year/period; verify nested temporal rows cover every claimed cell;
and require operator-reviewed revision plus selected legal references before serving a
filing snapshot. New revisions can meet the contract immediately. Existing gaps should
be emitted as a finite worklist rather than hidden behind allowlists or inferred
defaults.

### Re-measured at HEAD after the Modelo 390 split landed

A second loaded-authority measurement, taken after the Modelo 390 annual-epoch
split was committed, supersedes the counts above: 73 modelos and 97 revisions;
66 open `year_from` selectors, 12 bounded ranges, 19 enumerated-year selectors;
73 revisions with no `valid_to`; 2026 modelo coverage 66. All 97 revisions
resolve to `pending_review`. The three selector/effective-date disagreements
persist exactly as reported: Modelo 200 selector 2024 against `valid_from`
2025-01-01, Modelo 309 selector 2004 against 2003-12-31, Modelo 720 selector
2012 against 2013-02-01.

Two consequences are newly measurable. First, the revision-review gate is now
live at the production boundary, so every filing snapshot refuses: Modelo 303
2025 1T, Modelo 390 2025 0A and Modelo 100 2025 0A each raise
`filing-grade snapshot requires operator_reviewed revision`. The in-flight
export-fragment campaign attests only nine revisions, leaving 88 pending with
no declared owner. Second, unbounded extrapolation is quantified rather than
inferred: 64 modelos claim identical coverage for 2027, 2028, 2029, 2030 and
every later year, because nothing terminates their selectors.

The Modelo 390 split is also the empirical unit cost of an epoch repair: 156
files and roughly 12,850 inserted lines to replace one open revision with four
bounded epochs, on a modelo carrying 37 fragments per revision. That cost does
not generalise. Triaging the 66 open revisions by remediation shape gives 10
that need only a bounding edit (the modelo is already versioned per year, or
claims at most two years), and 56 that claim a long single open span. Those 56
claim 653 modelo-years across 1,874 fragments, but the distribution is extreme:
Modelo 341 asserts 27 filing years on 6 fragments, Modelo 038 25 years on 6,
and Modelo 840, 156, 186 and 848 24 years each on 6 to 8. Only three carry real
bulk — Modelo 200 at 1,045 fragments, Modelo 232 at 256 and Modelo 180 at 89.
The dominant cost is therefore per-modelo-year evidence adjudication, not file
mechanics.

### The authority grade already exists, as prose rather than data

Twenty-four `revision.toml` manifests already declare the distinction the
coverage contract needs, in a comment rather than a field. Modelo 341 states it
plainly: scheduling/applicability-grade, declaration-header casillas only, no
bundled diseño de registro, so no numbered money-closure casilla is fabricated.
The affected modelos are 038, 121, 122, 140, 143, 156, 165, 179, 181, 185, 186,
220, 222, 233, 234, 238, 270, 341, 380, 490, 576, 592, 763 and 848; twenty-two
of them fall inside the 56-revision long-span set.

Nothing types or enforces that claim. `CalculationClass` is a
`Literal["filing", "informative", "summary"]` declared on the modelo, not the
revision, and it encodes reporting role rather than evidence grade. A
six-fragment scheduling stub and a filing-grade revision are consequently
indistinguishable to every consumer, which is the precise mechanism by which an
open selector converts scheduling applicability into apparent filing authority.

This reframes the horizon question. Bounding Modelo 341 to its bundled-source
years would be wrong: its approving orden genuinely extends to subsequent years
on the scheduling axis. What is wrong is that the stub can reach a filing
surface at all. The evidence therefore favours binding the horizon to a declared
grade — evidence-bounded epochs where the claim is calculation or filing, an
open scheduling window that is structurally barred from filing snapshots where
the claim is applicability only.

### Scope not yet adjudicated

This research did not verify 73 modelos' legal inception dates or fetch every annual
AEAT design publication. It also did not decide whether “supported history” means all
years since each form's statutory creation, a product support window, or every year
for which a source artefact is bundled. Those are distinct product and legal choices;
the ADR must name one before a backfill campaign can claim completeness.

## Sources

- `src/cadrumo/domain/calculations/registry/_temporal.py:18`
- `src/cadrumo/domain/calculations/registry/_schema_references.py:106`
- `src/cadrumo/domain/calculations/registry/_schema.py:1009`
- `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py:45`
- `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py:171`
- `src/cadrumo/domain/calculations/registry/_schema_governance.py:1`
- `src/cadrumo/core/_revision_review.py:39`
- `src/cadrumo/domain/calculations/registry/_snapshot.py:298`
- `.vault/adr/2026-06-10-period-revision-resolution-adr.md`
- `.vault/audit/2026-08-14-registry-corpus-structure-hardening-audit.md`
