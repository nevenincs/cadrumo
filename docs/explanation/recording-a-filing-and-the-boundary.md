# Recording a filing, and why Cadrumo never files for you

This page explains the last stretch of the journey: the line between local work
in Cadrumo and the real Agencia Estatal de Administración Tributaria (AEAT).
The taxpayer or authorized filer uploads the export, and Cadrumo keeps local
history around that human act. This page explains why the boundary sits there.

## The boundary is permanent

Cadrumo cannot submit a return, make a payment, acknowledge a notification, or
change a value at AEAT. This is not a cautious default that a setting can turn
off. No submission command exists. Cadrumo is always the local product; AEAT is
always the external authority and counterparty.

The refusal preserves human control over a legal filing act. It prevents
Cadrumo from initiating an authority-side change and keeps submission within
the official channel used by the taxpayer or authorized filer.

## Read-only access is the only connection

Configured AEAT access is read-only. It can retrieve filed returns, receipts,
and supported authority observations for local review and comparison.

Nothing flows the other way. The connection has no path that writes, edits, or registers. Reading your data, view-only, is the whole of what it can do at the agency.

## You upload the file yourself

Submission happens through an official AEAT channel with the filer's
credentials, such as a digital certificate or Cl@ve. The filer selects the
export and completes the authority's submission flow.

For the steps, see [Upload your exported modelo at the AEAT portal](../how-to/file-at-aeat.md).

## Recording a filing in your own records

After upload, the local filing record identifies the saved revision that was
filed and when the filing occurred.

This record changes nothing at AEAT. It does not submit, resend, or confirm a
return. It preserves which local revision was filed and when.

## Checking your record against the agency's receipt

When you file, AEAT gives you a justificante - the official receipt for the
filing. Justificante reconciliation checks the filing identity and the declared
total available in that receipt against the local filing record.

This comparison can read a receipt you supply or a justificante retrieved
through the separate read-only AEAT surface. It does not ask AEAT to recompute
the return or alter the authority's record.

For the steps, see [Reconcile a filed modelo against its justificante](../how-to/reconcile.md).

## What this comparison can and can't tell you

Two evidence comparisons are distinct. Justificante reconciliation compares
filing identity and the receipt's declared total. For modelos enrolled in
detailed comparison, a separately parsed filed declaración supplies the
per-casilla values that Cadrumo compares with the corresponding local values.
The justificante itself is not the source of that per-casilla comparison.

Neither comparison is a live re-check of your maths against the agency.
Cadrumo compares saved local values with issued evidence. The justificante
supplies identity and declared total. For enrolled modelos, the parsed filed
declaración supplies per-casilla values.

Cadrumo can save read-only authority records as local evidence. This supports
comparison and record-keeping, not a fresh calculation. These operations do
not re-derive the tax result.

## Where this sits in the journey

This stage connects local preparation with the external authority. Cadrumo
prepares and records locally. The taxpayer or authorized filer completes the
official submission.

If a comparison finds a mismatch, [Editing and verifying a
calculation](editing-and-verifying.md) explains local correction. A recorded
filing can support later returns, as [How filings build on earlier
ones](building-on-earlier-filings.md) explains.
