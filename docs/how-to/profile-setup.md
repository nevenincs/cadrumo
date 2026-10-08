# Set up your taxpayer profile

A profile holds the facts about one taxpayer that every `aeat app` command reads
and updates. Set one up before you import transactions, calculate a {term}`modelo`,
or export a filing.

A profile is local. Creating, editing, showing, exporting, or importing a
profile never submits anything to the Agencia Estatal de Administración
Tributaria (AEAT). Cadrumo builds and checks your filing on your machine; you
upload it yourself.

If you haven't installed Cadrumo and run the `aeat` command yet, start with the
[quickstart](quickstart.md), then come back here.

(what-the-active-profile-means)=
## What the active profile means

The active profile is the taxpayer context for `aeat app` commands. While a
profile is active, commands such as records import, transaction classification,
modelo calculation, export, and local filing history read and update that
profile's data.

Keep one profile per taxpayer. Add a second profile when you prepare filings for
another taxpayer, separate a test profile from a real one, or restore a copy
under a different name. To understand why the tool is local-first and
human-gated, see the [explanation guides](../explanation/index.md).

List your profiles with `aeat config profile list` and see which one is active.
Create each additional taxpayer interactively so its passphrase is chosen at
the terminal, then switch by exact name. The executable example checks the
current active-profile composition without fabricating another taxpayer:

```{cli-sequence} profile-setup-multiple
:verify: Confirm the profile list identifies the active taxpayer exactly.
```

Logging in changes which local records, modelo drafts, and recorded filings
`aeat app` commands use. The login verb is `aeat config login`, not `aeat config
profile login`.

Name the profile exactly. `aeat config login` accepts a profile UUID or the
label as `aeat config profile list` prints it (letter case is ignored), and
nothing else: a partial name
or a shortened form is refused rather than guessed at. Omit the name to log in
to the profile already selected. The refusal is deliberate - guessing which
taxpayer you meant is how filings end up under the wrong one.

Log out with `aeat config logout` when you finish. Logout closes the storage
session and keeps the selected profile. Log in again by name to reopen its
session. It deletes nothing.

## Decide your facts before you start

Profile setup asks a series of questions. Most are conditional: the answers you
give early decide which later questions appear. Decide these facts first, and the
rest of setup follows:

- **Who the taxpayer is.** A natural person (an individual), a legal entity (a
  company such as an SL or SA), or an attribution entity (a co-ownership such as
  a *comunidad de bienes*, where income passes through to its members).
- **Which tax identifier applies.** Spanish citizens use their DNI number plus
  letter as their tax identifier (NIF). Foreign individuals use their NIE.
  Companies use their own NIF, which older documents call the CIF.
- **What the taxpayer does.** The economic activity and which kinds of income
  apply: business or professional activity, salaried work, rental income,
  investment income, capital gains, or a pension.
- **Which VAT regime applies.** Value Added Tax (VAT) determines whether the
  taxpayer charges and declares it, and how. The general regime files VAT
  through Modelo 303.
- **Where the taxpayer is resident.** The autonomous community for a Spanish
  resident, or the country of residence for a non-resident.
- **Which output language you want.** The language `aeat` uses for its
  messages. See [Choose the output language](#choose-the-output-language).

You don't need to memorize flag names. The guided wizard walks you through these
decisions. For the complete, current list of flags and their accepted values,
run `aeat config profile create --help` and `aeat config profile edit --help`:

```{cli-sequence} profile-setup-flag-help
:verify: Confirm both flag listings run and name the active profile the flags apply to.
```

## Create your profile

Create a profile interactively, or non-interactively with flags.

Run the guided wizard when you're setting up a profile for the first time:

```{cli-sequence} profile-setup-interactive-create
```

The wizard is a full-page, question-by-question walk. Answer one page, move to
the next; go back to change an earlier answer at any time. The first page asks
for your output language. Answer it and the rest of the wizard renders in the
language you chose. The pages then walk your identity, fiscal residence,
economic activity, VAT, enrollment, family situation (including your
descendientes), recurring obligations, and service preferences, ending on a
review page that shows every answer before anything is saved. Questions are
conditional: the wizard only asks what applies to the answers you already gave.

Each page explains its choices and shows the expected format for dates,
amounts, and identifiers, and refuses an invalid value on the spot. A
malformed date or tax identifier never reaches your stored profile.

The wizard prompts for the profile passphrase before it stores anything. Once
the profile exists it asks whether to set up an optional recovery code, which
can reset a forgotten passphrase; answering no is the default and you can
enable it later. See [protect access to your
data](protect-data-access.md#set-up-a-recovery-code-optional).

For unattended runs, supply the passphrase through the machine channel
described in
[Run without a passphrase prompt](protect-data-access.md#run-without-a-passphrase-prompt);
recovery is never offered on that path.

### Choose the output language

`aeat` prints its messages in Spanish unless you choose another language. Add
`--language en` (or `es`, `ca`, `hu`) straight after `aeat` for one command, or
store a default for your profile:

```{cli-sequence} profile-setup-output-language
:verify: Confirm the profile stores English as its default output language.
```

The `CADRUMO_OUTPUT_LANGUAGE` environment variable sets the language for a whole
shell session and takes precedence over the profile default. The examples in
this documentation are recorded in English.

(save-and-resume)=
### Save now, finish later

A profile you stop setting up before it is complete keeps what you answered
and stays marked as setup-incomplete. After unlocking it,
`aeat config profile view` reports that setup state; `profile list`
deliberately reports only the saved names and which profile is active.

`create` refuses a name that already exists, so don't run it again to resume.
Log in with `aeat config login NAME`, supply the remaining facts with
`aeat config profile edit`, then run `aeat config profile complete-setup`. It
names anything still missing, and once nothing is, the profile is ready for
`aeat app` commands.

Use flags with `--quiet` when you want a repeatable, scriptable setup. The
[worked example](#worked-example-a-natural-person-with-an-activity) shows a
complete scripted create.

`--quiet` runs without prompts and uses only the flags you provide. It creates
the profile even when facts are missing, and leaves it marked setup-incomplete.
Add `--accept-defaults` to fill the questions you omit from their built-in
defaults. Facts without a default, such as the tax identifier, stay unset.

A scripted create does not open a session. Run `aeat config login NAME` next.
Once every required fact is set, run `aeat config profile complete-setup` to
declare the profile ready to file from. If facts are still missing, the command
refuses and names them.

(worked-example-a-natural-person-with-an-activity)=
### Worked example: a natural person with an activity

This scripted create sets up a natural-person profile for an individual with an
economic activity. It passes the passphrase through `--secrets-stdin` (see
[Run without a passphrase prompt](protect-data-access.md#run-without-a-passphrase-prompt)),
then declares setup complete after login:

```text
aeat config profile create NAME --quiet --secrets-stdin \
  --entity-type natural_person --tax-id <NIF> --name <NAME> --surnames <SURNAMES> \
  --activity "documentation examples" \
  --irpf-income-categories actividad_economica \
  --tax-residence-jurisdiction-scope common_regime --tax-residence-ccaa madrid \
  --iva-regime GENERAL --iva-m303-regime-composition general \
  --no-iva-redeme-enrolled --no-iva-cash-accounting-regime-enrolled \
  --no-iva-voluntary-sii-enrolled \
  --no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled
aeat config login NAME --secrets-stdin
aeat config profile complete-setup
```

The sequence starts from a similar profile that has no income category or
autonomous community yet. It inspects and validates the profile before you rely
on it:

```{cli-sequence} profile-setup-worked-example
:verify: Confirm the scripted create produces a natural-person profile that validates.
```

## The facts setup asks for

Setup groups its questions by decision area. These values are stable command
tokens: they're case-sensitive and don't translate. Run
`aeat config profile create --help` for the exhaustive flag list. It includes the
conditional spouse, family-unit, non-resident, and enrollment questions this
guide summarizes rather than repeats.

### Who the taxpayer is

Choose the entity type:

- `natural_person`: an individual.
- `legal_entity`: a company. Record its legal form too, such as `sl`, `sa`, or `cooperativa`.
- `attribution_entity`: a co-ownership or community of goods whose income is
  attributed to its members.

For a natural person, list each kind of income that applies, repeating the flag
once per category:

- `actividad_economica`: business or professional activity.
- `trabajo`: salaried employment.
- `capital_inmobiliario`: rental income from property.
- `capital_mobiliario`: investment income such as dividends or interest.
- `ganancias_patrimoniales`: capital gains.
- `pension`: a retirement or disability pension.

Choose `actividad_economica` only when the taxpayer runs an activity. A pure
landlord, a salaried-only taxpayer, or a pensioner with no activity should not
select it.

For an activity, record how IRPF estimates its yield with
`--irpf-estimation-regime`. Direct estimation (`directa_normal` or
`directa_simplificada`) files Modelo 130. The objective-estimation (módulos)
regime, `objetiva`, files Modelo 131 instead. Cadrumo does not assume a regime
when you leave it unset.

### Identity

The tax identifier is required. Spanish citizens use their DNI number plus
letter as their NIF; foreign individuals use their NIE; companies use their own
NIF. Record the name and surnames (or the entity's display name), the economic
activity when there is one, and the fiscal-address postcode.

### Where the taxpayer is resident

For a Spanish IRPF (personal income tax) resident, set the autonomous community
(`--tax-residence-ccaa`), such as `madrid` or `cataluna`.

This tool does not model the foral regimes. Setting the community to
`pais_vasco` or `navarra` is refused, because residents there file with their
*Hacienda Foral*, under the *Concierto Económico* (País Vasco) or the *Convenio
Económico* (Navarra), not with the AEAT:

```text
Refused. Residents in pais_vasco file with the corresponding Hacienda Foral
under the Concierto Económico (Ley 12/2002), not with the AEAT. This CLI does
not model foral declarations. See sede.bizkaia.eus (Bizkaia),
gipuzkoa.eus/ogasuna (Gipuzkoa), araba.eus/ogasun (Álava), or
hacienda.navarra.es (Navarra) depending on your territory.
```

For a non-resident, set `--fiscal-residency non_resident_irnr` (not
`--tax-residence-ccaa`), then supply the country of residence with
`--country-of-fiscal-residence` (an ISO 3166-1 alpha-2 code, such as `DE`) and,
when required, a fiscal representative with `--representante-fiscal-nif` and
`--representante-fiscal-nombre`.

(which-iva-regime-applies)=
### Which VAT regime applies

Set `--iva-regime` to the taxpayer's VAT regime:

- `GENERAL`: the standard regime; files quarterly VAT through Modelo 303.
- `SIMPLIFICADO`: the simplified, module-based regime.
- `RECARGO_EQUIVALENCIA`: the equivalence surcharge for qualifying retailers.
- `REAGP`: the special regime for agriculture, livestock, and fishing.
- `EXENTO`: exempt activities, such as some education or healthcare.

Record any VAT enrollments that apply, such as ROI (intra-community traders) or OSS (one-stop-shop for cross-border B2C sales).

### Which recurring obligations apply

These facts decide which forms the taxpayer must file. Record the ones that are
true:

- `--has-employees` or `--pays-professionals-with-retencion`: pays salaries or professional fees with withholding.
- `--pays-rent-with-retencion`: pays business-premises rent with withholding.
- `--does-intracomunitario`: trades with businesses in other EU countries.
- `--third-party-transactions-above-347-threshold`: transactions with third
  parties exceed the Modelo 347 threshold.
- `--bienes-extranjero-above-threshold`: foreign assets exceed the legal
  threshold.
- `--art109-activity-income-withholding-ge-70pct`: the Art. 109 RIRPF 70 percent income-coverage exception applies for covered professional, agricultural, livestock, or forestry activity income. For activity starts, record the coverage fact for the current payment period.

Leaving an obligation flag unset is not the same as marking it false. When a
fact is undeclared, the readiness check reports the related form as *incomplete*
(cannot determine), not *not applicable*. Record each fact you know.

## Check your facts before you calculate

A wrong or missing fact produces a wrong filing. Confirm the profile before you
calculate a modelo. The example shows the active profile's readiness summary and
stored facts, validates them against the schema, then reports whether the
profile is ready to file one modelo for one year and period:

```{cli-sequence} profile-setup-inspect
:verify: Confirm the active profile's facts validate and see what a specific filing still needs.
```

`aeat app modelo readiness` checks one modelo, filing year, and period. Here the
profile is ready (`profile_ready` is true), but the Modelo 303 source inputs are
not (`binding_ready` is false), so the command exits with status 2. Use
[Find out which modelos apply to you](choose-modelo.md) to find the period codes a
modelo accepts. Fix any wrong facts with `edit` before you continue.

## How your facts decide which forms apply

The profile facts you recorded determine which modelos the taxpayer must file.
Use this mapping to sanity-check your profile, then confirm a specific form with
`aeat app modelo readiness`:

| When this is true of the taxpayer | These forms apply |
| --- | --- |
| Is a natural person | Modelo 100 (annual Renta) |
| Is a company | Modelo 200 (annual IS, corporate income tax), Modelo 202 (payments on account) |
| Runs an activity under direct estimation | Modelo 130 (quarterly IRPF) |
| Runs an activity under objective estimation (módulos) | Modelo 131 |
| Art. 109 activity-income coverage exception applies | Removes the Modelo 130 obligation |
| Charges VAT under the general regime | Modelo 303 (quarterly), Modelo 390 (annual) |
| Pays employees or professionals with withholding | Modelo 111 (quarterly), Modelo 190 (annual) |
| Pays business-premises rent with withholding | Modelo 115 (quarterly), Modelo 180 (annual) |
| Trades with EU businesses | Modelo 349 |
| Has third-party transactions over the 347 threshold | Modelo 347 |
| Holds foreign assets over the legal threshold | Modelo 720 |

This is a guide, not the authority. The tool decides applicability from the full
profile and the tax rules. To see what applies to your profile, use [Choose
which modelo to file](choose-modelo.md).

(modify-your-profile)=
## Modify your profile

Re-run the wizard over an existing profile to change its facts:

```{cli-sequence} profile-setup-edit-wizard
```

Edit mode walks the same pages with your current answers in place. Change what
you need, then confirm the review page. Nothing is written until you confirm:
changes are held until you confirm, and an interrupted edit discards them all.
There is no save-and-exit in edit mode. Finish the walk in one sitting. The
tool tells you both things at the end of every interactive edit, so an edit
never silently half-applies.

Descendientes are not part of profile edit. Manage them with the
[descendiente command](#manage-your-descendants). The edit summary
reminds you of this every time.

For a scripted change, pass `--quiet` with only the flags you want to change;
every fact you don't name stays as it was.

(manage-your-descendants)=
## Manage your descendants

Descendientes drive the *mínimo por descendientes* in the annual Renta.
Declare them during first-time setup; manage them afterwards with the
`descendiente` command.

Open the paged descendant editor:

```{cli-sequence} profile-setup-descendiente-door
```

The editor shows your declared descendientes, lets you change any answer, add
one, or reduce the count, and saves the complete set when you confirm. Reducing
the count removes the descendientes beyond it. The stored set always matches
exactly what you confirmed.

Script the same changes with the flag verbs:

```{cli-sequence} profile-setup-descendiente-verbs
:verify: Confirm the descendiente count returns to zero after the removal.
```

`add` takes one `--descendiente` per child as `KEY=VALUE` pairs separated by
commas. `NACIMIENTO` (birth date, `AAAA-MM-DD`) is required. Optional keys
include `RELACION` (`descendiente`, `adoptado`,
`acogimiento_preadoptivo_o_permanente`, `acogimiento_temporal`, or `tutela`),
`INSCRIPCION`, `DISCAPACIDAD` (`0`, `33`, or `65`), `CONVIVENCIA`, `CUSTODIA`,
`MESES_TRABAJO`, `GASTOS_GUARDERIA`, and `NIF`. Run
`aeat config profile descendiente add --help` for the full list. A descendiente
without a tax identifier is fine. Leave `NIF` out. `remove` takes the position
from `list`, counting from `0`.

`MESES_TRABAJO` names *which* months the mother worked, not how many. Write a
month as two digits, a run as `MM-MM`, and separate entries with `;`. Write
`MESES_TRABAJO=05-08` for May to August. Write `MESES_TRABAJO=01;03;09-12` for
January, March, and September to December.

Name the months. The guardería increment counts only the months the mother
worked *and* the child attended, so a count cannot say whether the two overlap.

## Maintain your profile

The following steps edit a fact and back up the profile to a sealed archive:

```{cli-sequence} profile-setup-maintain
:verify: Confirm the profile survives an edit and a sealed archive backup.
```

What each step does:

- **Edit** re-runs the wizard, or changes only the flags you pass with
  `--quiet`. See [Modify your profile](#modify-your-profile). Run `view`,
  `status`, or `validate` again after editing.
- **Archive export** writes a sealed, encrypted copy of the profile. The target
  filename must end with `.cadrumo-bucket.tar.gz`. The archive is encrypted with
  the profile passphrase and does not carry the profile label. Restore it with
  `aeat config profile archive import`, naming the profile and passing the
  archive with `--file`, and read a sealed
  archive's header without decrypting it using
  `aeat config profile archive inspect --file ARCHIVE`.

A sealed archive contains taxpayer data, including the tax identifier, activity,
and local filing history. Store it as sensitive tax data, and don't attach it to
a support request. See [import, export, and supporting
documents](../reference/import-export-and-evidence.md).

## Choose your service capabilities

Each profile carries its own opt-in for three optional services. The setup
wizard asks these questions when you create or edit a profile, and you can
change them at any time. These steps show the current posture, turn one
capability off, then show the posture again:

```{cli-sequence} profile-setup-capabilities
:verify: Confirm a capability change updates the active profile.
```

The three capabilities are:

- `cloud_evidence_upload`: allow sending sensitive supporting documents to a
  cloud LLM provider. Off by default. Barred for gestor profiles.
- `llm_vision`: read invoices with the on-host vision model. On by default.
- `google_export`: export calculations to Google Sheets. On by default.

Turn any capability on or off with `aeat config profile capabilities set`.
The example turns `llm_vision` off. Pass `cloud_evidence_upload on` to enable
cloud upload. A capability whose package extra is missing needs that extra
installed; see [Install Cadrumo](../workstation-setup.md) for the extras.

Sign out without deleting the profile using `aeat config logout` after the
login-gated maintenance and capability checks above. Logout revokes this
profile's shared human sign-in and closes its human sessions. The profile stays
selected; subsequent commands require fresh authentication. Enrolled API
credentials keep their separate authority:

```{cli-sequence} profile-setup-logout
:verify: Confirm logout closes the active session without deleting the profile.
```

## See what changed

Every change to a profile - creation, edits, imports, classifications,
calculations, and filings - is recorded as an event in that profile's
append-only history (a log you can read but not alter). Reading history needs an
open session, so log in to the profile first. The example lists the filters
`aeat config profile history` accepts:

```{cli-sequence} profile-setup-history
:verify: Confirm the history command lists its filters.
```

Repeat `--event-type` to include several types. Narrow the window with `--since`
and `--until`, or match one record with `--object-id` or `--actor`. An unknown
type is refused with the full accepted list, so an empty value is a quick way to
discover the vocabulary.

## Delete a profile permanently

Close the profile's sign-in before deleting it. Logout keeps that profile
selected, and Cadrumo refuses to delete the selected profile. Log in to another
existing profile to change the default selection, then confirm the irreversible
deletion of the original named profile. The example assumes
`docs-sequence-replacement` already exists; login asks for its passphrase.
It comes after every operation on the original profile because that profile
cannot be used again:

```{cli-sequence} profile-setup-delete
:verify: Confirm another profile is selected before deleting only the original named profile.
```

## If setup looks wrong

If a command reports no active profile, an invalid field value, or that you're
working under the wrong profile, see
[Diagnose and repair your local setup](troubleshooting.md).

When the troubleshooting steps don't resolve it, follow
[Prepare a privacy-safe support request](troubleshooting.md#prepare-a-privacy-safe-support-request).
It
names the outputs to include and the personal data to leave out before you take
the issue to the project's issue tracker.

## Next steps

- [Import and manage transactions](import-bank-statements.md)
- [Maintain Modelo 036 census facts in your profile](censo-update.md)
- [Plan your filing calendar](filing-calendar.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
