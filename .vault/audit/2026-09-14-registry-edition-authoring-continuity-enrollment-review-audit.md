---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:79aeecb8b221e8801273782c460553d4e3c88cab0cb75d488a56d79dd72e0b53'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
---
# `registry-edition-authoring` audit: `Continuity amendment and enrollment gates`

## Scope

Read-only review of the accepted edition-authoring decision including its approved structural-succession amendment, the implementation plan, the paired-source Modelo 309 research and the code-shape reference. Examined typed split/merge declarations, materialization and identity guards, lifecycle/origin/reference validators, semantic-role representation composition, Modelo 309 relationship declarations, and replacement packing and lineage-debt detector gates. No Modelo 100 data adjudication, publication, plan modification or production fix belongs to this review.

Independent focused run of the four reviewed test modules collected 63 cases: 62 passed and one failed in 24.71 seconds, exit 1. The live ledger gate reported stale refusals and newly uncovered Modelo 100 rows while that model remained under active authorship; this is an honest unresolved corpus signal, not an implementation finding or permission to weaken the gate. The packing gate and all structural, formula-supersession and planted-defect controls passed. This run is not a whole-authority or export-byte proof.

## Findings

### inherited-formula-identity | high | Unchanged inherited formulas can silently bind to a structural successor identity

Open. `dev/registry/compiler/_loader_internals.py:260` calls the casilla identity guard only when an inherited keyed member has a stated superseder. The unchanged-member branch appends the predecessor formula without comparing the target's predecessor and successor identities. An isolated real directory-loader fixture declares a 2024 formula targeting `0001` on lineage `combined`; a 2025 delta declares a split from `combined` into `surname` and `given`, reusing `0001` for `surname`, and does not restate the formula. Loading succeeds and the inherited formula still targets `0001`, now a different identity. All structural endpoint/lifecycle checks accept this otherwise valid split. The amendment expressly denies formula inheritance across different structural identities; checking only explicitly restated formulas leaves the omitted/inherited case unprotected. The current four formula identity tests all restate the formula and therefore miss this path.

### endpoint-evidence-scope | high | Structural relationship citations are not checked against the endpoint they claim to ground

Open. `dev/registry/compiler/_validate_revision_closure.py:113` checks that relation references exist and that each endpoint list includes an allowed evidence tier, but does not test endpoint applicability. Swapping `from_source_refs` and `to_source_refs` on all three committed Modelo 309 relationships returns no structural failures and no revision-reference-surface failures. The catalogue states `aeat-dr-309-2004` applies from 2004-01-01 through 2015-12-31 and `aeat-dr-309-2016` applies from 2016-01-01 through 2017-12-31. Thus the source endpoint can claim the design applicable only to the target interval and vice versa without refusal. This is an applicability/endpoint closure issue, not a requirement that sources have identical publication dates, disjoint references or edition-specific names. The live authored citations are correctly oriented; the validator does not protect that property.

### original-findings-recheck | low | Original target identity and endpoint evidence counterexamples are closed

Closed on independent re-review. The unchanged keyed-member branch now invokes the identity guard, and the original split-child target probe fails with the expected typed repurpose refusal. Structural source closure now receives the owning modelo, requires independent modelo/endpoint enrollment, checks the canonical source applicability overlap and checks explicit filing-period overlap. The original reversed-citation probe produces six endpoint-validity refusals. Correctly oriented and legitimately multi-edition sources remain accepted; unrelated-modelo and wrong-period detector cases refuse. Independent focused execution of `test_casilla_structural_succession.py` and `test_restated_family_merge.py` passed all 47 collected tests in 5.07 seconds, exit 0. This closes the two original counterexamples, not the additional operand path below. Six wider regression failures in older binding fixture setup were reported by the implementation owner and are not claimed passed by this review.

### inherited-formula-operand | high | An inherited formula can read a different structural identity through a reused operand identifier

Open. The target identity guard does not inspect expression operands. A second isolated real-loader fixture keeps formula target `0003` on stable lineage `total` and gives the predecessor formula `expression = { casilla_id = "0001" }`. A successor split withdraws lineage `combined` and reuses its local identifier `0001` for new lineage `surname`; the formula is omitted and therefore inherited unchanged. Loading succeeds, the target remains `total`, and the inherited operand now reads `surname` instead of `combined`. This silently transfers calculation semantics across distinct structural identities even though the newly added target guard passes. No formula retirement or successor-authored replacement expression exists in this fixture. Formula operands must retain their referenced identity when the formula is carried unchanged; they are not equivalent to the formula's own stable target identity.

### operand-remediation-recheck | high | Raw expression comparison still permits a default-only restatement bypass

The initial operand remediation refuses the original omitted-operand fixture and walks nested references through the canonical typed expression walker. Independent focused execution passed 53 tests in 6.35 seconds, exit 0. The operand finding remains open because the helper exempts a changed raw mapping before typed comparison: predecessor `{ casilla_id = "0001" }` and successor `{ casilla_id = "0001", args = [] }` validate to equal `FormulaExpression` objects, yet the explicit empty default makes the raw mappings differ and the guard returns without comparing the reused operand's identity. This is not a changed calculation. Compare typed expressions before granting the explicit-change exemption and add a default-only restatement refusal control.

### operand-final-recheck | low | Operand finding and default-only restatement bypass are closed

Closed on final independent re-review. Both expression mappings are now normalized into `FormulaExpression` before the change exemption is considered. The exact `{ casilla_id = "0001", args = [] }` counterexample remains typed-equal to its predecessor and now produces the expected typed operand-identity refusal. The original omitted-operand probe also refuses, without rewriting references or values. Direct and nested identical superseders, including explicit-default representations, are covered by negative controls; stable operands and explicitly changed successor expressions retain positive controls. Independent focused execution passed all 55 collected tests, exit 0. No open implementation finding remains in this bounded review. This closes neither the separately reported wider fixture failures nor outstanding corpus, export-byte, authority, packaging or publication proof obligations.

## Recommendations

- For `inherited-formula-identity`, validate the casilla identity of unchanged inherited members as well as superseders before accepting the materialized family. Exercise omitted formulas across a valid structural split or merge with a reused local identifier, alongside an unchanged same-chain control. Inspect equivalent casilla-addressed binding/declaration paths for the same omission. Refuse or require explicit appropriate retirement/replacement; never silently drop or reinterpret the formula.
- For `endpoint-evidence-scope`, validate official endpoint references against the exact source and target revision context using catalogue applicability and the existing endpoint/source closure contracts. Accept legitimate sources spanning several editions or published outside the covered interval; reject reversed, foreign and inapplicable endpoint citations. Add negative tests using real catalogue applicability rather than only unknown identifiers or empty arrays.
- Retain the replacement ledger gate's distinction between named debt and grounded continuity. Reconcile stale exceptions only after the owning source adjudications settle; a covered unresolved row remains debt and does not authorize publication.
- For `inherited-formula-operand`, check casilla-addressed expression operands in unchanged inherited formulas against predecessor and successor identity resolution, including nested operands. Preserve the distinction between inherited unchanged formulas and explicitly authored successor expressions: ordinary successor calculation changes must remain expressible. Add a reused split-child operand refusal and a stable-operand control.

The two counterexamples were independently reproduced with the real loader and reference validators; no production files were changed for the probes. Approval of the narrow schema amendment is not acceptance of these missing enforcement paths.
