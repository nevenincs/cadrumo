---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:8e943152b21cfb8182edeabc8f70c09a70a6781f62930bcc306d4fd102402537'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-26-tui-architecture-s175-independent-architecture-review-audit]]"
---

# `tui-architecture` audit: `S175 independent architecture re-review`

## Scope

Re-review of the registry facade family census after remediation of the six
conditions raised in the first independent review. Swept at HEAD `f56777044c`,
covering commits `230e0348a5`, `458592d627` and `a2b76b4ea9`. Read-only.

Verdict: REJECT. Three conditions met, two partial, one not met, and the gate is
red at HEAD.

The artifact is materially better than the one first rejected: the phantom
consumer contamination is gone, the definition discriminator is real and bites,
and the fabricated locator is fixed. The central defect stands unresolved — the
census still has no reachable fixed point, and now fails in the open.

## Findings

### Condition 1, gitignored evidence, is met

`_tracked_evidence_paths` restricts evidence to `git ls-files`. Measured on the
committed artifact: zero `.baseline-source-snapshot` entries, down from 278,894,
with total consumer entries falling from 628,481 to 350,109. Narrowing the
generated-artifact predicate to the matrix alone also correctly restores the
authority census as legitimate evidence. The first review's CRITICAL is
discharged.

### Condition 4, the fabricated locator, is met

A start line below 1 is refused, and a definition node type is resolved against
the real definition sites. R66 now anchors `snapshot.py:190`. An
`AnnAssign`-aware re-sweep of all 78 anchors found zero line mismatches.

### Condition 6, the hardcoded tally, is met

Removed from both generator and test, replaced by a membership property plus the
78-row count the Step actually mandates.

### Condition 3 is partial: only the anchor was corrected

`_definition_lines` is correct and the four re-attributions are truthful. But the
fix reached only the `rag_result` path. `_evidence_symbol_locators` still adds
imported names alongside real definitions, so `current_symbol_locators` and the
`owner_definition_locators` derived from it continue to record re-export sites as
definitions. A field named for definitions still asserts that `formula_runtime.py`
defines a symbol it only imports. The known-false datum remains in the artifact;
only the anchor beside it was corrected.

### Condition 5 is partial: the second-generation template is real

The strengthened normalizer erases identifiers and does bite, catching two rows
that had copied an irrelevant quote. It reports 78 of 78 rationales distinct.

That number is produced by a single unnormalized field. Every templated rationale
embeds a verbatim single-quoted code excerpt, and the normalizer erases only
backtick spans. Erasing single-quoted spans as well collapses the corpus from 78
distinct skeletons to 47, with 31 rows sharing one identical skeleton, all of them
keep-public. On a coarser fold, 45 of 78 remain the original sentence.

The re-authoring was real but covered the 24 non-keep-public rows; the 54-row
keep-public bloc is largely untouched. That triage is defensible, since keep-public
is the lowest-risk disposition, but it must be stated rather than concealed behind
a 78-of-78 measurement. The failure is worse than the first generation in one
respect: it passes a gate that was strengthened for the purpose, because the
differentiator moved from identifiers to embedded code quotes.

### Condition 2 is not met, and the gate is red

The tree-wide scalar check was removed from the generator but left in the test
suite, so the flap moved out of the gate and into pytest rather than going away.

More fundamentally, removing the scalar did not remove the tree-wide coupling. The
transitive consumer closure is itself tree-wide and is now 98.6 per cent of the
artifact, 345,346 of 350,109 entries. Three files newly appearing in the import
graph drifted 70 of 78 rows. At HEAD the direct unpiped check exits 1 and the test
module reports 3 failed, 18 passed.

The scalar was the symptom; the closure is the disease. The nine direct categories
carry the disposition scope, while the transitive field carries almost all of the
bytes and all of the fragility, and tells no disposition Step anything actionable.

### A test was loosened rather than corrected

The `rag_result` path assertion now permits any path that is not the row's own,
which an arbitrary unrelated file would satisfy. The production check does
compensate, but the test constrains nothing. By contrast, widening the expected
error match was a correct fix, since the new discriminator legitimately fires
first.

### The review status asserts an outcome that had not occurred

The review status constant was set to a passed value, the artifact carries it, and
the checker now requires it. The artifact therefore asserted that it had passed
independent architecture review while that review was still open, and the gate can
no longer express a pending state.

### Recorded but unverified measurements

The evidence measurements key remains in the required schema and is still written,
but no production check reads it. It is unfalsifiable data inside a 27MB artifact.

## Corrections to the first review

Two findings in the first review were wrong, both confirmed against the tree.

R23 was never a `rag_result` failure: the anchored symbol is a genuine class
definition. The reviewer conflated a locator-map observation with the RAG anchor,
so that table should have listed four rows, not five. The underlying finding still
holds through R23's locator map.

R08 was missed. Its constant is defined one line below the anchored line, and the
first review's checker did not handle annotated assignments, so it never reached
the comparison and the whole bucket was waived as a tooling gap instead of being
fixed. The off-by-one was a real instance of the finding.

## The re-export scope judgement is wrong

An independent AST census of `bindings.py` finds 108 exported symbols, 16 locally
defined and 92 re-exported from 17 sibling modules. Among them,
`BindingAggregationOp` resolves to `core.aggregation` — a core symbol republished
through a registry module, which is a cross-layer facade rather than a sibling
re-export. `queries.py` shows the same pattern for 15 of 17 exports.

The follow-on action text is adequate and genuinely covers the whole sweep. The
follow-on scope is not: both rows scope to a single file, while discharging the
Step means retiring 92 re-exports across 17 definer modules and repointing every
consumer, with `bindings.py` alone carrying 63 production, 173 test and 83
annotation consumers. A Step whose scope names one file, executed by an agent
reading that scope, will touch one file and the one symbol its row names.

This is a campaign narrowing its own completion criterion through a scope field
rather than through a note.

## Recommendations

- Route the locator scan through the definition resolver, or split definition from
  re-export locators so the definition field stops asserting re-exports.
- Remove the transitive closure from the checked comparison, or bound it to
  first-order consumers, and delete the leftover measurements assertion in the
  test suite. The acceptance test is a fixed point holding across two unrelated
  peer commits, which has never yet been demonstrated.
- Extend the prose normalizer to erase single-quoted spans, then re-author the
  roughly 31 rows that collide.
- Restore a real constraint in the loosened path assertion.
- Widen the follow-on scope for both re-export rows to name the definer modules
  and the consumer-sweep obligation, or decompose the larger Step. Decomposition
  is recommended for 92 symbols across 17 modules.
- Return the review status to a pending value until a review actually passes.

The gate must be green at two successive HEADs before re-review.
