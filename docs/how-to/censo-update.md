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

Every command on this page needs your master-key passphrase; the tool
prompts for it. The tool's messages are in Spanish.

If you have no profile yet, create one non-interactively with `--quiet` (a bare
`profile create NAME` opens an interactive wizard instead):

```bash
aeat config profile create me --quiet --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" --activity "consultoria"
```

Check the active profile first:

```{cli-sequence} censo-update-check-profile
:verify: Confirm the active profile reports its status.
@step Check the active profile.
@result aeat --format json config profile status
@expect result.active_profile == "docs-sequence-sandbox"
@expect result.configured == true
@expect exit_code == 0
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
scripted update, pass the field flags with `--quiet`. Name your own profile in
place of `docs-sequence-sandbox`:

```{cli-sequence} censo-update-record-facts
:verify: Confirm the profile validates after you record the census facts.
@step Record the activity description from your Modelo 036 copy.
aeat --format json config profile edit docs-sequence-sandbox --quiet --activity "consultoria"
@step Confirm the edited profile still validates.
@result aeat --format json config profile validate
@expect exit_code == 0
```

Copy each value from your Modelo 036 copy or the AEAT sede exactly. Do not
guess a regime or a start date.

## Record a Modelo 036 filing done outside Cadrumo

If you file a Modelo 036 alta, modificacion, or baja in AEAT's sede, record
that fact locally so later filings can rely on it.
[Record a Modelo 036 declaration you filed at AEAT](modelo-036.md) owns the
commands, the success output, and what the record does and does not change.
After you record a filing, update the profile fields the filing changed.

## Check the profile afterwards

Validate the active profile after editing census facts:

```{cli-sequence} censo-update-validate
:verify: Confirm the active profile validates after the census edits.
@step Read the active profile status.
aeat --format json config profile status
@step Validate the active profile.
@result aeat --format json config profile validate
@expect result.valid == true
@expect exit_code == 0
```

If the profile still reports missing facts, edit those fields directly:

```bash
aeat config profile edit <profile-name> --quiet --activity <value>
```

For modelo-specific readiness, use profile preflight:

```{cli-sequence} censo-update-preflight
:verify: Confirm the profile preflight runs for the target modelo and period.
@step Run the profile readiness preflight for Modelo 303, first quarter of 2026.
@result aeat --format json config profile preflight --modelo 303 --filing-year 2026 --period 1T
@expect result.modelo == "303"
@expect exit_code == 0
```

## Keep the facts current

Your AEAT census can change - a new activity, a regime change, a baja. The
application cannot detect that drift. Re-check the profile against your latest
Modelo 036 copy whenever you file a censo change, and before you plan a new
filing year.

## Next steps

- [Set up your taxpayer profile](profile-setup.md)
- [Plan your filing calendar](filing-calendar.md)
- [Import and manage transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
