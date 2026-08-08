---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b9117acae730e202692eb0f63d463c92716cbcaed74130ef45c5242f541cfacd'
step_id: 'S201'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Make both preflight issue mappings total by construction against IvaLedgerAggregationIssueReason so a new enum member cannot ship unmapped, since two lanes renamed members of this one enum in a day and the first failure masked the second entirely

## Scope

- `src/cadrumo/application/ledger/_preflight.py`

## Description

- Lift both preflight translation dicts out of their function bodies into module-level `_PREFLIGHT_REASON_BY_IVA_ISSUE` and `_PREFLIGHT_DETAIL_BY_IVA_ISSUE` constants, leaving the lookups as bare subscripts.
- Add `_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT`, the counterpart half of the partition, recording for each remaining enum member the reason preflight cannot receive it.
- Derive the missing-fact screen's emissions from a field-to-reason table in `_iva_ledger.py` and publish the derived `IVA_LEDGER_MISSING_FACT_REASONS`, so the emission set cannot drift from the screen.
- Declare `IVA_LEDGER_COUNTERPARTY_GATE_REASONS` for the counterparty screen, whose three branches read three different legal facts and do not collapse into a table.
- Promote both constants through the aggregation package facade.
- Add the partition gate, including an emission-parity assertion that exercises the shipped screens rather than restating their branches.

## Outcome

Both mappings are now total by construction over a **declared partition of the enum**, not over an implicit set. The bare subscript is kept deliberately: an arriving reason that is absent still raises rather than resolving to a wrong operator sentence, and the gate is what stops that raise from ever being reachable.

The gate is a property, not a tally. It asserts the mapped set and the not-reaching set are disjoint, contain nothing outside the enum, and together cover it exactly, so it bites on an added member whatever the member count is.

Emission parity is what keeps the two declared sets honest. Without it they would be hand-lists asserting themselves: a screen that starts emitting a newly added reason would satisfy every coverage assertion while still reaching preflight unmapped. The parity test drives the real screens across the category and member-state matrix and compares observed emissions to the declarations.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m unit -k preflight
    41 passed, 1076 deselected in 5.36s

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests -n0 -q -m unit -k "iva_ledger or shared_issue"
    49 passed, 786 deselected in 15.29s

    uv run --no-sync ruff check <four touched files>
    All checks passed!

    uv run --no-sync ty check <four touched files>
    All checks passed!

That is the `unit` lane only.

### The gate reds on purpose

Two mutations, both applied from a pytest plugin held outside the repository, so no tracked file entered a mutated state.

Mutation one adds a real member to the live enum, the exact defect shape:

    [mutation-plugin] RUNG 1: plugin loaded
    [mutation-plugin] RUNG 2: patch reached, invocations=1
    [mutation-plugin] RUNG 3: observable state change, set(E) grew by ['MUTATION_PROBE_REASON'] (20 -> 21)
    1 failed, 6 passed

The failure is the coverage assertion and only that one, naming the unclassified member. The other six stayed green legitimately: they are about disjointness, staleness, rationale text and emission parity, none of which an unclassified member disturbs.

Mutation two rebinds the counterparty screen so one branch emits an undeclared reason:

    [d5-plugin] RUNG 3: observable state change -- screen invoked 180 times, 12 emissions diverted to an undeclared reason
    1 failed, 6 passed

The failure is the emission-parity assertion and only that one. Adding a member was preferred to deleting one throughout: a deletion crashes production import and reds by collection error, which proves far less than a targeted red.

## Notes

The production half of this change reached HEAD through a peer's blanket sweeper commit while this lane was still working; only the gate was committed by this lane, as `98d0da5aa7485313f7dcc87414b67db3bef2d7e4`.

`src/cadrumo/tests/test_import_hygiene_gate.py` is red at HEAD with eight undocumented test-only private reaches, none of them from this lane's file — they name the llm client, the invoice source resolver, the iva classification rules and the registry loader. Left for their owners.

The originating S200 row is deliberately NOT closed by this lane. Its stated deliverable, mapping `UNSUPPORTED_IVA_RATE` into both mappings, was found to rest on a false premise and was not performed; the member is classified on the not-reaching side of the partition instead, with its rationale recorded. That judgement is escalated rather than taken silently.
