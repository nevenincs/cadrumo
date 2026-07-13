# Editing and verifying a calculation

This page explains saved calculation revisions and local verification. The
Agencia Estatal de Administración Tributaria (AEAT) remains the external tax
authority. Task steps stay in the linked how-to guides.

## A calculation is a saved version, not a final answer

Each time you run a calculation, the tool saves that result as its own version
and keeps the ones that came before. Nothing is overwritten. The earlier
versions stay on disk exactly as they were.

Corrections often change calculation inputs. Cadrumo records each distinct
result as a content-identified revision. Identical inputs resolve to the same
revision; changed inputs produce another revision.

The practical upshot is that review, verification, and export can name one
exact revision. A saved revision is a record of one calculation, not an AEAT
verdict and not a submission.

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

The check applies the published rules for the modelo and year. It also checks
required dependencies outside the draft. These include evidenced earlier
periods, reconciled value-added tax (IVA) balances, and stable source revisions for carried
values. Cadrumo saves the verification report for every outcome.

## Complete, incomplete, or blocked

A draft lands in one of three states after the check:

- **Complete.** Nothing blocks it. The draft passed the completeness check and
  is marked as verified. Cadrumo retains the version in this finalised, locked
  state.
- **Incomplete.** The only thing standing in the way is required boxes with no
  value yet. An incomplete draft needs those boxes filled and the check re-run.
- **Blocked.** The check found a failed rule, consistency problem, or external
  dependency. Examples include an unevidenced prior period, unreconciled IVA
  balance, or changed carry-forward source. The report identifies the cause.

The saved report lists empty boxes, failed rules, and suggested actions. It
separates blocking issues from warnings. Warnings identify review items without
stopping the draft. For how to read the report and
act on each finding, see
[understand a verification report](../how-to/verification-reports.md).

## What verifying does not mean

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

A passed check means the revision passed Cadrumo's local checks. It does not
mean AEAT accepted the filing, submission occurred, or the filing is timely.
The [command and stage lookup](../reference/commands-and-configuration.md)
links exact verify, report, and export definitions.

## Why verification is necessary but not sufficient for export

When you ask Cadrumo to produce the file you may upload to AEAT, it requires an
eligible verified revision (or the applicable already-filed state). It refuses
a plain draft.

Verification is one gate, not the whole export decision. The export boundary
also checks required evidence and other filing-specific preconditions. A
revision can therefore pass verification and still be refused at export with
the missing evidence or failed gate identified. This separation prevents a
locally consistent revision from becoming an upload artifact before its
required provenance is present.

## Where this sits in the journey

This page is part of the
[Understanding Cadrumo's tax-preparation workflow](index.md) cluster. Earlier filings feed into
later ones; for how a verified prior period carries forward, see
[How filings build on earlier ones](building-on-earlier-filings.md). Review
precedes verification. Export follows verification and the remaining evidence
gates. The upload artifact is covered in
[Reviewing your numbers and producing the upload file](reviewing-and-exporting.md).
