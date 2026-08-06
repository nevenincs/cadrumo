---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:d067bd229c1c9e14c9597a4c0797ada0b8ffd3987c261547d9ba6170c42f62e2'
step_id: 'S08'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Decide and implement the fold rule per unmigratable-record class, covering the empty counterparty_name, the null country_code, the totals that do not reconcile, the absent line concept and the bare Decimal iva_rate against the closed IvaRate enum, stating per class whether the fold synthesises, refuses or quarantines and never silently coercing a value the source record did not hold

## Scope

- `src/cadrumo/application/invoices/_creation.py`

## Description

- Re-read the plan's own whole-plan gate before implementing, which changed what this Step had to build.
- Stated the outcome for each unmigratable class and proved it, one test per class, each constructing the shape that is legal on the slim side.
- Built every case from one validating baseline and added an anti-tautology control on that baseline.
- Corrected one stated rule to match the invariant the tree actually enforces, rather than adjusting the tree to match the plan.
- Added a positive control bounding the single permissive class.

## Outcome

**No migration code was written, and that is the Step's main design finding rather than an omission.**

The Step reads as though it needs a conversion routine — "stating per class whether the fold synthesises, refuses or quarantines". The plan's own whole-plan gate settles it the other way: the regime is pre-release, there is no released data, and no data migration is written. The fold is the operator re-entering records through the canonical verbs, not an automated rewrite.

So for almost every class the rule and its enforcement are the same thing: the canonical model **refuses the shape, loudly and by name, when the record is offered**. Enforcing this as an invariant rather than as conversion code is strictly more durable — there is no migration path that could later acquire a silent coercion, because there is no migration path.

The rules, and why each is the honest one:

- **Empty counterparty name — refuse.** Declared on M347. The only alternatives are inventing a name or filing a blank one, and both put a value into a return nobody observed.
- **Missing country — refuse.** Deliberately NOT derived from the tax-id prefix. The canonical rule is that a non-domestic country forces the tax id to be that country's NIF-IVA, so deriving one from the other would make the two agree by construction and destroy the cross-check that catches a wrong pairing.
- **Non-reconciling totals — refuse.** The most consequential. Adjusting the total to the lines or the lines to the total silently files a number the document did not state, and a record whose own arithmetic disagrees is evidence of an upstream error the fold cannot adjudicate.
- **No line concept — refuse the payload; the writer supplies a line.** Both halves are true and the distinction is load-bearing. The synthesised line carries exactly the base and cuota the slim record already held, so it is a representation change, not a value change. That is why this is the one class where supplying something beats refusing.
- **Rate outside the closed enum — refuse, never round.** The enum omits the transient 5% rate, so a pre-2025 document is precisely the case that must refuse. Rounding to the nearest member, or letting an unread rate fall to the exempt slot, mints a zero-cuota invoice whose printed total still shows the cuota charged.
- **Tax-id/country mismatch — refuse.** A class the original inventory did not name, because it is invisible to a field-list comparison: both stores carry both fields and the incompatibility lives entirely in the cross-field rule only one side has.
- **Factura simplificada — accept, bounded.**

**One rule came back sharper than assumed, and the test was corrected to match the tree rather than the reverse.** The simplificada acceptance is not blanket tolerance of a null tax id: the model permits the omission only on an invoice explicitly declared SIMPLIFICADA **and ISSUED**, because on a RECEIVED invoice that same field names the issuer's own identity and stays mandatory. A positive control now pins the refusal on the received side, so the acceptance cannot be read as "canonical tolerates a missing tax id" — a reading that would make the fold look safe for a population it in fact refuses.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_fold_record_classes.py -n 0 -q --no-header
    9 passed in 12.23s

    uv run --no-sync ruff check src/cadrumo/application/invoices/tests/test_fold_record_classes.py
    All checks passed!

The RED that corrected the simplificada rule is quoted, because it is what distinguishes the rule the tree enforces from the one this Step first assumed:

    Value error, counterparty_tax_id is required unless invoice_class is
    SIMPLIFICADA and kind is ISSUED; on a RECEIVED invoice it names the
    issuer's own identity, which stays mandatory

Every case is constructed from one baseline payload that is asserted to validate. Without that control each refusal could pass on an unrelated invariant while appearing to prove the class it names.

## Notes

**Two classes in this module were not in the Step's original list**, and both came from measurements taken earlier in this phase rather than from the plan: the tax-id/country mismatch, and the factura simplificada. Neither is discoverable by comparing field lists, which is the reason the capability inventory was rescoped to defaults and nullability.

**The apidocs drift gate is red and none of it is this campaign's.** It reports 11 missing stubs, 3 orphans and 8 stale, all for peer modules — the e-invoice parser package and adjacent work. This Step adds only a test module, which is not stubbed. The regeneration command was deliberately NOT run: it sweeps the whole module tree and would stage peer modules' stubs into this campaign's commit. Recorded so a later reader does not attribute the drift here, and does not "fix" it by sweeping.
