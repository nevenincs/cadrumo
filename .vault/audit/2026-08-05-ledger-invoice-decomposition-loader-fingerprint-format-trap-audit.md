---
tags:
  - '#audit'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:24474eff961a02f662f5635e8acc227423f8e72e34bb7ed57c835fcc61f06a90'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# `ledger-invoice-decomposition` audit: `loader fingerprint format trap`

A standing registry-suite failure with a clean, self-contained diagnosis. Recorded because it belongs to no campaign, reappears in every full-suite run, and is expensive to rediscover: the traceback points at a `write_text` call and names a `KeyError` whose key is a fragment of TOML, which reads like registry corruption rather than a test bug.

## Finding

`test_single_file_modelo_same_size_same_mtime_edit_invalidates` in the registry loader-fingerprint collision module fails with:

```
KeyError: ' year_from = 2019, periods = '
```

The test builds a synthetic single-file modelo from a module-level template string and substitutes a casilla number through `str.format`. The template contains a TOML inline table:

```toml
period_selector = { year_from = 2019, periods = ["1T", "2T", "3T", "4T"] }
```

`str.format` treats every brace pair as a replacement field, so it parses `{ year_from = 2019, periods = ` as a field name and raises `KeyError` before any registry code runs. The failure is entirely inside the test's own string handling.

MEASURED at HEAD on 2026-08-05: the template literal and the `.format` call are both present, and the key in the traceback is byte-identical to the inline-table prefix.

## Why it is not what it looks like

The failure surfaces at a `write_text` line in a registry-loader test, so the natural reading is that the loader or the registry tree is broken. It is neither. No registry TOML is malformed, no loader behaviour is implicated, and the assertion the test exists to make - that a same-size, same-mtime content edit still invalidates the fingerprint cache - has never run. The test has been failing at setup, which means the invalidation property it guards is currently unproven rather than merely unverified.

That is the substantive risk: a fingerprint cache that failed to invalidate on a same-size same-mtime edit would serve stale registry content after a source change, and this is the test that would catch it.

## Remediation

Escape the literal braces (`{{` / `}}`) in the template, or stop using `str.format` for a template containing TOML inline tables - a plain replace of a sentinel token, or an f-string built per call, both avoid the collision. Then confirm the test actually exercises its invalidation assertion rather than merely passing setup.

Do not silence it by deleting or skipping the case; the property is real and currently unguarded.

## Ownership

Unowned. Discovered while running the registry suite for the income-measure grounding phase; the module is unrelated to that work and was not modified by it. Raised here so the diagnosis survives rather than being re-derived at the cost of a full suite run each time.
