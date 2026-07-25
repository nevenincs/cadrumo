---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# `cli-authority-verb-conformance` audit: `period grammar refusal`

## Scope

Four ledger-import period-grammar cases that reddened during the W06.P18 focused verification wave, in `src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar.py`. The first revision of this note escalated them as a possible instructive-refusal breach and a possible accept-path regression. Both readings were wrong. This revision records the real cause, the fix, and the method error that produced the wrong reading, because the method error is the durable finding here.

## Findings

### The real cause: a stale invocation shape, not a period defect

All four cases addressed the import statement positionally. Under the pull-and-file standard the verb now takes a required `--file`, so the framework refused the unexpected argument and every case died at parse time, before any period logic ran. The bare usage block observed in the failure output was the framework refusing an extra argument. It was never a period refusal that had lost its accepted-set prose.

Corrected at commit `e351ded266`, which passes the statement through `--file` in all four cases. Confirmed at HEAD `8068188db8`: `18 passed in 8.87s`, previously 4 failed and 14 passed.

### There is no accept-path regression

The first revision singled out the accept case as a functional break on the grounds that a token the canonical grammar accepts was being refused. The token was never reaching the grammar. The refusal was at argument parsing, one layer above. Nothing in the period grammar was rejecting it.

### The instructive-refusal requirement is met

Driven through `--file` with an unrecognised token, the refusal names the accepted set and the corrected invocation: `Periodo '2026T1' no reconocido. Use un token AEAT: 1T-4T ... 0A ... (--period 1T --year 2024)`. It names both the accepted token family and the shape of a working call. The requirement that a closed-value refusal enumerate its accepted set rather than fail as a bare invalid value is satisfied on this surface.

### The method error, which is the finding worth keeping

The wrong reading came from reasoning about a refusal's text using only the assertion messages the failures printed. Those messages showed a usage block where accepted tokens were expected, which is indistinguishable from a genuine refusal that lost its prose. No amount of further reading would have separated the two, because the distinguishing evidence was not in the test output at all: it was in what the command does when invoked each way.

The discriminator was cheap and available throughout: invoke the verb by hand, both ways, and compare. The same wave had already used that instrument decisively elsewhere. The MCP identity question was settled by running the shipped executable end to end and watching a real server process answer, which is what turned an arguable test artefact into an unarguable production defect. The instrument was in hand and was not reached for on the structurally identical question one step later.

The generalisation: when the TEXT of a refusal is the thing in question, drive the surface manually before reasoning about the text. Failure output describes what a test asserted, not what the command does.

A second-order point worth stating plainly. Escalating was still correct. A stale invocation against a renamed option surfaces as a refusal-shaped error at exactly the boundary whose refusal text is under scrutiny, so the failure genuinely looks like a grammar defect. The error was not raising it; it was reasoning to a conclusion about it from the wrong evidence, and framing that conclusion as blocked-pending-a-commit rather than as answerable-now-by-a-manual-invocation.

### A durability weakness that survives the correction

All four cases assert against rendered operator prose. That is why an invocation-shape change reddened them rather than a behaviour change, and why the failure output could not distinguish a rewording from a regression. The same cases will redden again on the next wording pass. The accepted set should be asserted on the error envelope's structured context rather than on the refusal sentence. Tracked separately as Step S284.

## Recommendations

Treat this note as closed on its original subject. The period grammar is sound, the refusal is instructive, and the suite is green.

Carry the method rule forward: a question about what an operator-facing surface SAYS is answered by invoking it, not by reading the assertion messages of tests that failed against it. Reach for the manual invocation first, and reserve reasoning-from-failure-output for questions about what a test asserted.

The green suite IS evidence that the refusal names its accepted set, and this note previously said otherwise. The correction matters, because the weaker claim would send the next reader to build coverage that already exists.

The fix added no assertion, but it did not need to: the assertions were already there and had never been reached. `test_import_historic_period_forms_refuse_with_current_canonical_grammar` asserts a non-zero exit, then that the refused token is echoed, then that `1T`, `0A` and `--year` all appear in the output. That is the accepted-set content asserted directly on a refusal. Unmodified by the fix, and now passing. The two sibling cases assert the same shape.

So the standing gate exists. The manual invocation is corroborating evidence, not the only evidence.

Step S284 remains worth doing, but for the reason this note already gives under the durability weakness, not for a coverage gap: the assertions match rendered prose, so the next wording pass reddens them even though the behaviour is correct. Moving them onto the envelope's structured accepted-set makes them durable. It does not add coverage that is missing today.
