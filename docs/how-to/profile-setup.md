# Set up your taxpayer profile

Use this guide to create and maintain the taxpayer profile that `aeat app`
commands use. A profile is local. Creating, editing, showing, exporting, or
importing a profile does not submit anything to the Agencia Estatal de
Administracion Tributaria (AEAT).

## What the active profile means

The active profile is the taxpayer context for `aeat app` commands. When a
profile is active, commands such as ledger import, transaction classification,
modelo calculation, export, and local filing history read and update that
profile's local data.

Use one profile per taxpayer or distinct taxpayer context. You might keep
several profiles when you prepare filings for more than one taxpayer, separate a
test profile from a real profile, or import a restored copy under a different
name.

List profiles and see which one is active:

```bash
aeat config profile list
aeat config profile status
```

Switch before working on another taxpayer by unlocking that profile:

```bash
aeat config unlock my-other-profile
```

Switching changes which local ledger, modelo drafts, and filing markers `aeat
app` commands will use.

## Choose the setup mode

Use non-interactive flags when you want a repeatable setup:

```bash
aeat config profile create my-profile --quiet --tax-id 12345678Z
```

`--quiet` runs without prompts and uses only the flags you provide. Add
`--accept-defaults` only when you intentionally want `aeat` to fill omitted
questions from automatic configuration defaults.

You can also run:

```bash
aeat config profile create my-profile
```

That interactive path asks the same profile questions described below. Use the
sections below to decide each answer before you rely on the profile.

The visible prompt labels are Spanish. They include `Tipo de entidad`, `Forma
juridica`, `Categorias de renta IRPF`, net-turnover and new-entity questions,
tax id, visible name, surnames or business name, economic activity, fiscal
postcode, filing-obligation start date, taxation type code, CLI output
language, and conditional sex, marital, family, spouse, IVA, withholding,
residency, and notes questions. The exact prompt list depends on earlier
answers.

For the exact current flag names, enum values, and command-generated help text,
run:

```bash
aeat config profile create --help
aeat config profile edit --help
```

## Profile setup questions

The profile command groups questions by topic. Some questions are conditional:
for example, spouse questions apply to natural-person joint declarations, and
legal-entity form applies to legal entities.

### Taxpayer Type

`--entity-type`
: Choose `natural_person`, `legal_entity`, or `attribution_entity`. Natural
  persons are individuals. Legal entities cover companies such as SL or SA.
  Attribution entities cover property co-owners and communities of goods
  (Comunidades de Bienes) where income is attributed across members.

`--legal-entity-form`
: Use this only for a legal entity. It records the legal form such as `sl`,
  `sa`, `sal`, `sll`, `cooperativa`, `sociedad_civil_mercantil`,
  `sin_fines_lucrativos`, or `other`.

`--irpf-income-categories`
: Use this for a natural person (individual taxpayer). Repeat it for each IRPF income category that applies:
  * `actividad_economica` — Business or professional activity (such as individual freelancer, company economic activity, or sole proprietor income)
  * `trabajo` — Salaried employment (ordinary payroll income)
  * `capital_inmobiliario` — Real estate rental income (renting out houses, flats, or premises)
  * `capital_mobiliario` — Investment income (dividends, bank interest, etc.)
  * `ganancias_patrimoniales` — Capital gains (selling shares, property, cryptocurrency, etc.)
  * `pension` — Retirement or disability pension
  Do not select `actividad_economica` for a pure landlord, salaried-only taxpayer, or pensioner who has no economic activity.

`--incn-prior-12-months`
: Optional net turnover (INCN — *Importe Neto de la Cifra de Negocios*) for the previous 12 months. It matters for corporate tax contexts such as Modelo 202 modality checks.

`--new-entity-first-two-profit-periods` / `--no-new-entity-first-two-profit-periods`
: Legal-entity fact for the first two profit-making periods. Use the positive
  flag only when the reduced-rate condition applies; use the negative flag when
  you want to explicitly record that it does not.

### Identity and Display

`--tax-id`
: The taxpayer identifier (NIF, CIF, DNI, NIE, or NII). Spanish citizens use
  their DNI number as their tax identifier (NIF); foreign individuals use
  their NIE number as theirs; companies or legal entities use a NIF or CIF;
  certain foreign entities or EU operators use NII or NIF-IVA.
  This is the only unconditionally required creation flag in non-interactive mode.

`--name` and `--surnames`
: The person's name and surnames, or the entity's display name where the
  command asks for it. These values can appear in local output and export
  headers.

`--activity`
: Free-text economic activity or IAE heading. The setup flow asks for this only
  when the taxpayer actually has an economic activity, such as a legal entity or
  a natural person with `actividad_economica`.

`--address-postcode`
: Fiscal-address postcode. Use a Spanish postcode for the taxpayer's fiscal
  address when applicable.

`--activity-start-date`
: Optional census/activity start date in `YYYY-MM-DD` format. When set, the
  filing calendar can avoid showing obligations for periods before activity
  registration.

`--taxation-type`
: Renta declaration type for a natural person: `1` for individual, `2` for
  joint family-unit filing.

`--output-language`
: CLI output language for the profile. Current supported values are `es`, `en`,
  `ca`, and `hu`.

### First Declarant

These questions apply to natural-person profiles.

`--taxpayer-sex`
: Modelo/Renta sex code, `H` or `M`, when the target modelo needs it.

`--taxpayer-marital-status`
: Renta marital-status code: `1` single, `2` married, `3` widowed, `4`
  separated or divorced.

`--situacion-familiar`
: Family situation for IRPF rules, such as married, registered partnership,
  unregistered partnership, single, or separated/divorced. This is not the same
  as the form marital-status code; it helps determine family-unit eligibility.

`--taxpayer-marriage-date`
: Current marriage start date in `YYYY-MM-DD` format. The setup flow asks for
  it only when marital status is married.

`--taxpayer-birth-date`
: Birth date of the first declarant.

`--taxpayer-disability-grade`
: Disability-grade code when applicable.

`--taxpayer-death-date`
: Death date when filing for a deceased taxpayer context.

### Spouse

Spouse questions apply when the natural-person profile is set up for a joint
declaration path.

`--spouse-tax-id`
: Spouse NIF/NIE. Required for joint declaration contexts.

`--spouse-name`, `--spouse-surnames`, `--spouse-birth-date`, `--spouse-sex`,
`--spouse-disability-grade`
: Spouse personal facts used by Renta-related calculations and exports where
  applicable.

`--spouse-non-resident-irpf`
: Mark this when the spouse is non-resident for IRPF.

`--spouse-eu-eea-resident`
: Mark this when the non-resident spouse is resident in the EU/EEA.

`--spouse-eu-eea-country`
: EU/EEA country code for that spouse context.

### Family Unit

`--family-descendants-eu-eea-deduction`
: Mark when descendants in the EU/EEA affect the family-unit deduction.

`--family-minor-children-in-unit`
: Mark when minor children are part of the family unit.

### IVA

`--iva-regime`
: IVA (Value Added Tax) regime for the taxpayer activity. Common values include:
  * `GENERAL` — General regime (standard quarterly VAT declarations via Modelo 303).
  * `SIMPLIFICADO` — Simplified regime (based on modules/activities rather than real invoices).
  * `RECARGO_EQUIVALENCIA` — Equivalence Surcharge (obligatory for retailers selling directly to end-consumers without modifying the product).
  * `REAGP` — Special regime for Agriculture, Livestock, and Fisheries.
  * `EXENTO` — Exempt from VAT (for activities like education or healthcare).

`--iva-roi-enrolled`
: Mark if the taxpayer is registered in ROI (Registro de Operadores Intracomunitarios / VIES) to perform VAT-exempt transactions with businesses in other EU countries.

`--iva-oss-enrolled`
: Mark if the taxpayer is registered in OSS (One Stop Shop) for declaring and paying VAT on B2C electronic services or distance sales within the EU.

`--iva-sii-enrolled`
: Mark if the taxpayer is registered in SII (Suministro Inmediato de Información) for near-real-time electronic invoice reporting (obligatory for large companies).

`--iva-redeme-enrolled`
: Mark if the taxpayer is registered in REDEME (Registro de Devolución Mensual) to request VAT refunds on a monthly basis rather than annually.

`--iva-intracommunity-operations-exceed-50000-eur`
: Mark when intracommunity operations exceed the €50,000 threshold.

### Enrollment

`--enrollment-large-company`
: Mark when the taxpayer is a large company for filing-obligation purposes.

`--enrollment-public-administration-budget-gt-6000000`
: Mark when the public-administration budget threshold applies.

### Obligations

Use these flags to record which recurring obligations apply to the taxpayer.
They influence calendars, applicability checks, and modelo readiness.

`--has-employees`
: The taxpayer has employees and pays salaries with withholding. Checking this triggers the obligation to file **Modelo 111** (quarterly tax withholding for employees).

`--pays-professionals-with-retencion`
: The taxpayer pays professionals (e.g. business consultants, lawyers, independent freelancers) with withholding. Checking this triggers the obligation to file **Modelo 111**.

`--professional-income-withholding-ge-70pct`
: At least 70 percent of your professional income has prior tax withholding. **Checking this is very important for individual freelancers and sole proprietors: if at least 70% of professional invoices are issued with IRPF withholding, the taxpayer is legally exempt from filing and paying the quarterly Modelo 130 payments-on-account.**

`--pays-rent-with-retencion`
: The taxpayer pays rent for a business premises or office with tax withholding. Checking this triggers the obligation to file **Modelo 115** (quarterly premise rent withholding).

`--pays-capital-income-with-retencion`
: The taxpayer pays capital income with withholding.

`--uses-objective-estimation-irpf`
: The taxpayer uses IRPF objective estimation.

`--irpf-estimation-regime`
: IRPF estimation regime for economic activity, such as direct normal, direct
  simplified, or objective estimation. Current CLI tokens include
  `directa_normal`, `directa_simplificada`, and `objetiva`.

`--irpf-special-regime`
: IRPF special regime, normally `general`; use `impatriado` only for the
  documented displaced-worker regime context.

`--irpf-special-regime-start-date`
: Start date for the special regime, when `impatriado` applies.

`--does-intracomunitario`
: The taxpayer performs intracommunity operations.

`--third-party-transactions-above-347-threshold`
: Transactions with third parties exceed the Modelo 347 threshold.

`--bienes-extranjero-above-threshold`
: Foreign assets exceed the legal threshold.

### Fiscal Residence

`--fiscal-residency`
: Choose `resident_irpf` for ordinary Spanish IRPF residence, or
  `non_resident_irnr` for non-resident IRNR taxation.

`--country-of-fiscal-residence`
: ISO country code for non-resident contexts.

`--representante-fiscal-nif` and `--representante-fiscal-nombre`
: Fiscal representative details when required for a non-resident context.

`--tax-residence-ccaa`
: Autonomous community (*Comunidad Autónoma* — CCAA) for Spanish IRPF residents. The setup flow does not use
  this for non-resident IRNR profiles. The active implementation accepts common
  regime CCAA values; `pais_vasco` and `navarra` are refused with the foral
  regime message.

### Notes

`--notes`
: Optional local notes for your own memory. Treat this as sensitive text; do
  not store secrets, certificate material, bank credentials, or full personal
  documents here.

## Create a practical freelancer profile (Persona Tutorial)

To make the setup concrete, this tutorial assumes a specific filing persona: Ana Garcia Lopez, an individual freelancer. This example creates a minimal natural-person profile with economic activity:

```bash
aeat config profile create ana-2026 --quiet --accept-defaults --entity-type natural_person --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" --irpf-income-categories actividad_economica --activity "diseno grafico" --iva-regime GENERAL --tax-residence-ccaa madrid --output-language en
```

Then inspect and validate it:

```bash
aeat config profile show ana-2026
aeat config profile validate ana-2026
```

Fix any wrong facts before you import transactions or calculate a modelo.

## Edit an existing profile

Use `edit` with the profile name and the flags to change:

```bash
aeat config profile edit ana-2026 --quiet --address-postcode 28013
aeat config profile edit ana-2026 --quiet --iva-regime GENERAL
```

Run `show`, `status`, or `validate` again after editing.

## Check modelo-specific readiness

General validation checks the correctness of your profile fields:

```bash
aeat config profile validate
```

Modelo-specific readiness checks whether the profile contains the facts a
particular modelo needs. Run it before calculating:

```bash
aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T
```

Use `aeat app modelo describe MODELO` to see available period codes for that
modelo.

## Rename, duplicate, delete, and remove profiles

Rename a profile when only the visible label should change:

```bash
aeat config profile rename ana-2026 ana-real
```

Duplicate a profile when you want a second local profile that starts from the
same facts:

```bash
aeat config profile duplicate ana-real ana-copy --display-name "Ana copy"
```

Delete a profile only when you mean to remove it from normal use:

```bash
aeat config profile delete ana-copy --yes
```

Deletion is local and destructive. The profile is removed from ordinary list,
switch, and app workflows. If it was active, `aeat` clears the active profile
status.

Clear the active profile without deleting it:

```bash
aeat config profile logout
```

## Export and import a profile

Export writes a portable JSON package:

```bash
aeat config profile export ana-real --to ./ana-real-profile.json
```

Import a package into another session or another storage root:

```bash
aeat config profile import ./ana-real-profile.json
```

If a profile with the same label already exists, import under a new visible
name:

```bash
aeat config profile import ./ana-real-profile.json --label ana-restored
```

Portable profile files contain taxpayer data including your tax identifier,
activity, and local filing history. Store them as sensitive tax data and do
not send them in support requests unless you have removed personal details.

## Show profile contents and privacy notes

Display the active profile:

```bash
aeat config profile show
```

Display a named profile:

```bash
aeat config profile show ana-real
```

`profile show` is meant for local review. The normal CLI rendering hides tax
IDs but can still show names, activity, residence, regime, and other personal
facts. If you need to share profile information for support, share only the
specific field names and non-sensitive values.

## If setup looks wrong

If a command reports that no profile is active, a field value is invalid, or you
are working under the wrong profile, use
[Diagnose and repair your local setup](troubleshooting.md).

## Next steps

- [Work with Transactions](import-bank-statements.md)
- [Link Modelo 036 census information](censo-update.md)
- [Plan your filing calendar](filing-calendar.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
