---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:4e0cae22d88927c99d77a3c52965797fbb0d95f354a70afe7342d616ca62f1fc'
step_id: 'S24'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Prove each cross-domain assertion fails when the code is wrong, by mutating the decomposition and confirming the scenario reddens rather than passing vacuously

## Scope

- `src/cadrumo/application/aggregation/tests`

## Description

- Express the cross-domain reconciliation as returned data rather than bare assertions so it can be driven in both directions.
- Add four mutation tests, each feeding a decomposition wrong in exactly one place and asserting the checker names that break.
- Add the control asserting the checker is silent on the true decomposition.
- Run production-code mutations out of band and confirm the scenario reddens.

## Outcome

Landed with S23 in commit `c8bec3fff9`.

The reconciliation returns a tuple of violation strings instead of asserting inline. That shape is what makes non-vacuity provable: the live scenario asserts it finds nothing, four mutation tests assert it names exactly the break each introduced, and a control asserts it is silent on the correct figures. Without the control an always-empty checker passes every mutation test; without the mutation tests an always-full one passes the scenario. Neither half is sufficient alone, which is why both ship.

The four in-suite mutations: a disagreeing IVA base, a cuota that does not close the total, a withholding that does not close the cash, and an absent income base (which short-circuits and is reported as its own violation rather than crashing or silently skipping).

Production-code mutations, run out of band, each restored byte-exact and re-verified:

- Withholding inference always returns zero: 1 failed, 8 passed.
- Grounding marker always claims declared substrate: 2 failed, 7 passed.
- IVA missing-fact screen reports nothing: 1 failed, 8 passed.

Baseline before and after every mutation: 9 passed.

## Notes

The in-suite mutations act on the DATA, never by patching an aggregator. A monkeypatched pipeline is barred here and would in any case prove things about the patch rather than about the shipped path. The production-code mutations that genuinely break an aggregator therefore live out of band, in this record, and the module docstring says so explicitly so a later reader does not assume the in-suite set is the whole proof.

SAFETY CONSTRAINT ON WHICH FILES WERE MUTATED. The component-expectation module was dirty with a peer's in-flight legal-refs refactor at the time and was NOT mutated: a save-and-restore over live peer WIP risks destroying it if the process dies mid-run, and no proof is worth that. Only files clean at HEAD were touched, each verified byte-identical afterwards.

One red in the wider aggregation suite is a pre-existing order dependence in a peer module, not this work: it passes 12 of 12 in isolation and 21 of 21 when run together with this new module, so this module is not its cause.
