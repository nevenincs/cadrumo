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
- `--letra` is the LIVA art. 9.1.c letra that makes the sector differentiated:
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

List every election and declared sector on the active profile:

```{cli-sequence} prorrata-list
:verify: Confirm the register reads back the elections and declared sector.
```

## Next steps

- [Classify transactions](classify-transactions.md) so each input carries the
  data prorrata needs.
- [Review calculation inputs](review-calculation-values.md) to see the deducted
  amounts.
- [Prepare a Modelo 303 VAT filing](modelo-303.md) and
  [the annual Modelo 390 summary](modelo-390.md).
