# Review and supply calculation inputs

Use this guide when Cadrumo says a field is missing after a calculation. Also
use it when your form needs a value you enter by hand, such as a prior-year
income figure or a compensation amount from an earlier period.

## Before you start

You need:

- A master-key passphrase. Cadrumo prompts for it.
- An active profile. Create one with `aeat config profile create` (the
  `--quiet` form skips the wizard); see [Set up your profile](profile-setup.md)
  for the full options.
- A work unit for the filing you want to review. Create it with `aeat app modelo
  work create` before any review or calculate command (the review sequences
  below open the work unit in their setup steps).

## Inspect the modelo before entering values

Describe the modelo, list its casillas (all of them, then just the required
manual ones), and inspect its formulas with their legal and source references:

```{cli-sequence} review-values-inspect
:verify: Confirm the describe, casillas, and formulas surfaces resolve.
```

The `casillas` command shows the registry casilla id, printed form number,
input kind, required flag, and label. Use this before providing any
`--casilla` value so you know what the number means.

## Review a saved calculation

These commands read a saved calculation, so run a calculation first. On a fresh
work unit with no calculation yet, they refuse with `work unit has no selectable
current_calculation_revision_id`. Run `aeat app modelo work calculate` (see
[Supply manual casilla values](#supply-manual-casilla-values)) to produce a
saved draft, then come back here.

List the calculation revisions for one filing, show the current revision's
persisted casilla values, then verify the current draft, which the setup steps
above create and calculate for the reads below to inspect:

```{cli-sequence} review-values-review-saved
:verify: Confirm the saved calculation lists, shows values, and verifies.
```

Verification output reports whether completeness was granted, how many casillas
were resolved, how many required casillas are missing, and the findings that
block verification. Missing required casillas are values you must resolve before
export.

(supply-manual-casilla-values)=
## Supply manual casilla values

Use `--casilla` only for a box whose input kind is `manual`. Use the box number
printed on the official Agencia Estatal de Administración Tributaria (AEAT) form.
It is the same number you see on the paper or PDF
version of the modelo. Run `aeat app modelo casillas 130` to see the list (the
inspect sequence above shows this), and check the `input` column first.

`--casilla` works only on manual boxes. A `bound` box is filled through a
registry binding contract from an enrolled source resolver, so `--casilla`
refuses it with `cannot override bucket-derived
source-bound casillas` (for example, Modelo 130 box `02` Gastos is `bound`). Fix
the source instead. See [Supply a missing field value](#supply-a-missing-field-value).

A first-period filing also needs its prior-period bindings supplied (record them
as `0` when you have no prior figure). Supply the manual box and the bindings in
the same calculate call. This example sets box `06` (Retenciones e ingresos a
cuenta, a manual box) and seeds the three first-period bindings:

```{cli-sequence} review-values-manual-casilla
:verify: Confirm the manual box and first-period bindings calculate a draft.
```

Do not enter a box value without checking the list first. Read the label so
you know which field you are filling.

(supply-a-missing-field-value)=
## Supply a missing field value

When Cadrumo cannot fill a field automatically, the missing field appears in the
bindings list. Use the list to see which fields need your input, then supply
the value during calculation.

List every field the modelo binds, focus on the ones with no value yet, preview
what a value would produce without saving, then supply the first-period bindings
during calculation:

```{cli-sequence} review-values-bindings
:verify: Confirm the bindings list, preview, and calculation resolve the fields.
```


### Where a field's value comes from

The `bindings list` output shows, for each field, a `source` and a `readiness`
label. The `source` tells you who supplies the value; the `readiness` label
restates that source in plain language (for example, `ledger source` or `prior
filed revision`). Use the `source` to decide how to supply the value. The
common source categories are:

- **Profile fact** - Cadrumo fills it from your taxpayer profile, such as
  residence, declaration type, or family composition. Update your profile instead
  of entering the value manually.
- **Ledger source** - Cadrumo computes it by summing your classified transactions
  and invoices. You cannot override these; fix the ledger instead.
- **Prior filed revision** - carried forward from an earlier period you already
  filed in Cadrumo.
- **Relation** - folded in from another modelo's earlier figures. Supply it with
  `--relation KEY=VALUE` only when the modelo's help names the relation.
- **Manual** - this kind always needs you to type a value, with `--binding
  KEY=VALUE`, or `--casilla` for a box.

This reader-oriented list is not the complete `BindingSourceKind` reference.
Other modelos use additional typed sources, including invoice, withholding,
counterparty, and repeating-record families. Consult the binding listing for
the selected modelo instead of assuming that an unlisted source is manual.

A manual field always needs a value you enter by hand. A **prior filed revision**
field also needs one when there is no earlier filing yet to carry it forward.
See the first-time-filing note that follows. Profile and ledger fields are
filled from their sources. Relation fields may come from another filing or
require `--relation`, as identified by the modelo's help.

If you are filing for the first time and a field asks for a prior-period figure
you do not have, record it as zero, for example `--binding <field-id>=0`. Enter a
real prior figure only when you have one prepared outside Cadrumo.

### Régimen de atribución de rentas (socios)

If you are a socio, comunero, or partícipe of an entity in the régimen de
atribución de rentas (a sociedad civil, comunidad de bienes, or herencia
yacente), the entity files its own Modelo 184 in its own Cadrumo workspace. Your
personal Modelo 100 does not read across workspaces, so enter the attributed base
by hand.

Record the received share on your profile as `attribution_received` facts (entity
NIF, entity name, share percentage, attributed base, and filing year), then fold
the attributed base into your Modelo 100 régimen-de-atribución box with `--binding
<box>=<attributed-base>` when you run `aeat app modelo work calculate`. Cadrumo
warns you at verify time when the two halves disagree (facts recorded but the box
left empty, or a box value with no facts behind it), so a forgotten transcription
never files silently.

## Handle offsets and carry-forwards

Some modelos need prior-period values, credits, or compensation amounts. Do not
guess these from the current transaction ledger.

For Modelo 303 IVA compensation, inspect the local wallet, seed a first-period
opening balance, then correct it if you seeded the wrong amount:

```{cli-sequence} review-values-iva-wallet
:verify: Confirm the IVA compensation wallet seeds and corrects an opening balance.
```

Use `--amount 0` only for a true first Modelo 303 period with no previous IVA
compensation balance. Use a positive amount only when you have the pending
compensation amount from earlier Modelo 303 filings prepared outside this local
history.

Seeding refuses if a record already exists for the period. The correction
overwrites the seeded amount and records your `--reason` in an audit event. It refuses when no record exists for the period (seed it first) and
when an already-filed Modelo 303 has consumed the seeded basis. Correcting it
then would change a return you have already filed. In that case file a
complementaria instead (see [Correct an already filed local record](#correct-an-already-filed-local-record)).

For registry relation values, calculation accepts repeatable
`--relation KEY=VALUE` inputs. Use them only when the relevant modelo's
registry/help text identifies the relation you need:

```{cli-sequence} review-values-relation
:verify: Confirm the supplied relation value is recorded on the saved calculation.
```

## Add rows for list-based forms (184, 232, 347, 349)

Some informational modelos report a list of records rather than one set of boxes:
attribution members (Modelo 184), related-party operations (Modelo 232),
declared counterparties (Modelo 347), and intra-community operators (Modelo 349).
Supply each record with a repeatable `--row` input.

Each `--row` starts with the record type, followed by its fields:

```{cli-sequence} review-values-rows
:verify: Confirm the supplied member records save into the calculation.
```

Take the work-unit id from the `work_unit_id` field that `work create` prints.
For these multi-record modelos, pass the work-unit id as the positional argument
rather than the `--modelo / --year / --period` flags used elsewhere on this page.

Use one of these record types:

- `miembro` - an attribution member (Modelo 184).
- `vinculada` - a related-party operation (Modelo 232).
- `contraparte` - a declared counterparty (Modelo 347).
- `operador` - an intra-community operator (Modelo 349).

Cadrumo validates each row against the modelo's rules and refuses an incomplete
set:

- Modelo 184 - the members' `porcentaje` values must sum to 100.
- Modelo 347 - a counterparty's annual total must exceed 3,005.06 euros.
- Modelo 349 - the operator's intra-community NIF must match its country format.

The saved rows appear in the calculation output as `detail_row` lines. Check
them to confirm what was recorded.

Direct `--row` support is only one way repeating data can reach a calculation.
Modelo 720 foreign assets already use registry row-field bindings and an
enrolled resolver even though Modelo 720 is not in the direct `--row` allowlist
above. Do not treat the absence of a direct row command as an absent source
integration.

## Special calculation tools (IRPF comparison and exemptions)

For specialized calculations, the CLI provides evaluation and comparison commands:

- **Joint vs. individual Impuesto sobre la Renta de las Personas Físicas (IRPF)
  comparison (`compare-taxation`)**: Compare filing
  jointly as a family unit against filing individually for an active Modelo
  100. Create the Modelo 100 draft first, or the command refuses with
  `Ninguna unidad de trabajo activa`:

  ```{cli-sequence} review-values-m100-create
  :verify: Confirm the annual Modelo 100 draft exists for the filing year.
  ```

  
  ```{cli-sequence} review-values-compare-taxation
  ```
  
  This check does not save a draft. It shows the tax difference and a
  recommendation so you can decide which filing option costs less.

- **Maritime worker exemption preview (`preview-maritime-exemption`)**: Preview
  the IRPF exemption for maritime workers (Art. 7.p LIRPF or the Registro
  Especial de Buques y Empresas Navieras de Canarias (REBECA) 50% exemption):
  
  ```{cli-sequence} review-values-maritime
  :verify: Confirm the preview reports the RETMAR registration state.
  ```
  
  The command shows which tax boxes are affected by the exemption and the
  amounts, with references to the applicable law and the Régimen Especial de
  Trabajadores del Mar (RETMAR) registration state. This applies only to
  maritime workers. Most filers can skip this section.

(correct-an-already-filed-local-record)=
## Correct an already filed local record

If a filing was already uploaded and later needs correction, use the amendment
command. Do not recalculate the same period. That would not create the
correct complementaria (supplementary return) record:

```{cli-sequence} review-values-amend
```

Before using this command, import the {term}`justificante` for the filing you're
correcting. The amendment command does not submit anything to AEAT.

## Where to go next

- [Quickstart: produce a modelo file](quickstart.md)
- [The filing workflow](filing-spine.md)
- [How to prepare a Modelo 303 quarterly filing](modelo-303.md)
- [How to prepare the annual Modelo 390 summary](modelo-390.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [CLI reference](../cli/index.rst)
