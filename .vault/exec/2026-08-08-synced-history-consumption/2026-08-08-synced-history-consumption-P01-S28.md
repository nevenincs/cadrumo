---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:18f10e87309aa6447d2c6379c99d2eba67374f7a66c52929a247cd5808da4562'
step_id: 'S28'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Declare the trabajo net-income antecedent and the advisory predicate it enables, which is what makes the twelve casilla 0596 carries expressible. S22 established that the twelve suffered-retencion carries cannot be advised today because the revision carries no left-hand side for an implies_nonzero predicate, and that AEAT does model the concept: the bundled Manual practico de Renta 2024 Parte 1 page 234 runs a three-phase determination scheme terminating in rendimiento neto previo del trabajo, then rendimiento neto del trabajo, then rendimiento neto reducido del trabajo, indexed in the manual's own annex as an Esquema general. Whether the form carries a NUMBERED box for it is unsettled and does not need settling, because the antecedent must be declared internal_only. State that and state WHY in the fragment itself: an internal_only computed casilla is app-internal calculation support that production drops from the export layout, so it never enters the official numbered-box surface and cannot breach export parity, and without that comment a later reader sees a casilla with no official number and reads it as the export-parity defect this campaign has twice refused. Six fragments already declare internal_only including one on Modelo 100 itself, so the precedent is in the same modelo. Ground the casilla on the binding provisions the manual's scheme rests on rather than on the manual, which is AEAT material and good authority for structure but is not what establishes a compiled value. Ley 35/2006 articles 17, 18, 19 and 20 are all declared in the legal catalogue already. Then declare the ADVISORY implies_nonzero predicate whose antecedent is the new casilla and whose consequent is casilla 0596, matching the two ADVISORY predicates this revision already carries. Do the casilla, its construct and its bindings in ONE change, since the validator requires a construct's refs to cover its member casillas and its bindings and a partial sweep breaks registry load for everyone. Validate against a temp registry root rather than the shared path. Gate: the registry loads clean from a temp root, the predicate fires when the declared trabajo income is positive and casilla 0596 is zero, it holds silently when the income is zero so a filer with no trabajo income sees nothing, the diagnostic names the income certificate rather than a filing to capture because the taxpayer never filed Modelo 111, and a mutation removing the antecedent from the predicate stops it firing

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100`
- `src/cadrumo/application/modelo`

## Description

- Re-checked the row's own premise before building it, and found it false.
- Declared the ADVISORY predicate against a casilla that already exists, so no casilla, construct or bindings change was needed.
- Added the operator-facing advisory text as a code default, the module's documented pattern, so no locale catalogue was touched.
- Validated against a temp registry root, parsed the TOML before committing, and attributed three unrelated failures against a clean HEAD.

## Outcome

THE ROW'S PREMISE WAS WRONG AND THE WORK IS SMALLER THAN AUTHORISED. The row was opened to declare a new internal_only antecedent because S22 reported that the revision carried no trabajo income total. It does. Modelo 100 for 2024 declares all three of AEAT's scheme totals as computed numbered casillas: 0017 rendimiento neto previo, 0022 rendimiento neto, 0025 rendimiento neto reducido, plus 0012 total ingresos integros computables.

S22's finding was a SEARCH ARTEFACT. It searched localized labels, which surfaced only deductions and increments, while the registry identifies these casillas by semantic_role. Searching semantic_role returns irpf_rendimiento_trabajo_rendimiento_neto_previo, _rendimiento_neto, _rendimiento_neto_reducido and _total_ingresos_integros. So the antecedent existed the whole time, and the diseno question S22 escalated and this row was built to sidestep never needed answering.

What that voids: no new casilla, no internal_only declaration and therefore no need for its justification comment, no construct-and-bindings sweep, and no export-parity exposure at all. Four of the row's constraints fell away because the premise did. The change is one predicate plus its advisory text.

THE ANTECEDENT IS 0012, THE GROSS TOTAL, NOT 0025. Retencion is computed on gross income, and 0025 is post-deducciones and post-reducciones, so it can be zero for a filer who did suffer withholding. Using it would suppress the advisory in exactly the cases the advisory exists for. The choice is recorded in the fragment with the rejected alternative named.

THE ADVISORY TEXT IS A CODE DEFAULT, NOT A LOCALE KEY. The module resolves advisory text through a translation lookup with a per-predicate code default, and documents that a registered locale key still takes precedence so translators can enrich the catalogue later without a code change. Two predicates already use it. So this needed no locale edit, which matters because the catalogues are under heavy concurrent churn and were out of scope.

WHY THIS IS NOT THE CATEGORY-KEYED SIGNAL THAT WAS REFUSED. A signal keyed on the declared income category fires on a low-income employee or pensioner whose zero retencion is lawful, because withholding is scaled to the payer's projected annual rate and is zero below the thresholds. implies_nonzero holds trivially at or below zero, so a filer with no trabajo income never fires. The silent case is asserted rather than assumed.

THE REMEDY NAMES THE CERTIFICATE AND NOTHING ELSE. The text tells the operator to enter the figure from the payer's certificado de retenciones e ingresos a cuenta and states that the taxpayer never filed the Modelo 111 that declares it. The first draft said no capture can fetch it, which is true but tripped the test's own guard against the words pull, capture and fetch. Rewording rather than loosening the guard was the right way round: the guard stays crude and therefore hard to defeat later.

## Verification

    uv run --no-sync python -c "<rtoml parse of the changed fragment>"
    TOML PARSES OK, predicates: 3

    uv run --no-sync python -c "<ValidatedRegistryAuthority.load against a temp root>"
    TEMP-ROOT LOAD OK. M100/2024 predicates: 3

The registry change was never validated against the shared bundled path, only against a copy extracted from HEAD with the changed fragment overlaid, because an invalid registry installed live reds the tree for every agent and did so for twenty minutes earlier today.

    uv run --no-sync pytest -n0 -q <the new predicate test>
    5 passed in 105.89s

Four behaviour assertions plus the wording guard: it fires on positive gross income with zero retencion, holds silently on zero income, holds when the retencion is credited, and the declared predicate is ADVISORY with non-empty legal refs. The test reads the predicate off the loaded registry rather than restating its expression, so a change to the fragment is exercised rather than duplicated.

MUTATION PROOF, out-of-repo plugin, holder asserted before rebinding. The evaluator was rebound so every implies_nonzero expression always holds.

    1 failed, 4 passed in 39.02s
    FAILED ...::test_it_fires_when_trabajo_income_is_declared_and_no_retencion_is_credited

Exactly the firing assertion reddens and all three controls stay green, which is the correct blast radius: a blind evaluator can only destroy the detection. Had the silent-case control also reddened, the test would have been asserting the evaluator rather than the predicate.

ATTRIBUTION OF THREE FAILURES IN A WIDER RUN, none of them this change. A registry-tests run reported three failures. Against a clean extracted HEAD one still fails, so it is pre-existing or peer churn. Against clean HEAD with only this change's three files overlaid, seven tests pass including both Modelo 200 tests that failed in the working tree.

    HEAD + only this change's files: 7 passed in 43.40s

So the other two are peer WIP present in the working tree and not caused here.

Type and lint gates on the touched production module: ty check all checks passed, ruff format unchanged, ruff check clean.

## Notes

CORRECTION TO S22, WHICH THIS ROW EXISTED TO SERVE. S22 stated the revision carries no trabajo income total and named that as the missing signal blocking twelve carries. That statement was an artefact of searching localized labels rather than semantic roles. The twelve were expressible all along. The diseno investigation S22 triggered was not wasted, since it established that AEAT models the concept and produced the internal_only route, but that route turned out to be unnecessary rather than the answer.

The correction generalises: a registry search over localized labels can miss a casilla that exists, because labels resolve through the locale catalogues while the registry's own identity for a semantic concept is semantic_role. A negative result from a label search is not evidence of absence.

WHAT THIS COVERS AND WHAT IT DOES NOT. The twelve Modelo 111 fed casilla 0596 carries, on the 2024 revision ONLY. The 2020 through 2023 and 2025 revisions carry the same casilla and are not covered here: a predicate is declared per revision, and copying one across revisions without checking each revision's own casilla set would be the analogy this campaign forbids. The six Modelo 123 fed 0597 carries were already expressible against existing capital-mobiliario antecedents and are untouched. The single Modelo 184 fed 1577 carry stays deliberately unassessed.

A ninth peer sweep took all three of this change's files into HEAD before they could be committed here. All three were verified present in HEAD afterwards by content: the predicate id, the advisory text and the test file.
