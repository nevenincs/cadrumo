---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f390504eefc0ce6aa6606c699ecc99df17880cc85aa793a6dc58be79f3b5b62c'
step_id: 'S286'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Refuse to price an unknown model rather than reporting it free

## Scope

- `src/cadrumo/llm/_pricing.py`

## Description

This is a LANDING-VERIFICATION record, not a claim of authorship. The record scaffolded for this row on 2026-08-08 was committed with every body section EMPTY, so the row carried a matching exec record that recorded nothing. That is the state the campaign's own discipline exists to prevent: delivered-as-specified, delivered-narrower and recorded-but-not-implemented all wear the same checkbox, and an empty record makes them indistinguishable. This fills it from HEAD.

- Re-read the row's premise against HEAD and find the defect already closed. `estimate_cost_usd` returns `None` for a model its table does not price, never `Decimal("0")`.
- Confirm the reasoning is recorded at the site rather than only in the plan: the function's own docstring states that returning zero is how a cost surface reports an absence as a positive answer, since a caller budgeting from a zero figure concludes the call was free rather than unpriced.
- Confirm the fix did not collapse two different facts. Free and unpriceable stay distinct: the local provider genuinely costs nothing and still returns `Decimal("0")`. Collapsing them would have put the defect back under a different name.
- Confirm the table is not the fix. The docstring records that widening the table cannot fix this, because a pricing snapshot goes stale by construction and the models it does not carry are a permanent moving population, so the refusal is the durable answer and the table is not.
- Confirm prefix resolution survives: the lookup still takes the first entry whose model field is a prefix of the argument, so dated and versioned suffixes inherit their family rates.

## Outcome

Every cost figure for the tier this campaign actually targets no longer reads free. The row named `claude-haiku-4-5`, `claude-opus-4-1` and `gpt-4o` as pricing at zero for a million tokens; the shipped gate now asserts each of those either resolves a real rate or returns `None`.

**The row file locator was WRONG and is corrected in the same action as this record.** The row cites `src/cadrumo/llm/_client.py`. The function does not live there and did not when the row was written: `_client.py` only imports it. The implementation is `src/cadrumo/llm/_pricing.py`. A locator naming a file that merely imports the symbol sends the next reader to the wrong module, and is exactly the kind of stale coordinate this campaign has been correcting elsewhere.

**What this excludes.** The row asked only that an unknown model stop pricing at zero, and that is delivered. It does NOT deliver a complete or current pricing table, and no row in this plan does. Any cost figure the harness reports for an unpriced model is now an explicit absence rather than a number, which is the honest state but not the same as a priced one. The measured lane must treat a `None` as not-measured, never as no-cost.

## Verification

Read directly from HEAD `ac219c97e8`:

    def estimate_cost_usd(...) -> Decimal | None                    llm/_pricing.py:31
    "A model this table does not price returns None, never zero."   llm/_pricing.py:38
    "Free and unpriceable stay distinct."                           llm/_pricing.py:47

Implementing commit, by another lane:

    6376b7ec3b  2026-08-08 13:19  fix(llm): refuse to price an unknown model instead of reporting it free

Shipped gate found beside it, not authored here:

    src/cadrumo/llm/tests/test_unpriced_model_is_not_free.py

carrying both directions: a priced family resolving a real rate, an unpriced one returning `None`, and the local provider still returning `Decimal("0")` so the free-versus-unpriceable distinction is asserted rather than assumed.

Gate run requested from the single test-run authority rather than executed here.

## Notes

The empty scaffold is the finding worth carrying forward. A record can exist, pass the vault check, survive a git log inspection, and still say nothing; the only reliable tell is reading the body. Two of this batch eight records were in that state.
