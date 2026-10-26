# File your modelo at the AEAT portal

This page covers the handoff from a checked draft to a real filing at the
Agencia Estatal de Administración Tributaria (AEAT), as an ordered checklist:
present the figures yourself at the portal, save the AEAT receipt, and record
the filing in Cadrumo. You prepare and check a {term}`modelo` with `aeat`, but
the tool never submits anything to AEAT. You file at the portal yourself, signed
with your own credentials. The `work file` command at the end only records the
filing in Cadrumo; it does not and cannot file on your behalf.

How you present depends on the modelo. Cadrumo holds no AEAT software-developer
registration, so the export of a modelo whose record design reserves a software
identity, such as Modelo 303 or Modelo 390, carries an all-zero development
identity in its header. The export warns that AEAT will not accept that file for
presentation, so key the calculated box values into the portal form instead.
For a modelo whose layout Cadrumo does not fill with a software identity, such
as Modelo 130, the export leaves those fields blank and shows no such warning.

## Before you start

You need:

- An active taxpayer profile carrying `--name` and `--surnames`, or filing refuses
  because it cannot stamp the taxpayer's name. Create one with `aeat config
  profile create`; see [Set up your taxpayer profile](profile-setup.md).
- A saved calculation that passed the check, for the modelo and period you want
  to file. If your draft hasn't passed the check yet, see [checking a draft
  declaration](verification-reports.md).
- Your own AEAT portal credentials, a digital certificate or Cl@ve. These are
  your credentials for AEAT's website, separate from anything configured inside
  `aeat`. The tool's [AEAT authentication](authenticate-with-aeat.md) is for
  read-only data pulls, not for filing.

Every `aeat` command on this page needs your passphrase; the
tool prompts for it.

`aeat` prints its messages in Spanish unless you choose another language. Add
`--language en` (or `es`, `ca`, `hu`) straight after `aeat` for one command, or
store a default for your profile with
`aeat config profile edit --output-language en`. The examples in this
documentation are recorded in English.

If you're new to the workflow as a whole, start with the
[quickstart](quickstart.md).

(the-filing-chain)=
## The filing chain

The sequence below runs the machine half of the filing. It starts from a
classified Modelo 303 for the first quarter of 2026, with supporting documents,
that is already calculated and checked. It confirms the checked calculation,
exports a Modelo 303 file that AEAT will not accept because it carries the
development identity, and records the filing in Cadrumo. Between the export and
recording the filing, you present the figures at the AEAT portal yourself (steps
2 and 3). The last step of the sequence is the reconcile command you run once
you have the AEAT receipt on disk; it is shown but not run here, because it
needs your real receipt:

```{cli-sequence} file-at-aeat-chain
:verify: Confirm the checked draft exports with the development identity and records the filing record in Cadrumo.
```

The rest of this page walks each step of that chain in order.

(step-1-confirm-the-draft-is-verified)=
## Step 1: confirm the draft passed the check

If no checked calculation exists, `work revision --select latest-verified`
refuses; run the check first. See [checking a draft
declaration](verification-reports.md).

Read the checked figures back with `aeat app modelo work revision`. These are the
values you present at the portal, box by box.

For a modelo that does carry a layout, `export` writes the file in the official
layout, never a PDF or a spreadsheet: for most modelos a `.boe` file, a
fixed-width text file in the BOE (Boletín Oficial del Estado) record layout, and
for Modelo 100 an XML file. It runs entirely on your machine and never
contacts AEAT, and it prints the file's path, size and SHA-256 checksum. Record
that checksum: it fingerprints the file's exact contents, so if a question ever
comes up about which version you filed, re-derive it from the file on disk and
compare. Export refuses to overwrite an existing file unless you add `--replace`,
and it refuses an `--output` path whose parent directory does not exist.

## Step 2: present the figures at the AEAT portal yourself

This step happens entirely outside `aeat`, in your browser. Log in with your
own certificate or Cl@ve. Do not expect the tool to do any part of this step
for you.

1. Log in at AEAT's Sede Electrónica.
2. Choose the presentation page for your modelo and period.
3. Enter the calculated box values in the form. If the export did not warn about
   the development identity and the portal offers a file import for your modelo,
   you can try importing the exported file instead. If the portal refuses it,
   enter the figures in the form.
4. Review the figures the portal shows against your checked calculation.
5. Sign and submit.

Portal screens change over time, so the exact labels may differ. If you can't
find the presentation page for your modelo, AEAT's own help or your advisor is
the right source. The portal is theirs, not the tool's.

(step-3-save-the-justificante)=
## Step 3: save the AEAT receipt

Immediately after submitting, download the AEAT receipt ({term}`justificante`).
AEAT usually offers it as a PDF.

Keep it with your tax records. You'll use it in step 5 to reconcile AEAT's
record against your local one.

(step-4-record-the-filing-locally)=
## Step 4: record the filing

Only after the portal submission succeeds, record the filing in `aeat` with the
`work file` step from [the filing chain](#the-filing-chain) above.

`work file` only records in Cadrumo that you filed, and nothing more. It does not
and cannot submit anything to AEAT. Add context with the optional flags `--notes
TEXT` and `--by TEXT`, for example who filed and any portal reference you want to
remember.

If the command refuses, the usual causes are:

- The filing window gate: the period's filing window isn't open. A window that
  has already closed cannot be reopened. Recording is optional, and the refusal
  message names `aeat app modelo export` as the local finish line. See the
  [filing calendar](filing-calendar.md) for window dates.
- The check: the saved calculation hasn't passed the check.

Read the cause shown in the error message before retrying.

(step-5-reconcile-the-justificante-against-your-local-record)=
## Step 5: reconcile the AEAT receipt against your local record

Compare AEAT's receipt against your local record with the `reconcile import`
command shown as the last step of [the filing chain](#the-filing-chain). Run
reconciliation after step 4 so the comparison is against the filing you
recorded. It reports whether the figures match or not. The command refuses a PDF
it cannot read with `The PDF could not be read`. For reading the results and
handling mismatches, see [reconcile a filing](reconcile.md).

With AEAT authentication configured, skip the manual download and let the tool
fetch the receipt itself. `reconcile pull` pulls the AEAT receipt from AEAT,
stores it encrypted in your profile, and reconciles in one step:

```{cli-sequence} file-at-aeat-reconcile-pull
```

See {ref}`Pull and store the AEAT receipt <pull-and-store-the-justificante>`.

## If something goes wrong at the portal

If the submission was rejected or interrupted, or you presented the wrong figures,
do not record the filing in Cadrumo. The record describes only a submission that
succeeded at the portal.

Instead:

1. Fix the draft in `aeat`.
2. Check the calculation again.
3. Read the corrected figures back with `aeat app modelo work revision`.
4. Retry the presentation at the portal.

If you filed by uploading a `.boe` file, re-export it to a new path and compare
the checksum it prints with the one you recorded. If they match, you have the
same file you presented before.

If the portal rejected the submission itself, consult AEAT or your advisor. The
rejection happened on AEAT's side, and their message is the authoritative
explanation.

## Where to get help

For diagnosing problems on your machine (refused commands, export errors, failed
checks) see [troubleshooting](troubleshooting.md). Unfamiliar terms are defined in
the {doc}`glossary </_generated/glossary>`. Before you share command output to ask
for help, remove personal tax identifiers such as your NIF, CIF, DNI, NIE, or NII.

## Next steps

- [Import, export, and supporting documents](../reference/import-export-and-evidence.md) -
  distinguish the local upload file from official AEAT filing proof.
- [Reconcile a filed modelo against its AEAT receipt](reconcile.md) - read the results and resolve mismatches.
- [Check a draft declaration and act on the issues](verification-reports.md) - understand what a passed
  check means before you file.
- [Filing calendar](filing-calendar.md) - see when each period's filing window
  opens and closes.
- [Read AEAT notifications](check-aeat-notifications.md) - read AEAT's view
  after you file.
- [CLI reference](../cli/index.rst) - full command and flag details.
