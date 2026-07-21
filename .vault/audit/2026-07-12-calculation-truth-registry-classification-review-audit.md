---
tags:
  - '#audit'
  - '#calculation-truth-registry-classification-review'
date: '2026-07-12'
modified: '2026-07-14'
related:
  - "[[2026-07-12-calculation-truth-registry-plan]]"
  - "[[2026-07-12-calculation-truth-registry-reference]]"
---

# `calculation-truth-registry-classification-review` audit: `P01.S01 legacy classification index`

## Scope

Review the P01.S01 Vault-only classification reference and execution record
before closing the continuation-plan step. The review covers arithmetic,
source-line anchoring, disposition wording, and the boundary against falsely
closing a legacy checklist row. No production code, tests, or user-facing
documentation changed.

## Findings

### mechanical-accounting | info | the classification index accounts for every unchecked legacy row exactly once

An independent read-only recomputation confirms the pinned legacy-plan hash,
705 unchecked rows, 38 exact matches to the published live/filed capture
expression, the complete listed anchor set, and a 667-row complement. The
per-section table also totals 705, 38, and 667.

### disposition-boundary | low | the review prevented an unproved actionable claim

The first draft described the 667-row complement as actionable or unverified
and phrased absence-of-evidence conclusions too broadly. The reference and
execution record now call that set an unverified residual requiring current
grounding and state that delivered and superseded are zero only within this
index because it supplies no per-row proof. The correction preserves the
mechanical result and removes the overclaim.

### wrapped-row-classification | high | the published blocked and residual totals do not apply the stated full-row rule

The hash and 705 unchecked-row count are reproducible, and no delivered or
superseded claim is made. However, the reference says its expression is
evaluated against each row's full checklist text while its published 38-anchor
set is the result of testing only the physical checkbox line. Recomputing the
rule over each complete Markdown list item, including its indented
continuations, finds 58 blocked rows and 647 unverified residuals. The omitted
20 blocked anchors are `753`, `982`, `1020`, `1176`, `1246`, `1316`, `1373`,
`1430`, `1546`, `1645`, `1710`, `1960`, `2078`, `2152`, `2228`, `2286`,
`2346`, `2888`, `2917`, and `4412`. Consequently, the published section
blocked/residual counts are also wrong in Waves 5, 7-11, 13-17, 19-21, Tasks,
and Teardown. This blocks truthful completion of P01.S01 because P01.S02 would
otherwise inherit an accounting rule that is contrary to the reference's own
definition.

### wrapped-row-correction | info | the corrected index parses complete logical Markdown bullets before matching

P01.S01 was reopened through the plan CLI before correction. The repaired
parser takes the opening unchecked bullet and its direct indented continuation
text, stops at a sibling or ancestor bullet, and excludes nested bullets and
their continuations because each nested unchecked checkbox has its own source
line and disposition. Recalculation yields 58 evidence-gated rows and 647
unverified residuals; the reference's anchor list and every affected section
count now carry those values. The category is intentionally named
evidence-gated: the expression is a mechanical full-bullet dependency signal,
not a claim that every match has completed individual external-blocker
adjudication.

### p01-s02-publication-boundary | low | the S02 publication designates the corrected reference as the sole authoritative ledger without widening it

The S02 record adds only the authoritative-publication designation and repeats
the corrected `0` delivered, `0` superseded, `58` evidence-gated, and `647`
unverified counts. It does not duplicate the source-line ledger, reclassify an
individual evidence-gated row as externally blocked, or promote an unverified
residual to genuinely actionable. Its stated row-level current-source plus
execution-or-decision evidence gate preserves the boundary established by S01.
The earlier wrapped-row high finding is resolved by the corrected full-bullet
reference and its matching S01 outcome; no CRITICAL or HIGH finding remains
for S02. The legacy plan checkboxes and all production, test, documentation,
and locale surfaces remain outside this Vault-only publication scope.

### row-level-closure-invalid | high | the published index is not the final disposition ledger required by P01

A later completion review found that the publication boundary was still too
permissive. The reference classifies `58` rows only through a lexical
evidence-dependency rule and leaves `647` rows as unverified residuals; it does
not assign the required delivered, superseded, blocked, or genuinely actionable
disposition to any individual legacy obligation. Its pinned legacy-plan SHA-256
is `c56016eff8788947381fe692b29ece937706b7dbd313d2be2dad1dead8daa120`,
while the current 705-row plan is
`c46325be3870a5643825935b01da36747b3acedd2a811124669c2dd362ab04d3`.
The reference also cites the removed `src/aeat` tree even though current source
is under `src/cadrumo`. At least 131 calculation-truth-registry execution files
exist, but the published index maps none of them to its individual rows.

The canonical plan command therefore reopened both P01 Steps. P02.S03 remains
open: neither the mechanical keyword partition nor a similarly named current
symbol is sufficient evidence for a successor implementation backlog.

## Recommendations

P01.S02 must attach current-source and row-level execution or accepted-decision
evidence before promoting any unverified residual to delivered, superseded,
blocked, or genuinely actionable. Do not alter a legacy checkbox through this
classification record.
- Repair the reference's row parser and all affected total/section/anchor
  tables before using P01.S01 as the input to P01.S02.
- Use the corrected 58/647 index for P01.S02; preserve the separate
  source-and-execution evidence requirement before assigning a final
  disposition to any individual row.
- Keep P01.S01 and P01.S02 open until all 705 current-plan rows have reproducible
  source plus execution-or-decision evidence and exactly one final disposition.
- Do not close P02.S03 or convert the 647 residuals into implementation work by
  inference. Narrow, separately approved adjudication plans may investigate
  bounded candidate families without claiming to complete the 705-row ledger.
