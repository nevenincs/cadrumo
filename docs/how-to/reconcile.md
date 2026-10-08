(reconcile-a-filed-modelo-against-its-justificante)=
# Reconcile a filed modelo against its AEAT receipt

This page covers the AEAT receipt ({term}`justificante`), the signed PDF receipt
the Agencia Estatal de Administración Tributaria (AEAT) issues when you file at
the portal, and reconciliation: how to pull the receipt from AEAT and keep it as
an encrypted copy in your profile, and how to compare it against the filing you
recorded so a typo at the portal, a wrong period, or an out-of-date local value
surfaces now instead of during a later review.

There are two ways to supply the AEAT receipt:

- **Pull it from AEAT** with `reconcile pull` - the tool fetches the receipt
  from the AEAT sede (read-only), stores an encrypted copy in your profile,
  and reconciles in one step.
- **Use a local PDF** with `reconcile import --file` - you downloaded the AEAT receipt yourself; the check is local and never contacts AEAT.

## Before you start

You need:

- an active profile
- a declaration that was presented at the AEAT portal, ideally recorded with
  `aeat app modelo work file` so the comparison uses the saved calculation you
  presented
- for the pull commands: working AEAT authentication - see
  [Authenticate with AEAT](authenticate-with-aeat.md)
- for `reconcile import`: the AEAT receipt PDF on disk

To create a profile, see [Set up your taxpayer profile](profile-setup.md). For
the filing workflow, see the [quickstart](quickstart.md). Every command on
this page needs your passphrase; the tool prompts for it.

(pull-and-store-the-justificante)=
## Pull and store the AEAT receipt

Keep the receipt with your records: it is the official proof behind every filed period. Fetch the AEAT receipt for one filed period and store it in your
profile without reconciling yet. This reads from the AEAT sede, so it is shown
as an example that is not run:

```{cli-sequence} reconcile-pull-store
```

`pull` is live-only: it reads from AEAT (read-only) and needs the configured
authentication session. `--modelo`, `--year`, and `--period` are all
required. When authentication is not ready, the pull refuses before contacting
AEAT and names what is missing. For example, `No active AEAT session` means no
session exists, and `Cl@ve Móvil identity does not match the active profile tax
identity` means the Cl@ve identity differs from the active profile's. See
[Authenticate with AEAT](authenticate-with-aeat.md).

The output reports the stored capture: its snapshot id, the expediente it
belongs to, the PDF's content fingerprint, and when it was captured. The JSON
form (`--format json`) also carries the Código Seguro de Verificación (CSV)
printed on the receipt. The PDF bytes are stored encrypted inside your profile,
so you do not need to keep a separate downloaded copy. Pulling again for the
same modelo, year, and period stores a fresh capture and marks the earlier one
as superseded, so the latest receipt is always the active one.

If the declaration has a current filing record, the pull also stamps the capture
on it as proof (`filing_evidence_stamped`). Otherwise the output prints the
`aeat app modelo filing-record import` command that attaches it.

List every capture stored in the active profile, then inspect one (an
unambiguous prefix of the snapshot id is enough). Both read the stored captures
back through the live AEAT receipt commands, so they are shown as examples that
are not run:

```{cli-sequence} reconcile-justificante-list
```

The view reports the expediente id, the PDF fingerprint, whether the capture is
still active or superseded, and when it was captured. The JSON form also
carries the receipt's CSV.

(pull-the-justificante-from-aeat-and-reconcile)=
## Pull the AEAT receipt and reconcile

Fetch the receipt for the filing and reconcile in one command. The pull reads
from AEAT, so it is shown as an example that is not run:

```{cli-sequence} reconcile-pull
```

Replace `303`, `2026`, and `1T` with the modelo, year, and period of your
actual filing. You can also name the declaration directly as a positional
argument instead of the `--modelo --year --period` selectors.

The pull is read-only at AEAT. The fetched receipt is stored as an encrypted
capture in your profile, so the official proof stays available after the
command finishes. To list or inspect stored captures later, see
{ref}`Pull and store the AEAT receipt <pull-and-store-the-justificante>` above.

## Reconcile against a local PDF instead

If you already downloaded the AEAT receipt from the portal, compare the filing you recorded against that file. This check is local and never contacts AEAT,
but it needs the real receipt PDF on disk, so it is shown as an example that is
not run:

```{cli-sequence} reconcile-import
```

This check is local. It reads the PDF you supply and never contacts AEAT.

## Read the result

Both routes report one of two verdicts:

- **matches** - every compared field agrees with the local filing record.
- **`mismatches`** - one or more fields differ. The report names each field and
  shows the local value next to the value found in the PDF.

A PDF that cannot be read gets no verdict. The command refuses it with `The PDF
could not be read`. Check that the file is the AEAT receipt and not a
different document.

Reconciliation compares four header fields: the modelo code, the filing year,
the period, and the taxpayer identifier (NIF or NIE). An AEAT receipt also
prints a total. When the modelo declares which box holds its result, Cadrumo
compares that total with your saved calculation and reports a `total`
difference. It prefers the calculation recorded as filed, then a checked one,
then the most recent, so record the filing with `work file` first to compare against what you
presented. It does not compare other box (casilla) values.
When the total cannot be compared, the verdict comes with a
`totals_not_reconciled` advisory. Read it before you rely on `matches`.

## Handle a mismatch

A `mismatches` verdict names the header field that differs and shows your local
value next to the value in the AEAT receipt.

1. Confirm the AEAT receipt is the correct one for this filing, not a different
   period or taxpayer. A wrong receipt is the most common cause.
2. If the modelo, year, or period differs, you either reconciled against the
   wrong filing or filed the wrong period at the portal. Re-run reconciliation
   with the correct selectors, or check what you submitted.
3. If the taxpayer identifier differs, confirm the active profile matches the taxpayer the AEAT receipt was issued to.
4. If the field is a `total`, AEAT printed a result that differs from your
   calculated one. Compare it with the figures you presented at the portal. If
   you presented different figures, correct them with the correction workflow.
5. If the AEAT receipt itself appears wrong, contact your asesor or AEAT
   directly.

## If a box value looks wrong

Reconciling against the AEAT receipt compares the header and the result total,
not individual box (casilla) values. To compare box by box, reconcile against
the filed declaration instead. Add `--kind declaration` to `reconcile import`,
with the PDF of the declaration you downloaded:

```text
aeat app modelo reconcile import --modelo 130 --year 2026 --period 1T --file declaracion.pdf --kind declaration
```

Each differing box appears as a `casilla` difference. Only modelos enrolled in
box-level reconciliation accept this kind. The others refuse with
`Declaration-PDF casilla-level reconcile is not yet enrolled for this modelo`.

To correct a box value, use the correction workflow rather than reconciliation.
Re-check the inputs and re-calculate. If the period was already filed, file a
complementaria. See
[Review and supply calculation inputs](review-calculation-values.md).

(what-to-keep-as-evidence)=
## What to keep as proof

The AEAT receipt is your proof of what AEAT received. Here is what each path
stores:

- `reconcile pull` stores the fetched AEAT receipt as an encrypted copy in your
  profile.
- `reconcile import` reads a PDF you supply but does not store it. If you reconcile
  against a downloaded PDF, also pull the receipt so an encrypted copy is kept in
  your profile. See {ref}`Pull and store the AEAT receipt <pull-and-store-the-justificante>`.
- The reconciliation history stays in your profile as an encrypted record of each
  run. It does not replace the AEAT receipt.

## Review past reconciliations

Each reconciliation is recorded in the profile's event history. List the past
reconciliations recorded for the active profile:

```{cli-sequence} reconcile-list
:verify: Confirm the recorded reconciliations read back cleanly.
```

On a fresh profile the list is empty; after you reconcile a filing a row
appears for each run.

Add `--work-unit-id <id>` to narrow the list to a single declaration. Each row
shows when the reconciliation ran, the declaration, where the proof came from, the
verdict, how many fields differed, and who ran it. Each run is stored in your
profile, so the list reads back what happened at the time.

## Next steps

- [Import, export, and supporting documents](../reference/import-export-and-evidence.md) -
  understand what the AEAT receipt proves and what a complete audit handoff
  still requires.
- [File your modelo at the AEAT portal](file-at-aeat.md) - the filing handoff that produces the AEAT receipt.
- [Quickstart](quickstart.md) - the end-to-end filing workflow.
- [Review and supply calculation inputs](review-calculation-values.md) - correct
  a filing if reconciliation finds a mismatch.
- [CLI reference](../cli/index.rst) - full option reference.
- [Diagnose and repair your local setup](troubleshooting.md) - fix local
  readiness problems.
