---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:28c5891a0ca746321095cb11c1fd340342ef2939105bc3ac36cf014d9a7e27f7'
step_id: 'S146'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh read the thirty-six creation call sites that assert no exit code and decide each individually, since they assert on output or on later state rather than on success and therefore cannot be swept, this being a reading job whose size should be stated honestly before it starts rather than a mechanical conversion

## Scope

- `src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/entrypoints/cli/_config/tests/`

## Description

- Size the population by reading it, before converting anything.
- Classify each site by what its enclosing test does with the invocation.
- Report the honest number even when it is zero.

## Outcome

**The row resolves to zero conversions, and that is the finding rather than a
gap in the log.** It was sized at thirty-six sites; the honest number of
convertible ones is none.

The population is thirty-three, not thirty-six, because it moved as the
preceding conversion row landed. It splits four ways. Twenty-four run the CLI
as a SUBPROCESS and assert on a return code, so an in-process registration
helper cannot substitute for them at all -- those became their own row. Four
are helpers already excluded on the return contract, since a helper that hands
a click result to its caller cannot have its body replaced without changing
what the caller asserts. One observes its own result and stays. The remaining
two are not invocations.

**Those last two are why the number is zero rather than two.** One is a
projected action's `cli_path` field inside a model-dump equality; the other is
the expected argv that a schema-to-argv projection is asserted to produce.
Both are lists that MENTION the creation verb rather than lists PASSED to it.
Converting either would have replaced an assertion's expected value with a
registration call -- and in the second case that fails in the one direction
that looks like success, because destroying the expected value of a projection
test is exactly how a green suite stops proving the projection.

## Notes

**The sizing pass carried a defect worth recording with its symptom.** It
classified each site by whether the ENCLOSING FUNCTION compares an exit code.
That is the wrong question for a helper: the helper returns, the caller
compares, and the helper therefore looks like it discards its result. Three
sites were labelled convertible fixtures that were already excluded on their
return annotations -- a gate established two rows earlier and not applied to
the tool that was meant to enforce it. **A classifier that reasons about a
function's body cannot classify a function whose job is to hand the answer
onward.**

The same reading exposed an error in the preceding row's published figures,
which were corrected in that record rather than here. The census matched list
literals containing the verb, and some such lists are assertions about the CLI
path rather than calls to it.

**A row sized before its population is read is not an under-delivery when it
shrinks.** Thirty-six anticipated and zero delivered is the same shape as the
neighbouring row's nineteen anticipated and four touched: in both, the reading
was the work, and the sweep was the part that turned out not to exist.
