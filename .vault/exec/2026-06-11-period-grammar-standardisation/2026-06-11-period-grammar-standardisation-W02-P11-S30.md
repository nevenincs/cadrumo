---
tags: ['#exec', '#period-grammar-standardisation']
date: '2026-06-11'
step_id: 'S30'
related:
  - '[[2026-06-11-period-grammar-standardisation-plan]]'
---

# W02.P11.S30 Add Combined Period String Gate

Scope: add a core regression gate for combined period strings across tracked `src/aeat` and `docs` text files.

## Description

- Add a repo-wide pytest gate under the core test suite that scans tracked text files under `src/aeat` and `docs`.
- Match calendar-quarter tokens, year-qualified quarterly hybrids, and `period=` assignments whose value starts with a combined year token.
- Exclude generated, cache, build, and binary-style paths from scanning.
- Keep `.vault` history out of scope by scanning only the configured source and docs roots.
- Allow registry modelo TOML authoring inputs, explicit refusal/regression tests, Period docs/tests, privacy-redaction strings, and external/corpus fixture labels with documented allowlist rules.
- Emit failures as `path:line` diagnostics with the matching pattern name and source snippet.

## Outcome

The core suite now carries a ratchet test that fails on newly introduced unallowlisted combined period strings while preserving known intentional legacy examples and fixture labels. Verification passed with ruff clean, the focused core period suite at `69 passed`, and CLI import smoke printing `OK`.

## Notes

Required RAG grounding timed out with `HTTP search on port 8766 timed out after 30.0s` and `code=http_search_timeout`; direct `rg` discovery and code inspection provided grounding.
