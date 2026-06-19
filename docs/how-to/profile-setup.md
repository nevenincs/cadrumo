# Set up your taxpayer profile

A profile holds the facts about one taxpayer that every `aeat app` command reads
and updates. Set one up before you import transactions, calculate a {term}`modelo`,
or export a filing.

A profile is local. Creating, editing, showing, exporting, or importing a
profile never submits anything to the Agencia Estatal de Administracion
Tributaria (AEAT). The tool builds and verifies your filing on your machine; you
upload it yourself.

If you haven't installed and run `aeat` yet, start with the
[quickstart](quickstart.md), then come back here.

## What the active profile means

The active profile is the taxpayer context for `aeat app` commands. While a
profile is active, commands such as ledger import, transaction classification,
modelo calculation, export, and local filing history read and update that
profile's data.

Keep one profile per taxpayer. Add a second profile when you prepare filings for
another taxpayer, separate a test profile from a real one, or restore a copy
under a different name. To understand why the tool is local-first and
human-gated, see the [explanation guides](../explanation/index.md).

List your profiles and see which one is active:

```bash
aeat config profile list
aeat config profile status
```

Switch to another taxpayer before working on it:

```bash
aeat config switch my-other-profile
```

Switching changes which local ledger, modelo drafts, and filing markers `aeat
app` commands use. The switch verb is `aeat config switch`, not `aeat config
profile switch`.

## Decide your facts before you start

Profile setup asks a series of questions. Most are conditional: the answers you
give early decide which later questions appear. Decide these facts first, and the
rest of setup follows:

- **Who the taxpayer is.** A natural person (an individual), a legal entity (a
  company such as an SL or SA), or an attribution entity (a co-ownership such as
  a *comunidad de bienes*, where income passes through to its members).
- **Which tax identifier applies.** Spanish citizens use their DNI as their tax
  identifier (NIF). Foreign individuals use their NIE. Companies use a NIF or
  CIF.
- **What the taxpayer does.** The economic activity and which kinds of income
  apply: business or professional activity, salaried work, rental income,
  investment income, capital gains, or a pension.
- **Which IVA regime applies.** IVA (Value Added Tax) determines whether the
  taxpayer charges and declares it, and how. The general regime files IVA
  through Modelo 303.
- **Where the taxpayer is resident.** The autonomous community for a Spanish
  resident, or the country of residence for a non-resident.
- **Which output language you want.** The language `aeat` uses for its output.

You don't need to memorize flag names. The guided wizard walks you through these
decisions. For the complete, current list of flags and their accepted values,
run:

```bash
aeat config profile create --help
aeat config profile edit --help
```

## Create your profile

Create a profile interactively, or non-interactively with flags.

Run the guided wizard when you're setting up a profile for the first time:

```bash
aeat config profile create my-profile
```

The wizard asks the questions described in this guide. Its prompt labels are
Spanish (for example `Tipo de entidad`, `Categorias de renta IRPF`), because
they mirror the AEAT forms; the values you choose are stable command tokens that
don't change with `--language`.

The wizard prompts for your master-key passphrase before it stores anything. In
a non-interactive shell, set `AEAT_SECRET_PASSPHRASE` first, or the command
refuses with `AEAT_SECRET_PASSPHRASE is not set`.

`aeat` prints its prompts, refusals, and error messages in Spanish. The output
blocks quoted below are English translations of those messages.

Use flags with `--quiet` when you want a repeatable, scriptable setup:

```bash
aeat config profile create my-profile --quiet --tax-id 12345678Z
```

`--quiet` runs without prompts and uses only the flags you provide. A `--quiet`
run refuses if a required flag is missing and tells you which one to add. The
tax identifier is the one value you must always provide:

```text
Refused. This --quiet run is missing required details. Add these flags and run
the command again: --tax-id.
```

Add `--accept-defaults` when you intentionally want `aeat` to fill the questions
you omit from its built-in defaults.

### Worked example: an individual freelancer

This example creates a minimal natural-person profile for a freelancer with an
economic activity:

```bash
aeat config profile create ana-2026 --quiet --accept-defaults \
  --entity-type natural_person \
  --tax-id 12345678Z \
  --name "Ana" --surnames "Garcia Lopez" \
  --irpf-income-categories actividad_economica \
  --activity "diseno grafico" \
  --iva-regime GENERAL \
  --tax-residence-ccaa madrid \
  --output-language en
```

Inspect and validate it before you rely on it:

```bash
aeat config profile show ana-2026
aeat config profile validate ana-2026
```

## The facts setup asks for

Setup groups its questions by decision area. These values are stable command
tokens: they're case-sensitive and don't translate. Run
`aeat config profile create --help` for the exhaustive flag list. It includes the
conditional spouse, family-unit, non-resident, and enrollment questions this
guide summarizes rather than repeats.

### Who the taxpayer is

Choose the entity type:

- `natural_person` - an individual.
- `legal_entity` - a company. Record its legal form too, such as `sl`, `sa`, or
  `cooperativa`.
- `attribution_entity` - a co-ownership or community of goods whose income is
  attributed to its members.

For a natural person, list each kind of income that applies, repeating the flag
once per category:

- `actividad_economica` - business or professional activity.
- `trabajo` - salaried employment.
- `capital_inmobiliario` - rental income from property.
- `capital_mobiliario` - investment income such as dividends or interest.
- `ganancias_patrimoniales` - capital gains.
- `pension` - a retirement or disability pension.

Choose `actividad_economica` only when the taxpayer runs an activity. A pure
landlord, a salaried-only taxpayer, or a pensioner with no activity should not
select it.

### Identity

The tax identifier (NIF, CIF, DNI, or NIE) is required. Spanish citizens use
their DNI as their NIF; foreign individuals use their NIE; companies use a NIF or
CIF. Record the name and surnames (or the entity's display name), the economic
activity when there is one, and the fiscal-address postcode.

### Where the taxpayer is resident

For a Spanish IRPF (personal income tax) resident, set the autonomous community
(`--tax-residence-ccaa`), such as `madrid` or `cataluna`.

This tool does not model the foral regimes. Setting the community to
`pais_vasco` or `navarra` is refused, because residents there file with their
*Hacienda Foral* under the *Concierto Económico*, not with the AEAT:

```text
Invalid value for '--tax-residence-ccaa': Residents in pais_vasco file with the
corresponding Hacienda Foral under the Concierto Económico (Ley 12/2002), not
with the AEAT. This CLI does not model foral declarations.
```

For a non-resident, choose `non_resident_irnr` and supply the country of
residence and, when required, a fiscal representative.

### Which IVA regime applies

Set `--iva-regime` to the taxpayer's IVA regime:

- `GENERAL` - the standard regime; files quarterly IVA through Modelo 303.
- `SIMPLIFICADO` - the simplified, module-based regime.
- `RECARGO_EQUIVALENCIA` - the equivalence surcharge for qualifying retailers.
- `REAGP` - the special regime for agriculture, livestock, and fishing.
- `EXENTO` - exempt activities, such as some education or healthcare.

Record any IVA enrollments that apply, such as ROI (intra-community operators) or
OSS (one-stop-shop for cross-border B2C sales).

### Which recurring obligations apply

These facts decide which forms the taxpayer must file. Record the ones that are
true:

- `--has-employees` or `--pays-professionals-with-retencion` - pays salaries or
  professional fees with withholding.
- `--pays-rent-with-retencion` - pays business-premises rent with withholding.
- `--does-intracomunitario` - trades with businesses in other EU countries.
- `--third-party-transactions-above-347-threshold` - transactions with third
  parties exceed the Modelo 347 threshold.
- `--bienes-extranjero-above-threshold` - foreign assets exceed the legal
  threshold.
- `--professional-income-withholding-ge-70pct` - at least 70 percent of
  professional income already had IRPF withholding. This removes the Modelo 130
  obligation for many freelancers, so record it when it's true. Set it together
  with `--pays-professionals-with-retencion`. Otherwise the setup verifier flags
  the pair as inconsistent.

Leaving an obligation flag unset is not the same as marking it false. When a
fact is undeclared, the readiness check reports the related form as *incomplete*
(cannot determine), not *not applicable*. Record each fact you know.

## Check your facts before you calculate

A wrong or missing fact produces a wrong filing. Confirm the profile before you
calculate a modelo.

Show the active profile's readiness summary:

```bash
aeat config profile status
```

Show the stored facts in full:

```bash
aeat config profile show
```

Validate the facts against the schema, which catches malformed or contradictory
values:

```bash
aeat config profile validate
```

Check whether the profile holds the facts a specific form needs, for a specific
filing context:

```bash
aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T
```

`preflight` names the missing fields for that `(modelo, filing-year, period)`
context. Use [Choose which modelo to file](choose-modelo.md) to find the period
codes a modelo accepts. Fix any wrong facts with `edit` before you continue.

## How your facts decide which forms apply

The profile facts you recorded determine which modelos the taxpayer must file.
Use this mapping to sanity-check your profile, then confirm a specific form with
`preflight`:

| When this is true of the taxpayer | These forms apply |
| --- | --- |
| Is a natural person | Modelo 100 (annual Renta) |
| Is a company | Modelo 200 (annual IS, corporate income tax), Modelo 202 (payments on account) |
| Runs an activity under direct estimation | Modelo 130 (quarterly IRPF) |
| Runs an activity under objective estimation (módulos) | Modelo 131 |
| At least 70% of professional income already had withholding | Removes the Modelo 130 obligation |
| Charges VAT under the general regime | Modelo 303 (quarterly), Modelo 390 (annual) |
| Pays employees or professionals with withholding | Modelo 111 (quarterly), Modelo 190 (annual) |
| Pays business-premises rent with withholding | Modelo 115 (quarterly), Modelo 180 (annual) |
| Trades with EU businesses | Modelo 349 |
| Has third-party transactions over the 347 threshold | Modelo 347 |
| Holds foreign assets over the legal threshold | Modelo 720 |

This is a guide, not the authority. The tool decides applicability from the full
profile and the registry rules. To see what applies to your profile, use
[Choose which modelo to file](choose-modelo.md).

## Maintain your profile

Edit a profile with the flags you want to change:

```bash
aeat config profile edit ana-2026 --quiet --address-postcode 28013
```

Run `show`, `status`, or `validate` again after editing.

Rename a profile when only the visible label should change. The active-profile
pointer follows the rename:

```bash
aeat config profile rename ana-2026 ana-real
```

Duplicate a profile to start a second one from the same facts. The second name
you pass is the new profile's name - the name you address it by in every later
command. The new profile becomes the active one:

```bash
aeat config profile duplicate ana-real ana-copy
```

Delete a profile only when you mean to remove it. Deletion is local and
irreversible. If the deleted profile was active, `aeat` clears the active-profile
pointer:

```bash
aeat config profile delete ana-copy --yes
```

Clear the active profile without deleting it:

```bash
aeat config profile logout
```

Export a profile to a portable JSON file:

```bash
aeat config profile export ana-real --to ./ana-real-profile.json
```

Import a profile into another session or storage root. Import under a fresh label
when one with the same name already exists. The imported profile becomes the
active one:

```bash
aeat config profile import ./ana-real-profile.json --label ana-restored
```

A portable profile file contains taxpayer data, including the tax identifier,
activity, and local filing history. Store it as sensitive tax data, and don't
attach it to a support request unless you've removed personal details.

## See what changed

Every change to a profile - creation, edits, imports, classifications,
calculations, and filings - is recorded as an event in that profile's
append-only history (a log you can read but not alter). Reading history needs an
active profile, so switch to it first if you ran `logout`. Browse it to see what
changed, when, and by which command:

```bash
aeat config profile history ana-real
```

Narrow a long history with filters, which combine:

```bash
aeat config profile history ana-real --event-type profile.renamed
aeat config profile history ana-real --since 2026-01-01 --until 2026-03-31
aeat config profile history ana-real --actor operator
```

Repeat `--event-type` to include several types. An unknown type is refused with
the full accepted list, so an empty value is a quick way to discover the
vocabulary.

A rename appears as two events on purpose: `profile.renamed` records that the
data changed, and `bucket.renamed` records that you ran the rename action. One
answers "what changed", the other "what was done".

## If setup looks wrong

If a command reports no active profile, an invalid field value, or that you're
working under the wrong profile, see
[Diagnose and repair your local setup](troubleshooting.md).

When the troubleshooting steps don't resolve it, follow
[Prepare a privacy-safe support request](troubleshooting.md) on that page. It
names the outputs to include and the personal data to leave out before you take
the issue to the project's issue tracker.

## Next steps

- [Work with transactions](import-bank-statements.md)
- [Link Modelo 036 census information](censo-update.md)
- [Plan your filing calendar](filing-calendar.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
