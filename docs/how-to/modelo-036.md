# Record a Modelo 036 declaration you filed at AEAT

Modelo 036 is the AEAT census declaration - the form you use to register, update, or
deregister your tax situation. You file it yourself at AEAT's Sede Electrónica (the
sede), the official online portal. The commands on this page only record that fact
in your local audit trail afterwards - they never file anything at AEAT. To pull your
registered census facts from AEAT into your profile, see
[update your profile from AEAT census data](censo-update.md).

## Before you start

You need:

- An active profile - see [set up your taxpayer profile](profile-setup.md).
- The date you filed the declaration at the sede.
- Optional: the justificante - the receipt number the sede shows after you file.

## Record the declaration

Pick the command that matches what you filed:

- If you registered an activity, record an alta.
- If you changed registered facts, record a modificacion.
- If you deregistered, record a baja.

Record an alta:

```bash
aeat app modelo m036 alta --declared-on 2026-01-10 --sede-justificante <acuse>
```

Record a modificacion:

```bash
aeat app modelo m036 modificacion --declared-on 2026-03-15 --sede-justificante <acuse>
```

Record a baja:

```bash
aeat app modelo m036 baja --declared-on 2026-12-31 --sede-justificante <acuse>
```

`--declared-on` is required - the ISO date (year-month-day) you filed at the sede.
`--sede-justificante` is optional and accepts up to 128 characters. `--note` adds an
optional note for your own records, up to 512 characters.

## What success looks like

The command prints the saved record:

- A `declaration_id` - a long reference number for the record.
- The event kind - alta, modificacion, or baja.
- The declared-on date.
- When the record was saved.
- The justificante, if you gave one.

That printed output is your confirmation. Save it with your records.

## List and view recorded declarations

List the declarations you have recorded in the active profile:

```bash
aeat app modelo m036 list
```

The list shows each declaration's id, event kind, declared-on date, recorded-at
timestamp, and whether you gave a justificante. An empty list means you have recorded
no declarations yet.

View one declaration in full by its id (or an unambiguous prefix of it):

```bash
aeat app modelo m036 view <declaration-id>
```

The view shows the full record, including the justificante and your note if you gave
them. An id that matches no recorded declaration is refused.

No command edits or deletes a recorded declaration.

## If you typed something wrong

Re-running the command with identical values is safe - it records no additional
declaration, and you get the same declaration ID back.

Running the command with a corrected kind, date, or justificante records an
additional declaration. Add a `--note` explaining the correction so your audit trail
stays readable. Changing only `--note` does not create a new record. No command
edits or deletes a recorded declaration.

## What the record does and does not do

The record is a local note for your own audit trail. It does not change your filing
calendar, your obligations, or your profile facts.

After AEAT processes your declaration, bring your registered census facts into your
profile with the censo pull, compare, and apply commands - see
[update your profile from AEAT census data](censo-update.md).

## Where to get help

- If a command fails, see [troubleshooting](troubleshooting.md).
- For unfamiliar terms, see the {doc}`glossary </_generated/glossary>`.
- Before sharing command output with anyone, strip tax identifiers such as NIF, CIF,
  DNI, NIE, or NII.

## Next steps

- [Update your profile from AEAT census data](censo-update.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Check your filing calendar](filing-calendar.md)
- [CLI reference](../cli/index.rst)
