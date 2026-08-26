---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:086316711e0dda26718ac36a6ed50455c4f3b33cef84983be6d194f817e47a63'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W01.P02.S09 independent review`

## Scope

Independent review of `W01.P02.S09`: the governing ordered-event and redaction decision, event variants, direct tests, and execution evidence. The review checked discrimination, ordering, UTC and receipt correlation, safe-fact enforcement, canonical observability ownership, the S10 interaction boundary, immutability, and serialization behavior.

## Findings

### unsafe-diagnostic-reference | high | Event reference fields admit raw sensitive or presentational text

`OperationLogRecord.diagnostic_ref` and `OperationDiagnosticEvent.diagnostic_ref` use the generic `OperationReference`, which constrains only length. Values such as a NIF, credential or token, full URL with query data, localized prose, or raw exception text therefore validate and enter the ordered event stream under a field documented as a redacted diagnostic reference. Rejecting an extra `message` field does not secure the admitted string channel. This violates the ADR requirement that event facts be safe and that secrets, localized prose, raw context, and exception payloads stay outside journals, events, diagnostics, and projections.

## Recommendations

- Use a canonical opaque diagnostic/correlation reference type whose syntax cannot carry prose, URLs, NIFs, exception rendering, or secret values, or validate these event fields at the event boundary against that exact contract. Add planted refusal tests for each prohibited family and one accepted canonical diagnostic reference.

The remaining reviewed contract is sound: seven event variants form a strict discriminated union; sequence, UTC, stable codes, and progress counts fail closed; terminal events correlate receipt identity, revision, and settlement time; models are frozen; and JSON round-trip restores the exact variant. S06 axes, S07 receipt identity, UTC validation, and observability capture remain canonical owners, while S10 interaction payloads are correctly deferred. Focused pytest reports 7 passes, Ruff passes, and basedpyright is clean, but these gates do not exercise the admitted reference channel. No critical or medium finding is asserted.

## Final re-review disposition

### unsafe-diagnostic-reference | open-high | Fingerprint length constraint is broader than canonical producers

Both event channels now use a dedicated `sha256:` lowercase-hex alias, and planted tests reject NIF, secret, token, bearer, URL/query/path, localized prose, and exception-shaped values on each channel. Live canonical producers emit exactly 12-character abbreviated or 64-character full fingerprints, so a narrow event alias is appropriate and does not duplicate observability capture or broad redaction logic.

However, the pattern `^sha256:[0-9a-f]{12,64}$` admits every intermediate length as well as the two canonical forms. Unsupported values such as 13- or 63-character fingerprints therefore validate, and no mutation test refuses an intermediate length. The reported 16 passing tests, Ruff, and basedpyright prove the prohibited families and endpoint lengths but not exact producer parity. The pattern must express exactly 12 or 64 lowercase hexadecimal characters and plant at least one intermediate-length refusal before the high finding closes. No critical or medium finding remains.

## Exact-shape closure disposition

### unsafe-diagnostic-reference | closed | Event references match only canonical fingerprint shapes

`OperationDiagnosticReference` now accepts only `sha256:` followed by exactly 12 or exactly 64 lowercase hexadecimal characters. The 13- and 63-character planted mutations fail, while both live canonical producer shapes pass. The prior prohibited-family tests continue to cover both log and diagnostic channels without introducing a second redaction or observability authority.

Final evidence records 18 event tests passed, Ruff passed, and basedpyright reported no diagnostics. No critical, high, or medium findings remain.
