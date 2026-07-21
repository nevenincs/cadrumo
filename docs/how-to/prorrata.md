# Apply IVA prorrata deductions

Use this guide when the taxpayer cannot deduct all input IVA. This happens when
the activity mixes operations that grant the right to deduct with operations
that do not (exempt operations without the right to deduct). Spanish IVA calls
this *prorrata*. Record the taxpayer's prorrata choice once and the tool applies
it to Modelo 303 and Modelo 390 automatically.

Cadrumo does not submit anything to AEAT. The prorrata register is local,
profile-scoped taxpayer state, not an AEAT filing surface.

The tool needs a master-key passphrase and prompts for it.

**Requirement:** a valid taxpayer profile. Create one with
`aeat config profile create <name>` before you start. [Set up your taxpayer
profile](profile-setup.md) walks through it.

## Which prorrata applies

- **General prorrata** (LIVA art. 104): one deduction percentage applies to
  every deductible input for the year. Use it when the taxpayer has no reason to
  separate inputs.
- **Especial prorrata** (LIVA art. 103): each input deducts by its own use.
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
- The percentage source (`--provenance`) defaults to `carried_prior_definitiva`
  (the prior year's definitive percentage). Pass `--provenance aeat_autorizada`
  with `--reference` for an AEAT-authorised percentage, or `--provenance
  inicio_actividad` with `--reference` for a start-of-activity proposal.

## Elect especial prorrata and classify inputs

Elect especial for the year:

```{cli-sequence} prorrata-elect-especial
:verify: Confirm the especial election replaces the general one for the year.
```

Here `--percentage` is the common-use percentage, the rate applied to shared
inputs (LIVA art. 106.Uno regla 3.ª / art. 104.Dos). The same `--provenance` and
`--reference` options apply.

Then tag each input row with its use when you add it:

```{cli-sequence} prorrata-classify-input
:verify: Confirm the tagged common input is recorded in the ledger.
```

`--input-classification` takes one value:

- `exclusively_deductible` - the input serves only operations that grant the
  right to deduct; it deducts in full.
- `exclusively_non_deductible` - the input serves only operations that do not; it
  deducts nothing.
- `common` - the input is shared; it deducts at the common-use percentage.

Tag an input but elect no especial for that year and the tool warns the tag is
inert: the input deducts under the general percentage. Elect especial to make
the tag take effect.

## Declare a differentiated sector

Declare a differentiated sector when part of the activity has its own deduction
regime (LIVA arts. 9.1.c / 101):

```{cli-sequence} prorrata-declare-sector
:verify: Confirm the differentiated sector is registered.
```

- `--sector-id` is a stable id the register entries and ledger rows reference.
- `--letra` is the LIVA art. 9.1.c letra that makes the sector differentiated:
  `a`, `b`, `c`, or `d`.
- `--activity-code` is a CNAE or IAE code grouped into the sector. Repeat it for
  each code; give at least one.

Scope an election to a sector with `--sector`, and tag a row's sector with
`--sector` on `ledger add`:

```{cli-sequence} prorrata-sector-scoped
:verify: Confirm the sector-scoped input is recorded against the declared sector.
```

Tag a row with a sector you have not declared and the tool warns the tag is
unmatched: the input deducts at the common-use percentage until you declare the
sector. Declare the sector first, or fix the id.

## Read the settlement advisories

When you calculate the year-end Modelo 303 (the 4T settlement), the tool may
surface non-blocking advisories:

- **Especial may be mandatory** - when the taxpayer computes under general
  prorrata and especial would deduct at least 10% less, the law (LIVA
  art. 103.Dos.2) makes especial mandatory. Classify every input of the year so
  the tool can run this check; until then it prompts you to classify.
- **Inert classification** - an `--input-classification` tag set with no especial
  election for that year.
- **Unmatched sector** - a `--sector` tag naming a sector not yet declared.

These are advisories, not refusals. Read them alongside the
[calculation inputs](review-calculation-values.md) before you
[verify the filing](verification-reports.md).

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
- [Prepare a Modelo 303 IVA filing](modelo-303.md) and
  [the annual Modelo 390 summary](modelo-390.md).
