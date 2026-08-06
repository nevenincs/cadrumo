---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:bd0e4d8f6e1a431077b4e1a7124eed7e4de0c5357751d6f179388fec2a937af0'
step_id: 'S52'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Carry recargo de equivalencia inside the ledger transaction totals identity, so the substrate Modelo 303 and 130 actually read stops refusing the truthful row and accepting the falsified one

## Scope

- `src/cadrumo/domain/transactions/_models.py`
- `src/cadrumo/domain/transactions/tests/test_gross_invariant.py`

## Description

- Move the transaction totals identity to `gross == taxable_base + iva_amount + recargo_amount`, and rename the validator and rewrite its docstring so neither still asserts the two-term form.
- Leave the self-assessed branch at `gross == taxable_base`, and state why the surcharge does not join it.
- Leave all three retención relaxation branches untouched, and record the direction argument that makes recargo their opposite.
- Name `--recargo-amount` in the refusal when the cash sits above the declared substrate and no surcharge was recorded.
- Extract the refusal-hint chain into a module-level helper, paying the validator's grandfathered complexity down from 29 to 22 cyclomatic and 26 to 21 cognitive.
- Correct the cross-quarter recargo end-to-end fixture, which built the falsified shape and documented it as a property of the model.

## Outcome

The polarity is inverted. Both measurements are on the real model, the first
before any edit and the second after, using one supply at the general tier:
base 1000.00, IVA 21 % = 210.00, recargo 5.2 % = 52.00, cash 1262.00.

```
BEFORE  TRUTHFUL  (recargo inside gross, 1262)   REFUSED
        FALSIFIED (recargo declared, gross 1210) ACCEPTED

AFTER   TRUTHFUL  (recargo inside gross, 1262)   ACCEPTED
        FALSIFIED (recargo declared, gross 1210) REFUSED
                  taxable_base + iva_amount + recargo_amount must equal the
                  gross to the cent: 1000.00 + 210.00 + 52.00 = 1262.00 != 1210.00
```

A row that records neither a surcharge nor a substrate is unaffected in both
directions, which is the overwhelming majority of the corpus.

This was not a missing capability. The model refused the only truthful way to
record the operation and accepted the one shape that understates the cash by
exactly the surcharge, so a comerciante minorista entering a real supplier
payment was steered into the false row by the validator itself.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/transactions src/cadrumo/application/aggregation -n 0 -q --no-header
796 passed, 7 deselected in 45.11s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/domain/iva
  src/cadrumo/application/ledger src/cadrumo/application/modelo
  src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py
  src/cadrumo/adapters/persistence/profile -n 0 -q --no-header
2745 passed, 128 deselected in 649.10s (0:10:49)
```

The corrected end-to-end fixture is marked integration, so a path-scoped run
could deselect it silently. It was re-run alone to confirm it executed:

```
uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_e2e_ledger_m303_recargo_cross_period.py -n 0 -q --no-header -v
collected 1 item
1 passed in 8.84s
```

```
uv run --no-sync ruff format --check <four touched files>    4 files already formatted
uv run --no-sync ruff check <four touched files>             All checks passed!
uv run --no-sync ty check src/cadrumo/domain/transactions/_models.py
All checks passed!
```

Four mutations, each applied to a copy-aside and restored:

```
M1  drop the recargo term from the reconstitution        reddens 5
M2  accept any substrate above the cash unconditionally  reddens 15
M3  move recargo to the retención (cash) side            reddens 3
M4  disable the instructive recargo hint                 reddens 1
```

M1 is the one that reddens both polarity tests at once: without the term the
truthful row is refused again and the falsified row is accepted again, so the
pair is load-bearing in both directions rather than one test carrying the
other. M2 is the independent confirmation that the falsified-row refusal does
not pass incidentally. M3 reddens the both-terms test and nothing else can
catch it. M4 pins the hint.

The source was restored byte-exact and verified two ways rather than by
trusting the copy step: SHA-256 equal to the pre-mutation digest
`59019043a85a2a8b118621e41a2b0bf13ff1c5708a3606afb4e3a0da61c7d057`, and a
post-hoc diff scan finding no `if False`, no `- recargo`, and no bare
early-accept branch anywhere in the change.

## Notes

**The earlier invoice fix was incomplete, and the reason it survived is worth
more than this patch.** The invoice identity was corrected this same morning,
mutation-proved, and recorded with a full account of why recargo joins the
total while retención does not. All of that was right. What nobody asked was
whether the same identity existed anywhere else. It did, on the ledger
transaction, which is the substrate Modelo 303 and Modelo 130 actually
aggregate from, so the half that reaches a filing was the half left broken for
the rest of the day. A fix proved correct at one site says nothing whatever
about its siblings, and proving it harder at that one site does not begin to
close the gap. The transferable move is a sweep for the *concept* after the
fix lands, not more evidence at the site already understood. This defect was
found by exactly that sweep and was not visible in the diff or from reading
the file.

**The surcharge is inside the gross and the withholding is outside it.** That
is the axis the whole validator turns on. Retención reduces what the payer
transfers without changing what the operation cost, which is why every
relaxation branch is gated on the substrate *exceeding* the cash. Recargo is a
price component under LIVA art. 161, repercutido on the entrega alongside the
cuota, so it raises the cash. Omitting it did not merely narrow the check, it
inverted the check for these rows: a recargo row reconstitutes *below* its
cash, and no relaxation covers that direction, so the truthful row fell
through every branch to the raise. The three relaxation branches were left
exactly as found, and the two terms compose correctly without touching them —
a row carrying both lands above the cash by the withholding alone.

**One test carries the opposite-sides claim and the others cannot.** A row
carrying only recargo, or only retención, balances identically whichever side
that term sits on, so every single-term case would survive a future
simplification that moved either one. The both-terms case is a módulos
supplier selling to a retailer under recargo with 1 % retención withheld at
source: the surcharge raises the cost to 1262.00 and the withholding lowers
the transfer to 1252.00. Mutation M3 confirms that swapping the sides reddens
that test and the two truthful-row tests, and reddens nothing else.

**The self-assessed branch deliberately does not carry the surcharge.** On a
reverse-charge acquisition or an import the supplier repercutes neither the
cuota nor the recargo — the acquirer self-liquidates both — so neither reaches
the cash movement the row records. That branch stays at
`gross == taxable_base`. This is pinned by a test rather than left to the
reader, because the natural reflex on seeing the general branch gain a term is
to add it to both.

**A test was asserting the defect as a design fact.** The cross-quarter
recargo end-to-end fixture built its rows with the cash set to base plus IVA
and its docstring stated that the recargo "is a separate cuota the model does
not fold into the IVA-inclusive gross". It was describing the model
accurately; the model was wrong. Both the row construction and the prose
moved. This is the second time in this campaign that prose asserting a
property the code lacks turned out to be the readable half of a real defect,
and the direction was reversed here: the code was wrong and the comment
faithfully documented it, which is harder to spot than a stale comment because
nothing disagrees.

**The transaction has no suplido and none was added.** The Step's brief asked
whether the same omission applies. It does not: `Transaction` carries
`recargo_amount` and no suplido field at all, so there is no second term
silently dropped from this identity. The invoice gained `suplido_amount`
separately, and a suplido takes a third position — inside total and inside
cash, outside both base and cuota — so extending it to the transaction is a
design decision with its own consequences for the aggregation reads, not a
line to append here.

**The complexity baseline was hand-edited to two keys rather than
regenerated.** The rename orphaned the validator's grandfathered entries,
which are keyed by qualified function name. The sanctioned regeneration
rewrites the whole production scope, and the gate is currently failing on 125
hotspots owned by other campaigns, so regenerating would have swept all of
them into this commit under this message. Instead the two keys were renamed by
hand and their tolerated values lowered from 29 to 22 and from 26 to 21, the
measured post-refactor figures. No new debt was accepted and the entry got
stricter. The gate's new-or-regressed count moved 127 to 125, confirming this
change contributes nothing to the failure; the residual 125 are pre-existing
and untouched.
