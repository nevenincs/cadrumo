# Reviewing your numbers and producing the upload file

Once the tool has worked through your records, it produces two different things: a comfortable place to review your calculation, and the exact file the tax agency's portal will accept. This page explains what each one is, why they're separate, and how they fit into your filing. It's written for an everyday autónomo (a self-employed person filing their own taxes) - no spreadsheet or tax-software background needed.

## Why there are two outputs, not one

The two outputs answer two different needs.

The first is for you. Before you commit to any numbers, you want to see how each total was reached, sanity-check it against what you remember, and adjust a figure if something looks off. A plain list of final amounts doesn't let you do that. You need the workings.

The second is for the machine on the other end. The Agencia Estatal de Administración Tributaria (AEAT - the Spanish tax agency) accepts uploads only in one precise text format. That file isn't meant to be pleasant to read; it's meant to be read by the portal, character for character.

These two files are not the same file, and you shouldn't expect one to do the other's job. One is a review surface. The other is a delivery format. Keeping them apart is what lets each one be good at what it does.

## The spreadsheet review surface

Your calculation is laid out as a spreadsheet in Google Sheets: a row for each input, a row for each result, and the totals built from them. The totals carry live formulas (the spreadsheet recomputes as you change a number), so if you correct an input, every total that depends on it updates in front of you. You can see exactly how a {term}`casilla` on the official {term}`modelo` arrives at its figure, rather than taking it on trust.

That makes the spreadsheet a place to think, not just to look. You change a figure, the dependent totals recompute in front of you, and when you're satisfied you pull your reviewed edits back so the tool records them against your filing. The spreadsheet is tied to the exact calculation it was built from, so the edits land in the right place.

To walk through this surface in practice, see [Review calculations with Google Sheets](../how-to/review-with-google-sheets.md).

One honest note about formats. The tool can also produce an offline spreadsheet file (an `.xlsx`). That file exists as a fixed record of the calculation and its supporting evidence - a copy you can keep - not as an open-in-Excel review tool. It doesn't recompute, and there's no documented way to edit it and feed your changes back. Treat it as a keepsake of what the numbers were, and use Google Sheets when you actually want to review and adjust.

## The official upload file

The official upload file (the exact text-file layout the agency's portal accepts) is the artefact you hand to AEAT. It isn't a spreadsheet and it isn't meant to be edited by hand. Every value sits at a fixed position in the file, because AEAT publishes the precise layout each modelo must follow, and the portal rejects anything that doesn't match it down to the character.

You don't design that layout, and you don't have to understand it. The tool builds the file from your reviewed calculation, following the agency's published structure, entirely on your own computer. Nothing is sent anywhere as part of producing it - generating the file and submitting it are separate acts, and the tool never submits for you.

For the step that produces this file, see the export step in [Upload your exported modelo at the AEAT portal](../how-to/file-at-aeat.md).

## A fingerprint for the exact file you produced

When the tool writes the upload file, it reports a fingerprint of the file's exact contents, along with the file's size. The fingerprint is a short code derived from every character in the file; change a single digit and the code changes completely.

This gives you a way to be certain later which file you actually uploaded. Note the fingerprint when you produce the file, and if a question ever comes up about which version you filed, you can re-derive the fingerprint from the file on disk and compare. Matching codes mean it's the same file; different codes mean something changed. It's a quiet safeguard, not something you need to act on day to day.

## Where this sits in your filing

Producing these outputs is near the end of the journey, not the start. The broader path - from your records, through calculation, to a file you can upload - is laid out in [Understanding the AEAT pipeline](index.md).

These outputs come after the completeness check described in [Editing and verifying a calculation](editing-and-verifying.md). Review and export are worth doing only once the tool is satisfied the modelo is complete; otherwise you'd be reviewing numbers that are still going to move.

Producing the upload file is not the same as filing it. What happens after you have the file - uploading it at AEAT yourself, and why the tool stops at the file rather than submitting - is covered in [Recording a filing, and why the tool never files for you](recording-a-filing-and-the-boundary.md).
