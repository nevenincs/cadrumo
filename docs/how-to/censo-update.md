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

```{cli-sequence} censo-update-create-profile
```

Check the active profile first:

```{cli-sequence} censo-update-check-profile
:verify: Confirm the active profile reports its status.
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

```{cli-sequence} censo-update-edit-wizard
```

The wizard walks the profile fields, including the census-backed ones. For a
scripted update, pass the field flags with `--quiet`. Name your own profile in
place of `docs-sequence-sandbox`:

```{cli-sequence} censo-update-record-facts
:verify: Confirm the profile validates after you record the census facts.
```

Copy each value from your Modelo 036 copy or the AEAT sede exactly. Do not
guess a regime or a start date.

(import-certificado-situacion-censal)=
## Import a Certificado de Situación Censal

The sede issues a *Certificado de Situación Censal* (procedure G313) that
states your census facts as AEAT holds them. Download it yourself from the
sede, then read it into your profile from the file. The first step previews;
the second records:

```{cli-sequence} censo-update-certificado-file
```

The command previews the census facts the certificate carries without writing
anything. Add `--apply` to record them onto the active profile.

Facts recorded this way carry a *non-official evidence* marker: they came from
a document you supplied, not from an AEAT-confirmed read, so profile views show
their provenance and the filing calendar's `censo.enrolment_unverified`
warning still applies. Where a certificate value disagrees with an answer you
gave in setup, the profile keeps a record of the divergence and
`aeat config profile show` warns you until you resolve it.

```{note}
Reading the certificate's contents is not yet active: the command currently
refuses every document while layout coverage for AEAT-issued certificates is
being completed, and tells you so. Until then, enter the facts by hand as
described above — the command's interface is stable and this page applies
unchanged once reading activates.
```

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
```

If the profile still reports missing facts, edit those fields directly:

```{cli-sequence} censo-update-edit-field
```

For modelo-specific readiness, use profile preflight:

```{cli-sequence} censo-update-preflight
:verify: Confirm the profile preflight runs for the target modelo and period.
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
