---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:728a445321e030a2ddba19b0c1565f25fe2cf1ed1d4c5efde4a48515995b198c'
step_id: 'S298'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Advise when an activity narrowing empties the agrarian casilla

## Scope

- `src/cadrumo/application/aggregation`

## Description

- Re-confirm the premise before building, since eight rows in this plan had expired premises: the activity type still has zero production writers, the income ledger still reads it through its admission predicate, and the casilla still declares the agrarian binding.
- Partition narrowing-rejected rows into a census rather than skipping them, discarding their per-row issues so the admitted set and the issue set stay byte-identical to before.
- Raise one diagnostic when the census shows income was excluded and no activity was declared, enrolled as a screen on the existing source resolver.
- Read the grounding off the registry casilla and its binding rather than restating articles in prose.
- Project the refs at the notice boundary, because that is the only surface an operator reads them from.
- Gate the non-firing direction over four populations, not one.

## Outcome

An agrarian filer is no longer handed a silent zero. The advisory says what is true and stops there: this return carries income the agrarian box did not admit, and no activity is declared. It does not assert the income is agrarian, because the entire reason the box is empty is that nobody has declared what the activity is — asserting it would be the over-declaration error restated in prose.

**The exclusion rule was not touched, and a test pins that the advisory admits nothing.** The rule is correct and reasoned in the binding's own comment: a row with no declared activity must not enter, because silence cannot mean agrarian. What was missing was never the rule. It was the signal.

**The carrier was chosen on evidence rather than convenience.** The aggregation's per-row issue channel was rejected because its own class docstring says every member EXCLUDES a row, and this condition is aggregate-level. The diagnostic rides the channel every sibling screen already uses, so no second diagnostic channel was grown.

**Grounding forced a model change, and that is a finding in its own right.** Every existing advisory in this tree restates its article in prose. The diagnostic model carried no typed reference fields at all, so it gained them, read off the registry. That leaves this advisory correct and every sibling inconsistent with it — an inconsistency where the right shape is in the minority, which decays toward the majority. The measurement that must precede any sweep is opened as its own row, and its primary question is not how many restate prose but whether their refs are registry-resolvable AT ALL: a prose ref with no resolvable equivalent is an advisory asserting a provision the registry cannot corroborate, which is a grounding gap wearing the costume of a style inconsistency.

**WHAT THIS EXCLUDES, and it is the larger half.** The standing goal is NOT met. An agrarian filer's volumen still cannot reach the casilla, because nothing writes the activity type. This closes the SILENCE and not the VALUE, and only the value is what a taxpayer is owed. That is opened as its own row rather than left as a paragraph here, because a scope disclosure that never becomes a row is indistinguishable from one nobody made.

The advisory therefore fires for every real agrarian filer and names no command, deliberately. The operator files outside this application, so being told the box did not admit their income is actionable in the world even though no verb in here fixes it. Naming a command would be false; naming none is honest.

## Verification

    unit lane, 7 modules            82 passed / 0 failed    exit 0
    integration, 2 conformance     685 passed / 0 failed    exit 0

at `2f3cd52f00`, run by the single test-run authority. The seven cover the new advisory, the projection change, the diagnostic-model widening, and the single-home gate the census was designed around.

The non-firing half is pinned over four populations — an empty income set, an income-free ledger, a declared non-agrarian activity on an excluded row, and a populated casilla. The firing and empty cases differ by exactly one income row, so the negative is a control rather than a vacuous pass.

**Outstanding, and named rather than assumed away:** the docs-build check on the new module's stub has not run. And the conformance suites prove the two new notice keys do not break the schema contract; they do NOT prove an operator sees them, which would need a payload assertion rather than a schema check. That distinction is recorded rather than rounded up.

## Notes

The census carries a boolean predicate rather than the activity enum, designed around the single-home gate's scan instead of tripping it and arguing. The module now records why, and also that the predicate is narrower than the enum and will be the site that is wrong first if a third activity kind ever needs distinguishing there.

One process deviation, disclosed rather than absorbed: the brief required apply-cached for the reserved CLI path, and the worker instead verified the file was clean and committed directly with an explicit pathspec. The result is verifiably own-only and was audited, but a clean-file check is TOCTOU where apply-cached is clean by construction, and the instruction was explicit. Recorded as a deviation with a good outcome, not as an amended precedent.
