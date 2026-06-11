# Editing and verifying a calculation

This page explains two ideas that sit at the heart of the tool: what a saved
calculation actually is, and what the completeness check does (and does not)
tell you. It's written for everyday taxpayers - an autónomo working through a
{term}`modelo` - rather than for accountants. AEAT is the
Spanish tax agency (Agencia Estatal de Administración Tributaria). If you want
the step-by-step actions, this page links out to the how-to guides; here the
focus is on understanding why the tool behaves the way it does.

## A calculation is a saved version, not a final answer

Each time you run a calculation, the tool saves that result as its own version
and keeps the ones that came before. Nothing is overwritten. The earlier
versions stay on disk exactly as they were.

This matters because tax work is rarely right the first time. You enter a
figure, calculate, spot something off, correct it, and calculate again. The
tool treats every one of those calculations as a distinct saved version,
identified by its exact contents. Two calculations with identical inputs are
the same version; change a single number and you get a new one, sitting
alongside the old.

The practical upshot: you can compare versions, and you can go back. A saved
version is a record of one attempt, not a verdict. The numbers are real, but
they're not committed to anything until you decide they are.

## Editing and recalculating

Some of a modelo's numbers come straight from your imported bank data. Others
can't - a figure you enter by hand, or a correction to what the tool worked
out. When that happens, you supply the missing value and recalculate, which
produces a new saved version reflecting your change.

A modelo is made of casillas (numbered boxes). Each box either holds a value or
waits for one. Editing is the act of giving a box the value the form still
needs, then recalculating so the totals reflect it. For the actual mechanics of
reviewing and changing box values, see
[Review and supply calculation inputs](../how-to/review-calculation-values.md).

## What verifying checks

Verifying runs a completeness check over a draft - a saved version you haven't
finalised yet. In plain terms, the check asks three things:

- Does every required box have a value, or are there required boxes with no
  value yet?
- Do the sums add up consistently, with no box contradicting another?
- Is there anything that blocks the form from being treated as complete?

The check reads the agency's published rules for that modelo and year, then
measures your draft against them. It produces a report and saves it, whatever
the result - even a draft that fails leaves a record, so you can see what was
checked and when.

## Complete, incomplete, or blocked

A draft lands in one of three states after the check:

- **Complete.** Nothing blocks it. The draft passed the completeness check and
  is marked as verified. The tool keeps the version in this finalised, locked
  state.
- **Incomplete.** The only thing standing in the way is required boxes with no
  value yet. An incomplete draft needs those boxes filled and the check re-run.
- **Blocked.** The check found an issue that stops the draft - a rule that
  failed, or a consistency problem - that you need to resolve before it can be
  marked complete.

The saved report is where the detail lives: which required boxes are still
empty, which rules failed, and what to do next. It separates issues that block
the form from issues that are only a warning - a warning surfaces something
worth a second look but doesn't stop the draft. For how to read the report and
act on each finding, see
[understand a verification report](../how-to/verification-reports.md).

## What verifying does not mean

This is the most important part of the page, so read it carefully.

A passed completeness check is a local check. It confirms that your draft is
internally consistent and that nothing required is missing, according to the
agency's published rules as the tool understands them. That is all it confirms.

In particular, verifying is **not**:

- **The agency accepting your filing.** The tool never contacts AEAT. A
  verified draft has been checked on your own machine, not reviewed or accepted
  by the tax agency.
- **A guarantee the upload will succeed.** Passing the check does not promise
  that submitting the form to AEAT will go through. Submission happens
  separately, outside the tool.
- **A deadline check.** The completeness check says nothing about whether you're
  on time. It does not look at filing deadlines at all. A draft can pass the
  check long after the deadline has passed, or well before it - the check
  neither knows nor cares.

Treat a passed check as "my draft is complete and consistent," never as "I have
filed" or "I am on time."

## Why the tool wants a verified version before it builds the upload file

When you ask the tool to produce the file you'll upload to AEAT, it works only
from a version that has passed the completeness check (or one already recorded
as filed). It refuses a plain draft.

The reason is protective. The upload file is the thing that leaves the tool and
goes to the agency. Building it only from a checked, complete version stops an
incomplete or inconsistent draft from being turned into a filing by accident.
The check is the gate the version has to clear before it can become an upload
file.

## Where this sits in the journey

This page is part of the
[Understanding the AEAT pipeline](index.md) cluster. Earlier filings feed into
later ones; for how a verified prior period carries forward, see
[How filings build on earlier ones](building-on-earlier-filings.md). Once a
version has passed the check, the next outputs - reviewing the result and
producing the upload file - are covered in
[Reviewing your numbers and producing the upload file](reviewing-and-exporting.md).
