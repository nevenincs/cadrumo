---
tags:
  - '#reference'
  - '#canonical-exception-remediation'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:7f9746030fa4a795f3d422fe7864fa937ea3359e9601cf4cef36789f67e28a18'
related:
  - "[[2026-09-14-ast-exception-gate-remediation-closeout-review-audit]]"
---

# `canonical-exception-remediation` reference: `production inventory`

The repaired source gate and an independent builtins-wide AST scan establish the
production migration surface and the registry/envelope contracts each package must
preserve.

## Summary

The source inventory contains 69 direct built-in exception roots: the intentional
`CadrumoError` root, the Playwright protocol fallback, and 67 Cadrumo-owned migration
targets. Owned targets partition into 48 application, 9 entrypoint, 5 domain, 2
adapter, and 3 core exceptions. The repaired five-base gate
misses `OperationObservationUnknownOperationError`, whose `LookupError` base is at
`src/cadrumo/application/operations/persistence/journal.py:200`.

Migration produces 80 new registry identities because 13 currently unregistered
descendants enter the canonical hierarchy with their bare parent. These include the
manifest validation, authority artifact/store, and TUI navigation families.

`CadrumoError.__init_subclass__` binds subclasses by exact fully qualified identity at
`src/cadrumo/core/errors/hierarchy.py:110`. Registry rows require unique codes,
categories, message keys, retryability, and runbook identities at
`src/cadrumo/core/errors/error_codes.py:86`; envelope construction and redaction live in
the same module at line 300.

Core failures use `CoreError` or `CoreValidationError`. Other layers retain concrete
definitions in the narrowest owning module and derive from `CadrumoError` unless a more
specific registered root exists. Layer shards compose at
`src/cadrumo/core/errors/registry/declared_codes.py:15`.

Private control-flow carriers must become typed results or registered private
exceptions. The optional Playwright fallback at
`src/cadrumo/adapters/outbound/aeat/_playwright.py:46` is the only discovered external
exception-type boundary; installed Playwright supplies the third-party class and the
absent-extra fallback only keeps typed catch sites importable.

Enrollment tests follow `src/cadrumo/adapters/persistence/storage/tests/test_errors.py:24`
and `src/cadrumo/core/bucket/tests/test_bucket_errors.py:38`: assert canonical ancestry,
unique registration, safe context, and envelope round trips.
