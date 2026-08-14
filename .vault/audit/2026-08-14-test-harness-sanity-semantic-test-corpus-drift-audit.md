---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:bfbc4adb6f96504412a29cce86075ae3e0093517be13017dda574bb9783d4bb8'
related:
  - '[[2026-08-14-test-harness-sanity-plan]]'
---
# `test-harness-sanity` audit: semantic sweep of test-corpus drift

## Scope

Five parallel semantic sweeps of the test corpus, searching by MEANING rather than by identifier, across profile seeding, repository construction, command-envelope and assertion helpers, registry and oracle readers, and behaviours living under several names. Every reported locator was opened and read; semantic search located, targeted search confirmed, and a body comparison adjudicated.

The sweeps exist because the campaign's own census sees only decorated fixture definitions. Plain helper functions, assertion helpers, builders and value constructors are outside its reach entirely, and that is where most of the drift turned out to live.

## Findings

### assertion-strictness | high | Four helpers are weaker than a sibling doing the same job

These are correctness defects rather than duplication. A weak assertion is worse than an absent one, because it reads as coverage.

One refusal helper asserts only that the machine-fact context is non-empty, while its sibling asserts the exact content and the registered error code. The weak copy passes a refusal carrying entirely the wrong facts. One validation helper accepts any validation error for any reason, where its sibling can pin the failing field by pattern; it cannot distinguish the right field failing from an unrelated one, which is the precise false pass such helpers exist to prevent. One command-envelope decoder checks that two keys are present, standing in for the full envelope model its canonical counterpart validates. And a terminal-refusal helper asserts every field except the evidence, with the result that no assertion anywhere in the suite covers the evidence content of that refusal.

### assertion-strictness | high | One error-document reader silently misses indented output

Four independent readers scan command output for a JSON error document. Three strip each line before testing whether it begins an object; the fourth does not. A document emitted with leading whitespace is therefore found by three and silently missed by the fourth, which is a false negative rather than a failure.

The root cause is structural rather than careless. The canonical envelope decoder validates only SUCCESS envelopes, because an error document carries an error member where the model expects a result, so the model cannot validate it. No error-side counterpart was ever built, and four authors independently filled the gap. Repairing the outlier alone would leave the hole that produced it.

### fixture-aliasing | high | Thirteen behaviours live under thirty-eight names

Keying the census on body rather than name shows thirteen distinct fixture bodies each defined under more than one name, spanning sixty-eight definitions and thirty-eight names. The worst is one body under seven names, every one a singleton. Another is one body under six names across seventeen definitions, and a third one body under four names across fifteen.

Nothing could have found this. A search for any one name returns a single site and reads as unique; the census groups by effective name FIRST, so a renamed twin sits outside its comparison by construction; and a reviewer would have to already know the other names to notice. The gate was not failing, it was keyed on the wrong axis.

### helper-duplication | high | One concept, six names, roughly ninety sites

Writing a filing-ready profile record for a test is implemented under six independent names, each re-duplicated between three and nineteen times. The drift crossed a tree boundary: the development-side evaluation tests carry a fifth independent reimplementation with no visibility into any of the shared support modules.

The bodies are frequently byte-identical while the module-level facts constant they close over is not: same constant name, different content in every file, differing in tax identifier, in activity description, and in whether an activity-start fact is present at all. The wrapper plumbing is duplicated; the facts are legitimately per-scenario. Consolidating the former without collapsing the latter is the whole task.

### helper-duplication | high | A four-line identifier wrapper defined in about one hundred and thirty files

A wrapper converting the production casilla-identifier validator's refusal into a test-assertion failure is defined per module, varying only in a label string. No shared home exists. Whether the right remedy is one shared helper or none at all is being assessed: the wrapper's only contribution is the exception conversion, and if the production refusal is already instructive the correct migration deletes a hundred and thirty definitions and adds nothing.

### helper-duplication | medium | Eighteen copies of the bundled-oracle reader, and a cached loader redefined next door

Eighteen modules read a bundled worked-example payload through the same three-line body, varying only by filename constant. Separately, an expensive cached registry-tree loader is redefined byte-identically one file away from its canonical home in the same package, so two independent caches of the same tree can be populated in one session.

### not-drift | resolved | Three patterns that look like duplication and are not

The two mechanisms for giving a test a profile are a genuine fork, not a duplicate pair: one sets an in-process context override that evaporates at block exit, the other additionally writes a durable pointer that survives it. Sites needing the pointer to outlive the seeding block legitimately need the second. An initial reading described this as one mechanism activating a pointer and the other not; that was corrected on evidence, and the corrected distinction is what forbids the merge.

A direct pointer write that bypasses the selection path is also not drift: it points at a bucket with no profile record, which the selection path structurally cannot do, so it exercises mechanics nothing else can reach.

A module-scoped runtime paired with per-test truncation is deliberate architecture with a documented cost rationale, already consolidated in one package, and explicitly warned against being flipped naively.

### cross-campaign | resolved | The ordering hazard was the failure, and it was never a custody regression

They were the same event. The capsule publishes by an atomic no-replace directory rename onto the bucket path; the workflow state repository constructs its engine EAGERLY, creating that directory before any query runs; and Python evaluates a method call's receiver before the call, so `workflow_state_repository().update(lambda s: register_minimal_profile(s, ...))` materialised the destination before the rename could claim it. Around twenty-eight sites shared that shape.

The custody package was never at fault, and the sibling's docstring had named the hazard all along -- nobody had read it as describing a live failure. Two fixes were rejected on inspection: making the registrar order-safe internally cannot work, because by the time it runs the caller has already created the directory in the same expression; and making the capsule tolerate an existing destination would weaken another campaign's atomic publish to paper over test setup. The call shape was the defect and the call shape was fixed.

A second fact emerged while fixing it: the `.update()` wrapper was ALWAYS a persistence no-op, since the registrar never reads or mutates the state handed to it, so the repository short-circuited before saving. The sites were not merely mis-ordered; they were doing nothing.

### instrumentation | critical | The canonical-homes gate had been dark, and its silence was indistinguishable from a pass

The import-hygiene scan computes seven violation families and then, on the line immediately before its reporting block, enforced an exact-census digest pin over one unrelated sub-census. That pin refuses ANY addition, removal or reclassification of a legacy-interface identity, so the moment that sub-census drifted the scan raised and discarded all seven already-computed families without printing a line.

It had been failing on committed state, for everyone. What it was concealing: one hundred and twenty-five cross-package private imports and fourteen pure re-export modules -- precisely the violations the canonical-homes mandate exists to catch, reporting as no output at all.

The remedy deliberately did not adjudicate the stale census, which belongs to the campaign migrating that interface. The manifest is generated unchecked, the full report prints, and the identical refusal is raised at the end: same verdict, same exception, same message, with the evidence no longer thrown away. Fifteen hundred lines of report now print where there were none.

The general lesson is about gate DESIGN, not this gate: a digest pin over an exact census is the digest analogue of a hardcoded count. It reds on every legitimate change to the thing it watches, it gates on a tally rather than a property, and when it sits upstream of an accumulating report it takes six unrelated families down with it.

### cross-campaign | open | One commit shipped production refusals without sweeping its test callers

A single peer commit -- making the custody capsule the sole profile authority -- introduced at least two production refusals whose test callers were never updated, and both were found independently, by different agents, hours apart.

The first refuses custody deletion without an authenticated retention assessment; measured against a shadowed detached-HEAD control it accounts for eight failures across two configuration test modules, identical with and without this campaign's changes. The second refuses wizard profile creation without prior credential registration, and accounts for most of fourteen failures across the four subprocess command-line modules. The evidence that the second is not a refactor artefact is that it fires identically through three independently-coded settings mechanisms, which a transport change could not reproduce.

Neither is this campaign's to fix: adapting the callers means deciding whether each refusal is correct and what satisfying it looks like in a test. Recorded for the owning campaign rather than worked around.

## Outcome

Every finding above was actioned rather than filed. The weak assertions were strengthened and each was proven to fail on the thing it names; the missing error-side decoder was built and all four readers migrated onto it; the census was re-keyed on body; the identifier wrapper population was deleted rather than relocated, on the evidence that production already delegates bare; the oracle readers, the profile registrar, the revision-id resolver and the executable resolver each acquired one home; and the fresh-interpreter command harness was consolidated in two layers with each caller's isolation settings kept explicit.

Two things were deliberately NOT consolidated, and the reasons are part of the result rather than omissions. Five oracle readers return an untyped mapping instead of the strict payload model: a different contract, not a lesser one, and folding them in would have made a typing decision their own suites should make. One snapshot site hand-authors the export layout under test, which the canonical builder would unconditionally overwrite; it is constraint-shape-divergent, not duplication.

The aliasing finding is the one that remains substantially open, and the honest number is that it moved from thirteen behaviours under thirty-eight names to twelve under thirty-six. The reason it is slow is visible in the data: in the worst cluster, five of the seven definitions are autouse with reaches of two hundred and five, twenty-five, eleven, nine and four tests, and the remaining two are explicitly requested. A flat merge would hand every site the union of that reach. The tractable clusters are being taken first; the dangerous ones are carried forward explicitly rather than being counted as done.

## Recommendations

- Strengthen each weak assertion helper to its stronger sibling's shape, and treat any test that then fails as a finding rather than as a reason to revert.
- Build the missing error-side envelope decoder and migrate all four readers onto it, rather than repairing the one that misses indented output.
- Key the census on body as well as name, so one behaviour under many names becomes detectable rather than requiring a sweep to notice.
- Give each aliased behaviour one name and one home, preserving each site's scope and autouse, and remembering that a shared autouse fixture placed in a package configuration file widens its reach silently.
- Decide the identifier wrapper's fate on whether the production refusal is already instructive, and prefer deleting the population to relocating it.
- Leave the two profile mechanisms forked, and repair only the sites that hand-assemble the second one incompletely.

## Notes

The sweeps were run against a tree several other campaigns were writing to, so every locator carries the caveat that line numbers drift; each was re-confirmed at report time. Two reports corrected their own earlier claims on evidence, which is the behaviour that makes the rest of their findings trustworthy.

The method is the durable output. Describing behaviour rather than naming identifiers is what surfaced the aliasing class, and re-searching using a strong hit's own snippet is what pulled in its siblings. A name-based search cannot find a renamed twin, and neither can a census keyed on name.
