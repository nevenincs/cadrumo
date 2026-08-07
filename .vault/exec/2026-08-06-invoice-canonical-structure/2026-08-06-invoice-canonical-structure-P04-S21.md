---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:cd03b9f68f3a41945a956b67caafadf657b91d07f8bce0ad296c966738564736'
step_id: 'S21'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Record that InvoiceKind STAYS in the iva domain and do NOT relocate it, because the enum is a shared direction axis both domains consume, domain/iva imports it at module level in two files while domain/iva references domain/invoices only under TYPE_CHECKING guards, so moving it would convert a clean one-way static dependency into a hard module-level cycle that two new deferred imports would then have to paper over

## Scope

- `src/cadrumo/domain/iva/_classification.py`

## Description

- Measured the import direction between the two domains before moving anything.
- Established which references are module-level and which are guarded, since only the first constrain a relocation.
- Read the enum's own declared purpose, which turned out to answer the question directly.
- Re-scoped the Step to a recorded decision rather than executing the relocation.

## Outcome

**`InvoiceKind` STAYS in the iva domain. The relocation was not performed, because performing it would make the architecture worse.**

The Step reads "relocate `InvoiceKind` from the iva domain to the invoices domain keeping its name". Measured at `HEAD`, the dependency direction between those two packages is currently **clean and one-way**:

- `domain/invoices` imports from `domain/iva` at module level, in five files.
- `domain/iva` references `domain/invoices` **only under `TYPE_CHECKING` guards**, with a runtime fallback assignment. At runtime there is no iva-to-invoices module import at all.

So the static graph flows invoices-to-iva, with the reverse direction held open only for type checking. Moving `InvoiceKind` would force `domain/iva/_flow.py` and `domain/iva/_components.py` — both of which import it at **module level** — to import from `domain/invoices` at module level, creating a hard import-time cycle where today there is none. Closing that cycle would then require two new deferred imports, added solely to survive a move that had no other benefit.

**The enum's own docstring settles the intent.** It states it is the "single canonical enum spanning both the substrate classifier and ledger / invoice records", and that it "replaces the prior split between `InvoiceDirection` (substrate) and `InvoiceKind` (invoices)". It is deliberately shared, and it was placed where it is BECAUSE both domains consume it. Relocating it into one of its two consumers would re-create the split it was unified to remove — just with the asymmetry pointing the other way.

**Why the Step looked right.** `InvoiceKind` names an invoice property, so the invoices domain reads like its natural home. That intuition is about the noun, not about the dependency graph, and the graph is what a relocation actually moves. The Step was authored from the naming, and naming is exactly the evidence that cannot see a cycle.

## Verification

Closed by a recorded decision. The measurements behind it:

    rg -n "from \.\.invoices" src/cadrumo/domain/iva/*.py
    only _invoice_classification.py, and only inside an `if TYPE_CHECKING:` block
    with `else: IvaRate = object` as the runtime fallback

    rg -n "from \.\.iva import" src/cadrumo/domain/invoices/*.py
    five module-level imports (_validators, _service, _models, _enums, _decomposition)

    domain/iva/_flow.py:91 and domain/iva/_components.py:61
    both import InvoiceKind at MODULE level from within the iva package

Blast radius, had it proceeded: 101 files reference the symbol, all of which would have had to land in one atomic commit alongside two new cycle-breaking deferred imports.

No code changed, so there is no test run to quote. The claim is falsifiable by re-running the three sweeps above.

## Notes

This is the second Step in the campaign closed as **re-scoped because executing it would introduce a defect**, the first being the EU-VAT-ID field addition. Both were framed as preconditions of later work and both would have added the thing the campaign exists to remove — one a second identity authority, this one a module-level cycle.

The shared shape is worth naming: both Steps reasoned from **what a symbol is called** rather than from **what depends on it**. That is a reasonable way to author a plan and a poor way to execute one, because a name is visible in isolation while a dependency is only visible in aggregate.

If a later campaign still wants this symbol out of the iva package, the honest options are to move it to a neutral third home that neither domain owns, or to first invert the invoices-to-iva dependency — both larger decisions than a relocation, and neither of them this plan's.
