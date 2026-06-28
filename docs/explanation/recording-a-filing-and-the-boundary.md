# Recording a filing, and why the tool never files for you

This page explains the last stretch of the journey: the line between the work you do on your own computer and the real Agencia Estatal de Administración Tributaria (AEAT, the Spanish tax agency). It is for everyday autónomos who have built a modelo, checked it, and now want to know how filing actually happens. The short answer is that you file it yourself, and the tool keeps a careful record around that act. This page is about why the boundary sits where it does.

## The boundary is permanent

The tool can never submit a return, register anything, or change a single value at the agency. This is not a cautious default you could switch off later. There is no setting, no flag, and no expert mode that turns it on. The submit path is built to refuse, every time, with a clear error rather than a quiet attempt.

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

When you file, the agency gives you a justificante - the official receipt confirming what it received. The tool can compare your local figures against that receipt to catch any disagreement. This is checking your record against the agency's receipt.

The comparison reads only the receipt you supply. It does not contact the agency to do its work. You hand it the justificante; it reports whether your record matches, diverges, or doesn't line up with any receipt yet.

For the steps, see [Reconcile a filed modelo against its justificante](../how-to/reconcile.md).

## What this comparison can and can't tell you

State this plainly, because it's easy to expect more than the tool delivers.

The comparison confirms that your local record matches the receipt's header fields - the modelo, the filing year, the period, and your tax ID. If your record and the receipt agree, it tells you so. If they disagree, it names the fields that don't match. It does not compare the individual box values; it checks that the receipt is for the same return.

It is **not** a live re-check of your maths against the agency. The tool does not ask AEAT to recompute your return and compare answers. It compares your record against a receipt you already hold, at the level of the header fields that identify the return.

The tool can also save read-only copies of the agency's own record as evidence - keeping a copy of what AEAT holds, so you have it on file. That too is comparison and record-keeping, not a fresh calculation. None of these steps re-derives your tax; they confirm what was filed and keep proof of it.

## Where this sits in the journey

This is the end of the pipeline that the [overview](index.md) lays out. Everything before it - building the modelo, checking it, recording the result - is yours to do locally; this page is where that local work meets the real agency, across a line the tool will not cross.

If a comparison turns up a mismatch and you fix it, re-checking the corrected version is covered in [Editing and verifying a calculation](editing-and-verifying.md). And once a filing is recorded, it becomes evidence the tool can lean on for later returns, which [How filings build on earlier ones](building-on-earlier-filings.md) explains.
