(apply-iva-prorrata-deductions)=
# Apply VAT prorrata deductions

Use this guide when the taxpayer cannot deduct all input VAT. This happens when
the activity mixes operations that grant the right to deduct with operations
that do not (exempt operations without the right to deduct). Spanish VAT calls
this *prorrata*. Record the taxpayer's prorrata choice once and the tool applies
it to Modelo 303 and Modelo 390 automatically.

Cadrumo does not submit anything to AEAT. The prorrata register is stored
locally with the taxpayer's profile; it is not something you file at AEAT.

The tool needs your passphrase and prompts for it.

**Requirement:** a valid taxpayer profile. Create one with
`aeat config profile create <name>` before you start. [Set up your taxpayer
profile](profile-setup.md) walks through it.

## Which prorrata applies

- **General prorrata** (LIVA art. 104): one deduction percentage applies to
  every deductible input for the year. It applies unless the taxpayer opts for
  especial or the law requires especial (LIVA art. 103.Dos).
- **Especial prorrata** (LIVA arts. 103 and 106): each input deducts by its own use.
  Fully deductible inputs deduct in full, inputs used only for non-deducting
  operations deduct nothing, and shared ("common") inputs deduct at the general
  percentage. Tag each input with its use.

Elect nothing and the tool keeps the whole-entity general treatment its own
settlement already produces. Use this guide only when the taxpayer elects a
percentage or splits the business into differentiated sectors.

## Provisional and definitive percentage

Prorrata works with two percentages for each year:

- The **provisional percentage** is the one you elect or carry forward. The
  periods before the last one deduct input VAT at this percentage (LIVA
  art. 105.Uno and 105.Dos).
- The **definitive percentage** is calculated at the end of the year from the
  year's full-year volumes of operations with and without the right to deduct
  (LIVA art. 104.Dos). It is never taken from a single quarter. The tool reads
  those volumes from the annual volume casillas of the settlement period's
  calculation; if they are not declared, it reports that instead of guessing.

The register stores both. The provisional percentage is the election; the
definitive one is recorded on the year's entry once it is settled. A year's
definitive percentage seeds the next year's provisional one with `prorrata
seed`.

## Elect general prorrata

Elect the year's general percentage:

```{cli-sequence} prorrata-elect-general
:verify: Confirm the general election is recorded on the profile.
```

- `--ejercicio` is the filing year the election covers.
- `--percentage` is the provisional deduction percentage, 0 to 100 (LIVA
  art. 104.Uno + 105.Uno).
- `--provenance` and `--reference` name the document the percentage stands on:
  `inicio_actividad` for a start-of-activity proposal (LIVA art. 105.Tres) or
  `aeat_autorizada` for an AEAT-authorised percentage (LIVA art. 105.Dos). The
  tool refuses a typed-in percentage without both.
- To carry the prior year's definitive percentage (LIVA art. 105.Uno), run
  `aeat app ledger prorrata seed --ejercicio <year>` instead. It reads the
  percentage from the stored prior-year Modelo 303 settlement, and refuses when
  no stored settlement carries a definitive percentage.

## Elect especial prorrata and classify inputs

Elect especial for the year:

```{cli-sequence} prorrata-elect-especial
:verify: Confirm the especial election replaces the general one for the year.
```

Here `--percentage` is the common-use percentage, the rate applied to shared
inputs (LIVA art. 106.Uno regla 3.ª / art. 104.Dos). The same `--provenance` and
`--reference` options apply. `--evidence-reference` names the document behind an
option you exercise this year. Omit it to record that the regime already in
force continues.

Then tag each input entry with its use when you add it:

```{cli-sequence} prorrata-classify-input
:verify: Confirm the tagged common input is recorded in the records.
```

`--input-classification` takes one value:

- `exclusively_deductible` - the input serves only operations that grant the
  right to deduct; it deducts in full.
- `exclusively_non_deductible` - the input serves only operations that do not; it
  deducts nothing.
- `common` - the input is shared; it deducts at the common-use percentage.

Tag an input but elect no especial for that year and the tool warns the tag is
inert: the input deducts under the general percentage. The recorded example
starts without an election, so it prints that warning. Elect especial to make
the tag take effect.

The tag only sets how much of a deductible input deducts. An input deducts
only when its row also carries `--deduction-kind` on `ledger add` or
`classify`. The kind `domestic_current` requires a linked purchase invoice as
its supporting document. See [Attach invoices and receipts to transactions](ledger-evidence.md).

## Declare a differentiated sector

Declare a differentiated sector when part of the activity has its own deduction
regime (LIVA arts. 9.1.c / 101):

```{cli-sequence} prorrata-declare-sector
:verify: Confirm the differentiated sector is registered.
```

- `--sector-id` is a stable id that the register entries and the entries in your records reference.
- `--letra` is the LIVA art. 9.1.c subparagraph that makes the sector differentiated:
  `a`, `b`, `c`, or `d`.
- `--activity-code` is a CNAE or IAE code grouped into the sector. Repeat it for
  each code; give at least one.

Scope an election to a sector with `--sector`, and tag an entry's sector with
`--sector` on `ledger add`:

```{cli-sequence} prorrata-sector-scoped
:verify: Confirm the sector-scoped input is recorded against the declared sector.
```

Tag an entry with a sector you have not declared and the tool warns the tag is
unmatched: the input deducts at the common-use percentage until you declare the
sector. The recorded example starts without a declared sector, so it prints
that warning. Declare the sector first, or fix the id.

Three more commands manage a sector's percentage. `prorrata seed-sector` seeds
a sector's provisional percentage from its own prior-year definitive one.
`prorrata settle-sector` settles the year-end definitive percentage from the
sector's annual volumes of operations with and without the right to deduct.
`prorrata revoke-especial` revokes especial for a year after a prior-year
especial state, and requires `--evidence-reference`. Run each with `--help` for
its options.

## Regularise in the last period (casilla 44)

The settlement period of the year is the 4th quarter, or month 12 for a monthly
filer. In that Modelo 303 the two percentages split the work in two:

- The settlement period's own input VAT deducts at the **definitive**
  percentage, through the ledger, like any other period's input VAT at its
  percentage.
- Casilla 44 (*Regularización prorrata por porcentaje definitivo*, LIVA
  art. 105.Cuatro) regularises only the **earlier** periods of the year. For
  each of them the tool takes the gross deductible input VAT, applies the
  definitive percentage, and subtracts the deduction that period actually
  practised at the provisional percentage. The difference, positive or
  negative, goes into casilla 44.

The tool re-derives each earlier period's gross input VAT from your ledger and
reads the deduction it practised from that period's filed observation. The
Modelo 390 regularisation field restates the filed settlement casilla 44.

If a source is missing or contradicts another, casilla 44 stays unresolved and
the calculation reports a finding that names the cause. Nothing defaults to
zero. See [Unresolved findings](#unresolved-findings).

## Declare a gross base for periods entered by hand

An earlier period you filed outside Cadrumo, or entered by hand, may have no
deductible input VAT in the ledger. The tool then cannot re-derive its gross
base. Declare it yourself, per period and, where you declared sectors, per
sector:

```console
aeat app ledger prorrata declare-gross --ejercicio <year> --period 1T --amount 400.00 --evidence <your-document-reference>
```

- `--amount` is the gross deductible input VAT of that period before prorrata,
  in euros with at most two decimals.
- `--evidence` names your own document that backs the amount. It is required.
- `--sector` scopes the declaration to a declared differentiated sector; omit
  it for the whole-activity entry.
- `--replace` replaces a declaration already held for the same period and
  sector. Without it, a second declaration for the same period is refused.

A declaration is your own statement, recorded with the provenance
`operator_declared`. It is not an AEAT observation. The regularisation uses it
only for a period whose ledger holds no deductible input. Where the ledger does
hold input, the ledger wins and must agree with your declaration; a
disagreement becomes a finding.

Remove a declaration with `aeat app ledger prorrata remove-gross --ejercicio
<year> --period 1T`, adding `--sector` for a sector entry.

## Read the settlement advisories

When you calculate the year-end Modelo 303 for the 4th quarter settlement, the tool may
surface an advisory that does not block filing:

- **Especial may be mandatory** - when the taxpayer computes under general
  prorrata and the deduction under general exceeds the deduction under
  especial by 10 percent or more, the law (LIVA art. 103.Dos.2) makes especial
  mandatory. Classify every input of the year so the tool can run this check;
  until then it prompts you to classify. The check does not run for a register
  with declared sectors.

Two more warnings appear when you add a row, not at settlement:

- **Inert classification** - an `--input-classification` tag set with no especial
  election for that year.
- **Unmatched sector** - a `--sector` tag naming a sector not yet declared.

These are notes, not refusals. Read them alongside the [calculation
inputs](review-calculation-values.md) before you [check the
filing](verification-reports.md).

## Review the register

List every election, declared sector and declared gross base on the active
profile:

```{cli-sequence} prorrata-list
:verify: Confirm the register reads back the elections and declared sector.
```

Each declared gross base shows its period, sector (if any), gross amount,
provenance (`operator_declared`), evidence reference and declaration time. The
text output prints one `gross` line per declaration, after the entries and
sectors. `--format json` carries the same fields under `gross_declarations`.

## Unresolved findings

The regularisation never fills a gap with a guess. When it cannot calculate
casilla 44 it leaves the box unresolved and reports a finding. The common ones
mean:

- **Annual volumes not declared** - declare the year's volumes of operations
  with and without the right to deduct, so the definitive percentage can be
  calculated.
- **Provisional percentage missing** - elect or seed a percentage, or file the
  prior year's settlement so it can be carried.
- **Earlier liquidations not filed** - the regularisation covers the year's
  earlier periods; each one must be filed in Cadrumo or have a declared gross
  base.
- **Gross base unknown or disagreeing** - the ledger holds no deductible input
  for a period that declared some, or the ledger and your declaration differ.
  Record the input, or declare or replace the gross base.
- **Ledger and filed liquidation diverge** - the input VAT at the provisional
  percentage does not reproduce what the period filed. Reconcile them first.
- **Sector definitive percentage missing** - settle each sector with `prorrata
  settle-sector` before regularising.

Fix the named cause and recalculate. A finding that asks you to calculate the
box yourself means the case is outside what the tool derives.

Nothing here files or submits anything. The register, the percentages and the
declared gross bases are stored locally with the profile, and the calculation
only fills casilla 44 in a local draft. Filing and any AEAT submission stay
with you.

## Next steps

- [Classify transactions](classify-transactions.md) so each input carries the
  data prorrata needs.
- [Review calculation inputs](review-calculation-values.md) to see the deducted
  amounts.
- [Prepare a Modelo 303 VAT filing](modelo-303.md) and
  [the annual Modelo 390 summary](modelo-390.md).
