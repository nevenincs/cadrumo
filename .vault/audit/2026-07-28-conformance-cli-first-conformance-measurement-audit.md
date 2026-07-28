---
tags:
  - '#audit'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
  - "[[2026-07-27-conformance-cli-adr]]"
---

# `conformance-cli` audit: `first conformance measurement`

## Scope

The first real conformance measurement of the bundled AEAT modelo registry, taken
with the tool this campaign built, at the campaign's own HEAD. Produced by the
`report` and `coverage` verbs of the dev-side conformance CLI over the validated
registry: 73 modelos, 90 revisions, 1261 reconciled casillas, 21 bundled oracle
payloads, 15792 locale label leaves per locale.

This is a measurement record, not a verdict. Every figure below is discovery
evidence about coverage of checking; none of it is a correctness score, and no
row here authorises downstream work.

## Findings

### governance-provenance-is-entirely-undeclared | expected | Every revision is unreviewed and no revision names an engineer

The review census reads `pending_review 90`, `agent_reviewed 0`, `operator_reviewed 0`,
and `engineered_by` is declared on zero of 90 revisions. This is the fail-closed
default working exactly as the governing decision designed it: absence means
pending, so the backlog is visible on day one rather than assumed away.

It is also the campaign's most actionable output. Ninety revisions carry no
attestation of who engineered them or who reviewed them, and until this campaign
there was no field in which to say so. The stamping campaign that follows is the
work this number exists to schedule.

### independent-checking-is-the-thin-axis | measured | Under five percent of reconciled casillas are checked against an outside authority

`independent_check_coverage` is 0.0468 across the registry: 59 of 1261 reconciled
casillas are checked against a bundled AEAT oracle. A further 39 of 90 revisions
reconcile nothing at all, which is a different fact again and is reported as such
rather than as a zero.

Read correctly, this says most reconciliation in the registry is the engine
agreeing with itself. It does not say any number is wrong. The distinction is
carried inline on the axis itself so it cannot be lost by a reader skimming rows,
and the campaign's own experience is the argument for the metric: the prorrata
rounding defect and the zero-volume divergence both sat inside the ninety-five
percent that nothing independently checked, and both were found only because a
grounding pass went looking.

### model-law-coverage-is-complete | clean | Every revision satisfies its required evidence tiers

`rows_without_required_gap` is 90 of 90, and `registry_scope.diagnostics` is zero.
The legal-authority, official-source and layout-authority tiers are satisfied on
every revision in the tree. This axis is genuinely healthy and worth stating
plainly alongside the thin one, because a governance report that only ever reports
gaps trains its reader to discount it.

### classification-axes-disagree-on-twenty-four-modelos | open | Two axes describe the same partition and do not agree

Twenty-four modelos carry a divergence between `calculation_class` and
`tax_domain`. Eleven declare the informative calculation class, seventeen carry the
informative tax domain, and the intersection is two. None of the twenty-four is
forced: the fold verifies against the real registry validator that the alternative
value is available in every case, which is what makes the divergence actionable
rather than a modelling constraint.

The two axes are not redundant labels. One is an enforced posture that binds a
modelo to an invariant refusing formulas and relations; the other is a bare label.
That asymmetry is why the disagreement is worth reporting and why mechanically
aligning them would be wrong.

### five-schema-axes-are-declared-but-never-used | open | Zero declarations produce zero failures, which is indistinguishable from always correct

Five schema surfaces exist and no TOML in the tree declares any of them: the
summary calculation class (0 of 73), support-removal decisions (0 of 90),
the review-required extraction confidence (0 of 43), the real-corpus verification
source (0 of 43), and manual extraction on the completeness manifest (0 of 52).

Each is reported as UNUSED rather than as passing. An axis nothing declares cannot
fail, and a governance surface that renders that as a clean row is lying by
omission. The summary class is the most pointed instance: Modelo 390 is the
canonical annual summary and defaults to the filing class.

### capability-coverage-thins-sharply-down-the-stack | measured | Calculation grade is majority, export formats are a minority

Calc-grade and completeness manifests each cover 52 of 90 revisions and
verification expectations 51, but extraction profiles cover 31, fixed-width export
23, and XML dictionary export 6. Authorization is granted on 30 of 73 modelos.

The shape is a funnel rather than a defect: a modelo can be legitimately
parse-only, and authorization is default-deny by design. The number worth carrying
forward is the gap between calc-grade and export capability, since a revision that
computes but cannot emit an official artefact is a filing the operator cannot
complete in-app.

### locale-coverage-sits-near-half-on-every-non-Spanish-locale | measured | Catalan 55.1, English 54.1, Hungarian 53.9 percent of label leaves

Measured across 15792 label leaves per locale. Spanish is excluded by construction,
because the official registry casilla label IS the Spanish authority rather than a
translation of anything.

### oracle-attribution-is-now-complete | clean | No bundled payload sits outside the grounding relation

Unattributed oracle payloads and unmatched oracle evidence are both zero against 21
bundled payloads. This axis was 1 when the campaign started: one payload declared
its modelo and filing year in its body but carried no year in its filename, and the
fold attributed by filename alone, so four AEAT figures had never entered any gate.
The repair also found that payload was malformed against its own corpus convention,
stuffing scenario inputs into the expected-values map.

## Recommendations

Run the stamping campaign the governance census schedules, and stamp honestly:
the CLI deliberately cannot write an operator signoff, so operator attestation
remains a human act on the file. An agent-tier stamp is the correct record for
agent-engineered revisions and should not be inflated.

Raise independent checking where it is cheapest first. The registry already
carries bundled oracle payloads for a small set of modelos; the constraint is
declared grounding claims, not evidence. Every casilla whose figure a bundled
oracle already states and the engine already reproduces is a free enrolment, and
the campaign closed one such case as a worked example.

Reconcile the twenty-four classification divergences by deciding, per modelo, which
axis is right. The fold reports the alternative is available in every case, so each
is a decision rather than a migration.

Rule on the five unused schema axes: either declare them where they belong or
retire them. An axis that has never been used in the tree's lifetime is either a
gap in the data or a surface that should not exist, and the report cannot tell the
two apart.

Treat every figure here as re-derivable rather than quoting it forward. The tool
recomputes from the loaded registry on each run, so a number copied into a document
is stale the moment a peer lands a revision. The campaign observed this directly:
independent-check coverage moved from 0.0460 to 0.0468 during the campaign's own
final hours, and the unattributed-payload count moved 1 to 0 mid-run.
