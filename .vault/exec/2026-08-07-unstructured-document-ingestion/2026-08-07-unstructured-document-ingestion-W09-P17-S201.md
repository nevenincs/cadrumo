---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b29add02dad71819361637294aca8c5cccaa7be86e551460a4c6cfceef464945'
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
- Enforce the partition at module import, matching the placement and message shape of the discrepancy-kind guard in `_confirmation_gate.py`, so an unclassified member fails the import rather than one test run.
- Keep as tests only what an import-time check cannot carry: emission parity against the shipped screens, the rationale-text requirement, and the proof that the import itself refuses.

## Outcome

Both mappings are now total by construction over a **declared partition of the enum**, not over an implicit set. The bare subscript is kept deliberately: an arriving reason that is absent still raises rather than resolving to a wrong operator sentence, and the gate is what stops that raise from ever being reachable.

The check is a property, not a tally: mapped and not-reaching are disjoint, contain nothing outside the enum, and together cover it exactly, so it bites on an added member whatever the member count is.

Placement follows the shipped precedent rather than inventing a second one. The sibling guard one module over fails its import when a discrepancy kind is unmapped, and its axis absorbed two independent misses in one week that both reached a test run instead of an import failure. The same argument applies here, so the check moved to import time.

What differs from that sibling is the shape of the classification, and only because the axes differ. It maps one enum onto one target with no second side, because every discrepancy kind is a real defect its single consumer acts on. This enum has two consumers with different reach: the projection path raises all twenty members, preflight runs two screens and never enters the rest. Thirteen members have no preflight counterpart, and inventing one would ship an operator-facing message for a condition this layer cannot detect. Its docstring is right that an exemption row is the worse shape where severity is a product choice; here the second side records a structural fact about which path can emit what, which omission cannot express. The honest alternative is splitting the enum so preflight's consumer sees only its own reach, which is a cross-surface refactor of the aggregation package and not this module's to make.

Emission parity is what keeps the two declared sets honest. Without it they would be hand-lists asserting themselves: a screen that starts emitting a newly added reason would satisfy every coverage assertion while still reaching preflight unmapped. The parity test drives the real screens across the category and member-state matrix and compares observed emissions to the declarations.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m unit -k preflight
    38 passed, 1085 deselected in 5.87s

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests -n0 -q -m unit -k "iva_ledger or shared_issue"
    49 passed, 786 deselected in 15.29s

    uv run --no-sync ruff check <four touched files>
    All checks passed!

    uv run --no-sync ty check <four touched files>
    All checks passed!

That is the `unit` lane only.

### The guard reds on purpose

The mutation proof is now permanent rather than a one-off: adding a real member to the live enum and re-executing the shipped module source is a test that runs every suite run, paired with a positive control proving the same load succeeds unmutated. A guard that always fires is not a guard, and without the control the refusal would be consistent with a module that simply cannot load.

Adding a member is preferred to deleting one throughout: a deletion crashes production import through a missing attribute and reds on a signature saying nothing about this guard.

The guard itself was then neutralised from a pytest plugin held outside the repository, which rewrites the shipped source into a temporary copy with the guard block stripped and repoints the module's file attribute at it, so no tracked file entered a mutated state:

    [neutralise-plugin] RUNG 1: plugin loaded
    [neutralise-plugin] RUNG 2: guard block removed, blocks_removed=1
    [neutralise-plugin] RUNG 3: observable state change -- source shrank 32131 -> 31503 chars
    1 failed, 3 passed

The failure is the import-refusal proof and only that one. The other three stayed green legitimately: the positive control still loads the module, and emission parity and the rationale-text requirement are untouched by removing the partition guard.

Earlier, against the pre-adoption test-time shape, two further out-of-repo mutations each reddened exactly one assertion: adding an enum member (set grew 20 to 21) reddened the coverage assertion, and diverting twelve counterparty emissions to an undeclared reason reddened the emission-parity assertion.

## Notes

The production half of this change reached HEAD twice through peers' blanket sweeper commits while this lane was still working, `24267e3167` and then `77fd9393e7` for the import guard. Only the tests were committed by this lane, as `98d0da5aa7485313f7dcc87414b67db3bef2d7e4` and `68335c0867acbae92ffd4448dd71c09607d1ae0c`. Landed content was verified through `git show HEAD:<path>` rather than trusted to the sweep.

`src/cadrumo/tests/test_import_hygiene_gate.py` is red at HEAD with eight undocumented test-only private reaches, none of them from this lane's file — they name the llm client, the invoice source resolver, the iva classification rules and the registry loader. Left for their owners.

The originating S200 row is deliberately NOT closed by this lane. Its stated deliverable, mapping `UNSUPPORTED_IVA_RATE` into both mappings, was found to rest on a false premise and was not performed; the member is classified on the not-reaching side of the partition instead, with its rationale recorded. That judgement is escalated rather than taken silently.
