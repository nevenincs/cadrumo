---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:3b840311d0ae0f5011243098072bb29910a29fa489da30d50b3ce0bc9aff9eef'
step_id: 'S251'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Stop the internal fault projection passing a value_error message through verbatim, since its never-emit-the-input guarantee is defeated by any domain validator that formats the offending value into its own message text. Measured: a boundary carrying a domain exception emits Value error, tax identifier SE556677889901 must be exactly 9 characters, got 14 inside the violations context, so the value crosses the boundary inside the constraint message rather than as the input field the helper correctly withholds. The helper's docstring claims a protection it does not have on that path. This already applies to the two boundary members using it today, so it is a live class rather than one introduced by widening. BLOCKS the input-boundary widening ruled under S239, which would make it three surfaces rather than two

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Reproduce the leak against the real projection, and establish which pydantic
  error types carry validator-authored prose rather than a message pydantic
  composed from the declared constraint.
- Withhold the message for those types only, reporting the rule as the error
  type plus the raising exception's class, both source identifiers.
- Count a withheld message rather than dropping it silently, so a thin report
  is distinguishable from a validator that said nothing.
- Make the docstring true of what the code does, in the same commit.

## Outcome

Modified: `src/cadrumo/entrypoints/cli/_errors.py`. Added
`src/cadrumo/entrypoints/cli/tests/test_internal_fault_context_withholds_the_value.py`.

**The shape chosen: withhold the message, project the rule as the error type
plus the raising exception's class.** Dropping the message alone would have
traded a privacy defect for an unreportable fault, and trimming or
pattern-scrubbing the prose would be a guess about what is sensitive -- which is
the guess this projection exists to avoid making. An exception class name and a
pydantic error type are identifiers from the source tree, so neither can carry
taxpayer data, and together they say which contract failed.

The withholding is scoped to `value_error` and `assertion_error`. Every other
pydantic error type composes its message from the DECLARED constraint -- "String
should have at most 9 characters", "String should match pattern ..." -- naming
the rule without the value, which is already the projection the helper promises.
Those still come through intact.

Measured through the real projection, before and after. Before, a domain
validator raising `ValueError(f"tax identifier {value!r} must be ...")` produced
a context containing the identifier verbatim. After, the same failure produces
`tax_id: value_error (ValueError)` and the identifier appears nowhere in the
serialised context.

**A second leak vector on the same helper, found while measuring and NOT closed
here.** A violation's `loc` reproduces mapping KEYS as well as field names, so a
record holding a mapping keyed by a tax identifier puts that identifier in the
path: a reproduction yields `by_party.SE556677889901`. Telling a key from a
field name needs the model class, which a `ValidationError` does not carry, so
the fix is a design change rather than a filter, and a pattern-matching redactor
would be exactly the guess rejected above. Reachability was measured rather than
assumed: the outbound boundary's result model tree carries exactly one
string-keyed mapping, whose keys are per-modelo detail-row field names, so the
vector is not reachable with taxpayer data on that boundary today. The
stored-data boundary accepts arbitrary persisted records and was not enumerated.
This is recorded in the helper's docstring as a known gap rather than left
implied, and is reported for its own row -- for the same reason this row exists,
that the guarantee should hold at the helper rather than by luck of which models
happen to exist.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests -n0 -q -m unit
    4 failed, 754 passed, 3027 deselected in 97.02s (0:01:37)

None of the four belongs to this lane, established by control rather than by
argument: re-run with this change neutralised at runtime, the same four fail
identically while the two cases that assert the withholding flip to failing.
They are a module-size budget on `_app_live.py` and `_config/_manager_actions.py`,
a descendant payload gaining a field, and an m184 member-row model change.

    uv run --no-sync pytest <the four error suites> -n0 -q -m "unit or integration"
    18 passed in 44.74s

That reading is of a tree byte-identical to HEAD for both files this Step
commits.

Mutation-proved from outside the repository, asserting the leak was observably
restored before reporting: reverting the rule projection reds 2 of the new cases.

## Notes

The first commit attempt failed because the new test file was untracked, and the
`git show` used to verify it reported an unrelated sweeper commit that had landed
a peer's edit to the same module in the interval. That made the working copy
potentially stale against HEAD, so every removed line was inspected before
committing: all were this lane's own replaced content and no peer line was
dropped. The commit carries exactly two files.
