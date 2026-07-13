# Reviewing your numbers and producing the upload file

After Cadrumo calculates a revision, it can produce a spreadsheet review
surface and, later, an AEAT-compatible upload file. This page explains why the
two outputs are separate. Compatibility with the published file layout does
not guarantee that the AEAT portal will accept a particular filing.

## Why there are two outputs, not one

The two outputs answer two different needs.

The review surface shows how each total was derived. It supports comparison
with source records and correction before verification.

The second is for the machine on the other end. The Agencia Estatal de
Administración Tributaria (AEAT) publishes precise text layouts for modelo
uploads. The file is designed to match that layout, not to be pleasant to read.

The review surface and delivery format have separate roles. Review material
supports inspection and correction. The delivery file follows the published
AEAT layout.

## The spreadsheet review surface

The local `.xlsx` review workbook contains live formulas. A spreadsheet engine
can recalculate dependent totals when an editable input changes, exposing how
inputs contribute to the displayed casillas. It is a review artifact, not the
AEAT upload file and not an independent tax authority. Cadrumo does not ingest
edits from this offline workbook. Those edits remain in the `.xlsx` file and do
not change a calculation revision.

Google Sheets is an optional, separately configured calculation-review surface.
Synchronization occurs only through its dedicated workflow. It is separate
from the offline `.xlsx` workbook and the encrypted Drive mirror. See [Review
calculations with Google Sheets](../how-to/review-with-google-sheets.md) for the
supported operations and boundaries.

## The AEAT-compatible upload file

The upload file is an AEAT-compatible artifact built to the published
fixed-position layout. It is not a spreadsheet and should not be edited by
hand. Layout compatibility is necessary, but portal acceptance can still
depend on identity, filing-window, authority-side validation, and other AEAT
conditions that Cadrumo cannot guarantee.

Cadrumo builds the file from a reviewed calculation and the published AEAT
structure. Nothing is sent as part of export:
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

The [workflow overview](index.md) places review and export after calculation.

The order is calculate, review, verify, then export. Review happens before
verification so corrections can create a new calculation revision. Verification
is necessary for export, but export may still refuse when required evidence or
other export-boundary gates are missing.

Producing the upload file is not filing. [Recording a filing, and why Cadrumo
never files for you](recording-a-filing-and-the-boundary.md) explains human
upload and local recording.
