# Reviewing your numbers and producing the upload file

After Cadrumo calculates a revision, it can produce a spreadsheet review
surface and, later, an AEAT-compatible upload file. This page explains why the
two outputs are separate. Compatibility with the published file layout does
not guarantee that the AEAT portal will accept a particular filing.

## Why there are two outputs, not one

The two outputs answer two different needs.

The first is for you. Before you commit to any numbers, you want to see how each total was reached, sanity-check it against what you remember, and adjust a figure if something looks off. A plain list of final amounts doesn't let you do that. You need the workings.

The second is for the machine on the other end. The Agencia Estatal de
Administración Tributaria (AEAT) publishes precise text layouts for modelo
uploads. The file is designed to match that layout, not to be pleasant to read.

These two files are not the same file, and you shouldn't expect one to do the other's job. One is a review surface. The other is a delivery format. Keeping them apart is what lets each one be good at what it does.

## The spreadsheet review surface

The local `.xlsx` review workbook contains live formulas. A spreadsheet engine
can recalculate dependent totals when an editable input changes, exposing how
inputs contribute to the displayed casillas. It is a review artifact, not the
AEAT upload file and not an independent tax authority. Cadrumo has no ingestion
path for edits made in this offline workbook; those edits remain in the `.xlsx`
file and do not create or change a calculation revision.

Google Sheets is an optional, separately configured calculation-review surface.
Cadrumo does not synchronize it automatically: calculation export, pull,
compute, and verify are explicit operations. This Google calculation-sync path
is separate from the offline `.xlsx` workbook.

To walk through this surface in practice, see [Review calculations with Google Sheets](../how-to/review-with-google-sheets.md).

Drive mirror push is a third, unrelated operation: it mirrors encrypted Cadrumo
records to the configured Drive location. It does not ingest an offline
workbook, pull Google Sheets calculation edits, or create a calculation
revision. Only the documented Google calculation-sync operations can return
supported Sheet edits to Cadrumo; offline `.xlsx` edits cannot be returned.

## The AEAT-compatible upload file

The upload file is an AEAT-compatible artifact built to the published
fixed-position layout. It is not a spreadsheet and should not be edited by
hand. Layout compatibility is necessary, but portal acceptance can still
depend on identity, filing-window, authority-side validation, and other AEAT
conditions that Cadrumo cannot guarantee.

You don't design that layout, and you don't have to understand it. Cadrumo
builds the file from your reviewed calculation, following the authority's
published structure, on your own computer. Nothing is sent as part of export:
generating the file and submitting it are separate acts, and Cadrumo never
submits for you. The [filesystem and safety
reference](../reference/filesystem-state-and-safety.md) records this boundary
as a lookup contract.

For the step that produces this file, see the export step in [Upload your exported modelo at the AEAT portal](../how-to/file-at-aeat.md).

## A fingerprint for the exact file you produced

When Cadrumo writes the upload file, it reports the file size and the full
SHA-256 digest of its bytes. Any byte change is expected to produce a different
digest.

Recomputing the digest later and finding the same value gives strong evidence
that the bytes are unchanged, assuming the digest was captured and compared
correctly. A different digest proves the compared bytes differ. A digest does
not itself prove which file a human selected in the AEAT portal.

## Where this sits in your filing

Producing these outputs is near the end of the journey, not the start. The broader path - from your records, through calculation, to a file you can upload - is laid out in [Understanding Cadrumo's tax-preparation workflow](index.md).

The order is calculate, review, verify, then export. Review happens before
verification so corrections can create a new calculation revision. Verification
is necessary for export, but export may still refuse when required evidence or
other export-boundary gates are missing.

Producing the upload file is not the same as filing it. What happens after you
have the file—uploading it through AEAT yourself and recording the outcome—is
covered in [Recording a filing, and why Cadrumo never files for
you](recording-a-filing-and-the-boundary.md).
