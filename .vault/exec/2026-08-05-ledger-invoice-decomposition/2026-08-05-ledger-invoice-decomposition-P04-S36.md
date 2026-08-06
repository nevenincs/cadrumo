---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:ede3edda4f330624902920e5009ce26ce6f02d599291f93c6e3fc73b9763eb68'
step_id: 'S36'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Decide whether the external-grounding gate admits bound casillas, since a bound value is as oracle-checkable as a computed one, before amending the S15 and S16 Step texts

## Scope

- `.vault/adr`

## Description

- Establish what the gate does today and whether it would refuse the Steps it precedes.
- Rule on the question and record it as an ADR decision rather than leaving it as a Step note.

## Outcome

Ruled as ADR decision D12: **the gate admits bound casillas, under one anti-tautology condition.**

MEASURED before ruling. `test_external_oracle_grounding_enrolled.py:61` is
`test_every_externally_grounded_casilla_is_computed_and_enrolled`, and the audit emits a
finding kind `oracle_casilla_not_computed`. So the gate requires COMPUTED and would strand
anything else.

That matters because casilla 01 on the ledger-income chain is BOUND, resolved by
`ledger_renta_income_aggregation`. The gate as written forbids grounding the very chain
S15 and S16 exist to ground — which is precisely why this Step precedes them.

The exclusion rested on an assumption worth naming: that a bound value is not
independently checkable because the test supplies its own substrate. That hazard is real,
but it is not what bound-versus-computed distinguishes. A computed casilla is equally
circular when its inputs are chosen to hit the target. A bound casilla is genuinely
checked when the binding — which fact, which selector, which aggregation op — must select
and fold real substrate to reach a figure the test did not choose. The binding is the
thing under test, exactly as the formula is for a computed one.

So the discriminator is not the casilla's kind but WHERE THE FIXTURE CAME FROM. A bound
casilla may be declared externally grounded when its fixture is authored from the worked
example's DESCRIBED FACTS — the operations, amounts and dates the AEAT example states —
and never from its RESULT.

## Verification

The ruling is a decision record, so its verification is that the premise was measured
rather than assumed:

```
rg -n "def test_every_externally_grounded_casilla_is_computed_and_enrolled"    src/cadrumo/domain/calculations/registry/tests/test_external_oracle_grounding_enrolled.py
61: def test_every_externally_grounded_casilla_is_computed_and_enrolled() -> None:
```

The gate's own finding kinds (`oracle_casilla_not_computed`) confirm the computed-only
requirement, and `_external_grounding.py:16` confirms it fires when a revision declares a
grounded casilla the engine does not compute.

The gate amendment itself is implementation work for whoever lands S15/S16, and the
condition above is what their fixtures must satisfy.

## Notes

**This Step existed because a gate can be right in intent and wrong in its proxy.** The
gate's purpose — a declared grounding claim must be backed by a real oracle figure the
engine independently reproduces — is correct and unchanged. Only its test for that was
wrong: "is the casilla computed" was standing in for "is the reproduction independent",
and those come apart exactly where this campaign needed them to.

The anti-tautology burden does not disappear; it moves onto fixture provenance, which the
oracle's own `raw_evidence_locator` already anchors. A grounding claim whose fixture
cannot be traced to described facts in the cited example is the real failure, and
`no-tautological-calculation-tests` already forbids it. D12 neither weakens nor restates
that rule.

**Ruled by the coordinator rather than deferred.** This was reported to the operator as a
blocker several times before being recognised as an ordinary architecture decision the
swarm-orchestration rule places with the coordinator, who adjudicates and persists
decisions in the vault. Reporting it as operator-blocked kept two implementable Steps
parked behind a decision nobody needed to make.
