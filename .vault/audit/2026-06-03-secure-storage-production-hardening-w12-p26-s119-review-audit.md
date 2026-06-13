---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S119]]'
---

# `secure-storage-production-hardening` Code Review

## S119-001 | LOW | Site-health HTML evidence accepted raw remote-provider fragments

Initial audit found that `SiteHealthEvidence.html_fragment` was bounded to 4096 characters but accepted the remote response body unchanged. A bounded raw fragment can still carry taxpayer identifiers, URL paths or query tokens, and bearer-token-shaped text into `SiteHealthError`, workflow alerts, diagnostics, or logs.

Resolution: `SiteHealthEvidence` now applies `aeat.core.redaction.redact_for_log()` to `html_fragment` during pydantic model construction. The evidence record remains strict, frozen, and bounded, and the redacted value is sliced back to the same 4096-character limit so the post-redaction payload cannot exceed the evidence cap. Diagnostic fragments use the same centralized audit/log redaction policy as exception text.

Status: closed.

## S119-002 | INFO | Parser-boundary regression covers remote HTML evidence

The new WAF parser regression builds a real classified HTML response containing a NIF canary, URL path/query, and bearer-token canary. It asserts the returned `SiteHealthStatus.evidence.html_fragment` retains useful classification context while removing the raw sensitive values.

Status: closed.

## S119-003 | INFO | Remaining rows stay open

S119 does not close export deserialization, record-spec, or censo-live affected-file rows. Those remain pending as `W12.P26.S120` through `W12.P26.S122`.

Status: open follow-up.

## S119-004 | INFO | Mandatory review found no blockers

The mandatory S119 code review found no high or critical issues and no actionable privacy regression. It confirmed the central redaction path, post-redaction evidence bound, parser-boundary test coverage, and plan traceability for AFR-017 closure.

Status: closed.
