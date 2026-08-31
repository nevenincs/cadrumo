---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c6d566ebbe5d6a75c3943f313890f3b047e09d9048563840c263ffc11a2bceca'
step_id: 'S163'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the light eager re-export facades on an import resolver that reads every relative form, after a regex census reported twelve namespaces unread that 386 tests were reading

## Scope

- `src/cadrumo/`

## Changes

- `M` forty-one `__init__.py` namespaces made inert, and every consumer repointed at the defining module
- `verify:` eager re-export facades 83 -> 42; inert namespaces 63 -> 86
- `verify:` `pytest --collect-only -q` -> 28877 collected, 6 errors, all pre-existing and peer-owned
- `verify:` `pytest core + renta + submission + usage_ratios + evidence + export + transactions -n 0` -> 2603 passed, 28 failed, none import-related and none naming a retired namespace
- `verify:` no file fails to parse, no relative import resolves to a missing module

## Notes

The step exists because the FIRST census was wrong, and the second was wrong in
a different way. Both reported confidently.

The regex census matched the bare-package form (`from .. import X`) and the
immediate-sibling form (`from ..retention import X`) but not the dotted-path
form (`from ....domain.retention import X`), which is how most consumers
actually import. It reported twelve namespaces as having ZERO readers. They were
retired on that reading and collection went to 386 errors: 185 tests read
`domain.retention` alone. The twelve were restored from committed content,
byte-clean, and collection returned to its 6 pre-existing errors.

The replacement resolved `level` and `module` the way Python does -- and still
reported the same twelve unread. It carried an off-by-one: level 1 means the
containing package, which for an `__init__.py` is the module itself but for a
plain module is itself-minus-its-own-name. Applying the package form to both
mis-resolved nearly every consumer.

So the third version carries a ground-truth arm. Five namespaces were PROVEN to
have readers by the 386 collection errors; the scan refuses to report at all
unless it can see all five. That arm is the only reason the third version can be
trusted, and it is the step that both earlier versions skipped.

### What the corrected instrument found

Zero namespaces are unread. All 83 have consumers, so there was never a tranche
of free retirements -- that tranche was an artifact of the defect, twice.

### Three more defects, each found by reading rather than reasoning

The repointing tool was wrong three times, and in each case I predicted a cause
and the prediction was wrong. Reading the emitted line against the committed one
settled all three in a single pass:

- a function-local import was rewritten at column zero, so eleven files stopped
  parsing
- `from .. import X` already ends in its dots, and joining another one landed a
  level too high -- `from ...sub` instead of `from ..sub`
- a facade re-exporting `_x as x` leaves no `x` in the defining module, so the
  repointed import has to carry the private name and re-alias it

The tool refuses rather than guessing when a consumer imports a name the eager
block does not carry. That refusal is load-bearing: it stopped the sweep on
`application.registry`, where a gate test imports `__all__` from the namespace
itself and retirement changes what that test MEANS.

### A structural constraint the sweep discovered

`storage.blob_store` and `storage.envelope` retired cleanly and broke 639
collections. Their PARENT namespace's lazy map reads its own exports through
them, so a child cannot go inert before its parent. Both were restored; the
consumers repointed at defining modules stayed correct and were kept.

That is the dependency ordering behind the two largest open steps -- storage at
257 lazy exports and core at 357 -- and it means those two are not merely bigger
instances of this work but its precondition.

### Five namespaces refused retirement on their own merits

Retired and then reverted, each for a reason worth keeping rather than
retrying:

- `application.invoices` -- a gate test asserts the production resolver IS
  publicly exported. Retirement does not fail that test, it contradicts it, so
  the question is which rule governs and that is not a mechanical call.
- `core.resources` -- consumers reach it as `resources.bundled_path(...)`,
  attribute access on the module object. No import scan can see that, which
  makes it the one shape this whole instrument is blind to by construction.
- `aeat.browser`, `storage.blob_store`, `storage.envelope` -- the parent's lazy
  map reads its own exports through the child.

The parent-first constraint is now a guard in the tool rather than a lesson, so
the sweep refuses those instead of discovering them at collection time.

### What the residual refusals are

Forty-two namespaces still carry an eager block. They divide into namespaces
whose parent must go first, namespaces that also carry a `__getattr__` lazy map
(the eager block is only half the facade), and namespaces that DEFINE production
code directly rather than re-export it -- the last being the population of
`P07.S17`, `P07.S67` and `P07.S83`, which is relocation work and not this.

### A peer's staged commit was broken, and the sweep spread it

`application.calculations` (156 exports, 153 consumers) was `MM` -- staged AND
further modified. It was retired anyway, because the status check and the sweep
ran in one command and there was nothing to gate on between them.

Their staged change regrouped two names into different import blocks, and BOTH
new homes are wrong: `relation_prefill_period_zero_default_binding_ids` is
defined in `_relation_prefill_m202`, not `_relation_prefill`, and
`filing_external_evidence_blockers` in `_cross_period_external_evidence`, not
`cross_period_clean_state`. The retirement read that staged map as authority and
propagated it, and 240 collections failed.

Restoring their staged version did NOT fix it -- it reinstated their defect,
which is how the defect was found at all. The `MM` was almost certainly them
midway through fixing it, and that unstaged fix is what the sweep overwrote.
Both symbols are now re-homed on the modules that define them, their staged
regrouping intent preserved, and the namespace left eager: retiring it belongs
to whoever holds that commit.

The rule this yields is narrower than "skip dirty files". A facade's import
block is a MAP, and a sweep that repoints consumers through it inherits
everything the map gets wrong -- so a facade being actively edited is not merely
a merge hazard, it is an unreliable source. Read the map against the defining
modules before trusting it, which the tool now cannot do for a name it cannot
find and refuses on instead.
