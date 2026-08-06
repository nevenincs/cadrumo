---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:f11bdfe5e9e6cd4ab457aa5fb68f03d980b33918d6f0172d62cd4843318e23ff'
step_id: 'S16'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Ground the chain on an exempt-services example proving the under-declaration direction is closed

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Add `src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_oracle_exempt.py` driving one IVA-exempt professional service through the same three chain links as the rated sibling.
- Ground the figures the same way: the invoice's own base imponible for casilla 01, and the RIRPF art. 95.1 rate from the registry parameter catalogue for the retencion.
- Assert the declared category is what makes the cuota zero, reading the Axis-A table rather than testing for a null field, since that distinction is what the whole recovery rests on.
- Pin the substrate-absent branch's shortfall to the withheld amount rather than to a literal, tying the two losses to one another.
- Assert the cash falls strictly below the base, fixing the case's identity as the under-declaring direction.
- Omit the rate-inversion guard the rated sibling carries, and record in the module why it cannot discriminate here.

## Outcome

Landed as commit `e038988344` (1 file, +294, 0 deletions).

Raw counts, serial runs (`-n 0`): the module alone 7 passed, 0 failed, 0 skipped; with its rated sibling 14 passed, 0 failed, 0 skipped.

The under-declaration direction is closed by visibility rather than by exclusion, and the module pins exactly that. An exempt operation has no cuota to offset the withholding, so the bank credit of 850 sits strictly below the 1000 ingresos integros. Without its base, casilla 01 receives the 850 and the return under-declares by precisely the 150 withheld, while the offsetting retenciones credit is lost at the same time. The fallback is deliberately kept, because dropping the row would under-declare by the whole 850 instead of by 150, so the ungrounded screen firing IS the closure.

The exempt case earns separate coverage rather than a parameter on the rated one, and the mutation proof below is the evidence: restoring the pre-relaxation precondition reddens two gates here and none in the rated module.

## Notes

The rate-inversion guard was written, run, and removed, and the removal is the finding. With no cuota the invoice total equals the base, so cash equals base times one minus the rate exactly, and inverting the rate off the cash returns the same 150 by coincidence. The assertion therefore excluded nothing while looking like a check. It is recorded in the module docstring as deliberately absent rather than silently dropped, because a later reader comparing the two siblings would otherwise read the asymmetry as an oversight. The cuota is what breaks the coincidence, which is why that guard belongs to the rated case only.

The substrate-absent variant drops the declared category along with the base, which is not incidental. A base with no cuota and a bank credit with nothing recorded against it are indistinguishable on the amounts alone; only the declared category separates exempt income from untagged income. Keeping the category while dropping the base would have described a different, narrower row than the clean-bank-import state the branch is meant to represent.

### Mutation proofs

Run in process by rebinding the function under test, so no broken state existed in the working tree at any point.

- Restore the pre-relaxation withheld precondition, where the cuota is determinable only from a recorded `iva_amount`: 2 of 7 gates red here, 0 of 7 red in the rated module. That asymmetry is the whole justification for the separate module.
- Sum the gross amount unconditionally: 3 of 7 red.
- Sum only the declared base: 2 of 7 red.
- Apply the retencion rate to an IVA-inclusive total: 2 of 7 red.

## Second pass: the scenario itself becomes AEAT's

The first pass grounded the figures on published RATES while choosing its own base, and recorded in the Notes above that the bundled manual-oracle corpus could not be used because the honesty gate requires an `input_kind = "computed"` casilla and Modelo 130 casilla 01 is bound. That blocker was real and is now retired twice over: the governing decision has since admitted bound casillas under a fixture-provenance condition, and this pass does not need that admission at all, because it grounds a COMPUTED casilla sitting immediately downstream of the bound one.

The step asked for an AEAT worked example, and one exists. AEAT Manual practico de Renta 2024, Parte 1, Capitulo 7, "Caso practico (determinacion del rendimiento neto derivado de actividad profesional en estimacion directa, modalidad simplificada)". Its nota (7) states the exemption on AEAT's own account: "Se deduce como gasto el IVA soportado por tratarse de una actividad exenta de este impuesto que no da derecho a deducir las cuotas soportadas." The IVA soportado is a deductible gasto precisely BECAUSE the activity is exempt, so the exempt-services character of the example is published rather than inferred from the profession.

The gap it closes was measured, not assumed. Modelo 100 casilla 0171 ("Ingresos de explotacion") is `input_kind = "bound"` to `renta-2024-ledger-income-0171`, source kind `ledger_renta_income_aggregation`. The pre-existing oracle for this same caso practico supplies 0171 as a hand-typed casilla input, so it grounds the formula chain ABOVE the binding while stepping over the two links this campaign exists to defend: the aggregation that turns invoices into observations, and the resolver that folds observations into the bound casilla. Both now run for real.

Driven from the two ingresos lines the manual prints (Honorarios 124.000, Conferencias 10.800) as exempt ledger rows, through `aggregate_renta_m100_income_ledger` and `resolve_ledger_renta_income_aggregation_binding_values` against the committed 2024 revision, the chain resolves 0171 = 134.800 and the registry formula chain then reaches 0180 = 138.400 and 0226 = 58.100 — the manual's own printed "Total ingresos" and its thrice-printed "Rendimiento neto". Casilla 0180 is added to the bundled oracle payload and declared `externally_grounded`, which is the durable half: it is the first PUBLISHED total downstream of the binding, so a compensating pair of errors on the ingresos side can no longer pass.

The fixture carries only facts the example DESCRIBES — two income lines, their amounts, the exempt treatment it states — and never its result. Nothing in it is derived from 138.400 or 58.100.

### What this example can and cannot demonstrate

The under-declaration direction is closed here by VISIBILITY, not by a euro shortfall, and the distinction is measured rather than asserted. Dropping the base from an income row degrades its grounding to the cash fallback and fires the ungrounded screen, but 0180 still reaches 138.400: an exempt operation carrying no withholding is banked at exactly its base, so the same missing field costs this taxpayer nothing on this invoice and costs them the withheld amount twice over on a withheld one. Claiming a shortfall here would be claiming a number the scenario does not produce, so the module says so instead.

### Files

- `src/cadrumo/domain/calculations/registry/tests/test_ledger_income_chain_aeat_exempt_worked_example.py` (new, 8 gates).
- `src/cadrumo/_data/corpus/manual_oracles/modelo-100-2024-estimacion-directa-simplificada.json`: `expected_by_casilla_id` gains `"0180": "138400.00"`, quoted from the manual's own valores-fiscales "Total ingresos" row; notes record the anchors and the chain it grounds.
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/verification_expectations/0003-reconcile-when-present.toml`: `0180` added to `externally_grounded_casilla_ids` (already present in `reconcile_when_present_casilla_ids`, and `input_kind = "computed"`, so both honesty directions hold).
- `src/cadrumo/application/aggregation/__init__.py`: `aggregate_renta_m100_income_ledger` promoted to the package facade, a precondition of the consuming test rather than a follow-up.

Scope note: the step's declared scope is the registry tests directory. The three files outside it are what make the grounding a bundled claim rather than a local assertion, and they mirror exactly what the pre-existing 0226 grounding of this same example already does.

### Verification

Raw counts. New module alone: 8 passed, 0 failed, 0 skipped. With both oracle siblings, the honesty gate and the pre-existing 0226 module, serial (`-n 0`): 28 passed, 3 deselected by the unit-lane marker. Those 3 run green in the integration lane (`-m integration`): 3 passed. Whole `src/cadrumo/domain/calculations/registry/tests` package: 3589 passed, 0 failed. `ruff check`, `ruff format --check` and `ty check` clean on the touched Python files.

### Mutation proofs

Run in process by rebinding the function under test, so no broken state existed in the working tree at any point. Counts are out of the module's 8 gates.

- Resolver returns a constant regardless of what was aggregated: 1 red. **This mutation initially reddened NOTHING, and that is the finding.** The anti-tautology gate as first written nudged the already-RESOLVED binding value, so the mutation never reached the link the gate claimed to cover — a gate that looked like an anti-tautology check while excluding nothing. It was rewritten to add one euro to the INVOICE and re-run the whole chain from the ledger row upward, which is what makes it bite.
- One contributing observation silently dropped: 5 red.
- Ungrounded screen silenced: 1 red — the visibility half of the under-declaration direction is load-bearing rather than decorative.
- Banked cash folded instead of the declared base: 0 red HERE, and 2 of 7 red in the sibling exempt module. Measured, and recorded in the module docstring: this example is genuinely blind to the cash-versus-base substitution because its cash equals its base, which is exactly why the withheld sibling is not redundant with it.

## Follow-on: the bypass this step found, turned into a contract

Writing the second pass surfaced something bigger than the step. Casilla 0171 was being hand-typed by the pre-existing oracle for this same caso practico, and the question that followed was whether anything else did the same. It did. The remediation is a contract in the scenario runner rather than a one-off fix, and the sequence that produced it is worth recording because three of its four turning points were places where the obvious move was wrong.

### Counting before fixing changed the size of the finding by an order of magnitude

The first report named ONE bypassed binding. Measuring across the tree found NINE in that module alone: 0171 on the ledger-income binding, plus 0186, 0193, 0194, 0202, 0203, 0206, 0208 and 0217, each on a ledger-expense binding. So the module bypasses the gasto aggregation as thoroughly as the income one. Fixing the casilla in front of me would have closed the finding at a ninth of its true size and left the other eight reading as covered.

### The second module was mine

The module this step delivered inherited eight of those nine. Its gasto inputs were taken from the existing input map without checking `input_kind` - the same mistake, in the same file, one pass later. It is defensible as scoping: the step drives the INCOME leg through its binding and the expense aggregation is genuinely out of its scope. It was not, however, a deliberate choice at the time, and reporting it rather than quietly correcting it is what kept the finding honest.

### The static gate was built, measured, and rejected

The natural shape is a scan of the test tree for scenarios whose inputs include a bound casilla. Built first, then measured: it resolved thirteen of twenty-six scenario constructions. The remaining thirteen pass their inputs through factory parameters, and it reported them clean. Following factory parameters back to their call sites recovered one module and left thirteen blind.

A gate that resolves half its surface and reports the rest clean is the failure this project keeps finding - an instrument that lies about its own coverage, which is then trusted because nobody audits the scoreboard. It was not shipped, and the decision was vindicated immediately: a THIRD module, three archetype scenarios on the 2025 revision hand-typing 0171, sat squarely in the blind set and was caught only by the runner.

### Where the check went, and why two channels were needed

`run_registry_calculation_scenario` is the one point every scenario passes through, and it already holds the resolved revision beside the inputs, so the check there is exact and complete by construction.

One declaration field turned out to be provably wrong. The harness has a single channel for casilla values, so a value obtained by RUNNING the aggregation and the binding resolver arrives indistinguishable from one typed into a literal. With a single hand-typed field, this step's own module - which genuinely drives 0171 through the chain - would have had to declare it hand-typed, recording the exact opposite of what happened in the field a later reader would trust. Two opposite claims therefore carry two names, `hand_typed_bound_casillas` and `chain_resolved_bound_casillas`, and a casilla may satisfy exactly one.

Refusals run both directions: an undeclared bound input naming the casilla AND the binding stepped over; a declaration for a casilla the revision does not bind, which is a stale excuse outliving the binding it excused; a blank reason; a declaration for an input the scenario does not supply; and the same casilla filed under both channels. No central allowlist - the reason travels with the scenario, because a central list would drift from the scenarios exactly as the bypass drifted from the registry.

Corroboration that the discipline was already known and merely unenforced: the shared fixture module carried a hand-written comment noting that two other casillas are bound and must be supplied through the binding channel. Someone had applied the rule to two casillas and had no way to enforce it on the rest.

### Proofs, and two floors that had to be corrected

The contract redded on the real defects before any declaration existed: six failures across the two known modules, each naming all nine casillas, then three more from the module nobody knew about. That was the first test rather than a synthetic fixture, on the reasoning that a check which does not fire on a defect present right now is wrong whatever a constructed case says.

Anti-vacuity was built in two layers because the first layer was insufficient. The registry-surface floors pin that bound casillas exist at scale - measured at 34 revisions across 19 modelos, floors set at 20 and 10. Those floors would all stay satisfied if scenarios were routed around the runner entirely, so a second pair pins the SCENARIO population: at least twenty constructions spanning at least four revisions, and every module that builds a scenario either calls the runner or is imported by a module that does. The reachability form avoids naming the one legitimate builder-without-runner in an allowlist.

Two floors were corrected against measurement rather than argued. An initial guess of ten M100 revisions carrying bound casillas was wrong (six), so the scan was widened tree-wide instead of the floor being lowered to fit. And a modelo-span floor for the scenario population is NOT available: all twenty-six constructions target Modelo 100. The revision span stands in, and the absence is recorded in the module so the stronger check can replace it if the harness ever grows a second modelo.

The gate was then mutation-proved against itself, since the checking instrument attracts the least scrutiny. Disabling the runner check reddens three of its gates; emptying the bound set reddens three; the bound surface vanishing everywhere reddens four including the anti-vacuity floor; emptying the scenario population reddens both routing floors, as does a builder unreachable from any runner. Baseline and every restore clean.

### Files, and what stays open

- `src/cadrumo/domain/calculations/registry/_scenarios.py`: the two declaration fields, their model-level validators, and the runner-side refusal invoked once the snapshot resolves.
- `src/cadrumo/domain/calculations/registry/tests/test_scenario_bound_input_declaration.py`: new, 11 gates.
- `test_m100_2024_estimacion_directa_manual_worked_example.py`, `test_ledger_income_chain_aeat_exempt_worked_example.py` and `_registry_scenarios_support.py`: declarations with per-casilla reasons naming what each scenario isolates and why the bound leg is outside it.

Full registry package 3600 passed, 0 failed. ruff, ruff format and ty clean on every touched file.

Open, and the larger half: NO scenario anywhere drives the ledger-EXPENSE aggregation into its bound casillas. Eight bound expense casillas are hand-typed wherever they appear. The income leg now has coverage and the expense leg has none - stated in code now rather than invisible, which is the most this pass could honestly deliver.
