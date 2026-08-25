# Maintain Modelo 036 census facts in your profile

Use this guide to keep your AEAT census facts - the {term}`censo` - correct in
the active local profile. In Spain, the censo is tied to Modelo 036
registration and changes.

This guide covers Modelo 036. Modelo 037 is superseded and not used in this
workflow.

You fill census facts three ways: pull them from AEAT, read them from a
certificate you downloaded, or enter them by hand. The pull reads AEAT's own
*Mis Datos Censales* consulta and fills your identity and address; it cannot
reach the regime facts, so you enter those yourself.

The tool never files Modelo 036, never submits changes to AEAT, and never
modifies AEAT records. The pull reads and stops there.

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

## Pull your census facts from AEAT

AEAT publishes your current census position at *Mis Datos Censales*. Pull it
into the active profile. The first step previews; the second performs a new
authenticated read and records that read's eligible facts:

```{cli-sequence} censo-update-censo-pull
```

Nothing is written until you add `--apply`.

```{warning}
The current CLI does not turn the first command's preview into a saved approval.
The `--apply` command reads AEAT again and applies that new observation. Review
the `--apply` result itself before relying on the updated profile. Work is in
progress to expose the application's captured, exact-baseline reviewed-apply
lifecycle on this command; until that lands, do not treat the earlier preview
as the operand that was applied.
```

Authenticate first; see
[Authenticate with AEAT](authenticate-with-aeat.md). The pull reads your own
record and takes your fiscal ID from the authenticated session, so you cannot
point it at another taxpayer.

### What the pull reports

Every field comes back as one of three outcomes.

**Adopted**: the profile had no answer, or the value came from an earlier
censal read, so `--apply` writes AEAT's current value. A preview only reports
what would be eligible.

**Unchanged**: you and AEAT already agree.

**Diverging**: you and AEAT disagree. The pull reports the difference and
writes nothing. You decide which is right, then correct the profile or your
censo. A value you declared is never overwritten. A field you deliberately
cleared stays cleared, and the pull tells you AEAT still holds a value for it.

Once the pull has filled a blank field, a later pull refreshes that same field
when AEAT's value changes. It filled it, so it may update it. Anything you
declared yourself stays yours.

### What the pull cannot fill

The pull fills your fiscal address, postcode, and cadastral reference.

It does not fill your fiscal ID. It reads your fiscal ID to confirm the record
AEAT returned is yours, and never writes it.

It does not fill your regime facts: activity, tax regime, IVA regime,
enrollment. AEAT publishes no read-only surface that carries them. Enter those
by hand as described below.

It does not split your name. AEAT returns surnames and given names as one
string, and a wrong split is worse than a blank field, so the pull leaves both
alone.

If a pull returns a record whose fiscal ID is not your profile's, it refuses
outright rather than reporting a difference. A read of someone else's census
is not a disagreement to weigh.

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
described above. The command's interface is stable, and this page applies
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

Your AEAT census can change - a new activity, a regime change, a baja.

Pull again to catch drift in your identity and address. The pull reports
anything AEAT now holds that your profile does not.

The pull cannot see a regime change, so re-check those fields against your
latest Modelo 036 copy whenever you file a censo change, and before you plan a
new filing year.

## Next steps

- [Set up your taxpayer profile](profile-setup.md)
- [Plan your filing calendar](filing-calendar.md)
- [Import and manage transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
