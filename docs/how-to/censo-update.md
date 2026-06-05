# Sync your taxpayer census (Censo)

This guide shows you how to download your official taxpayer census facts
(*censo*) from the Agencia Estatal de Administracion Tributaria (AEAT) and
compare them with your active local profile.

Use this when your local profile may be missing your registered activity, tax
address, or regime facts.

## Before you start

You need:

- An active taxpayer profile.
- Your DNI, NIE, NIF, or CIF saved in that profile.
- AEAT authentication configured for read-only access, such as a registered
  certificate or Cl@ve session.

The censo commands read from AEAT and update local profile data only after you
review and apply the downloaded facts. They never submit declarations or modify
AEAT records.

## Download the censo snapshot

Download your census information into a local snapshot:

```bash
aeat config profile censo refresh
```

This retrieves the facts associated with your tax identifier from the AEAT portal
and saves a local snapshot.

## Review the downloaded facts

Show the local snapshot before applying it:

```bash
aeat config profile censo show
```

Check that the facts match the taxpayer you intended to work on.

## Compare with your profile

Preview how the official censo facts differ from your current local profile settings:

```bash
aeat config profile censo compare
```

This displays the AEAT values alongside your local profile settings. Review this
output before applying changes.

## Apply the update

Apply the downloaded censo snapshot to your local profile:

```bash
aeat config profile censo apply
```

This command updates your profile facts to match the AEAT records. Facts you
entered manually remain untouched.

## Check the profile

Validate the profile after applying censo facts:

```bash
aeat config profile status
aeat config profile validate
```

If the profile still reports missing facts, add them with
`aeat config profile edit` before you calculate a modelo.

## Next steps

- [Set up your taxpayer profile](profile-setup.md)
- [Plan your filing calendar](filing-calendar.md)
- [Import and classify a bank statement](import-bank-statements.md)
