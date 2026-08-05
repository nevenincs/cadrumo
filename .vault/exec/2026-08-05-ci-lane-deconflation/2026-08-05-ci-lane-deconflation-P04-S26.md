---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d2954ef2357c80f1a78eaa92ef0c841398f04667841915f4cefb57a8a43d4a55'
step_id: 'S26'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Require an exec record whose evidence is a passing test to state the selection that produced it, three agents in one day nearly accepted a marker expression that selected nothing and exited zero

## Scope

- `.vaultspec/templates`

## Description

- Establish which enforcement mechanisms are actually available before choosing one.
- Widen the rule from stating the selection to quoting the instrument.
- Add the Verification section to the exec template and confirm it reaches a scaffolded record.

## Outcome

The decision record is `2026-08-05-ci-lane-deconflation-exec-verification-evidence-adr`. The
exec template gains a `## Verification` section prompting for the invocation and the runner's
verbatim summary line.

**The rule was widened from the one the row asks for.** The row requires an exec record to
state the SELECTION. That would catch the three observed instances and nothing else. The
landed rule is **quote the instrument, do not summarise it** — which catches the same three,
also catches a measurement of the wrong object (a quoted invocation names what was measured),
and is easier to comply with rather than harder, because pasting a line requires no judgement
about what to preserve while paraphrasing requires deciding what matters.

The reframing came from asking why the signal was lost. The runner already prints `NOTHING
RAN` and `PARTIAL RUN` banners naming the deselection, and three careful agents read past
them. So the gap is not that authors omit the selection — it is that they summarise the
instrument, and every summary discards exactly the part that separates a real pass from a
vacuous one. "15 passed" is true of a run that deselected 25 and of one that deselected none.

## Verification

    uv run --no-sync vaultspec-core vault add exec --feature ci-lane-deconflation --step P04.S26
    Created: .vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P04-S26.md

    rg -n "^## Verification" <that file>
    59:## Verification

That is a positive control rather than an assertion: the template edit was confirmed to reach
a freshly scaffolded record, so the section exists because it was observed to appear, not
because the file was edited and assumed to take effect. This record is the first document
written under the convention it establishes.

## Notes

**Three enforcement mechanisms were considered and two are barred, which shaped the answer
more than any preference did.** A repo-side gate scanning exec records is forbidden by the
code-stands-alone mandate — source, tests and configuration must not reference harness paths,
and a gate globbing the exec tree is exactly that reference, inverting the one-way direction.
A new always-on rule is barred by the codification retirement of 2026-07-13. The correct home,
a check in the harness tool itself, is upstream of this repository and can only be proposed.

**The template is therefore not the only home, and the reason is durability.** The template is
tracked here, but a harness upgrade has written to it before — 2026-07-30 added one line to
each of eight templates — so a local edit may not survive the next one. Because it is tracked,
a revert would surface as a diff rather than vanishing silently, but harness-upgrade commits
are the class reviewed most loosely. The requirement is therefore stated in the campaign plan's
own Verification section as well, which no upgrade touches and which is already the
established place for per-row closure criteria. Template prompts, plan binds, neither depends
on the other surviving.

**The scope is stated honestly in the ADR rather than stretched.** This convention does not
catch a decayed tree-state claim, whose command and result were both correct when run; it does
not catch a measurement whose flaw is in its setup rather than its invocation, which is how a
counterfactual leaving orphaned definitions behind produced a wrong number from a correctly
quoted command; and it does not catch a tautological test, which quotes exactly as cleanly as
a real one. Stretching one field across those would produce a convention that is followed and
does not work, which is a worse outcome than a narrow one that does.
