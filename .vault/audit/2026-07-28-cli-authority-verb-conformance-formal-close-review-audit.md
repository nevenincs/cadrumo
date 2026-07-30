---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-25-cli-authority-verb-conformance-campaign-close-honesty-review-audit]]"
---

# `cli-authority-verb-conformance` audit: `Formal close review`

## Scope

Formal review serving the campaign's review row. Read as a third-party report
of what is missing, vague, or assumed-but-unverified.

## Method, and its honest limits

STATED FIRST BECAUSE IT BOUNDS EVERYTHING BELOW. This is a PERSONA-SWITCH
review by the agent that drove the campaign, not an independent one. A
dedicated reviewer was dispatched with a full brief and produced nothing across
three idle signals and two direct requests. The campaign's own close-review
discipline sanctions the persona switch as one of three acceptable forms, so
this is a legitimate route - but it is the weaker one, and a reader should
discount it accordingly. An independent pass over the same surface is still
worth having.

Depth is uneven and is declared rather than implied. The test-quality axis was
reviewed properly, with an instrument built for it. The safety, boundary and
intent axes were checked at CONFIRMATION depth only - against measurements
taken earlier in the campaign - not re-derived. That is why the review row is
closed on a stated scope and the zero-finding verdict row is NOT.

The semantic index was unusable throughout: 20 indexed sections against 3742
tracked Python files, generation self-reporting `succeeded`. Nothing here rests
on a semantic result.

## Findings

### systemic-unfloored-emptiness-gates | major | The false-green class is systemic, currently latent, and bounded

The campaign has found the same defect five times in unrelated instruments: a
gate asserting a property of a set it never proves is non-empty. I was asked to
assume a sixth exists. The result is more useful than a sixth instance.

An AST scan over 16331 test functions looked for the exact shape - a function
asserting a collection is empty, containing no assertion that any count is
non-zero, where the collection derives from scanning a corpus (filesystem walk,
module iteration, registry read). It reports **246 candidates tree-wide, 87
inside this campaign's surface**.

The instrument is a CANDIDATE GENERATOR, not a finding list, and the difference
matters. A first pass without the corpus-scanning filter returned 2045, most of
them legitimate assertions on a constructed object's default attributes - a
parse error's empty `missing` tuple is not a vacuous gate. Narrowing to
corpus-derived collections cut it to 246. Neither number is a defect count,
because the heuristic cannot see a floor asserted outside the function.

One representative candidate was read in full rather than counted. The
profile-backend retirement gate walks `application/` and `entrypoints/`,
collects files containing any of five forbidden tokens, and asserts the
offender list is empty - with no floor. Measured: that walk covers **1207 plus
526 files, 1733 in total**. So it is NOT vacuous today; the corpus is real and
the assertion is meaningful.

The defect is therefore LATENT rather than active: a path rename or a package
relocation silently empties the corpus and the gate stays green while the
tokens it forbids survive. That is precisely how the five confirmed instances
came about - none was born vacuous.

Classified major as a CLASS and not a blocker, because no active false green
was demonstrated. The remedy is mechanical and known: one floor assertion per
gate, of the shape this campaign has now applied four times.

### campaign-own-gates-carry-floors | low | The gates this campaign repaired do carry floors, checked

Every gate this campaign added or repaired asserts its subject count before
asserting its property: the write-guard criterion gate asserts both an app-leaf
floor and a selected-mutation floor, the combined-period gate asserts a scan
corpus above 500 files plus a hostile-input probe, the execution-record outcome
gate asserts subject floors against measured live figures, and the layering
dimension asserts evaluated equals declared. Three of the four were
mutation-checked at the time they landed.

That is the narrow claim: the campaign did not add to the class it was
eradicating. It says nothing about the 87 candidates it did not create.

## Verdict

The campaign is SUBSTANTIALLY sound and NOT yet safe to declare structurally
complete, and the two are not in tension.

What I would sign off on: the removed-verb cutover, which measures clean across
the live 290-leaf tree with no alias, hidden registration or removed spelling
surviving; the write-guard repair, whose fail-open is closed and whose
catalogue is now bound to the live tree with a criterion rather than curated;
the layered contracts, all five evaluated and kept; and the evidence bar, met
by all 25 closed verification rows with the checker itself proven to
discriminate a zero-collected run.

What I would NOT sign off on. The semantic sweep row cannot be satisfied at all
while the index is dead, and no substitute covers that row's own instrument.
Six keychain-marked custody cases have never been observed green in any lane
here and remain unverified rather than passing. The 87 unfloored gate
candidates in this surface are unadjudicated. And this review is a persona
switch with three of its four axes at confirmation depth, which is a real
limitation on how much weight its own zero-blocker finding can carry.

Measured at HEAD `7113d72aa2248133ec15764ceccd05cb55fddbc0`.

## Recommendations

Give the 87 in-surface unfloored gates a floor, or prove per gate that its
corpus cannot silently empty. Bounded, mechanical, and it closes the class
rather than another instance of it.

Repair the semantic index as an operator action - a restart discards an
in-progress build and an interrupted rebuild truncates what survives - then
rerun the semantic sweep row against a healthy instrument.

Obtain an independent review of the safety, boundary and intent axes. This one
confirmed rather than re-derived them, and the campaign's own history is that
inference passes over exactly the defect a check would find.

## Amendment at HEAD `35a46ff4f25664c2895a56e25196e502511722c2`: one instance was ACTIVE, not latent

UPGRADES the systemic finding above. I classified the class as latent on the
strength of one candidate I read, whose corpus turned out to be 1733 real
files. Acting on the finding found a live one, so "latent" understated it.

THE SIXTH INSTANCE, and it was silently green. The retired-command-phrase gate
derived its repository root as `parents[4]` where the file's depth requires
`parents[5]`. Measured independently rather than taken from the fix: the old
expression resolves to `<repo>/src`, so the gate's two runtime surfaces became
`<repo>/src/src/cadrumo` and `<repo>/src/env` - neither of which exists. It
scanned ZERO files and asserted an empty leak list, passing green, for as long
as that literal has been wrong.

The floor is what surfaced it. Adding a corpus assertion made the gate fail
immediately, the root was corrected, and the corrected scan then surfaced one
genuine match - a module docstring naming the retired command path - resolved by
rewording so the literal is gone and the meaning survives. Both runtime surfaces
now resolve and exist, confirmed here directly.

So the class is: systemic, mostly latent, and confirmed to contain at least one
gate that was already lying. That is a materially stronger finding than the one
recorded above, and it was only reachable by acting on the recommendation rather
than filing it.

PROGRESS ON THE REMEDY. 12 gate functions floored across 5 files in the CLI and
dev-audit surface, each mutation-verified to fail on a collapsed corpus, with
false positives excluded and their reasons stated - fixed-path reads and
existence checks cannot silently empty, because a rename raises loudly. I
verified one floor myself rather than accepting the report: the CLI-module
corpus helper sees 456 modules and fails at 0 on a relocated root.

The heuristic is now a shipped tool, `dev/audit/vacuity_screen.py`, tracked and
runnable, rather than the throwaway script this review used. Its current
worklist is 108 candidates; the in-surface remainder is being worked and the
owning Step stays open until it is done.
