# Prepare the annual Modelo 100 Renta declaration

This page covers the annual Renta filing: creating the Modelo 100 work unit,
letting the year's data flow in, supplying the manual values that apply to
you, and verifying and exporting the declaration. Modelo 100 is the annual
IRPF declaration; the registry's official title is "Modelo 100. Declaración
del Impuesto sobre la Renta de las Personas Físicas."

Modelo 100 is the largest form the tool prepares - the 2025 revision carries
over two thousand casillas and two hundred formulas - and it is the one
filing that gathers the whole year: your ledger, your profile facts, your
quarterly instalments, and the withholdings others reported on your behalf.
For how those values arrive and how to trace any figure to its source, read
[How the Renta declaration is assembled](../explanation/how-renta-is-assembled.md)
- this page stays with the commands.

`aeat` does not submit Modelo 100 to AEAT. Export creates a local file that
you upload through the official AEAT channel yourself.

## Before you create the draft

**Requirement:** a valid taxpayer profile carrying the Renta-relevant facts.
Create one with `aeat config profile create <name>`. See [Set up your taxpayer
profile](profile-setup.md).

- Modelo 100 is annual: the period token is always `0A`, and the filing year
  is the year the income belongs to (the 2025 declaration is filed in 2026).
  Each filing year resolves to its own registry revision automatically.
- [Set up your taxpayer profile](profile-setup.md) with the Renta-relevant
  facts: residence comunidad, marital status, spouse and descendant data,
  disability grades. The profile feeds dozens of Modelo 100 bindings, and an
  incomplete profile surfaces as missing values later. Manage descendants
  with `aeat config profile descendiente add/list/remove`.
- Bring the year's ledger to clean and classified - Modelo 100 aggregates
  income and deductible expenses across the whole year. See
  [Import and manage transactions](import-bank-statements.md) and
  [Classify transactions](classify-transactions.md); confirm with:

  ```{cli-sequence} modelo-100-preflight
  :verify: Confirm the year's ledger reads back clean for the annual period.
  ```

  The transaction ledger is not the stock-inventory register. If your activity
  holds stock, maintain its encrypted inventory ledger separately, then enter
  the applicable Renta stock figures manually. There is no automatic
  inventory-to-Modelo-100 projection in this version.
- File and evidence the year's quarterly instalments first. Modelo 100 folds
  in your Modelo 130/131 payments on account and the retenciones reported on
  modelos 111, 123, 190, and 193 where they exist. Check what this
  declaration expects and what blocks it:

  ```{cli-sequence} modelo-100-dependencies
  :verify: Confirm the declaration's required source filings and dependencies read back.
  ```

  `dependencies` names each source filing and whether its clean-state
  evidence is satisfied; an unfiled or unevidenced quarter blocks the annual
  verify. Record or reconcile those filings first - see
  [Reconcile a filing](reconcile.md).

## Create, calculate, and verify

The example below follows an employee filer - a Madrid-resident salaried
taxpayer filing an individual 2025 return, with no self-employed activity, so
the Modelo 130/131 and retención-model folds are scoped out and the annual
grants on the employment figures alone. If you also file quarterly Modelo 130
instalments, they fold in as payments on account - see [Prepare a Modelo 130
IRPF instalment](modelo-130.md).

```{cli-sequence} modelo-100-renta-2025
:verify: Confirm the annual declaration passed verification before you export it.
```

Calculation reads the year's classified ledger, the profile facts, the prior
filings the registry binds in, and any carry-forward from last year's
declaration (negative bases carry via a prior-filing binding), then runs the
registry formulas and saves a draft revision. Here casilla `0003` carries the
24000 of salary income, casilla `0012` the rendimiento neto del trabajo, and
casilla `0019` the reducción por rendimientos del trabajo (art. 20 LIRPF) of
2000. The tool never fabricates a missing prior period: what it does not have
on record stays a visible blank for you to resolve, not a guessed zero.

Most of Modelo 100's casillas are optional manual inputs for situations the
ledger cannot know (employment income details, capital income, deductions).
Find what applies to you and what is still missing:

```{cli-sequence} modelo-100-inspect-inputs
:verify: Confirm the declaration's missing bindings, required casillas, and observations read back.
```

For stock under estimación directa, inspect and supply boxes 0177, 0181, and
0182 when they apply. They are manual inputs in the current registry. Do not use
0155 as an inventory substitute: an unused inventory helper still carries that
stale box name, but calculation does not route the inventory register through
it.

Supply a manual casilla and recalculate by passing `--casilla 0003=24000` on
the calculate command, alongside the bindings the declaration still needs (the
main sequence above shows the full form). Recalculating replaces the current
draft revision.

For the full input workflow - bound versus manual casillas, offsets, and
revision selection - see
[Review and supply calculation inputs](review-calculation-values.md). For a
spreadsheet review of the assembled declaration, see
[Review calculations with Google Sheets](review-with-google-sheets.md).

## Export and file

The verify step in the sequence above ran the annual completeness check,
including the cross-period gates: every dependency filing must be filed and
evidenced, and every carried figure must still point at the revision it was
filed under. A blocked report names the dependency in the way - resolve it and
re-run. See [Verify a draft filing](verification-reports.md).

Export the verified declaration. Export is the local finish line. Recording the
filed marker afterwards is optional and applies only while the obligation
window is open; it is an internal note that you have already presented the file
at the portal. The Renta 2025 window opens on 8 April 2026, after the date this
guide's examples run at, so the filed marker is shown as a display frame here,
as is the reconcile pull, which reads from AEAT:

```{cli-sequence} modelo-100-export-file
:verify: Confirm the verified declaration exports to a local file.
```

See [Reconcile a filing](reconcile.md) for the reconciliation verdicts.

## Next steps

- [How the Renta declaration is assembled](../explanation/how-renta-is-assembled.md)
- [Prepare a Modelo 130 IRPF instalment](modelo-130.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [File your modelo at the AEAT portal](file-at-aeat.md)
- [Reconcile a filing](reconcile.md)
