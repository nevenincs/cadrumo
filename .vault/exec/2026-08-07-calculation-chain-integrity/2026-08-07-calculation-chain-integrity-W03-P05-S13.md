---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d819128a77ac1373b9212a54d3b3a8413194a8ae2abf2a1c1820a8e6f57d369f'
step_id: 'S13'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S13

## Outcome

**Aggregated.** Modelo 131 casilla 05 is bound to the ledger, and both blockers this row recorded are closed rather than routed around.

The premise correction stands from the earlier pass and is worth restating, because it changes what was built: the agrarian quarterly volume is **casilla 05**, feeding the 2 % formula at casilla 06. Casilla 08 is retenciones e ingresos a cuenta. Casilla 01 is módulos-computed rendimientos, derived from signos and índices correctores, so no ledger sum could ever feed it — the pair that could genuinely double-count is `03` against `05`.

## Blocker one: the ledger can now mark what art. 110.1.c) excludes

`ConceptoIngreso` in `core` carries four members, and the reason it is four rather than two is the sentence the AEAT Modelo 131 instrucciones use for casilla 05:

> el volumen de ingresos del trimestre ... **incluidas las subvenciones corrientes y excluidas las subvenciones de capital y las indemnizaciones**

The distinction runs *inside* subsidies. A rule keyed on the word "subvención" gets exactly one of them wrong, and it is the inclusion that breaks — an operating subsidy silently dropped from a declared volume. `counts_toward_volumen_de_ingresos` is the single predicate, and the excluded set is declared twice on purpose (typed in `core`, grounded in the registry with its `legal_refs`) with a parity test binding them so they cannot drift.

An undeclared concept is **included**. That direction is chosen, not defaulted into: an unmarked receipt is far more likely to be ordinary income than exceptional, and reading silence as exclusion would drop real income out of a declared volume.

## Blocker two: the activity set, and why the mejillón question never arose

The earlier pass expected to need a legal determination on whether `B04 Producción de mejillón` falls inside art. 110's *pesqueras*. It does not arise, and the reason is the form rather than the article.

Art. 110.1.c) names *agrícolas, ganaderas, forestales o pesqueras*, but the bundled Modelo 131 instrucciones place the casilla-05 block under agrícolas, ganaderas y forestales and do not contain the word *pesquera* anywhere in the document. Modelo 131 is estimación objetiva and pesca is not in the módulos regime, so the article's wider wording covers a case this form cannot present. The selector is `A02, B01, B02, B03`, and neither pesquera code enters.

That is recorded in the parameter's own notes and asserted in a test, so a later reader who notices the article says *pesqueras* and "fixes" the selector meets the reason before the change.

The selector is also deliberately NOT the art. 95 agrícola/ganadera one. That set has no forestal code, so reusing it would have dropped a forestal filer's whole quarterly volume — a silent zero reintroduced by borrowing the nearest-looking authority.

## The aggregation, and its two opposite defaults

`aggregate_renta_m131_agrario_income_ledger` narrows rows before classification on two axes whose defaults point in **opposite** directions, each away from the worse error for its own axis:

- **Activity**: an undeclared `tipo_actividad` contributes nothing. Silence cannot mean agrarian, because routing an unmarked row into casilla 05 would move a non-agrarian filer's income into an agrarian box while the objetiva side of the same return already claims it. Under-filling a box the operator can complete by hand is recoverable; mis-routing income between two boxes of one return is not.
- **Concept**: an undeclared `concepto_ingreso` contributes everything, for the reason above.

The window is the quarter alone, not the Modelo 130 cumulative — art. 110.1.c) fixes the payment on *el volumen de ingresos del trimestre*.

Eight tests cover it, and every one is about a row that must NOT arrive, because the failure mode of an aggregation is silence: a dropped row leaves a smaller number and a smaller number looks correct. The mixed-catalogue test asserts the total rather than the count, so a partially-applied filter is visible.

## Canonicalisation, on the operator's directive

Three duplications were introduced during this work and all three are removed:

- **Two code-set parsers.** `_m131_agrarian_activity_codes` had its own comma-split; it now calls `tipo_actividad_code_set`, the one reader for `m036-tipo-actividad-code-set` parameters. A second parser is a second place the unit check and the unknown-token refusal drift.
- **Two projection loops.** The M100 and M131 aggregators wrote out the same lifecycle skip, classifier call and issue/observation split. Both now call `_project_income_onto_casilla`, which differs only in window, target casilla and an optional row filter.
- **Two activity classifiers.** `Art95ActivityPartition` was a four-member enum over the same article `IrpfActivityKind` already covers. It is **deleted**. The resolver now returns `IrpfActivityKind`, and the apartado-level detail stays on the registry parameters' `legal_refs` where it belongs rather than becoming a second public classifier that would have to be kept true.

That deletion turned out to be a gain, not just a subtraction. `IrpfActivityKind`'s docstring recorded the code-to-arm derivation as blocked for want of an input; a declared `tipo_actividad` is that input, so `irpf_activity_kind_for` closes it. The stale paragraph is retired in the same change — a docstring asserting a property the code no longer has is the same divergence the directive is aimed at.

## Verification

1946 tests across `domain/transactions`, `domain/deadlines`, `application/aggregation` and `core/tests` pass. The registry loads clean with casilla 05 `input_kind = "bound"` on all four revisions.

Two failures were seen and both were re-run in isolation and pass there: an AEAT-route-literal gate and the loader disk-cache isolation test. The second is worth recording rather than dismissing — a cold registry load measures **48.7 s** against that test's 60 s subprocess ceiling, so it is running within about 20 % of its limit and tips over whenever the box is loaded. That is a real fragility, it is not caused by the four small TOML files added here, and it will keep producing intermittent reds until either the load gets faster or the ceiling reflects the machine.
