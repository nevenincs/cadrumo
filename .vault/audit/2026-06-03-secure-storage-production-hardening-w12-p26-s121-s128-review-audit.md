---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s121-s128-exec]]'
---

# `secure-storage-production-hardening` Code Review

## S121-001 | INFO | Record-spec surface is parser metadata, not a remote mirror

`_record_spec.py` defines strict record/layout metadata consumed by export parsing. It does not create storage providers, mirror manifests, local side-stores, or remote object state. The broader export-format batch passed with 114 tests after the S120 registry/golden-output blockers were resolved.

Status: closed.

## S122-001 | INFO | Censo live remains read-only remote-provider code

`_censo_live.py` uses authenticated browser state and read-only Sede navigation. The provider boundary remains aligned with the existing AEAT outbound convention: remote state is guarded through read policies and Playwright errors are converted to Sede exceptions rather than swallowed.

Status: closed.

## S123-001 | MEDIUM | Declaration PDF bbox extraction used a weaker plaintext temp-file bridge

Initial review found that `_observed_casillas_from_declaration_pdf()` wrote declaration PDF bytes with `NamedTemporaryFile(delete=False)` before reopening the path for pdfplumber. The file was unlinked in a `finally`, but this was still a plaintext-at-rest bridge for taxpayer declaration PDFs and did not use the existing private-fd sensitive temp convention.

Resolution: the bbox path now uses `_temporary_sensitive_pdf_path()`, created by `tempfile.mkstemp`, writes through the already-open file descriptor, closes the descriptor before pdfplumber reopens the path, and unlinks the file on exit. The new real filesystem test proves the payload is written, mode is private on POSIX, and the file is removed after the context.

Status: closed.

## S123-002 | MEDIUM | Production write inventory had unreviewed diagnostic/reference writers

The production file-write inventory gate exposed three unreviewed writes while validating S123: the IVA wallet diagnostic summary and the ECB reference-rate refresh temporary/target writes. Leaving the inventory failing would make the closeout evidence weaker than the code state.

Resolution: the IVA wallet diagnostic writer is now classified as an operator-enabled redacted structural diagnostic, with a real Playwright-backed test proving raw query/input canaries, wallet amounts, and table labels do not enter the written summary. The ECB refresh writes are classified as maintenance writes for bundled official reference-rate data after parse validation. The full production write inventory now passes.

Status: closed.

## S124-001 | INFO | NIF/IVA check remains read-only remote-provider code

`_nif_iva_check.py` stays within the authenticated read-only Sede/VIES provider boundary. Remote operations are allow-listed, navigation failures are raised as AEAT Sede or registry validation exceptions, and the reviewed scope does not add persistence.

Status: closed.

## S125-001 | INFO | Filed-observation store uses active-bucket secure objects

`_observation_store.py` persists filed-declaration observations and captured artefacts through the runtime active-bucket secure-object repository. It does not retain JSON/JSONL plaintext side-stores or direct constructor defaults outside the existing secure-object boundary.

Status: closed.

## S126-001 | INFO | Sede parser remains a plaintext-exception parser boundary

`_parse.py` parses Sede HTML into typed data and raises `SedeParseError` on malformed remote shape. It does not write storage state. The reviewed exceptions preserve typed AEAT errors rather than swallowing malformed input.

Status: closed.

## S127-001 | INFO | Renta WEB Open safety remains remote-operation guard code

`_renta_web_open_safety.py` validates allowed read-only URLs and browser actions for the remote provider. The reviewed suppressions are limited to best-effort dialog dismissal and do not hide provider read/write classification failures.

Status: closed.

## S128-001 | INFO | Verify boundary remains read-only and storage-free

`verify/__init__.py` drives AEAT verification as a read-only remote provider. It validates remote operation policy, returns typed verification results, wraps failures as `JustificanteVerificationError`, and closes self-owned browser state best-effort without creating persistence state.

Status: closed.

## S121-S128-001 | INFO | No HIGH or CRITICAL findings remain

No high or critical findings were identified for S121 through S128 after remediation. The two medium issues found during this pass are closed with implementation changes and focused validation, not carried as residuals.

Status: closed.
