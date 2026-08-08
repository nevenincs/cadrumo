---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:df97cd0c022539b9ad7437d0299919df8299265743956afaa731581060d053ea'
step_id: 'S200'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Correction: this record previously asserted a fix that does not exist

An earlier version of this record claimed `UNSUPPORTED_IVA_RATE` "is mapped in
both preflight mappings at HEAD", evidenced by `grep -c` returning 2, "one per
mapping". **That was false**, and the evidence could not have supported it: a
count of token occurrences in a file cannot distinguish a mapping entry from a
comment. Measured through the live objects instead:

    _PREFLIGHT_REASON_BY_IVA_ISSUE  -> contains UNSUPPORTED_IVA_RATE: False
    _PREFLIGHT_DETAIL_BY_IVA_ISSUE  -> contains UNSUPPORTED_IVA_RATE: False
    _IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT -> True

Both occurrences the grep counted were the executing lane's work: one prose
mention inside a docstring, one classification entry. Commit
`7fc795177fa22eb110b038c321270139cf161bd4` carries the false claim in its message
and cannot be amended in a shared tree; this record is the correction of record.

## The row's premise was wrong, and the deliverable was correctly refused

`UNSUPPORTED_IVA_RATE` **cannot reach preflight**. Preflight consumes exactly two
aggregation screens — `iva_ledger_missing_fact_reasons` and
`validate_iva_ledger_counterparty_category`, called at `_preflight.py:480` and
`:488`. The reason is raised at a single site,
`application/aggregation/_iva_ledger.py:1295`, inside `_project_iva_transaction`
on the **projection** path, which preflight never enters. There was no `KeyError`
to fix.

Mapping it would have been actively harmful: it needs a new
`LedgerPreflightIssueReason` plus four locale strings for a condition the
readiness layer cannot detect — an unreached operator surface shipped by a
campaign whose dominant defect class is unreached surfaces. The nearest existing
reason, `MISSING_IVA_RATE`, would tell a taxpayer their rate is absent when it is
present and the year is not covered, which is the exact miscommunication the
enum's own comment warns against.

The executing lane classified the member as not-reaching, with its rationale
recorded in code, and **declined the literal deliverable**. That was the right
call.

## A second correction to the row's premise

The row attributed `UNSUPPORTED_IVA_RATE` to commit `360383e2`. That commit added
`IVA_RATE_DATE_OUTSIDE_TABLE_COVERAGE`; `UNSUPPORTED_IVA_RATE` is the
pre-existing member `360383e2` was written to stop over-firing.

## How the false claim survived to a checked row

Three compounding errors, all the coordinator's:

**A count used as a membership test.** `grep -c` answered "how many times does
this token appear", which was read as "is it in both mappings". The two questions
have the same answer often enough that the substitution feels safe.

**A number that matched the expectation.** Two mappings, count of 2, "one per
mapping" — the coincidence supplied the confirmation. A probe returning exactly
the expected value deserves more scrutiny than one that does not, not less.

**The row was closed on the coordinator's own measurement rather than the
executing lane's report.** The lane was mid-flight; the row was checked from a
sweeper's landing. Had the close waited for the report, the refusal would have
arrived with it.

## Disposition

The row stays checked because the question it opened is genuinely resolved — the
answer is that nothing should be mapped, and that answer is now recorded in code
and gated by `W09.P17.S201`'s partition. It is **not** a delivered-as-specified
close, and this record exists so the distinction is visible rather than hidden
under the same checkbox.
