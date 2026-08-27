# Reconcile a filed modelo against its justificante

This page covers the {term}`justificante`, the signed PDF receipt AEAT
issues when you file at the portal, and reconciliation: how to pull the
receipt from AEAT and keep it as encrypted evidence in your profile, and how
to compare it against your local filing record so a typo at the portal, a
wrong period, or a stale local value surfaces now instead of during a later
review.

There are two ways to supply the justificante:

- **Pull it from AEAT** with `reconcile pull` - the tool fetches the receipt
  from the AEAT sede (read-only), stores an encrypted copy in your profile,
  and reconciles in one step.
- **Use a local PDF** with `reconcile import --file` - you downloaded the
  justificante yourself; the check is local and never contacts AEAT.

## Before you start

You need:

- an active profile
- a locally filed work unit (you have run `aeat app modelo work file` for this
  filing) that was presented at the AEAT portal
- for the pull commands: working AEAT authentication - see
  [Authenticate with AEAT](authenticate-with-aeat.md)
- for `reconcile import`: the justificante PDF on disk

To create a profile, see [Set up your taxpayer profile](profile-setup.md). For
the filing workflow, see the [quickstart](quickstart.md). Every command on
this page needs your master-key passphrase; the tool prompts for it.

(pull-and-store-the-justificante)=
## Pull and store the justificante

Keep the receipt with your records: it is the official evidence behind every
filed period. Fetch the justificante for one filed period and store it in your
profile without reconciling yet. This reads from the AEAT sede, so it is shown
as a display frame:

```{cli-sequence} reconcile-pull-store
```

`pull` is live-only: it reads from AEAT (read-only) and needs the configured
authentication session. `--modelo`, `--year`, and `--period` are all
required. When auth is not set up, the pull refuses before contacting AEAT
with a Cl@ve identity message (`La identidad de Cl@ve Móvil no coincide...`);
on a first run the real cause is usually that no AEAT session is configured
yet.

The output reports the stored capture: its snapshot id, the expediente it
belongs to, the CSV verification code printed on the receipt, the PDF's
content fingerprint, and when it was captured. The PDF bytes are stored
encrypted inside your profile, so you do not need to keep a separate
downloaded copy. Pulling again for the same modelo, year, and period stores
a fresh capture and marks the earlier one as superseded, so the latest
receipt is always the active one.

List every capture stored in the active profile, then inspect one (an
unambiguous prefix of the snapshot id is enough). Both read the stored captures
back through the live justificante surface, so they are shown as display frames:

```{cli-sequence} reconcile-justificante-list
```

The view reports the expediente id, the CSV verification code, the PDF
fingerprint, whether the capture is still active or superseded, and when it
was captured.

## Pull the justificante from AEAT and reconcile

Fetch the receipt for the filing and reconcile in one command. The pull reads
from AEAT, so it is shown as a display frame:

```{cli-sequence} reconcile-pull
```

Replace `303`, `2026`, and `1T` with the modelo, year, and period of your
actual filing. You can also name the work unit directly as a positional
argument instead of the `--modelo --year --period` selectors.

The pull is read-only at AEAT. The fetched receipt is stored as an encrypted
capture in your profile, so the official evidence stays available after the
command finishes. To list or inspect stored captures later, see
[Pull and store the justificante](#pull-and-store-the-justificante) above.

## Reconcile against a local PDF instead

If you already downloaded the justificante from the portal, compare your local
filing record against that file. This check is local and never contacts AEAT,
but it needs the real receipt PDF on disk, so it is shown as a display frame:

```{cli-sequence} reconcile-import
```

This check is local. It reads the PDF you supply and never contacts AEAT.

## Read the result

Both transports report one of three verdicts:

- **matches** - the justificante matches the local filing record.
- **mismatches** - one or more fields differ. The report names each field and
  shows the local value next to the value found in the PDF.
- **evidence_invalid** - the PDF could not be read. Check that the file is the
  AEAT justificante and not a different document.

Reconciliation compares four header fields only: the modelo code, the filing
year, the period, and the taxpayer identifier (NIF, CIF, DNI, or NIE). It does
not compare box (casilla) values. A `mismatches` verdict always names
one of those four fields, never a box.

## Handle a mismatch

A `mismatches` verdict names the header field that differs and shows your local
value next to the value in the justificante.

1. Confirm the justificante is the correct one for this filing, not a different
   period or taxpayer. A wrong receipt is the most common cause.
2. If the modelo, year, or period differs, you either reconciled against the
   wrong filing or filed the wrong period at the portal. Re-run reconciliation
   with the correct selectors, or check what you submitted.
3. If the taxpayer identifier differs, confirm the active profile matches the
   taxpayer the justificante was issued to.
4. If the justificante itself appears wrong, contact your asesor or AEAT
   directly.

## If a box value looks wrong

Reconciliation does not compare box (casilla) values, so it cannot tell you that
a computed total differs from what you filed. To correct a box value, use the
amendment workflow rather than reconciliation. Re-check the inputs and
re-calculate. If the period was already filed, file a complementaria. See
[Review and supply calculation inputs](review-calculation-values.md).

## What to keep as evidence

The justificante is your proof of what AEAT received. Here is what each path
stores:

- `reconcile pull` stores the fetched justificante as an encrypted copy in your
  profile.
- `reconcile import` reads a PDF you supply but does not store it. If you reconcile
  against a downloaded PDF, also pull the receipt so an encrypted copy is kept in
  your profile. See [Pull and store the justificante](#pull-and-store-the-justificante).
- Reconciliation history is a read-back you can regenerate from the justificante,
  so it needs no separate backup.

## Review past reconciliations

Each reconciliation is recorded in the profile's event history. List the past
reconciliations recorded for the active profile:

```{cli-sequence} reconcile-list
:verify: Confirm the recorded reconciliations read back cleanly.
```

On a fresh profile the list is empty; after you reconcile a filing a row
appears for each run.

Add `--work-unit-id <id>` to narrow the list to a single work unit. Each row
shows when the reconciliation ran, the work unit, the evidence source, the
verdict, and how many fields differed. Reconciliation is repeatable on demand
from the justificante, so this is a convenience read-back rather than a separate
stored record.

## Next steps

- [Import, export, and evidence](../reference/import-export-and-evidence.md) -
  understand what the justificante proves and what a complete audit handoff
  still requires.
- [File your modelo at the AEAT portal](file-at-aeat.md) - the
  filing handoff that produces the justificante.
- [Quickstart](quickstart.md) - the end-to-end filing workflow.
- [Review and supply calculation inputs](review-calculation-values.md) - amend
  a filing if reconciliation finds a mismatch.
- [CLI reference](../cli/index.rst) - full option reference.
- [Diagnose and repair your local setup](troubleshooting.md) - fix local
  readiness problems.
