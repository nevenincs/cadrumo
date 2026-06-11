# Find out which modelos apply to you

A modelo is a numbered official AEAT tax form, such as 303 for IVA or 130 for quarterly income-tax instalments. Use this guide to ask the tool whether a given modelo applies to you, and why. The tool computes the answer locally from your saved profile facts, so it's only as good as the profile you keep. For deadlines and what's due when, see the [filing calendar guide](filing-calendar.md).

## Before you start

You need:

- An active profile with your taxpayer type, activity, and regime facts filled in. See the [profile setup guide](profile-setup.md), or the [quickstart](quickstart.md) if you're starting from nothing.

Check the profile first:

```bash
aeat config profile status
```

The status confirms the profile exists and carries the basics. The explain output lists the facts that drive each applicability answer. If a fact is missing, the verdict says so.

## Ask whether one modelo applies

Run `overview explain` with the modelo code. By default the tool answers for the current year; to ask about a different year, add `--year`.

```bash
aeat app overview explain 303 --year 2026
```

The answer has four parts:

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

## When the verdict is incomplete

An incomplete verdict usually means the decision depends on facts your profile doesn't declare yet. The main groups:

- **Who you are** - your taxpayer type and entity form (an individual identified by NIF; a company identified by NIF or CIF; an entity in atribución de rentas).
- **Your income-tax situation** - your IRPF estimation regime and which income categories you receive.
- **Your IVA situation** - your IVA regime and any special enrolments, such as the ROI (Registro de Operadores Intracomunitarios), the OSS (One-Stop Shop), or intra-community operations.
- **Whether you employ or withhold** - employees on payroll, or withholdings on professional fees, rent, or capital payments.
- **Informative-declaration thresholds** - facts such as third-party transaction volume or assets held abroad, which gate the informative forms.

Fix the missing facts by hand with the [profile setup guide](profile-setup.md), or sync your censo - your AEAT census record, the registration data AEAT holds about your activities and obligations - with the [censo update guide](censo-update.md). Then re-run `overview explain` and read the new verdict.

## Check readiness for one filing

When you already know which modelo, year, and period you're aiming at, ask for a preflight check instead:

```bash
aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T
```

The preflight reports the profile facts still missing for that specific filing context. Where `overview explain` answers whether the form applies, preflight answers whether you're ready to work on it.

The preflight picks the active revision for that modelo, year, and period automatically. Add `--revision-id` only when you need to pin an exact past revision for replay.

## Browse the catalogue

To see every form the tool knows, list the catalogue. Add `--year` to narrow it to one fiscal year:

```bash
aeat app modelo list
aeat app modelo list --year 2026
```

The list shows each modelo's code, official Spanish title, cadence, tax domain, and revision count. Cadence values include `quarterly`, `annual`, `monthly`, `ad_hoc`, and `profile_based` (the rhythm depends on your situation). Domains include IVA, IRPF, IS (corporate income tax), censo, and informative. Being listed does not mean a form applies to you - the catalogue covers everything the tool understands.

To look one form up in detail:

```bash
aeat app modelo describe 303
```

The description shows the form's official name, domain, cadence, active revision ID, and valid period tokens. Keep both commands as lookup aids. Applicability always comes from `overview explain`.

## What these commands don't tell you

These commands read your local profile and the built-in rules only. They do not file, submit, or contact AEAT, and they cannot tell you what AEAT has actually received from you. A verdict of **Applicable** is a statement about the rules and your facts - not a confirmation that a filing exists or is pending.

- For AEAT's own view of your situation, see the [notifications guide](check-aeat-notifications.md).
- For deadlines and what's due when, see the [filing calendar guide](filing-calendar.md).

## Where to get help

If a verdict looks wrong or a command fails, see the [troubleshooting guide](troubleshooting.md). Unfamiliar terms are defined in the {doc}`glossary </_generated/glossary>`. Before you share command output to ask for help, remove personal tax identifiers such as your NIF, CIF, DNI, NIE, or NII.

## Next steps

- [Plan your filing deadlines](filing-calendar.md)
- [Set up or correct your profile](profile-setup.md)
- [Sync your official census facts](censo-update.md)
- [Start from nothing with the quickstart](quickstart.md)
- [Prepare Modelo 303](modelo-303.md)
- [Prepare Modelo 390](modelo-390.md)
- [Browse the full CLI reference](../cli/index.rst)
