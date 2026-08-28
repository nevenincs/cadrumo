---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:56263f3429f07d9c889cd4ff2c8a2d5b0fe2f5930791b0f040ea4333423d3f5f'
step_id: 'S307'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Validate defaults on the shared strict-frozen model configuration rather than patching each embedding module as the gap resurfaces: the canonical config declares strict, frozen and no-extra-fields but never validate_default, so a default value that would fail its own field validation is accepted silently, and the operations payload-graph gate has now refused three separate models for exactly this reason in one Step; add the missing declaration at the shared constant, run both test lanes before committing, and treat any model whose default then fails as a latent defect to report rather than a regression to work around

## Scope

- `the shared strict-frozen ConfigDict in core/_models.py`
- `and a full two-lane verification run over the models that consume it`

## Changes

- `M` `src/cadrumo/core/_models.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding296_bindings.py`
- `A` `src/cadrumo/core/tests/test_strict_frozen_config_validates_defaults.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/core/tests/test_strict_frozen_config_validates_defaults.py -m unit -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/core/tests src/cadrumo/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py -m unit -n0` -> `fail`

## Notes

### The blast radius was measured before anything was changed

The change was made in a detached worktree off the shared tree first, so the
main line was untouched while its effect was being established. Every model
carrying the shared configuration was then probed: 1873 modules imported with
no import failures, 2587 pydantic models discovered, 1696 of them on the shared
constant, 4380 defaulted fields checked.

Exactly one default failed its own field validation. Not a wide sweep, and not
several Steps.

### The probe was wrong first, and was fixed rather than reported

The first pass reported 26 failures. Twenty-four were artefacts of the probe
itself: the type adapter it used refuses a configuration argument for
model-typed annotations, and unresolved forward references raise instead of
validating. Reporting that number would have turned a one-line change into an
apparent tree-wide crisis.

The probe was corrected and every surviving candidate was then re-confirmed by
constructing the real model with the flag actually enabled. One more candidate,
a mapping-proxy default, constructs perfectly well under real pydantic and was
dropped. The measured figure is one.

A second false measurement was caught mid-flight and discarded: the first
behavioural run in the isolated worktree was importing the main tree's package
through the editable install rather than the modified source, so it was
measuring the unchanged code. The interpreter's resolved package path and the
live configuration value were both asserted before any later result was
trusted.

### The one latent defect, and why it was fixed the way it was

`Withholding296Observation.subclave` declared a default of the empty string
under a pattern requiring exactly two digits. The default could never satisfy
its own constraint, and nothing noticed, because a default was trusted unread.

The fix was chosen from the registry rather than from what would turn the tree
green. The official perceptor record for this modelo declares the subclave slot
as not required, two characters wide, with no padding - so an undeclared
subclave is a legitimately empty slot, not a missing code. The constraint was
therefore widened to admit the absent case explicitly, which leaves the empty
default valid, keeps two-digit validation for any supplied value, and invents
no regulatory value. Substituting a plausible-looking code such as the sibling
field's would have been inventing one.

Behaviour after the change was checked in all three directions: the default
remains the empty string, a supplied two-digit subclave still validates, and a
one-digit subclave is still refused.

### Mutation proof, run as the production toggle rather than a patch

The gate here is the declaration itself, so the proof is the declaration being
removed. Two runs of the same selection, at the same commit, in the same
worktree, with nothing different but the flag:

- flag on: 9 failed, 1666 passed
- flag off: 12 failed, 1663 passed

The difference is exactly three assertions, all of them the ones that depend on
the declaration: the constant declaring it, a default violating its own pattern
being refused, and the same for a default produced by a factory. **Zero tests
fail with the flag on that pass with it off** - the change causes no regression
in the measured set, and the nine failures shared by both runs are identical
gate and census tests untouched by this work.

The suite also carries an anti-tautology assertion that stays green in both
directions on purpose: the same field on a locally declared configuration
without the declaration still accepts the invalid default. Without it, the
refusal test would pass just as happily against a field pydantic checks for
some unrelated reason and would prove nothing about the shared constant.

### The sibling constant moved with it

The hidden-input variant of the shared configuration had the identical gap and
received the identical declaration. Leaving it behind would have recreated, in
one file, exactly the per-site divergence this change exists to end.

### Provenance: captured again, into an unrelated subject

None of this was committed by its author. A concurrent broad commit in the
shared worktree captured all three files under a subject about resolving
user-profile usage ratios through their own defining module, together with
several unrelated files. The content at the main line is correct and was
verified there afterwards; the commit subject describes different work.

This is the ninth such capture during this campaign and the fourth against this
author's work. The earlier lesson stands and is now routine rather than
notable: a capture does not only misattribute authorship, it can split a change
or land it under a description that makes it unfindable later.
