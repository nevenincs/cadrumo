---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e8cee69596cb92ae534bd0d6442aa3f80d50fa7d923750defeae76ec7ca9818c'
step_id: 'S18'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Rename InvoiceLine.category_id to state what it is, first confirming whether the preflight site using category_id with the spending-taxonomy meaning shares a serialised key with it or is unrelated, and sweeping data consumers as well as callers

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

- Settled the homonym question first, as the Step required, before touching the field.
- Measured whether the field is read at all, which changed what the rename is FOR.
- Renamed the field and its validator, and recorded the field's real status at the declaration.
- Swept data consumers as well as callers.
- Corrected the categories package docstring, which asserted a coupling that does not exist.

## Outcome

**The homonym question resolves cleanly: they are homonyms, not a shared serialised key.** The Step warned that renaming on an unverified assumption of independence would break the preflight silently. It cannot: the invoice-line field has **zero production readers**, so it is not feeding the preflight, which reads the transaction/ledger field on an entirely different model. Nothing connects them.

**But the ambiguity worth fixing turned out to be closer to home than the preflight.** This aggregate already carries `Invoice.iva_category` — a completely unrelated axis. One is the **IVA treatment of the operation**; the other a **spending classification of the line**. Two fields called "category" on one aggregate is how a reader reaches for the wrong one, and how a grep for either finds both. Naming the field for the taxonomy it belongs to fixes the ambiguity that was actually costly, which is not the one the Step anticipated.

**The field is dormant**: written and persisted, read by no production consumer, and typed as a bare string rather than to the taxonomy it is named for. It is kept rather than removed, because per-line spending classification is a real capability this aggregate is shaped for and the pre-release regime's delete-don't-migrate rule governs *legacy* surfaces, not unfinished ones. What changed is that the state is now recorded at the declaration, so a reader cannot infer from the field's presence that aggregation consumes it.

**The categories package docstring asserted exactly that inference and was wrong on both halves.** It claimed `domain.invoices` "carries the same stable category identifiers on invoice and purchase evidence records **used by aggregation**". The identifiers are not the same — the field is not typed to the taxonomy — and no aggregation consumer reads it. A reader trusting that entry would go looking for a coupling that has never existed.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/adapters/persistence/profile src/cadrumo/application/invoices -m "integration or unit" -q --no-header
    554 passed in 30.95s

    uv run --no-sync ruff check <the four changed files>
    All checks passed!

Data consumers were swept as well as callers, per the Step's criterion. The non-Python occurrences — the CLI ledger docs, the generated command tree, the user-profile schema and the quickstart sequences — are all the ledger/transaction taxonomy, untouched by this rename. The two invoice-line roundtrip fixtures are the only serialised carriers of the renamed key, and both are swept.

The dormancy claim is the load-bearing one and was measured directly: no production module reads a line's category, and the decomposition contract does not mention it.

## Notes

This is the **fourth** instance in this campaign of prose that was accurate when written and silently became false, and the second where the false statement was a *cross-module claim about a coupling*. The others were the persistence guard's justification, the English locale leaf, and the M349 resolver's stated ground.

The pattern across all four: each named a relationship between two things, and each went false because one side changed without the other. None of them would have been caught by a test, because none of them was executable — which is why the countermeasure recorded earlier (prefer a justification resting on control flow over one resting on a set's contents) matters more than diligence in re-reading.
