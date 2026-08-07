---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4dab74f9fdab986840e79382ceb84db32482b1e2bd6675ccb6a8794a99190f8a'
step_id: 'S29'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# restore the Modelo 303 filed-observation carry after a peer commit read a generated attribute the derivation never declared, adding the refunded-aware generated component to M303CompensationAvailableDerivation so available equals posterior plus generated on every basis, and repairing the posterior-absent fallback that silently dropped a declared negative resultado's credit to zero, verified by the 13 restored capture tests plus an out-of-tree mutation zeroing generated while leaving available correct

## Scope

- `src/cadrumo/domain/iva_compensation/_filed_derivation.py`
- `src/cadrumo/application/calculations/_iva_compensation_history.py`

## Description

- Add the refunded-aware `generated` component to `M303CompensationAvailableDerivation`, populated on all three branches, so `available == posterior + generated` holds universally including the refunded case.
- Read the generated component back out of the pure carry policy's answer on the resultado basis rather than re-implementing `max(0, -resultado)` a second time.
- Repair the posterior-absent fallback in the filed-history projection, routing it through the same pure policy with the absent posterior read as zero.
- Bind four Modelo 303 compensation casilla tokens in the calculations vocabulary module to the domain policy's declarations, removing a twin declaration.
- Re-point the vocabulary identity gate at the drift property rather than an import inventory.
- Suppress the deliberate missing-argument call for the canonical type checker, which reported it as a real error.

## Outcome

### The defect, and why it was urgent

A peer commit routed the filed-history projection through the canonical refunded-aware derivation, replacing an inline `max(0, -resultado)`, and read a `generated` attribute the derivation never declared. Every Modelo 303 filed-observation persistence raised `AttributeError`, taking 13 capture tests with it.

The commit landed at 22:39:02 on 2026-08-07. A live Cl@ve-authenticated AEAT pull had been proven working nine minutes earlier at 22:30 local, capturing two declaraciones, 158 casillas and six artefacts into encrypted storage. So this was a regression on the campaign's critical path, not a latent defect.

### The correct semantics, and what establishes them

Not a conditional on `basis` — a missing field. The accepted carry-reconciliation decision record rules that when a period's negative result is requested as devolución, the generated component is zero and the available carry is the posterior only, on the legal basis of RD 1624/1992 art. 30 and Ley 37/1992 art. 116: a refunded credit is returned, not carried. That makes `generated` a real term in a decomposition rather than a renamed field.

`generated` belongs on the derivation rather than in the caller because the disposition governs BOTH numbers, and both are written into one period state by one constructor. A caller that reads `available` from the derivation and computes the generated credit itself gets the refunded case right in one field and wrong in the other, producing a record that is internally inconsistent rather than uniformly wrong — and nothing downstream can then tell which field to believe. That is the reasoning the originating commit stated and did not finish.

On the resultado basis the component is derived as the policy's answer minus the posterior. A second implementation of `max(0, -resultado)` and its refunded zeroing is how the two halves would drift apart on the next regulatory change to the conversion.

### The posterior-absent decision

The derivation returns nothing when a filing declares no `iva.compensacion-pendiente-periodos-posteriores`, because its two AEAT-fetched callers read that as "do not stamp the availability casilla at all". The filed-history projection has no such choice to make: both amount fields of the period state are non-optional.

So between the originating commit and this repair, a filing that declared a negative resultado without that casilla silently dropped its generated credit to zero. That under-states the carry, which over-taxes the taxpayer one period later — the direction none of this apparatus watches, since every gate here is built against under-declaration.

The repair reads an absent posterior as the zero it means and routes through the same pure policy, restoring the figure the inline implementation produced before the regression. This is a caller-side reading that no decision record rules on, and it is the one genuinely unratified judgment in this Step: an absent casilla could mean "declared zero" or "not applicable", and reading it backwards would re-create the over-taxation in a different shape. Flagged for owner ratification rather than treated as settled.

### The second break, and why the gate changed rather than the import

A vocabulary identity gate went red because the originating commit dropped an import the gate asserted as an inventory. Re-adding one import would have cleared it and taught nothing. Investigating instead exposed a duplication the gate had never been able to see: the domain carry policy held its own validated twins of four of those casilla tokens, so a rename could be applied to one side and silently leave the other resolving — precisely the drift the vocabulary module exists to end, one layer further down.

The four are now bound to the domain declarations, on the principle that a policy deciding a casilla's value owns that casilla's identity. The gate now asserts that any module naming an authority token holds the authority's object, and stays silent about a module that simply does not name one. That is strictly more coverage: an inventory asserts something the code is free to change for good reasons, while the property catches the twin declarations the inventory missed.

One blind spot is documented in the gate rather than papered over: CPython interns short string literals, so identity cannot discriminate a twin declaration of the bare-numeric token. That limitation applied equally to the previous form of the gate.

### Commits

The change is split across four commits with three different subjects, because a broad-commit agent swept this working tree into HEAD mid-verification. `13eebf1247` carries the core semantics — the `generated` field, its documentation and the posterior-absent repair — under the subject "land the in-flight source work", which names none of it. `9ad1e31b6d` carries the formatter delta that sweep preceded. `c8a03e129c` carries the vocabulary rebinding and the gate rewrite. `94970bc8d3` carries the type-checker suppression. A reader following `git log` on the derivation module will not reach the legal grounding from any of those four subjects, which is why this record exists.

Attribution was confirmed with a pickaxe search for the added field on the derivation module, returning exactly one commit whose added lines are this Step's authored prose verbatim.

## Verification

The red, before the fix:

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -n0 -q
    13 failed, 26 passed in 118.48s (0:01:58)

Green after, across the restored capture tests, the derivation policy tests and the two new gates:

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py src/cadrumo/domain/iva_compensation/tests src/cadrumo/application/calculations/tests/test_iva_compensation_filed_observations.py src/cadrumo/application/calculations/tests/test_iva_compensation_casillas.py src/cadrumo/application/calculations/tests/test_binding_prefill.py -n0 -q
    116 passed in 49.74s

Confirmed again at the committed tree:

    uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_iva_compensation_casillas.py src/cadrumo/application/calculations/tests/test_binding_prefill.py src/cadrumo/application/calculations/tests/test_iva_compensation_filed_observations.py src/cadrumo/domain/iva_compensation/tests -n0 -q
    71 passed in 20.21s

Linters and the canonical type checker on both touched packages:

    uv run --no-sync ruff check src/cadrumo/domain/iva_compensation src/cadrumo/application/calculations
    All checks passed!

    uv run --no-sync ruff format --check src/cadrumo/domain/iva_compensation src/cadrumo/application/calculations
    130 files already formatted

    uv run --no-sync ty check src/cadrumo/domain/iva_compensation src/cadrumo/application/calculations
    All checks passed!

### Mutation proof

Every mutation was applied by a pytest plugin loaded from a scratchpad directory outside the repository, so nothing under the source tree changed and no residue could survive a crash. Every run passed `-n0` explicitly, because the project's default options inject parallel workers and a mutation applied in the controlling session never reaches a worker — which would make the proof vacuous while reading green.

Zeroing `generated` while leaving `available` correct, the exact half-fix shape the defect would have produced:

    CARRY_MUTATION=drop_generated uv run --no-sync pytest src/cadrumo/domain/iva_compensation/tests/test_filed_derivation_disposition.py src/cadrumo/application/calculations/tests/test_iva_compensation_filed_observations.py -n0 -q -p mutate_carry
    5 failed, 17 passed in 13.40s

The same mutation against the restored capture tests:

    CARRY_MUTATION=drop_generated uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -n0 -q -p mutate_carry
    1 failed, 42 passed in 37.16s

Zeroing the pure policy the posterior-absent fallback calls, which is the pre-repair behaviour for a filing declaring no posterior casilla:

    CARRY_MUTATION=zero_posterior_absent_policy uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_iva_compensation_filed_observations.py -n0 -q -p mutate_carry
    1 failed, 11 passed in 22.99s

Control, with the plugin loaded and no mutation selected, proving the plugin itself is not the cause of any red above:

    uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_iva_compensation_filed_observations.py src/cadrumo/domain/iva_compensation/tests -n0 -q -p mutate_carry
    46 passed in 16.42s

## Notes

**One open domain question, not resolved here.** Reading an absent posterior casilla as zero restores the pre-regression figure and is the reading this Step implements, but no decision record rules on it. An absent casilla could mean "declared zero" or "not applicable", and the wrong reading re-creates the over-taxation in a different shape. Ratification belongs to whoever owns the compensación figure, not to a code review, which can verify the arithmetic holds and that the record says what is claimed but cannot ratify a tax figure.

**Unowned semantics.** The core semantics reached the tree through another agent's broad sweep commit rather than through an owning-campaign decision, so nobody from the campaign that introduced the defect has ratified them. They rest on the accepted decision record's ruling, which is grounding, not on an owner's sign-off.

**Peer-owned reds triaged and deliberately untouched.** Sixteen registry-validation failures refusing snapshot build for two bindings that exist nowhere in a clean registry tree: one Modelo 303 transitional reducido cuota binding and one Modelo 131 agrarian volume binding. Both are committed authoring gaps, not working-tree churn — the registry tree was clean against HEAD when measured. Separately, three import-hygiene failures naming an aggregation test reaching a registry loader's private module for a tree-loading function, undocumented in the test-debt inventory. None is caused by this Step's diff and none was patched.

**Shared-tree incident.** A broad-commit agent swept this working tree into HEAD mid-verification, splitting one atomic change across four commits and landing the core semantics under a subject naming none of them. The same sweep captured the change before its formatter pass, leaving the tree lint-red on an unsorted import block until a follow-up commit. Downstream, two agents and the coordinator read the swept result as the owning campaign fixing its own break, which produced a stand-down instruction issued against work that had already landed. A pickaxe search on the added field settled attribution in under a minute; a report from an agent did not.

**A prior suppression was checker-specific.** The test proving the refund disposition cannot be forgotten omits the argument deliberately and carried only a suppression for a checker this project does not run in CI, so the canonical checker reported it as a real error and the domain package would not type-check. Suppressed for the canonical checker with the reason stated inline.
