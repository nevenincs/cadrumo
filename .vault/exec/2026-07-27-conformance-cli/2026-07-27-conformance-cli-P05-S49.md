---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S49'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# absorb the three tree-wide gate regressions this campaign caused, moving the module marker above the assignment, replacing the bare encoding literal with the shared constant, and extracting a cohesive concern out of each module that broke its size ceiling rather than lifting the ceiling

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Declare the module marker before the module constant in the oracle-payload boundary test.
- Read bundled oracle payloads through the shared UTF-8 constant instead of a bare literal.
- Extract the fichero-BOE structural-parity gate out of the filing export renderer into a sibling module.
- Extract the declared governance-stamp rules out of the registry schema into a sibling module.
- State the degraded-read rule in the classification-coherence test without citing a development record.

## Outcome

Five commits, each with an explicit pathspec. Four gate regressions were absorbed:
the three the step names, plus a fourth this campaign caused that the original
triage did not list.

**Module marker placement.** The oracle-payload boundary module declared its
year-less payload-name constant before `pytestmark`. The placement gate requires
the marker to precede constants, fixtures, and tests so a reader finds a module's
selection markers in one predictable place. The marker moved above the constant;
the module still collects and runs under the default selector afterwards, which
was verified rather than assumed because moving a marker can change selection.

**Bare encoding literal.** The oracle-payload parser read its bundled JSON with a
bare `encoding="utf-8"`. The enrollment inventory refuses bare literals in
production files precisely because a literal is invisible to any sweep that needs
to find every encoded read. The site now imports the shared constant from the core
external-constants module, matching the form a sibling in the same package already
uses. The gate names adding the file to its known-violating ratchet as the wrong
fix, and that was not done.

**Two modules broke their size ceilings.** Both were absorbed by extraction. No
baseline was regenerated, no exemption added, and no ceiling moved: the registry
schema's pin is still 1483 and the filing renderer still has no pin, so both are
governed by the same limits they broke through.

The filing export renderer fell from 1274 lines to 919 against an unmoved default
limit of 1250. It had been carrying two concerns: rendering a draft into AEAT wire
bytes, and asserting before the write that those bytes mirror the official modelo
structure. The second became a parity sibling. The seam chosen is disposition
rather than the set-derivation-versus-assertion split the brief guessed at: casilla
presence, record order, and casilla numbering are each scoped to what a given
filing's disposition actually files, so the refund-page suppression predicate that
decides that scoping moved with them and the renderer imports it back. That keeps
the dependency arrow one-way and leaves one authority for the required set rather
than a copy that could drift out of agreement with the assertion describing it. The
predicate stayed private because both callers are inside the package, so widening
it to a public name was unnecessary.

The registry schema fell from 1582 lines to 1482 against an unmoved pin of 1483.
The growth was this campaign's governance work, and the extracted concern is the
declared provenance stamp: the blank-attribution refusal, the signoff-horizon
bounds, the status-versus-attribution coherence rule, and the reasoning for
preferring fixed calendar bounds to a reading of the wall clock. The schema keeps
the four field declarations and the validators, which now delegate.

That last choice was deliberate and is the significant judgement in this step. A
mixin carrying the four fields would have moved considerably more prose and read
more elegantly, but pydantic places inherited fields first, so it would have
reordered the revision model's fields and changed serialisation order. That is an
observable behaviour change bought for a cosmetic gain, and the step's constraint
is that a silent behaviour change is worse than an oversized module. Field order
was confirmed unchanged after the extraction.

**Campaign metadata in a test docstring.** Running the wider structural gates
surfaced a fourth failure absent from the original triage: the classification
coherence test attributed the row-level labelling rule to a decision record in the
removable development scaffolding. Code stands alone and the reference direction is
one-way, so the docstring now states the reason directly. The file was committed by
this campaign's own earlier step, so it is in scope under the absorb rule rather
than a peer deferral.

Behaviour preservation was proven rather than asserted. An abstract-syntax
comparison of the nine moved filing functions against their pre-change originals,
with docstrings stripped, reports every one logic-identical. For the governance
rules, whose signatures necessarily changed when the bodies left the model, the
refusal message literals were compared and are identical; only the interpolated
identifier name differs, carrying the same value. The registry and filing suites
then ran green at 3418 passed, with the directly affected gates re-run serially
under 83 passed to rule out an xdist selection artefact.

Gate results, before and after:

- Module marker placement: was two violations, one this campaign's oracle-payload
  boundary module and one a peer's documentation sequence-build gate. Now one, the
  peer's. This gate is therefore still red for a reason outside this campaign.
- Bare UTF-8 literals: was one violation naming the grounding module at line 648.
  Now passes.
- Module size budget: was two violations, the filing renderer at 1274 against 1250
  and the registry schema at 1582 against 1483. Now passes, with measured counts of
  919 and 1482 against the same two unmoved limits.

The generated API reference stubs were regenerated and report no drift. The
full-tree collect-only gate ran clean immediately before committing, at 14998
collected with no collection errors.

## Notes

The semantic discovery probe mandated before coding work was explicitly waived by
the operator for this step: the semantic index is broken and its service stopped,
with a standing instruction not to start, restart, or reindex it. Grounding was
done with literal search and whole-file reads instead. This waiver is recorded here
because the mandate otherwise requires refusing the work outright.

One gate remains red after this step, and it is not this campaign's. The module
marker placement gate still reports the documentation sequence-build gate module,
which belongs to a separate campaign and was last committed by it. The fix is a
one-line move, but it was left alone: the step's brief scopes work to this
campaign's own regressions, and editing another campaign's file to green a shared
gate risks colliding with work in flight. This is reported as inventory for that
campaign's owner rather than silently absorbed.

The registry schema now sits one line under its ceiling. That passes, and it passes
for the right reason, because the module shrank while the limit did not. It is
still a thin margin and the next edit to that module will red the gate again. The
obvious next extraction is the verification-predicate concern, roughly three
hundred lines and cleanly cohesive, but it was deliberately not taken here: its
symbols are reached from around twenty-eight files, and a consumer sweep of that
size on a heavily peer-contended module is disproportionate to a
regression-absorption step. It is recorded as the recommended follow-up.

The complexity ratchet key for the moved record-order assertion was repointed to
its new module at its existing value, so the debt entry follows the subject rather
than reappearing as a new hotspot. No debt value was changed and no baseline was
regenerated; regenerating would have been unsafe with several peer campaigns
holding uncommitted work whose measurements would have been baked into a committed
baseline.

The mandatory code review has not been performed. No delegation tool was available
in this session, so the review is owed and should be dispatched by the coordinator
against the five commits.

Peer work in the shared tree was left untouched throughout. Uncommitted changes in
the line-frontend module, the classification-coherence implementation, the stamp
writer, and the plan document were present during this step and remain
uncommitted; every commit named its files explicitly and the staged set was
reviewed before each.
