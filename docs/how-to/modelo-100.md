# Prepare the annual Modelo 100 Renta declaration

This page covers the annual Renta filing: creating the Modelo 100 declaration,
letting the year's data flow in, supplying the manual values that apply to you,
and checking and exporting the declaration. Modelo 100 is the annual IRPF
(personal income tax) declaration; its official title is "Modelo 100. Declaración del Impuesto sobre la
Renta de las Personas Físicas."

Modelo 100 is the largest form the tool prepares - the 2025 version carries
over two thousand boxes and two hundred formulas - and it is the one
filing that gathers the whole year: your records, your profile facts, your
quarterly instalments, and the withholdings others reported on your behalf.
For how those values arrive and how to trace any figure to its source, read
[Deep dive: how the Renta declaration is assembled](../explanation/how-renta-is-assembled.md).
This page stays with the commands.

`aeat` does not submit Modelo 100 to AEAT. Export creates a local file that
you upload through the official AEAT channel yourself.

## Before you create the draft

**Requirement:** a valid taxpayer profile carrying the Renta-relevant facts.
Create one with `aeat config profile create <name>`. See [Set up your taxpayer
profile](profile-setup.md).

- Modelo 100 is annual: the period code is always `0A`, and the filing year
  is the year the income belongs to (the 2025 declaration is filed in 2026).
  Each filing year automatically uses its own version of the official form.
- [Set up your taxpayer profile](profile-setup.md) with the Renta-relevant facts:
  residence comunidad, marital status, spouse and descendant data, disability
  grades. The profile fills dozens of Modelo 100 boxes, and an incomplete profile
  shows up as missing values later. Manage descendants with `aeat config profile
  descendiente add/list/remove`.
- Bring your records for the year to clean and classified - Modelo 100 aggregates
  income and deductible expenses across the whole year. See [Import and manage
  transactions](import-bank-statements.md) and [Classify
  transactions](classify-transactions.md); confirm with:

  ```{cli-sequence} modelo-100-preflight
  :verify: Confirm the year's records read back clean for the annual period.
  ```

  Your transaction records are not the stock-inventory register. If your activity
  holds stock, keep its encrypted inventory register for the filing year with
  `aeat app ledger inventory`. Calculation reads that register for boxes 0177,
  0181, and 0182.
- Record the year's quarterly instalments as filed first. Modelo 100 folds in your
  Modelo 130/131 payments on account and the retenciones reported on Modelos 111,
  123, 190, and 193 where they exist. Check what this declaration expects and what
  blocks it:

  ```{cli-sequence} modelo-100-dependencies
  :verify: Confirm the declaration's required source filings and dependencies read back.
  ```

  `dependencies` names each source filing the tax rules can fold in and whether
  the proof of its filing is in place. The check leaves out the filings
  that do not apply to your profile and reports them as advisories, as the
  example that follows shows. For a filing that does apply, a quarter that is
  not recorded as filed or has no proof blocks the annual check. Record or reconcile those
  filings first - see [Reconcile a filed modelo against its AEAT receipt](reconcile.md).

<a id="create-calculate-and-verify"></a>

(how-to-modelo-100-create-calculate-and-verify)=
## Create, calculate, and check

The example below follows an employee filer - a Madrid-resident salaried taxpayer
filing an individual 2025 return, with no self-employed activity, so the amounts
from Modelo 130/131 and the withholding modelos do not apply and the annual
calculation uses the employment figures alone. If you also file quarterly Modelo
130 instalments, they fold in as payments on account - see [Prepare a Modelo 130
IRPF instalment](modelo-130.md).

```{cli-sequence} modelo-100-renta-2025
:verify: Confirm the annual declaration passed the check before you export it.
```

Calculation reads the year's classified entries in your records, the profile
facts, the prior filings the tax rules bring in, and any carry-forward from last
year's declaration (negative bases carry over through a rule that reads the prior
filing), then runs the formulas of the tax rules and saves a draft calculation.
Here box `0003` carries the 24000 of salary income, box `0012` the total
countable gross employment income (`24000.00`), and box `0019` the other deductible employment
expenses (art. 19 LIRPF) of `2000.00`. The tool never fabricates a missing
prior period: what it does not have on record stays a visible blank for you to
resolve, not a guessed zero.

Most of Modelo 100's boxes are optional manual inputs for situations your records
cannot know (employment income details, capital income, deductions). Find what
applies to you and what is still missing:

```{cli-sequence} modelo-100-inspect-inputs
:verify: Confirm the declaration's missing values, required boxes, and calculation notes read back.
```

For stock under estimación directa, boxes 0177, 0181, and 0182 are filled from
your encrypted inventory register for the filing year. `--casilla` and `--binding`
refuse a value for them. Without a complete register for that year, calculation
warns that no inventory register is available and the boxes stay at `0`, so
create the register before you file. Don't put stock figures in box 0155:
calculation doesn't read it as an inventory figure.

Supply a manual box value and recalculate by passing `--casilla 0003=24000` on the
calculate command, alongside the `--binding` values the declaration still needs
(the main sequence above shows the full form). Recalculating replaces the current
draft calculation.

For the full input workflow - boxes Cadrumo fills in versus boxes you supply,
offsets, and choosing among earlier calculations - see
[Review and supply calculation inputs](review-calculation-values.md). For a
spreadsheet review of the assembled declaration, see
[Review calculations with Google Sheets](review-with-google-sheets.md).

## Export and file

The check step in the calculation example ran the annual completeness check,
including the checks across periods: every filing this declaration depends on
must be recorded as filed and have its proof, and every carried figure must still
point at the version of the tax rules it was filed under. A blocked report names
the unresolved dependency. Resolve it, then run the check again. See [Check a draft declaration and act on the issues](verification-reports.md).

Export the checked declaration. Modelo 100 always writes an XML file, whatever
name you choose. Export refuses to overwrite an existing file unless you add
`--replace`, and refuses when the output folder does not exist. Export is the
local finish line. Recording the
filing afterwards (Record filing) is optional and applies only while the filing
window is open; it only notes in Cadrumo that you have already presented the file
at the portal. The Renta 2025 window opens on 8 April 2026, after the date this
guide's examples run at, so recording the filing is shown as an example that is
not run here, as is the reconcile pull, which reads from AEAT:

```{cli-sequence} modelo-100-export-file
:verify: Confirm the checked declaration exports to a local file.
```

See [Reconcile a filed modelo against its AEAT receipt](reconcile.md) for the reconciliation verdicts.

## Next steps

- [Deep dive: how the Renta declaration is assembled](../explanation/how-renta-is-assembled.md)
- [Prepare a Modelo 130 IRPF instalment](modelo-130.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [File your modelo at the AEAT portal](file-at-aeat.md)
- [Reconcile a filed modelo against its AEAT receipt](reconcile.md)
