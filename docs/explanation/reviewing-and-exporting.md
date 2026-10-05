# Reviewing your numbers and producing the export file

This page covers the two outputs the tool produces from a calculation - a
spreadsheet for you to review, and the export file in the layout
the Agencia Estatal de Administración Tributaria (AEAT) publishes - and why
they are separate things.

## Why there are two outputs, not one

The first output is for you. Before you commit to any numbers, you want to
see how each total was reached and adjust a figure if something looks off.
Your calculation is laid out in Google Sheets with a live formula behind
every total, so a corrected input recomputes everything that depends on it in
front of you, and your reviewed edits pull back into the tool once it confirms
the sheet matches the modelo, the version of the official form, the year, and
the period. The offline `.xlsx`
the tool can also produce carries the same live formulas, but nothing reads an
edited local workbook back, so it is a local review copy. The walkthrough is
[Review calculations with Google Sheets](../how-to/review-with-google-sheets.md).

The second output is for the machine on the other end. AEAT reads a precise
layout for each modelo: fixed-width text with every value at a fixed position
for most modelos, and XML for Modelo 100. The tool builds that file from your
reviewed calculation on your own computer - generating the file and
submitting it are separate acts, and the tool never submits for you. It
won't overwrite an earlier export unless you ask it to. When it writes the
file it reports a fingerprint of the exact contents, so you can later prove
which file you filed.

Not every export file is uploadable. Cadrumo holds no AEAT software-developer
registration, so the files for modelos such as 303 and 390 carry a development
identity, and the export warns that AEAT will not accept them. For those
modelos, key the calculated figures into the portal form. The steps are in
[File your modelo at the AEAT portal](../how-to/file-at-aeat.md).

One is a review surface; the other is a delivery format. Keeping them apart
is what lets each be good at what it does.

## Where this sits in your filing

Review comes first, while the calculation is still a draft you can change. The
export file comes after the completeness check described in
[Editing and checking a calculation](editing-and-verifying.md), because the
tool builds it only from a checked calculation or one recorded as filed. Producing the export file
is not the same as filing it; what happens after you have the file is covered in
[Recording a filing, and why the tool never files for you](recording-a-filing-and-the-boundary.md).
