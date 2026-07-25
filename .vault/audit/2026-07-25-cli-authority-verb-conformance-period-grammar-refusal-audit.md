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

Four ledger-import period-grammar cases in the CLI test surface that failed during the W06.P18 focused verification wave and could not be judged at the time. This note records the reasoning so the judgement is not lost when the surface they depend on settles. It reaches no verdict, and it recommends no fix.

The four cases live in `src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar.py`. They failed identically in the parallel and the sequential pass, so they are not worker artefacts.

## Findings

### The four cases are not one thing

Three concern the wording of a refusal. One concerns whether a valid input is accepted at all. Treating them as a single cluster is the mistake this note exists to prevent.

### One case is an accept-path failure and is judgeable on its own terms

`test_import_accepts_aeat_token_with_year` at line 312 asserts a successful import of a year-qualified AEAT period token. It fails with an assertion message that opens with the import command's usage block, meaning the invocation was refused rather than accepted. A token the canonical grammar is specified to accept is being rejected at the command boundary.

This is a functional outcome, not a presentation one. No change in how a refusal is worded can explain an accepted token becoming a refused one, so this case should not be absorbed into the wording discussion below. It is the strongest candidate for a real regression among the four.

### Three cases lost the accepted-token list from their refusal text

`test_import_historic_period_forms_refuse_with_current_canonical_grammar` at line 346 requires the refusal to name `2024-1T`. `test_import_period_without_year_refuses_with_year_guidance` at line 376 requires it to name `1T`. `test_import_period_year_prefixed_token_refuses_with_current_canonical_grammar` at line 406 requires it to name `2026T1`. In each, the refusal now renders a bare usage block followed by a framed error region, and the required token appears nowhere in it.

### What the requirement actually demands

The architecture boundary rule requires every closed-value CLI axis to hint its accepted values at the boundary, and requires a late registry-driven refusal to list the accepted set in its error message rather than fail as a bare invalid value. The stated reason is that the CLI gate is the operator's first instructive surface. The requirement is that the accepted set reaches the operator; it does not mandate any particular sentence.

That distinction is what makes the three wording cases unjudgeable rather than failed. There are two endings that satisfy the requirement and one that breaches it.

The first satisfying ending is that the period option becomes a typed enum at the command boundary, so the framework renders its own accepted-value list on parse failure. For a closed value set this is the ending the architecture rule prefers, and it would mean the three tests are stale rather than the code being wrong.

The second satisfying ending is that the accepted set survives structurally on the error envelope while the rendered text carries only the usage block. A sibling failure in the same wave, `test_registry_retained_commands_reject_command_local_json_flag` in `test_registry_cli.py`, shows framework-level boundary errors now being wrapped into a refused-CLI-boundary envelope carrying an option context, so a structured accepted-set field is plausible. All three cases assert against rendered text and would not observe it.

The breaching ending is that the accepted tokens appear neither in the rendered text nor in the envelope context. Then the refusal is the bare invalid-value refusal the rule forbids, and the repair belongs in the boundary rather than in the tests.

### What blocks the judgement

The CLI common module that owns the boundary refusal, `src/cadrumo/entrypoints/cli/_common.py`, was uncommitted in the shared worktree throughout the verification wave, alongside the error-taxonomy work visible in the sibling refused-CLI-boundary failure. The observed behaviour is therefore a snapshot of another campaign's intermediate state, and neither the rendered text nor the envelope shape can be treated as the intended end state.

### A durability weakness independent of the outcome

All four cases assert against rendered operator prose. That is why a boundary change reddens them rather than a behaviour change, and it is why the wave could not tell a regression from a rewording without reading the source. Asserting on generated or localised prose is fragile by construction; the same four will redden again on the next wording pass and cost another triage cycle.

## Recommendations

Re-check the accept-path case first and separately, as a candidate regression rather than as churn. Drive the year-qualified AEAT token through the import command and confirm it is accepted. If it is still refused, that is a functional break in the period grammar and it is independent of anything in the wording discussion.

For the three wording cases, apply a prose-independent test once the boundary module commits. For each refusal, assert that the accepted period tokens appear either in the rendered text or in the error envelope's context. If they appear in neither, the instructive-refusal requirement is breached and the boundary is the thing to repair. If they appear in the envelope, or the framework now renders its own accepted-value list, the requirement is met and the three assertions are stale.

Whichever way it lands, repair the four to assert on the structured accepted-set carried by the envelope rather than on the refusal sentence. That is what makes them durable across future wording changes, and it removes the prose dependency that made this wave's triage necessary.

Do not close the owning verification Step on a green re-run alone. A green result after the boundary settles could equally mean the accepted set came back or that the assertions were relaxed to match whatever the boundary now emits; the check above is what distinguishes those.
