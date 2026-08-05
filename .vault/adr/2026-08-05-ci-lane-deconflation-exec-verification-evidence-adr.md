---
tags:
  - '#adr'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:96eb687d394d193649a4faf508300fec6c97dcf2c2c678721dbbb9e0c687961e'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - "[[2026-08-05-ci-lane-deconflation-adr]]"
---
# `ci-lane-deconflation` adr: `quote the instrument, do not summarise it` | (**status:** `accepted`)

## Problem Statement

Three times in one day, across three different agents, a test invocation selected zero tests
and exited zero. Each would have read as green. One was a unit-marked test scoped to
integration, one the size-budget module, one the selector parity gate.

The runner is not at fault and emitting harder will not help: it already prints `NOTHING RAN`
and `PARTIAL RUN` banners naming the deselection, and all three were read past. The signal
exists at the point of execution and is lost by the time it reaches a record, because what
lands in the record is a paraphrase — "the tests pass", "3 passed" — and the paraphrase is
where the deselection count goes.

So the gap is not that agents omit the selection. It is that they **summarise the instrument
instead of quoting it**, and every summary discards exactly the part that distinguishes a
real pass from a vacuous one.

## Considerations

**The reader of the record is the person who needs to see it.** Whoever ran the command had
the banner and read past it. A control that only helps the runner has already failed three
times today.

**Paraphrase is lossy in one specific direction.** "15 passed" is true of a run that
deselected 25, and true of one that deselected none. The verbatim summary line distinguishes
them; no honest paraphrase does, because the author who paraphrases has already decided the
deselection was not worth mentioning.

**This generalises past selection.** The same day produced a measurement reading 17558 and
passing while the gate read 20589 and failed — two correct numbers about different objects.
A quoted invocation shows which object was measured; a summarised result does not. Quoting
the instrument is a wider control than stating the selection, and costs the same.

## Considered options

**A repo-side gate scanning exec records.** Rejected, and not on cost: the code-stands-alone
mandate forbids source, tests and configuration from referencing harness paths or vault
documents. A pytest gate globbing the exec tree is precisely that reference. The reference
direction is one-way and this would invert it.

**A new always-on rule.** Rejected: codification was retired on 2026-07-13 because the
always-on corpus bloats every agent context, with durable lessons to be recorded in the
campaign's records instead. This ADR is that record.

**A vaultspec-core check.** Correct home, not available here — it is upstream of this
repository. Proposed rather than adopted, see D3.

**A field in the exec template.** Adopted with a caveat, see D1 and D2.

## Constraints

The exec template at `.vaultspec/templates/exec-step.md` is tracked in this repository, and a
harness upgrade has written to it before (2026-07-30, one line added to each of eight
templates). So a local edit is not guaranteed to survive an upgrade. It is tracked, so a
revert would appear in a diff rather than vanishing silently — but harness-upgrade commits are
exactly the class reviewed loosely, which is the risk D2 addresses.

## Implementation

### D1 — An exec record citing an execution quotes the instrument verbatim

Where an exec record's evidence is that something ran, it carries the **invocation** and the
runner's **verbatim summary line**, not a paraphrase of either:

    uv run --no-sync pytest <paths> -m integration -n 0
    15 passed in 10.35s

The invocation shows the selection — marker expression and path scope — and the summary line
shows what that selection produced. A vacuous run is then visible in the record itself: a
reader meeting `NOTHING RAN` or a deselection count larger than the selection does not need
to trust the author's reading of it.

The rule is stated as **quote, do not summarise**, deliberately wider than "state the
selection", because the same discipline catches the wrong-object trap: a quoted invocation
names what was measured.

### D2 — The template carries the field; the plan carries the binding requirement

The template gains a `## Verification` section, matching the plan template which already has
one. That places the prompt where an author is already writing.

Because the template may be rewritten by a harness upgrade, the template is **not** the only
home. This campaign's plan states the requirement in its own Verification section, which is
in-repo, unversioned by the harness, and already the established place for per-row closure
criteria — that plan already carries "closes only when the gate is shown to FAIL against a
planted violation" for one row. A future campaign adopting this convention does the same.

Two homes is redundancy, not indecision: the template prompts, the plan binds, and neither
depends on the other surviving.

### D3 — Propose the field upstream

The durable home is the shipped exec template in vaultspec-core, where it survives upgrades by
being the thing upgrades install. Proposed there; adopted here in the interim. If it lands
upstream, D2's local template edit becomes redundant and should be dropped rather than
maintained in parallel.

## Rationale

The instruction this replaces was "state the selection". That would have caught the three
observed instances and nothing else. **Quote the instrument** catches the same three, catches
a measurement of the wrong object, and is not harder to comply with — it is strictly easier,
because pasting a line requires no judgement about what to preserve, and paraphrasing requires
deciding what matters. A rule that is easier to follow correctly than incorrectly is worth
more than a rule that is merely right.

Requiring the verbatim line also moves the burden to where the information still exists. At
execution time the deselection count is on screen; by the time a record is written it has been
discarded. The control has to bite before the discard, and the only reliable way to do that is
to make the artefact carry the original rather than a reading of it.

## Consequences

- Exec records get slightly longer and materially more checkable.
- A reviewer can refuse a record on its face, without re-running anything.
- The convention binds this campaign now, through its plan. It does not bind other campaigns
  until they adopt it or the upstream field lands.

### Scope, stated honestly

**This catches the vacuous-selection family, and the wrong-object family where the object is
visible in the invocation.** It does not catch:

- **Decayed tree-state claims** — a quoted command with a real result that was true when run
  and false when read. That is a timestamping problem, not an evidence-quoting problem, and
  needs a different control.
- **A measurement whose flaw is in its setup rather than its command** — the counterfactual
  that left orphaned definitions behind produced a wrong number from a correctly quoted
  invocation. Quoting shows what ran, never whether what ran answers the question.
- **Tautological evidence** — a test that passes while asserting nothing quotes exactly as
  cleanly as one that does not.

Stretching one field to cover those would produce a convention that is followed and does not
work, which is the failure mode this record exists to prevent one instance of.
