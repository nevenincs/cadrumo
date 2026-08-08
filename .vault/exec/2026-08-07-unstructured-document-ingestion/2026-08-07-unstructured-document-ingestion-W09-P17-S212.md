---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:391e32183b09ec90b931fd5d3a1cbab424b9d619a6596942d08f658126ef297f'
step_id: 'S212'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Let the counterparty show verb ask the question its own justification cites, since it calls resolve_confirmed_counterparty_facts with bucket_id, tax_identifier and country_code and omits evidenced_scope, while the contradiction branch fires only when evidenced_scope is not None. So show structurally cannot reach the path the record justifies it by. Operator consequence measured: someone who confirmed ES_CANARIAS and then holds a document printing mainland evidence is shown confirmed es_canarias, while the ladder mid-confirm returns a contradiction and no scope and the review items raise a blocker naming it, so the two surfaces diverge in exactly the case the verb exists for and the divergence is invisible from show. Add an optional evidenced-scope option threaded to the resolver so an operator holding a document can see the contradiction before confirming, or narrow the record and docstring to the architectural claim that one authority answers both surfaces and drop the contradiction sentence, which describes a sibling call site

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Add the optional evidenced-scope option to the counterparty show verb, typed
  as the territory enum at the Typer boundary, threaded to the same resolver
  the ladder asks.
- Extend the show payload with the evidenced territory, a contradicted flag,
  the confirmed territory and the resolver's own detail sentence.
- Emit the disagreement through the shared notice channel at warning severity.
- Rebuild the text line from the same three states the payload reports.
- Narrow the verb docstring and the payload docstring to the claim that holds.
- Add the two locale keys with real strings in all four catalogues.
- Add the verb's first dedicated CLI test module, driving the real Typer tree.

## Outcome

**The judgement the row left open was resolved as BOTH, and the reason is that
the option alone does not make the prose true.** The row offered adding the
option or narrowing the record to the architectural claim. The option is
optional, so a bare show still cannot reach the contradiction branch, and an
unconditional "what an operator is shown and what a later document resolves to
cannot drift apart" stays false whatever the option does. The prose therefore
had to be corrected regardless, and the option is what makes the corrected prose
worth reading: one form asks what is confirmed, the other asks the ladder's real
question, and the payload now says which.

The false claim was in the payload rather than only the verb, and it was
load-bearing rather than decorative. It justified the whole design -- reporting
what the ladder will answer rather than what the repository holds -- by a branch
the verb could not reach, which meant the payload's stated reason for existing
described a sibling call site.

**The contradicted flag is the part that changes operator behaviour.** On a
contradiction the resolver returns no fact, so the confirmed flag is false and
the territory is null -- byte-identical to a counterparty nobody has answered
for. The two want opposite remedies: one asks for a first answer, the other asks
which of two existing claims to withdraw. Without a field separating them a
payload sends an operator to the wrong verb, so the flag is what makes the state
actionable rather than merely reported.

The confirmed territory is carried in its own field and deliberately kept OUT of
the field meaning "what the rung will answer". On a contradiction the rung
answers nothing, and a consumer reading the confirmed value out of that field
would use a territory no document resolves to -- the same laundering the
resolver's own withholding exists to prevent.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_counterparty_show_cli.py -n0 -q -m integration
    6 passed in 10.02s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -n0 -q -m integration
    515 passed in 45.61s

Mutation proof, run from OUTSIDE the repository so no tracked file was edited.
A plugin on the path rebinds the resolver on the package facade the verb imports
at call time and drops the evidenced territory, which reproduces the defect
exactly rather than approximating it:

    PYTHONPATH=<scratch> uv run --no-sync pytest <the module> -n0 -q -m integration -s -p drop_evidenced_scope_plugin
    [MUTATION] drop-evidenced-scope plugin LOADED
    [MUTATION] rebinding installed on a real holder
    [MUTATION] APPLIED: calls=6 evidenced_scope_dropped=5
    3 failed, 3 passed in 7.43s

    FAILED test_evidence_disagreeing_with_the_confirmation_is_visible_before_a_confirm
    FAILED test_a_contradiction_is_distinguishable_from_an_unanswered_counterparty
    FAILED test_the_contradiction_reaches_the_operator_through_the_notice_channel

Four rungs. The banner proves the plugin loaded; a hard assertion proves the
rebinding found a real holder, since a no-op rebind would otherwise print
APPLIED while everything passed; the dropped-argument counter proves the wrapper
was not merely reached but actually had an argument to remove; and **the three
tests that stayed green are the control**. A mutation reddening the whole module
would prove wholesale damage rather than a simulation of the branch under test.
The three survivors are exactly the cases that do not depend on the contradiction
path -- the bare question, agreeing evidence, and the enum parse refusal -- so
the mutation is attributable to the one argument it removed.

## Notes

The locale catalogues carried another lane's uncommitted keys, eight lines per
file against this slice's two, and the drift check shows those keys have no code
reference yet -- so committing them would have landed half of that lane's atomic
change. The two keys here were staged through the apply-cached drive against
HEAD, with the staged set verified to carry zero foreign markers by an allowlist
derived from the patch itself, and taken by a verified-index commit. Eight added
locale lines committed, eight of them this slice's own.

The locale drift gate is red tree-wide on two keys belonging to the
identification lane. This slice's own parity is clean and was checked
separately rather than inferred from the gate: every catalogue reports no
missing keys, so both new keys resolve in all four with real, distinct strings
and neither is a self-referencing placeholder.
