# Maintain Modelo 036 census facts in your profile

Use this guide to keep your AEAT census facts - the {term}`censo` - correct in
the active local profile. In Spain, the censo is tied to Modelo 036
registration and changes.

This guide covers Modelo 036. Modelo 037 is superseded and not used in this
workflow.

You enter census facts by hand. The tool does not read your censo from AEAT:
AEAT publishes no read-only census view, and the only sede surface that shows
census data is the census *modification* tool, which this application never
operates. The tool does not file Modelo 036, does not submit changes to AEAT,
and does not modify AEAT records.

## Before you start

You need:

- an active taxpayer profile; see [Set up your taxpayer profile](profile-setup.md)
- the taxpayer's fiscal ID (NIF, CIF, DNI, or NIE) saved in that profile
- your censo facts as AEAT holds them: activity description and start date,
  tax regime, IVA regime, and enrollment facts. Read them from your Modelo 036
  copy or from the AEAT sede.

Every command on this page needs your master-key passphrase. The tool prompts
for it, or set `AEAT_SECRET_PASSPHRASE` to run non-interactively. The tool's
messages are in Spanish.

If you have no profile yet, create one non-interactively with `--quiet` (a bare
`profile create NAME` opens an interactive wizard instead):

```bash
aeat config profile create me --quiet --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" --activity "consultoria"
```

Check the active profile first:

```bash
aeat config profile status
```

## Why census facts matter

Census facts drive profile-dependent workflows:

- the activity start date keeps the filing calendar from showing obligations
  before your registered activity start
- the tax regime, IVA regime, and Renta/IRPF regime select which modelos and
  which calculation paths apply
- enrollment facts feed the filing calendar's obligation derivation

Enter them carefully. The application treats your entries as
operator-declared facts, not as AEAT-verified facts. The filing calendar
reports census-dependent obligations with a `censo.enrolment_unverified`
warning and refuses strict projection until you accept that basis; see
[Plan your filing calendar](filing-calendar.md).

## Enter or correct census facts

Edit the active profile with the wizard:

```bash
aeat config profile edit <profile-name>
```

The wizard walks the profile fields, including the census-backed ones. For a
scripted update, pass the field flags with `--quiet`:

```bash
aeat config profile edit <profile-name> --quiet --activity "consultoria"
```

Copy each value from your Modelo 036 copy or the AEAT sede exactly. Do not
guess a regime or a start date.

## Record a Modelo 036 filing done outside aeat

If you file Modelo 036 in AEAT's sede, record that local fact separately:

```bash
aeat app modelo m036 alta --declared-on 2026-01-10 --sede-justificante <acuse>
aeat app modelo m036 modificacion --declared-on 2026-03-15 --sede-justificante <acuse>
aeat app modelo m036 baja --declared-on 2026-12-31 --sede-justificante <acuse>
```

These commands record that you filed the Modelo 036 alta, modificacion, or baja
through AEAT. They never file with AEAT themselves. After you record a filing,
update the profile fields the filing changed. For the flags, the success
output, and what the record does and does not change, see
[Record a Modelo 036 declaration you filed at AEAT](modelo-036.md).

## Check the profile afterwards

Validate the active profile after editing census facts:

```bash
aeat config profile status
aeat config profile validate
```

If the profile still reports missing facts, edit those fields directly:

```bash
aeat config profile edit <profile-name> --quiet --activity <value>
```

For modelo-specific readiness, use profile preflight:

```bash
aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T
```

## Keep the facts current

Your AEAT census can change - a new activity, a regime change, a baja. The
application cannot detect that drift. Re-check the profile against your latest
Modelo 036 copy whenever you file a censo change, and before you plan a new
filing year.

## Next steps

- [Set up your taxpayer profile](profile-setup.md)
- [Plan your filing calendar](filing-calendar.md)
- [Work with Transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
