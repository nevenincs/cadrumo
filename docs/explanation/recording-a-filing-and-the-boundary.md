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

That refusal is deliberate. Filing a tax return is a legal act with your name on it. A piece of software that could press the button on your behalf would carry a risk you can never fully see. By making submission impossible, the tool removes that risk entirely and keeps you in the chair where the law expects you to be.

## Read-only access is the only connection

When you connect the tool to the agency, you grant it one thing: the ability to read your own data from AEAT, view-only. It can look at the returns you've already filed, the receipts on record, and the facts the agency holds about you. It reads this so it can show it to you and compare it against your local work.

Nothing flows the other way. The connection has no path that writes, edits, or registers. Reading your data, view-only, is the whole of what it can do at the agency.

## You upload the file yourself

The real submission happens in your own browser, on the agency's website, with your own login credentials - a digital certificate or Cl@ve (the Spanish government's shared identity login). You sign in as yourself, you upload the file the tool prepared, and you press submit. The tool never holds your credentials for this and never stands between you and the agency at that moment.

For the steps, see [Upload your exported modelo at the AEAT portal](../how-to/file-at-aeat.md).

## Recording a filing in your own records

After you've uploaded the return yourself, you come back and mark that saved version as final in your own history. This is recording that you've filed - a local note in your own records, like writing "sent" next to an invoice in your ledger.

It changes nothing at the agency. It does not submit, re-send, or confirm anything with AEAT. It marks one version as the answer you actually filed, so that later, when you look back, you know which numbers went out and when.

## Checking your record against the agency's receipt

When you file, AEAT gives you a justificante—the official receipt for the
filing. Justificante reconciliation checks the filing identity and the declared
total available in that receipt against the local filing record.

This comparison can read a receipt you supply or a justificante retrieved
through the separate read-only AEAT surface. It does not ask AEAT to recompute
the return or alter the authority's record.

For the steps, see [Reconcile a filed modelo against its justificante](../how-to/reconcile.md).

## What this comparison can and can't tell you

State this plainly, because it's easy to expect more than the tool delivers.

Two evidence comparisons are distinct. Justificante reconciliation compares
filing identity and the receipt's declared total. For modelos enrolled in
detailed comparison, a separately parsed filed declaración supplies the
per-casilla values that Cadrumo compares with the corresponding local values.
The justificante itself is not the source of that per-casilla comparison.

Neither comparison is a live re-check of your maths against the agency.
Cadrumo compares saved local values with already-issued evidence: identity and
declared total from the justificante, plus per-casilla values from the parsed
filed declaración where that modelo is enrolled.

The tool can also save read-only copies of the agency's own record as evidence - keeping a copy of what AEAT holds, so you have it on file. That too is comparison and record-keeping, not a fresh calculation. None of these steps re-derives your tax; they confirm what was filed and keep proof of it.

## Where this sits in the journey

This is the end of the pipeline that the [overview](index.md) lays out. Everything before it - building the modelo, checking it, recording the result - is yours to do locally; this page is where that local work meets the real agency, across a line the tool will not cross.

If a comparison turns up a mismatch and you fix it, re-checking the corrected version is covered in [Editing and verifying a calculation](editing-and-verifying.md). And once a filing is recorded, it becomes evidence the tool can lean on for later returns, which [How filings build on earlier ones](building-on-earlier-filings.md) explains.
