---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:331868c075c4a41d648a4bd3cd54c25fb82a8bd352f55ad5c02012d656b56790'
step_id: 'S10'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---




# Add a mutation-proof test confirming the reason-distinguishing branch fires per swallowed case and confirm the CLI report surfaces the Notice

## Scope

- `src/cadrumo/application/live/tests and src/cadrumo/entrypoints/cli/tests`

## Description

- Search by meaning for the justificante-to-observation matching concept, then confirm the exact declaration and every caller with a targeted search.
- Read the six-member unreached-reason taxonomy and the six distinct sites that produce it.
- Find the existing application-layer coverage of the reason taxonomy, and establish what it does and does not exercise.
- Trace the reason channel from the application layer to the CLI envelope and identify the transport boundary that folds it in.
- Confirm the transport boundary carries no coverage at all.
- Author a test module driving that boundary directly, over the full enum, with a negative control on the success path.
- Prove the new assertions bite, with a mutation applied from outside the repository.
- Replace a dict splat with explicit keyword arguments so the boundary's types are checked rather than erased.

## Outcome

The reason-distinguishing branch was ALREADY covered per swallowed case, and covered well: the existing application-layer test arranges five of the six dead ends through the real enrolment path, derives its expected set from the enum rather than hand-listing it, asserts the reasons are DISTINCT rather than merely counting them, and carries a negative control proving the success path emits nothing. It excludes only the reason whose arrangement would require a test double standing in for the real store, and it says so. Nothing there needed rebuilding.

The half that was missing is the second clause of this Step: the CLI report surfacing the Notice. The reason taxonomy exists to undo a uniform silence, and it only reaches an operator if the CLI folds it onto the envelope. That fold is a single statement at the boundary where three advisory sources converge on one channel, and it had NO coverage — the function containing it had no test referencing it anywhere in the tree. Deleting that statement would have left the whole suite green while every reason went silent at exactly the surface an operator reads.

The existing application-layer test is named for that relay and its docstring reasons about it, but it does not exercise it: it constructs the advisories onto the run model itself and then asserts them back off the same object. That is a pydantic storage roundtrip, so it cannot fail when the forwarding is removed. The name and the docstring claim reach the assertions do not have. The new module closes that gap rather than editing a peer-owned file mid-flight; the weaker test is left standing and recorded below, since it is not wrong, only narrower than it reads.

Four assertions now drive the transport boundary: every enum member survives the fold as its own notice with its reason readable in context; a forwarded notice arrives verbatim so severity, code, message and context all survive; a refused pair and an unusable receipt stay distinguishable while sharing the channel; and a run that reached all its evidence forwards nothing. The expected set is derived from the enum, so a newly added reason fails here instead of going unrelayed.

## Verification

Clean:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_app_live_filed_notice_relay.py -n0 -q
    4 passed in 3.74s

Mutated, with the mutation plugin resident OUTSIDE the repository and loaded by path:

    PYTHONPATH=<scratchpad> uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_app_live_filed_notice_relay.py -n0 -q -p mut_notice_relay
    MUTATION APPLIED: FiledHistoryOnboardingRun.evidence_notices rebound to (), holder confirmed non-empty before rebinding
    3 failed, 1 passed in 2.19s

The mutation rebinds the attribute the production statement reads, so the statement still executes and becomes the no-op that deleting it would have produced. Nothing under the source tree changed, so a peer sweep cannot commit the mutation and a crashed run leaves no residue.

The plugin REFUSES rather than passing on three no-op conditions: the channel field absent from the model, an unmutated instance not returning the advisories it was built with (so there is no holder to rebind), and the rebinding failing to take. A mutation harness that silently fails to bite prints APPLIED and turns the entire proof decorative.

The one test that stays green under mutation is the negative control, which asserts the advisory is ABSENT; it must survive, and a mutation that reddened it would mean the control was testing the wrong thing. Positive control on reach: the refused-pair advisory is still present in the mutated run, so the mutation emptied only the forwarded channel and did not disable the builder wholesale.

Lint and types:

    uv run --no-sync ruff format --check <file>; uv run --no-sync ruff check <file>; uv run --no-sync ty check <file>
    All checks passed!

Commit `f7caa4eba0e8859c9b3a4991cea9c01e961545c0`, verified after the fact:

    git show HEAD --numstat
    138	0	src/cadrumo/entrypoints/cli/tests/test_app_live_filed_notice_relay.py

One file, additions only, no peer path in the commit.

## Notes

Recorded rather than silently fixed: the existing application-layer relay test asserts on a field the test itself populated, so its name and docstring claim coverage of the fold that its assertions do not provide. It is not a false test — every fact in it verifies — but it cannot fail if the forwarding is deleted. It is left in place; the gap it appeared to cover is now covered for real at the boundary itself. Worth a follow-up to narrow its name and docstring to what it actually proves, which is that the reason taxonomy has at least six members and that the model stores one advisory per member.

The reason requiring a test double to arrange — the one where secure storage cannot return bytes it holds — remains uncovered at the application layer, as the existing test states. It IS covered at the transport boundary here, since the new module drives the full enum. So the taxonomy is now fully exercised at the surface an operator reads, and partially at the layer that produces it.

A dict splat in the first draft of the helper erased the model's field types and produced type diagnostics. Replaced with explicit keyword arguments rather than suppressed: a suppression there would have hidden exactly the boundary this Step exists to check.

This Step's first clause was already satisfied before the work started. That is recorded as found, not claimed as delivered.
