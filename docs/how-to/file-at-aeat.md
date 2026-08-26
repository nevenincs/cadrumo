# File your modelo at the AEAT portal

This page covers the handoff from a verified draft to a real filing at AEAT, as
an ordered checklist: present the figures yourself at the portal, save the
justificante, and record the filing locally. You prepare and check a
{term}`modelo` with `aeat`, but the tool never submits anything to AEAT. You
file at the portal yourself, signed with your own credentials. The `work file`
command at the end records a local marker only; it does not and cannot file on
your behalf.

How you present depends on the modelo. Modelo 130 exports a local fichero-BOE
file for upload. Modelo 303's registry layout also exists, but its export
currently refuses because Cadrumo has no reviewed AEAT product/software
identity authority with which to stamp the envelope; key its calculated box
values into the portal form instead.

## Before you start

You need:

- An active taxpayer profile carrying `--name` and `--surnames`, or filing
  refuses because it cannot stamp the operator name. Create one with
  `aeat config profile create`; see
  [Set up your taxpayer profile](profile-setup.md).
- A verified saved calculation (work unit) for the modelo and period you want
  to file. If your draft isn't verified yet, see
  [verification reports](verification-reports.md).
- Your own AEAT portal credentials, a digital certificate or Cl@ve. These are
  your credentials for AEAT's website, separate from anything configured inside
  `aeat`. The tool's [AEAT authentication](authenticate-with-aeat.md) is for
  read-only data pulls, not for filing.

Every `aeat` command on this page needs your master-key passphrase; the
tool prompts for it. The tool's messages are in Spanish.

If you're new to the workflow as a whole, start with the
[quickstart](quickstart.md).

(the-filing-chain)=
## The filing chain

The sequence below runs the machine half of the filing end to end: it prepares a
classified, evidenced Modelo 303 for the first quarter of 2026, verifies it,
confirms the verified revision, shows Modelo 303 `export` refusing, and records the local
filed marker. Between the refusal and the marker, you present the figures at the
AEAT portal yourself (steps 2 to 4 below). The final frame is the reconcile
command you run once you have AEAT's justificante on disk; it is shown but not
run here, because it needs your real receipt:

```{cli-sequence} file-at-aeat-chain
:verify: Confirm the verified draft refuses export and records the local marker.
```

The rest of this page walks each step of that chain in order.

## Step 1: confirm the draft is verified

If no verified calculation exists, `work revision --select latest-verified`
refuses; run verification first. See
[verification reports](verification-reports.md).

Read the verified figures back with `aeat app modelo work revision`. These are
the values you present at the portal, box by box.

For a modelo that does carry a layout, `export` writes a `.boe` file: a
fixed-width text file in the official BOE (Boletín Oficial del Estado) record
layout, not a PDF or a spreadsheet. It runs entirely on your machine and never
contacts AEAT, and it prints the file's path, size and SHA-256 checksum. Record
that checksum: it fingerprints the file's exact contents, so if a question ever
comes up about which version you filed, re-derive it from the file on disk and
compare.

## Step 2: present the figures at the AEAT portal yourself

This step happens entirely outside `aeat`, in your browser. Log in with your
own certificate or Cl@ve. Do not expect the tool to do any part of this step
for you.

1. Log in at AEAT's Sede Electrónica.
2. Choose the presentation page for your modelo and period.
3. Enter the calculated box values in the form. If your modelo carries a
   fichero-BOE layout and you exported one, import that file instead.
4. Review the figures the portal shows against your verified calculation.
5. Sign and submit.

Portal screens change over time, so the exact labels may differ. If you can't
find the presentation page for your modelo, AEAT's own help or your advisor is
the right source. The portal is theirs, not the tool's.

## Step 3: save the justificante

Immediately after submitting, download the {term}`justificante`. AEAT usually offers it as a PDF.

Keep it with your tax records. You'll use it in step 5 to reconcile AEAT's
record against your local one.

## Step 4: record the filing locally

Only after the portal submission succeeds, record the filing in `aeat` with the
`work file` frame from [the filing chain](#the-filing-chain) above.

`work file` records a local "filed" marker and nothing more. It does not and
cannot submit anything to AEAT. Add context with the optional flags `--notes
TEXT` and `--by TEXT`, for example who filed and any portal reference you want
to remember.

If the command refuses, the usual causes are:

- The filing window gate: the period's filing window isn't open. A window that
  has already closed cannot be reopened. The refusal message suggests what to
  do instead. See the
  [filing calendar](filing-calendar.md) for window dates.
- The verification state: the saved calculation isn't verified.

Read the cause shown in the error message before retrying.

## Step 5: reconcile the justificante against your local record

Compare AEAT's receipt against the figures you recorded locally with the
`reconcile import` command shown as the final frame above. Run reconciliation
after step 4 so the comparison is against your filed record. It reports a
verdict of matches or mismatches; the command refuses a PDF it cannot read as
invalid evidence. For reading verdicts and handling mismatches, see
[reconcile a filing](reconcile.md).

With AEAT authentication configured, skip the manual download and let the
tool fetch the receipt itself. `reconcile pull` pulls the justificante from
AEAT, stores it as encrypted evidence in your profile, and reconciles in one
step:

```{cli-sequence} file-at-aeat-reconcile-pull
```

See [Pull and store the justificante](reconcile.md#pull-and-store-the-justificante).

## If something goes wrong at the portal

If the submission was rejected or interrupted, or you presented the wrong
figures, do not record the local filed marker. The marker describes only a
submission that succeeded at the portal.

Instead:

1. Fix the draft in `aeat`.
2. Re-verify the calculation.
3. Read the corrected figures back with `aeat app modelo work revision`.
4. Retry the presentation at the portal.

If you filed by uploading a `.boe` file, re-export it and use the checksum
printed at export to confirm which file is on disk. If it matches the one you
recorded, you have the same file you presented before.

If the portal rejected the submission itself, consult AEAT or your advisor. The
rejection happened on AEAT's side, and their message is the authoritative
explanation.

## Where to get help

For diagnosing problems on your machine (refused commands, export errors,
verification failures) see [troubleshooting](troubleshooting.md). Unfamiliar
terms are defined in the {doc}`glossary </_generated/glossary>`. Before you share command
output to ask for help, remove personal tax identifiers such as your NIF, CIF,
DNI, NIE, or NII.

## Next steps

- [Import, export, and evidence](../reference/import-export-and-evidence.md) -
  distinguish the local upload file from official AEAT filing proof.
- [Reconcile a filing](reconcile.md) - read verdicts and resolve mismatches.
- [Verification reports](verification-reports.md) - understand what "verified"
  means before you file.
- [Filing calendar](filing-calendar.md) - see when each period's filing window
  opens and closes.
- [Check AEAT notifications](check-aeat-notifications.md) - read AEAT's view
  after you file.
- [CLI reference](../cli/index.rst) - full command and flag details.
