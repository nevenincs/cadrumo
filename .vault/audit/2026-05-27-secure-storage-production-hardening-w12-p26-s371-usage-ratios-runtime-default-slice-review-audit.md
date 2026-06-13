---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-production-hardening-w12-p26-s371-usage-ratios-runtime-default-slice-exec]]'
---



# `secure-storage-production-hardening` Code Review

S371-USAGE-RATIOS-RUNTIME-001 | FIXED | Route-strict defaults initially exposed unenrolled census tests

The first review found that the service migration correctly enforced bucket-route matching, but `test_census_refuse_load.py` still activated the generic default test bucket while calling usage-ratio APIs with `bucket_id="b1"`. The fixture now activates `b1`, and the full usage-ratio package test suite passes under the stricter runtime contract.

S371-USAGE-RATIOS-RUNTIME-002 | FIXED | Non-UTF-8 payload bytes leaked a codec exception

The first review found that malformed secure-object payload bytes that were not valid UTF-8 bypassed the intended `UsageRatioPersistenceError` surface. `load_usage_ratios` now logs and wraps `UnicodeDecodeError` as `UsageRatioPersistenceError`, and a real encrypted repository regression covers the path.

S371-USAGE-RATIOS-RUNTIME-003 | INFO | Re-review found no remaining findings

After the census fixture enrollment fix and non-UTF-8 persistence-error regression, the `vaultspec-code-reviewer` re-reviewed the usage-ratio runtime-default slice and reported no findings.

S371-USAGE-RATIOS-RUNTIME-004 | INFO | Focused runtime coverage is adequate for this slice

Focused validation covers package-level usage-ratio behavior, missing-session refusal, route-mismatch refusal, active-profile isolation, direct-constructor removal from the service, and focused lint for every changed production and test module.
