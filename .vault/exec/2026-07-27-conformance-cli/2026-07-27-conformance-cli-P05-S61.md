---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:9baed00efc23a91baa19c9cfbde96e95e99acfd1aed0487fabbef2c15c8babcb'
step_id: 'S61'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# extract the verification-predicate concern out of the registry schema module, which now sits one line under its size ceiling so the next peer edit reds a gate they did not break

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Extract the verification-expectation concern out of the registry schema into a
  sibling module holding the expectation declaration and the folded snapshot policy.
- Route the package facade, the revision validation context, and the two
  intra-package test importers at the new canonical module.
- Regenerate the API reference stub for the new module.

## Outcome

One commit, `80909cc71f`, with an explicit eight-path pathspec. The registry
schema falls from 1482 to 1386 lines against an unmoved limit of 1483, restoring
97 lines of headroom where there had been one.

**The ceiling is a band, and that bounded the extraction.** The size ratchet does
not enforce a one-sided ceiling. It fails an entry that grows past its limit AND
an entry whose limit has drifted further above it than the declared slack
tolerance, because a pin that no longer tracks its subject is exactly the window
of invisible regrowth the ratchet exists to close. For this module the tolerance
computes to 149 lines against a limit of 1483, and an entry that falls to or
below the 1250 default is failed outright as dead weight. The legal band is
therefore 1334 to 1483, and the largest extraction that lands inside it is 148
lines.

That is decisive, because the concern the step names is larger than the band. The
full verification concern in this module is roughly 390 lines: the expectation
declaration, the folded policy, the predicate model, and the two operator
vocabulary constants. Extracting it would drop the module to about 1090, below
the default, and fail the gate as a stale pin. The only way to land it is to
remove the module's baseline entry, and the baseline lives under the development
tooling tree this step is explicitly barred from touching. Lifting or
regenerating the limit was refused outright, so the work was bounded to what the
band admits.

**The seam.** Within that bound the chosen unit is the verification-expectation
concern: the expectation declaration plus the folded policy across a snapshot's
expectations, 148 lines in the new sibling and 96 lines out of the schema. The
two belong together and not with the predicate model. The policy is derived from
nothing but the expectations, by a fold that exists so the application
verification surface does not re-derive the union, the strictest tolerance, and
the strictest coverage floor at each call site where the three could quietly
disagree. Its own prose already documents the three casilla axes the expectation
declares, and those same axes are what the expectation's invariants police: each
tuple unique, the when-present set disjoint from the computed set, the
externally-grounded set a subset of their union. Splitting the two would put one
concept's rules and its fold in different files.

The predicate concern was deliberately left in place rather than half-taken. The
predicate model and the operator vocabulary constant are one concept documented
twice, once as a 143-line class docstring and once as a 142-line annotated
constant that the registry-build validator reads. Either alone fits the band and
both together do not, so taking one would have scattered a single concept across
two modules for a cosmetic line count. The bad extraction was refused; the
recommendation from the previous extraction is therefore not closed, and remains
blocked on the baseline entry rather than on effort.

**No field moved, so nothing reordered.** The hazard recorded by the previous
extraction — that a mixin would reorder a pydantic model because inherited fields
are placed first, changing serialisation order for a cosmetic gain — does not
arise here, because whole symbols moved and every field declaration stayed on the
model that owns it. That was checked rather than assumed. Field order was
captured before the change and compared after for the revision model at 34
fields, the snapshot model at 18, and the expectation model itself at 11: all
three identical. The expectation model's generated JSON schema property order
matches its pre-change field order, and the folded policy's dataclass field order
is unchanged.

**Behaviour was proven, not asserted.** Both moved classes were dumped as
abstract syntax trees before the move and compared against the new module
afterwards. Both are identical — not merely logic-identical with docstrings
stripped, but identical including docstrings, because the bodies moved verbatim.
Separately, every string and format-string literal inside the two classes was
extracted from the pre-change file and compared with the post-change sibling: 23
literals, identical in sequence, so all five refusal messages that tests and
operators key on are unchanged.

**Consumer sweep.** The two moved symbols were reached from four sites that named
the schema module directly: the package facade, the revision validation context,
and two intra-package test modules. All four now import from the new sibling,
matching the precedent already set for the rounding sibling, which the facade
likewise imports canonically. Cross-package consumers in the application layer
reach both symbols through the package's public facade and needed no change. The
schema module keeps both names in its own export list because it genuinely
consumes them, in the revision and snapshot section declarations and in the
folded policy's return type; that is a real dependency, not a compatibility
re-export.

Gate results after the change:

- Module size band: the schema module is absent from both the over-budget and the
  stale partitions, measuring 1386 against 1483 with 97 lines of growth headroom
  and 52 of deletion headroom. The new sibling at 148 lines needs no entry, being
  well under the 1250 default. The stale partition is empty tree-wide.
- Registry suite: 3150 passed. None of the cache-isolation or
  disk-cache-fingerprint spurious failures appeared, so no isolated re-run was
  needed.
- Full-tree collect-only: 15016 collected, no collection errors, re-run
  immediately before the commit.
- Generated API reference: two stubs changed, the new module's own and the
  parent's table of contents entry naming it; the drift check then reports a
  conformant tree.
- Lint and format: clean across the whole registry package.
- Import structure: the cross-module import resolution and lazy-import policy
  gates pass.

## Notes

The semantic discovery probe mandated before coding work was explicitly waived by
the operator for this step: the semantic index is broken and its service stopped,
with a standing instruction not to start, restart, or reindex it. Grounding was
done with literal search and whole-file reads instead. This waiver is recorded
here because the mandate otherwise requires refusing the work outright.

Three gates are red for reasons outside this step, all attributable to the
command-line configuration campaign and all committed at the shared branch head
rather than uncommitted work in the tree. The module size gate reports the
configuration package entry point at 1252 lines against the 1250 default. The
core-struct docstring link gate reports the same package for an unlinked profile
record reference. The import hygiene gate reports an undocumented bridge module
in the wizard payload surface. None is touched by this step and none was absorbed:
editing another campaign's files to green a shared gate risks colliding with work
in flight, so they are reported as inventory for their owner. The schema module
is absent from all three findings, and the size gate's stale partition — the one
this step could have broken — is empty.

The recommended follow-up from the previous extraction is not closed and cannot
be closed under this step's constraints. Taking the predicate concern requires
dropping the module below its baseline entry, which then has to be removed, and
that entry lives in the development tooling tree. The honest sequencing is: a
future step that owns both the schema module and its baseline entry removes the
entry and takes the full 390-line verification concern in one commit, at which
point the module falls under the 1250 default with a wide margin and the sibling
built here absorbs the predicate model and its operator vocabulary. Until then the
band is the binding constraint, not the seam.

The mandatory code review has not been performed. No delegation tool was
available in this session, so the review is owed and should be dispatched by the
coordinator against commit `80909cc71f`.

Peer work in the shared tree was left untouched throughout. Uncommitted changes
in the classification coherence module, two registry test modules, the locale
manager surface, the conformance baseline, and the plan document were present
during this step and remain uncommitted; the commit named its eight files
explicitly and the staged set was reviewed and confirmed free of foreign paths
immediately before committing.
