---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S107]]'
---

# `secure-storage-production-hardening` Code Review

## S107-001 | LOW | OFX provider diagnostics exposed source filenames and paths

Initial audit found that `OfxProvider` logged `path.name` during ingest and parse failure handling, and raised parse failures containing the raw source path.

Resolution: OFX diagnostics now use `<input-ofx>` for source identity, and parse failure messages no longer contain the raw filesystem path or basename.

Status: closed.

## S107-002 | LOW | OFX validation dialect exposed account identifiers

`validate_source()` previously returned `detected_dialect="accounts=..."` with OFX account identifiers. Those values may be bank account identifiers and should not appear in operator diagnostics.

Resolution: validation diagnostics now return `account_count=<n>` instead of account identifiers. Tests assert that multi-account validation does not include `ACC-1` or `ACC-2`.

Status: closed.

## S107-003 | INFO | Plaintext-exception classification retained

The provider reads caller-supplied OFX/QFX plaintext source files and emits `RawTransaction` records. It does not create secure-object repositories, write local side-store state, or derive secure-storage namespaces. The appropriate affected-file target remains `plaintext-exception`.

Status: closed.

## S107-004 | INFO | Tests exercise real OFX provider behavior

The tests parse real OFX text through `ofxparse`, inspect actual `ProviderValidation` output, and capture real provider logs for an invalid source file. They do not mock the parser or provider.

Status: closed.

## S107-005 | LOW | Shared financial provenance still carries source paths

`RawTransaction.provenance.source_path` is built by the shared `FinancialProvider` base from the resolved source file path. Future secure-storage enrollment should decide whether persisted financial observations store full paths, redacted labels, or secure object references.

Status: open follow-up.

## S107-006 | INFO | Final review found no high-severity defects

Final review found no HIGH or CRITICAL issues. The reviewer confirmed S107 is safe to commit and push with the shared financial provenance-path follow-up deferred, and confirmed the OFX tests are non-tautological real-behavior tests.

Status: closed.
