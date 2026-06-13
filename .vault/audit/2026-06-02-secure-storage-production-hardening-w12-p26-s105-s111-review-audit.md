---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S105]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S111]]'
---

# `secure-storage-production-hardening` Code Review

## S105-S111-001 | LOW | Shared pdfplumber path errors exposed operator filenames

The S105 review found that the Borrador backend delegates into the shared pdfplumber primitive, where path-based failures formatted raw `pdf_path` values into exception text. Missing files, invalid PDFs, scan-only PDFs, and concatenated extraction failures could expose operator-controlled basenames or full paths.

Resolution: `src/aeat/adapters/inbound/pdf/_pdfplumber.py` now uses the stable `<input-pdf>` placeholder for path-based failure messages and reports only the upstream pdfplumber exception type name instead of interpolating third-party exception text.

Status: closed.

## S105-S111-002 | INFO | Plaintext-exception classification retained

The Borrador backend and shared pdfplumber primitive read caller-supplied PDF input and return in-memory page text. They do not persist secure objects, construct repositories, create local side-store state, or derive storage namespaces. The appropriate affected-file target remains `plaintext-exception`.

Status: closed.

## S105-S111-003 | INFO | Regression tests exercise real parser behavior

The new tests create real missing, invalid, and blank PDF inputs and assert on raised exception text. They do not mirror implementation branches, monkeypatch pdfplumber, or use fake parser objects.

Status: closed.

## S105-S111-004 | LOW | Byte-stream source labels remain caller-controlled

The byte-stream extraction path still includes caller-provided `source_label` values in exception messages. That label is not a filesystem path and is intentionally provided by callers, but future audit passes should confirm every caller supplies non-sensitive labels or centralize byte-stream label redaction.

Status: open follow-up.

## S105-S111-005 | INFO | Final review found no high-severity defects

Final review found no HIGH or CRITICAL issues and confirmed S105/S111 are safe to commit and push. The reviewer confirmed the new tests are non-tautological because they exercise real parser failure modes without mocks, fakes, monkeypatching, skips, or xfails.

Status: closed.
