---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-29'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S120]]'
---

# `secure-storage-production-hardening` Code Review

## S120-001 | LOW | Deserialiser errors could expose malformed wire bytes

Initial audit found that RESERVED mismatch errors included `raw!r`, and envelope collision errors echoed parsed divergent values. For a remote/export parse boundary, malformed payloads may contain taxpayer identifiers or filing values; diagnostics should identify the failure without copying the offending payload.

Resolution: malformed byte diagnostics now report length plus a short SHA-256 digest. Multi-segment divergent casilla and field errors name the colliding key but no longer include the conflicting values.

Status: closed.

## S120-002 | LOW | Decode failures could escape outside the AEAT export error hierarchy

Date parsing, invalid currency digits, and text decode failures could surface as stdlib `ValueError` or `UnicodeDecodeError`. That made the API less consistent under corrupt remote/export inputs.

Resolution: date, currency, and text decode failures now raise `AeatExportFormatError` with redacted length/digest context and no retained stdlib exception cause/context for malformed wire payloads.

Status: closed.

## S120-003 | INFO | Canary tests cover malformed wire privacy

New malformed CURRENCY and RESERVED tests feed taxpayer-like byte canaries through the real `deserialise()` path and assert the resulting `AeatExportFormatError` messages include length/digest breadcrumbs but not the raw canary bytes.

Status: closed.

## S120-004 | MEDIUM | Broader golden export validation exposed real registry and golden-output drift

The first broader export-format run did not provide usable closure evidence. It stopped on registry validation before the Modelo 130 and Modelo 303 golden tests could exercise the export surface, and the later focused run exposed a stale Modelo 303 BOE golden hash. Treating that as an external blocker would have hidden a real validation gap.

Resolution: the run was pursued to completion. Modelo 151 now validates in `test_modelo_151_registry.py`. At the time of S120, Modelo 714 Phase-A data no longer contained invalid placeholder formula rows; that historical registry test asserted the then-current manual patrimonio baseline rather than accepting fake business logic. Currentization on 2026-06-29: Modelo 714 now computes the art. 30 cuota íntegra scale (casilla 29) and the art. 31 80%-floor reference (casilla 39) from BOE-grounded registry formulas. The Modelo 303 golden hash was refreshed only after checking the official DP30303 workbook rows for casillas 110, 78, and 87 and adding byte-offset assertions for those fields. The broader export-format batch then passed with 114 tests.

Status: closed.

## S120-005 | MEDIUM | Chained stdlib exceptions could retain raw wire payloads

Mandatory review found that the first typed wrapping pass used exception chaining. Even with redacted `AeatExportFormatError` messages, a full traceback or debug renderer could still expose the original stdlib `ValueError` or `UnicodeDecodeError` containing raw decoded bytes.

Resolution: the date, currency, and text decode wrappers now capture only the stdlib failure type and raise outside the `except` context, leaving `__cause__` and `__context__` unset for the malformed payload cases covered by S120. The tests assert this for date and currency canaries.

Status: closed.

## S120-006 | INFO | Mandatory re-review found no remaining blockers

The mandatory S120 re-review confirmed that the prior medium chained-exception privacy finding is closed and found no remaining medium, high, or critical issues in the S120 scope.

Status: closed.

## S120-007 | MEDIUM | Invalid Modelo 714 placeholder formulas could make registry coverage tautological

During the broader export validation, fresh registry loading rejected Modelo 714 because the Phase-A formula table contained invalid placeholder entries rather than real registry formulas. Keeping those rows would have made the new registry coverage a shape test around fake data.

Resolution: the placeholder formula entries were removed, the construct scope was aligned to existing legal/source/application references, and `test_modelo_714_registry.py` then proved the manual casilla baseline through the real registry loader. Currentization on 2026-06-29: the same registry surface now carries real formulas for casilla 29 (`patrimonio-cuota-integra-escala-estatal`) and casilla 39 (`patrimonio-reduccion-limite-80-suelo`), so the S120 manual-baseline statement is historical rather than current. The focused Modelo 714 registry test passed with 4 tests, and the touched registry/test files passed Ruff.

Status: closed.

## S120-008 | INFO | No HIGH or CRITICAL findings remain for S120

After the follow-up validation and registry/golden-output corrections, no high or critical S120 findings remain. The medium issues above are closed, with evidence recorded in the paired execution note.

Status: closed.
