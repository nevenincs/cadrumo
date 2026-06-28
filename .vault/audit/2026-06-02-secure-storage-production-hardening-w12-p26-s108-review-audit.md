---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S108]]'
---

# `secure-storage-production-hardening` Code Review

## S108-001 | LOW | N26 parser diagnostics exposed source filenames and paths

Initial audit found that `PdfN26Provider._extract_pages()` raised parse failures containing the caller-provided filesystem path. `validate_source()` converted that exception into `ProviderValidation.warnings`, making the path visible in operator diagnostics.

Resolution: N26 parser teardown now raises `InvalidFinancialSourceError` with `<input-pdf>` instead of the raw path. Tests assert the invalid-PDF validation warning does not include the source basename or absolute path.

Status: closed.

## S108-002 | LOW | Parser teardown logs could expose upstream traceback paths

Sidecar review found that a redacted log message using `exc_info=True` can still attach upstream traceback text containing parser-internal source path references.

Resolution: the N26 parser now logs the upstream exception type without attaching traceback data. The invalid-PDF regression test asserts captured log records do not carry `exc_info`.

Status: closed.

## S108-003 | LOW | N26 test carried a tautological assertion

The default-currency enrollment test asserted `result is not object()`, which is always true and does not test production behavior.

Resolution: the tautological assertion was removed; the test now asserts the function result against the project `DEFAULT_CURRENCY` constant.

Status: closed.

## S108-004 | INFO | Locale catalogue gaps repaired via canonical CLI

`python -m aeat.locales audit` surfaced missing catalogue leaves for the new N26 parse-failure key and existing refused-error keys `errors.refused.modelo_184_share_sum` and `errors.refused.modelo_347_threshold`.

Resolution: locale leaves were scaffolded and then set through `python -m aeat.locales`; unrelated scaffold formatting churn was removed before commit.

Status: closed.

## S108-005 | INFO | Plaintext-exception classification retained

The provider reads caller-supplied N26 PDF source files and emits in-memory `RawTransaction` records. It does not create secure-object repositories, write local side-store state, or derive secure-storage namespaces. The appropriate affected-file target remains `plaintext-exception`.

Status: closed.

## S108-006 | LOW | Shared financial provenance still carries source paths

`RawTransaction.provenance.source_path` is built by the shared `FinancialProvider` base from the resolved source file path. Future secure-storage enrollment should decide whether persisted financial observations store full paths, redacted labels, or secure object references.

Status: open follow-up.

## S108-007 | LOW | CLI rendering boundary remains broader than provider validation

The S108 tests cover provider validation warnings and logs directly. A broader CLI/envelope test should eventually assert that financial import/review commands do not surface raw source paths after provider validation failures.

Status: open follow-up.

## S108-008 | INFO | Final review found no high-severity defects

Final review found no HIGH or CRITICAL issues. The reviewer confirmed S108 is safe to commit and push with shared provenance-path and CLI rendering follow-ups deferred. The review also found the AFR register row still marked `AFR-006` as pending after the step row was closed; the register row was corrected to `closed`.

Status: closed.
