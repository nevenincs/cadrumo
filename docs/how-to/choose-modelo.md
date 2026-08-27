# Find out which modelos apply to you

A modelo is a numbered official AEAT tax form, such as 303 for IVA or 130 for quarterly income-tax instalments. Use this guide to ask the tool whether a given modelo applies to you, and why. The tool computes the answer locally from your saved profile facts, so it's only as good as the profile you keep. For deadlines and what's due when, see the [filing calendar guide](filing-calendar.md).

## Before you start

You need:

- An active profile with your taxpayer type, activity, and regime facts filled in. See the [profile setup guide](profile-setup.md), or the [quickstart](quickstart.md) if you're starting from nothing.
- Your master-key passphrase. Every profile-scoped command needs it; the tool prompts for it.

Check the profile first with `aeat config profile status`. It confirms the profile exists and carries the basics. If a fact is missing, the verdict says so. The CLI emits the rationale, legal references, and refusals in Spanish.

## Ask whether one modelo applies

Run `overview explain` with the modelo code. By default the tool answers for the current year; to ask about a different year, add `--year`. The card below confirms the profile, asks whether Modelo 303 applies for 2026, then checks readiness for the first quarter, the whole diagnostic flow in order.

```{cli-sequence} choose-modelo-applicability
:verify: Confirm the tool reports whether Modelo 303 applies and whether the profile is ready to file it.
```

The explain answer has four parts:

- **The verdict** - whether the modelo applies to you for that year.
- **The rationale** - a plain-language explanation derived from the official rules.
- **The legal references** - the provisions the decision rests on. Use them to check the verdict or share it with an advisor.
- **The profile facts used** - exactly which of your saved facts the decision read. If one of those facts is wrong, the verdict is wrong too.

Some answers also include a scheduling note. Treat it as a pointer, not a calendar - the [filing calendar guide](filing-calendar.md) is the place for deadlines.

## What each verdict means

- **Applicable** - the form applies to you for that year. Plan to prepare and file it.
- **Not applicable** - your taxpayer situation excludes it. The rationale tells you which fact rules it out.
- **Attribution pass-through** - your entity is in régimen de atribución de rentas, such as a comunidad de bienes or a sociedad civil without a commercial object (sin objeto mercantil). The entity passes its income through to its members, so it doesn't file this self-assessment form itself. The members declare the attributed income on their own returns.
- **Incomplete** - the tool cannot decide and refuses to guess. Usually your profile is missing the facts needed; see [When the verdict is incomplete](#when-the-verdict-is-incomplete). For a few forms the tool has not yet derived an applicability rule. The rationale says so, and in that case no profile change alters the verdict.

(when-the-verdict-is-incomplete)=
## When the verdict is incomplete

An incomplete verdict usually means the decision depends on facts your profile doesn't declare yet. The main groups:

- **Who you are** - your taxpayer type and entity form (an individual identified by NIF; a company identified by NIF or CIF; an entity in atribución de rentas).
- **Your income-tax situation** - your IRPF estimation regime and which income categories you receive.
- **Your IVA situation** - your IVA regime and any special enrolments, such as the ROI (Registro de Operadores Intracomunitarios), the OSS (One-Stop Shop), or intra-community operations.
- **Whether you employ or withhold** - employees on payroll, or withholdings on professional fees, rent, or capital payments.
- **Informative-declaration thresholds** - facts such as third-party transaction volume or assets held abroad, which gate the informative forms.

Fix the missing facts by hand with the [profile setup guide](profile-setup.md). For your censo - your AEAT census record, the registration data AEAT holds about your activities and obligations - enter the facts from your Modelo 036 copy with the [censo facts guide](censo-update.md). Then re-run `overview explain` and read the new verdict.

## Check readiness for one filing

When you already know which modelo, year, and period you're aiming at, ask for a readiness check with `aeat app modelo readiness`, the closing frame of the card above.

Readiness reports what still stands between you and working on that specific filing: the profile facts still missing, the registry revision that applies, and any ledger rows that would block a calculation. Where `overview explain` answers whether the form applies, readiness answers whether you're ready to work on it.

These two commands read different facts, so they can disagree for the same profile and modelo, and that is expected. `overview explain` checks applicability facts (taxpayer type, regime, income categories); on a profile that has not declared its taxpayer type it returns `applicable false / verdict incomplete` ("el tipo de contribuyente no está declarado"). `modelo readiness` checks whether you can work on that period. A `ready` result is not a confirmation that the form applies to you - read `overview explain` for applicability and `modelo readiness` for filing readiness, not one as a proxy for the other.

Readiness reports several axes separately, and a complete profile is only one of them. A freshly set up profile commonly returns `profile_ready True` alongside `binding_ready False`: your own details are in place, but the figures the form pulls from - the sources listed under `missing_bindings` - are not yet available. Readiness exits with status `2` while any axis is unready, so read the axis that is `False` rather than the single overall verdict.

Readiness picks the active revision for that modelo, year, and period automatically. Add `--revision-id` only when you need to pin an exact past revision for replay; it is accepted only when it names the same revision the year and period already select.

## Browse the catalogue

To see every form the tool knows, list the catalogue with `aeat app modelo list`, add `--year` to narrow it to one fiscal year, then look one form up in detail with `aeat app modelo describe 303`:

```{cli-sequence} choose-modelo-catalogue
:verify: Confirm the catalogue lists the known forms and describes Modelo 303 in detail.
```

The list shows each modelo's code, official Spanish title, cadence, tax domain, and revision count. Cadence values include `quarterly`, `annual`, `monthly`, `ad_hoc`, and `profile_based` (the rhythm depends on your situation). Domains include `iva`, `irpf`, `is` (corporate income tax), `censo`, `informative`, `cross_tax`, `irnr` (non-resident income tax), `patrimonio` (wealth tax), and `iae` (tax on economic activities). Being listed does not mean a form applies to you - the catalogue covers everything the tool understands.

The description shows the form's official name (Spanish), domain, cadence, active revision ID, the full list of revision IDs, the valid period tokens, and three structure counts - casillas (boxes), vinculaciones (data bindings), and fórmulas (formulas) - that describe how complex the form is. Keep both commands as lookup aids. Applicability always comes from `overview explain`.

## What these commands don't tell you

These commands read your local profile and the built-in rules only. They do not file, submit, or contact AEAT, and they cannot tell you what AEAT has actually received from you. A verdict of **Applicable** is a statement about the rules and your facts - not a confirmation that a filing exists or is pending.

- For AEAT's own view of your situation, see the [notifications guide](check-aeat-notifications.md).
- For deadlines and what's due when, see the [filing calendar guide](filing-calendar.md).

## Where to get help

If a verdict looks wrong or a command fails, see the [troubleshooting guide](troubleshooting.md). Unfamiliar terms are defined in the {doc}`glossary </_generated/glossary>`. Before you share command output to ask for help, remove personal tax identifiers such as your NIF, CIF, DNI, NIE, or NII.

## Next steps

- [Plan your filing deadlines](filing-calendar.md)
- [Set up or correct your profile](profile-setup.md)
- [Maintain Modelo 036 census facts in your profile](censo-update.md)
- [Start from nothing with the quickstart](quickstart.md)
- [Prepare Modelo 303](modelo-303.md)
- [Prepare Modelo 390](modelo-390.md)
- [Browse the full CLI reference](../cli/index.rst)
