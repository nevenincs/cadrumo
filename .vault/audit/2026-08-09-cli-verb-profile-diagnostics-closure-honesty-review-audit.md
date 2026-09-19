---
tags:
  - '#audit'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:a09a7409ff22c1f72b669b1aa54bdbfc3762067f1e153faa67d9a9345eab39f5'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---

# `cli-verb-profile-diagnostics` audit: `closure honesty review`

## Scope

The fresh-context closure review the plan's own Verification section requires
before the campaign may be declared complete, run against the plan, its audit,
and all thirty-six Step Records as if inheriting the campaign cold. Every claim
below was checked against current code and current catalogue data rather than
against the prose describing it.

Read at a moment when P09 was open and its four target files carried
uncommitted work, which bounds what could honestly be measured and is recorded
under the last finding.

**Cross-reference:** an independent honesty review landed concurrently as `[[2026-08-09-cli-verb-profile-diagnostics-fresh-context-honesty-review-audit]]`, reaching the same two actionable findings (verification-gate-scope / F1, residual-paths-misdirect / F2-F3). That review's recommendations are already actioned as Phase `P11` on the plan: `P11.S43` (fix the three misdirecting messages) and `P11.S44` (the terminal re-verification gate this doc's `verification-gate-scope` finding calls for). Treat these two documents as one finding independently confirmed twice, not two separate findings.

## Findings

### exec-record-coverage | low | Every Step carries a real Step Record, and the usual checked-but-empty failure mode is absent

All thirty-six Steps have a Step Record. Every record carries authored content
rather than an unfilled scaffold: none retains template annotation residue and
none is a stub. The failure mode this review most expected to find - a closed
checkbox with nothing behind it - does not occur in this campaign. The Step
Record for the earlier honesty review is itself sound work: it opened new
Phases for what it found instead of folding findings back into closed Steps,
and it deferred two items explicitly rather than silently.

### verification-gate-scope | high | The three closure gates are satisfied by a Phase that predates half the campaign

The verification Phase holds the three Steps the Verification section names as
closure criteria: the sequential suite run, the locale-parity confirmation, and
the fresh-context honesty review. All three are closed. Five later Phases,
about half the campaign's Steps, were created BY that honesty review and land
after it - their own Phase descriptions say so, naming the review or its
closing catalogue sweep as their origin.

So the gates were satisfied against a tree that no longer exists. The
sequential-run record states that the owner surface is green, which was true
when written and predates four test modules the later Phases created. The
consequence is that the campaign can be declared complete, honestly and by its
own written criteria, on a verification that never observed half of it.

This is structural rather than anyone's error: the review that satisfies the
gate is the same activity that generates the work invalidating it, so the
defect reappears in any plan that places its honesty review anywhere but last.
It is the shape where delivered-as-specified and recorded-but-not-reverified
wear the same checkbox.

### closing-sweep-completeness | medium | The closing catalogue sweep stopped early and left three messages of the same defect class

The final Phase records that its sites were found by the closing
locale-catalogue sweep. A census run for this review - matching every profile
schema field key as a dotted token against operator-facing prose, rather than
guessing a prefix pattern - finds three further messages still naming a profile
field by raw dotted path. All three are `next_action` values on modelo
findings, which are primary operator-facing output rather than incidental
diagnostics, so they are squarely inside the campaign's mandate.

Two further matches were examined and deliberately excluded: the configuration
get and set help strings name a dotted key because the dotted key is the
argument form the operator types there, which is the correct rendering rather
than the defect.

### residual-paths-misdirect | high | The three remaining sites name a section that does not exist

The three messages above do not merely spell a raw path where a label belongs.
They instruct the operator to set a field under a `profile` section, and no
such section exists in the profile schema. Both fields live under the
`taxpayer_type` section. An operator following the instruction is therefore
sent to a path that cannot be found, which is a worse outcome than an
unfriendly but accurate identifier.

Both resolve cleanly through the mechanism this campaign already built once the
correct section is used, rendering an operator label together with its legal
basis, so the remedy is the same shape as the Phases that preceded it and
carries no new design question.

### unowned-method-recommendation | medium | The audit recommendation that was a method change has no Step and no gate

The earlier audit closed with three recommendations. The first two became
Phases and are delivered. The third - that the next inventory be scoped by
behaviour rather than by location - is a method change carrying no Step, no
verification gate, and no follow-up reference, so nothing can report it as
undone. The two findings above are direct evidence it was not fully applied,
since the sweep it was meant to govern still stopped early. A recommendation
must be actioned, refused with a recorded rationale, or tracked; this one is
none of the three.

### records-precede-steps | low | Four Step Records describe work that has not landed

The final Phase's four Step Records are complete and authored while their
Steps remain open and their target files carry uncommitted work. This is work
in flight rather than a defect, and it was left untouched. It is recorded
because it inverts the usual reading: a reviewer checking whether every closed
Step has a record gets a clean answer, while four records describe work that
is not yet in the tree. Record presence must not be read as completion here.

### measurement-limits | low | What this review did not measure, stated so nobody infers it was clean

The sequential suite was deliberately not re-run. The final Phase's files
carried uncommitted work throughout this review, so a run would have measured
an in-flight edit rather than a landed tree; it belongs at actual closure,
which is the preceding gate-scope finding's point.

The census read the English catalogue only. The parity gate means the same keys
exist in all four, so the finding transfers, but the prose of the other three
was not read. The census also keys on dotted tokens, so a message naming a
profile field in prose without a dot would escape it - that class remains
unmeasured by the original sweep and by this one alike, and no claim of
completeness is made over it.

## Recommendations

1. Do not close this campaign against the Verification section as written. Add
   a terminal verification Phase that re-runs the sequential suite, the
   locale-parity confirmation and a closure review after the final Phase lands,
   or amend the Verification section to require those gates re-run at closure
   rather than accepting the existing closed Steps.

2. Open a Phase for the three residual messages, correcting the section they
   name and rendering both fields through the schema-derived label mechanism
   this campaign already established, with tests asserting no raw dotted path
   survives in their output.

3. Record the third recommendation of the earlier audit as tracked work or as
   an explicit refusal with a stated rationale, so that a method change the
   campaign relied on stops being invisible to every later reader.

4. When a plan places an honesty review mid-sequence, treat every Step the
   review opens as invalidating that review's own gate. The durable form is to
   let the review run last, or to require re-verification whenever it opens
   work.
