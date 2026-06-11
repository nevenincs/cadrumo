# Upload your exported modelo at the AEAT portal

This guide walks you through the handoff from a verified draft to a real filing
at AEAT, as an ordered checklist. You prepare and export a modelo (a numbered
official AEAT tax form) with `aeat`, but the tool never submits anything to
AEAT. You upload the exported file at the AEAT portal yourself, signed with
your own credentials. The `work file` command at the end records a local marker
only; it does not and cannot file on your behalf.

## Before you start

You need:

- A verified saved calculation for the modelo and period you want to file. If
  your draft isn't verified yet, see [verification reports](verification-reports.md).
- Your own AEAT portal credentials - a digital certificate or Cl@ve. These are
  your credentials for AEAT's website, separate from anything configured inside
  `aeat`. The tool's [AEAT authentication](authenticate-with-aeat.md) is for
  read-only data pulls, not for filing.

If you're new to the workflow as a whole, start with the
[quickstart](quickstart.md).

## Step 1: confirm the draft is verified

Ask for the verified saved calculation before exporting anything:

```bash
aeat app modelo work revision --modelo 303 --year 2026 --period 1T --select latest-verified
```

If a verified calculation exists, the command shows it. If none exists, the
command refuses - run verification first, because the export in the next step
refuses an unverified draft. See
[verification reports](verification-reports.md).

## Step 2: export the filing file

Export the verified calculation to a file the AEAT portal accepts:

```bash
aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe
```

The exported `.boe` file is a fixed-width text file in the official BOE
(Boletín Oficial del Estado) record layout - not a PDF or a spreadsheet. The
export runs entirely on your machine and never contacts AEAT.

The command prints the written file's path, its size in bytes, and its SHA-256
checksum. Record the checksum - it identifies exactly which file you uploaded.

## Step 3: upload the file at the AEAT portal yourself

This step happens entirely outside `aeat`, in your browser. Log in with your
own certificate or Cl@ve - do not expect the tool to do any part of this step
for you.

1. Log in at AEAT's Sede Electrónica.
2. Choose the file-upload presentation page for your modelo and period.
3. Import the exported `.boe` file.
4. Review the figures the portal shows against your verified calculation.
5. Sign and submit.

Portal screens change over time, so the exact labels may differ. If you can't
find the presentation page for your modelo, AEAT's own help or your advisor is
the right source - the portal is theirs, not the tool's.

## Step 4: save the justificante

Immediately after submitting, download the {term}`justificante`. AEAT usually offers it as a PDF.

Keep it with your tax records. You'll use it in step 6 to reconcile AEAT's
record against your local one.

## Step 5: record the filing locally

Only after the portal submission succeeds, record the filing in `aeat`:

```bash
aeat app modelo work file --modelo 303 --year 2026 --period 1T
```

This command records a local "filed" marker and nothing more - it does not and
cannot submit anything to AEAT. Add context with the optional flags `--notes
TEXT` and `--by TEXT`, for example who filed and any portal reference you want
to remember.

If the command refuses, the usual causes are:

- The filing window gate: the period's filing window isn't open. A window that
  has already closed cannot be reopened. The refusal message suggests what to
  do instead, and export keeps working either way. See the
  [filing calendar](filing-calendar.md) for window dates.
- The verification state: the saved calculation isn't verified.

Read the cause shown in the error message before retrying.

## Step 6: reconcile the justificante against your local record

Compare AEAT's receipt against the figures you recorded locally:

```bash
aeat app modelo reconcile file --modelo 303 --year 2026 --period 1T --file ./justificante.pdf
```

Run reconciliation after step 5 so the comparison is against your filed
record. It reports a verdict of matches or mismatches; the command refuses a
PDF it cannot read as invalid evidence. For reading verdicts and handling
mismatches, see [reconcile a filing](reconcile.md).

## If something goes wrong at the portal

If the upload was rejected or interrupted, or you uploaded the wrong file, do
not record the local filed marker. The marker describes only a submission that
succeeded at the portal.

Instead:

1. Fix the draft in `aeat`.
2. Re-verify the calculation.
3. Re-export the filing file.
4. Retry the upload at the portal.

Before retrying, use the checksum printed at export to confirm which file is
on disk. If it matches the one you recorded, you have the same file you
uploaded before.

If the portal rejected the file itself, consult AEAT or your advisor. The
rejection happened on AEAT's side, and their message is the authoritative
explanation.

## Where to get help

For diagnosing problems on your machine - refused commands, export errors,
verification failures - see [troubleshooting](troubleshooting.md). Unfamiliar
terms are defined in the {doc}`glossary </_generated/glossary>`. Before you share command
output to ask for help, remove personal tax identifiers such as your NIF, CIF,
DNI, NIE, or NII.

## Next steps

- [Reconcile a filing](reconcile.md) - read verdicts and resolve mismatches.
- [Verification reports](verification-reports.md) - understand what "verified"
  means before you export.
- [Filing calendar](filing-calendar.md) - see when each period's filing window
  opens and closes.
- [Check AEAT notifications](check-aeat-notifications.md) - read AEAT's view
  after you file.
- [CLI reference](../cli/index.rst) - full command and flag details.
