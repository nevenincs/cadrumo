# Link Modelo 036 census information

Use this guide to pull your AEAT census information - the *censo* - into the
active local profile and compare it with what you entered by hand. In Spain, the
censo is tied to Modelo 036 registration and changes.

This guide covers Modelo 036. Modelo 037 is superseded and not used in this
workflow.

The censo commands read from AEAT and save local profile data only after you
review and apply it. They do not file Modelo 036, do not submit changes to
AEAT, and do not modify AEAT records.

## Before you start

You need:

- an active taxpayer profile; see [Set up your taxpayer profile](profile-setup.md)
- the taxpayer's fiscal ID (NIF, CIF, DNI, or NIE) saved in that profile
- AEAT authentication configured for read-only live access; see
  [Authenticate with AEAT](authenticate-with-aeat.md)

Check the active profile first:

```bash
aeat config profile status
```

## Why link censo information

Modelo 036 censo facts are AEAT facts about the taxpayer's registered tax
situation. Pull them into `aeat` to check the local profile against AEAT records
before you plan deadlines, classify expenses, or calculate modelos.

The implemented censo/profile flow can affect:

- activity start date, which helps avoid showing obligations before the
  taxpayer's registered activity start
- establishment or premises facts, where AEAT publishes them
- selected withholding percentage facts, where AEAT publishes them
- home-office area facts, which can seed home-office usage ratios for relevant
  expense categories
- censo stale metadata on modelo work units, so later review can see whether
  the work used fresh or older local censo facts
- local audit history for censo pulls and censo applies

If you do not link censo information, you still work with a manually entered
profile. The consequence is that profile-dependent workflows use your manual
facts only. Calendar and filing-calendar checks may be less reliable if the
activity start date, tax regime, IVA regime, Renta/IRPF regime, or enrollment
facts are incomplete or wrong. Home-office ratios derived from censo floor-area
facts will not be available.

Use [Plan your filing calendar](filing-calendar.md) after profile and censo
review. Use modelo-specific guides, such as
[How to prepare a Modelo 303 quarterly filing](modelo-303.md), once the profile
and ledger are ready.

## Pull the latest Modelo 036 censo snapshot

Pull the latest AEAT censo facts into the local snapshot store:

```bash
aeat config profile censo pull
```

This live read uses the active profile and the configured AEAT authentication,
and saves a snapshot under the profile. It does not apply those values yet. It
requires an active AEAT authentication session.

If AEAT returns no usable censo facts, the pull can stop with a no-facts error.

## Review the snapshot

Show the latest snapshot:

```bash
aeat config profile censo show
```

Show a specific earlier snapshot by its reference number:

```bash
aeat config profile censo show --snapshot-id <snapshot-id>
```

Confirm the facts belong to the taxpayer and match what you expect from the
AEAT censo surface.

`show`, `compare`, and `apply` need a saved snapshot. If no snapshot exists,
they refuse instead of inventing censo values.

## Compare AEAT censo with your profile

Compare the snapshot with the current local profile:

```bash
aeat config profile censo compare
```

The comparison reports matching fields, diverging fields, censo-only fields,
and profile-only fields. Review this before applying anything. Profile-only
facts are not automatically wrong; they may be manual facts that AEAT does not
publish through this censo surface.

## Apply reviewed censo facts

Apply the snapshot only after review:

```bash
aeat config profile censo apply
```

Apply writes AEAT-reported censo facts into the local profile with censo
provenance. The new censo snapshot replaces existing censo-derived facts.
Manually entered facts from other sources are preserved so you can still compare
manual profile values with AEAT-reported values.

If the snapshot includes home-office floor-area facts, apply can seed local
home-office usage ratios for categories that use that censo-derived ratio. If
the snapshot has no valid area facts, no home-office ratio is seeded and
home-office classification falls back to the manual or saved ratio workflow.

## Record a Modelo 036 filing done outside aeat

If you file Modelo 036 in AEAT's sede, record that local fact separately:

```bash
aeat app modelo m036 alta --declared-on 2026-01-10 --sede-justificante <acuse>
aeat app modelo m036 modificacion --declared-on 2026-03-15 --sede-justificante <acuse>
aeat app modelo m036 baja --declared-on 2026-12-31 --sede-justificante <acuse>
```

These commands record that you filed the Modelo 036 alta, modificacion, or baja
through AEAT. They never file with AEAT themselves. For the flags, the success
output, and what the record does and does not change, see
[Record a Modelo 036 declaration you filed at AEAT](modelo-036.md).

## Check the profile afterwards

Validate the active profile after applying censo facts:

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

## When linking is required

Linking censo information is optional for a manually maintained profile. Link it
when your filing calendar, tax regime, IVA regime, Renta/IRPF regime, enrollment
facts, or home-office expense ratios depend on official censo facts.

It is required only for workflows where you need the local profile to be
grounded in the AEAT-reported censo snapshot or where a command explicitly
refuses because no censo snapshot exists.

## Next steps

- [Authenticate with AEAT](authenticate-with-aeat.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Plan your filing calendar](filing-calendar.md)
- [Work with Transactions](import-bank-statements.md)
- [Review and supply calculation inputs](review-calculation-values.md)
