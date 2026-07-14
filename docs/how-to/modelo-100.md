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
Create one with `aeat config profile create <name>` — see [Set up your taxpayer
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
  [Classify transactions](classify-transactions.md); confirm with
  `aeat app ledger preflight --year 2025 --period 0A`.
- File and evidence the year's quarterly instalments first. Modelo 100 folds
  in your Modelo 130/131 payments on account and the retenciones reported on
  modelos 111, 123, 190, and 193 where they exist. Check what this
  declaration expects and what blocks it with `aeat app modelo requires 100
  --year 2025 --period 0A` and `aeat app modelo work dependencies --modelo 100
  --year 2025 --period 0A`. `dependencies` names each source filing and whether
  its clean-state evidence is satisfied; an unfiled or unevidenced quarter
  blocks the annual verify. Record or reconcile those filings first - see
  [Reconcile a filing](reconcile.md).

## Create, calculate, and verify

The example below follows an employee filer - a Madrid-resident salaried
taxpayer filing an individual 2025 return, with no self-employed activity, so
the Modelo 130/131 and retención-model folds are scoped out and the annual
grants on the employment figures alone. If you also file quarterly Modelo 130
instalments, they fold in as payments on account - see [Prepare a Modelo 130
IRPF instalment](modelo-130.md).

```{cli-sequence} modelo-100-renta-2025
:seed: renta-2025
:verify: Confirm the annual declaration passed verification before you export it.
@step Open the annual Modelo 100 work unit for 2025.
aeat --format json app modelo work create --modelo 100 --year 2025 --period 0A
@capture work_unit_id result.work_unit_id
@step Calculate, supplying this employee filer's salary income and withholdings by hand, with a zero prior-year negative-base carry for a first filing.
aeat --format json app modelo work calculate {work_unit_id} --casilla 0003=24000 --binding renta-2025-certificado-trabajo-retenciones=2400 --binding renta-2025-base-liquidable-negativa-general-anterior=0
@capture calculation_revision_id result.calculation_revision_id
@expect result.casilla_values.0003 == "24000"
@expect result.casilla_values.0012 == "24000.00"
@expect result.casilla_values.0019 == "2000.00"
@step Verify the annual declaration before you export it.
@result aeat --format json app modelo work verify {calculation_revision_id}
@expect result.granted_verificado_completo == true
@expect result.completeness_status == "complete"
@expect exit_code == 0
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
Find what applies to you and what is still missing with `aeat app modelo
bindings list --modelo 100 --year 2025 --period 0A --missing`, `aeat app modelo
casillas 100 --period 0A --required`, and `aeat app modelo work observations
--modelo 100 --year 2025 --period 0A`. Supply a manual casilla and recalculate
with `aeat app modelo work calculate --modelo 100 --year 2025 --period 0A
--casilla 0003=24000`.

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

Export the verified declaration with `aeat app modelo export --modelo 100 --year
2025 --period 0A --output ./modelo-100.boe`. After you file at the portal, record
the local marker with `aeat app modelo work file --modelo 100 --year 2025
--period 0A` and reconcile with `aeat app modelo reconcile pull --modelo 100
--year 2025 --period 0A`.

## Next steps

- [How the Renta declaration is assembled](../explanation/how-renta-is-assembled.md)
- [Prepare a Modelo 130 IRPF instalment](modelo-130.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Upload your exported modelo at the AEAT portal](file-at-aeat.md)
- [Reconcile a filing](reconcile.md)
