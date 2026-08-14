---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:cb34d6bca680314addf9bf392067f4674006c635c4d2c14a8d4c545a92ae9c66'
step_id: 'S09'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define ordered phase, progress, safe-log, effect, notice, diagnostic, and terminal event contracts

## Scope

- `src/cadrumo/application/operations/_events.py`
- `src/cadrumo/application/operations/tests/test_events.py`

## Description

- Re-ground ordered event identity, cursor sequence, safe facts, redaction, observability composition, and terminal settlement in the live accepted ADR, plan, research, semantic code/vault results, and targeted source census.
- Define a strict discriminated `OperationEvent` union with immutable phase, progress, safe-log, effect, notice, diagnostic, and terminal variants.
- Carry only stable codes, bounded numeric progress, closed axes, and validated opaque `sha256:` diagnostic correlation references; exclude localized prose, exceptions, raw context mappings, raw identities, secrets, tokens, bearers, URLs, query/path material, and secret-bearing message channels.
- Bind terminal events to the exact terminal receipt identity, revision, and settlement timestamp.

## Outcome

- Reused S06 `OperationEventKind` and `OperationEffect`, S07 identity/revision/receipt models, UTC validation, and observability diagnostic references rather than redeclaring their authorities.
- `OperationLogRecord` is a safe lifecycle projection and does not replace the existing observability sink, capture, retention, or redaction implementation.
- Sequence begins at one, event codes follow stable machine syntax, progress cannot exceed its total, union discriminators fail closed, and terminal facts cannot drift from their receipt.
- Remediation gates passed: `uv run pytest src/cadrumo/application/operations/tests/test_events.py -q` reported `18 passed in 4.00s`; Ruff reported `All checks passed!`; basedpyright reported `0 errors, 0 warnings, 0 notes`.

## Notes

- Live code and vault semantic queries succeeded on port 8766. The code index warned that `7314` of `96048` published sections were missing, so absence was not used as evidence; targeted `rg` and whole epicenter reads adjudicated existing event, notice, diagnostic, severity, redaction, and observability owners.
- Live remediation grounding found existing diagnostic fingerprints emitted as `sha256:` plus exactly 12 or exactly 64 lowercase hexadecimal characters. `ContentDigest` is not a superset because it omits the prefix and excludes the established 12-character correlation form, so S09 owns only the narrow `OperationDiagnosticReference` boundary alias and does not duplicate broad redaction. Planted tests refuse raw NIF, secret, token, bearer, URL/query/path, localized prose, and exception-like inputs on both log and diagnostic channels; 13- and 63-character mutations prove intermediate fingerprint lengths fail closed while exact 12- and 64-character producer shapes pass.\n- The interaction event family remains reserved for S10 and is not duplicated here.
- Final independent review closed all critical, high, and medium findings. The binding plan row was closed via `vault plan step check`. `uvx vaultspec-core vault check all` exited zero with `1360 warnings`; global residuals include 4 annotation warnings, 39 markdown warnings, 29 schema warnings, 3 modified-stamp warnings, and the pre-existing body-schema corpus findings.
