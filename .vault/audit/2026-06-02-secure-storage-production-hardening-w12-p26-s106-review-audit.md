---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S106]]'
---

# `secure-storage-production-hardening` Code Review

## S106-001 | LOW | Declaracion parser diagnostics exposed operator source filenames

Initial audit found that `parse_declaracion` debug logs used `source_path.name`, and word-position fallback logging emitted the raw `pdf_path`. Those diagnostics could expose operator-controlled PDF basenames.

Resolution: parser debug logs now use `source=<input-pdf>`, and word-position fallback logging uses `<input-pdf>` plus the upstream exception type.

Status: closed.

## S106-002 | LOW | Template-not-detected locale context exposed raw PDF path

The template-not-detected error passed the raw `Path` object into error context. Locale strings interpolate `{path}`, and the core error registry passes `Path` values through, so CLI-rendered error text could expose the PDF path.

Resolution: the parser now passes `<input-pdf>` as the context value for `path`.

Status: closed.

## S106-003 | INFO | Plaintext-exception classification retained

The parser reads caller-supplied PDF input, extracts registry-grounded observations, and returns typed data. It does not write local side-store state, construct secure-object repositories, or bypass secure-storage persistence for application-owned records.

Status: closed.

## S106-004 | INFO | Tests exercise real parser behavior

The new tests parse a real corpus PDF under caplog, create a real markerless PDF to trigger template detection failure, and call word extraction on a real invalid PDF file. They do not mock pdfplumber, monkeypatch parser functions, or mirror implementation branches.

Status: closed.

## S106-005 | LOW | Declaracion pypdfium fallback log exposed raw paths

Reviewer follow-up found that the declaracion pdfplumber backend's pypdfium fast path logged the resolved input path on fallback.

Resolution: the fallback debug log now uses `<input-pdf>` plus the upstream exception type. A focused backend privacy test calls the real cached fast-path function with a sensitive-looking path and asserts emitted logs do not contain the raw path or basename.

Status: closed.

## S106-006 | LOW | Observation provenance still carries source_pdf_path

`DeclaracionObservation` still includes `source_pdf_path` as provenance. This is not emitted by the hardened logs/errors and is part of the existing typed observation schema, but future secure-storage enrollment should decide whether persisted observations store full source paths, redacted labels, or object references.

Status: open follow-up.

## S106-007 | INFO | Final review found no high-severity defects

Final follow-up review found no HIGH or CRITICAL issues. The reviewer confirmed the pypdfium debug-path leak is fixed, S106 is safe to commit and push with the documented `source_pdf_path` provenance follow-up deferred, and the new tests are non-tautological real-behavior tests.

Status: closed.
