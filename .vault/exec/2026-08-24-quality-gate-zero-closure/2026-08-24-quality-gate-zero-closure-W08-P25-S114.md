---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:bea62688dbfa75d30c77217424866b38f7d5032a8eeced5f8854d2c7d928c51d'
step_id: 'S114'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Land the locale-bound assertion detector, joining each asserted literal against all four catalogues and enumerating the pinning forms from their declaration site rather than from observed usage -- _LANGUAGE_FLAGS, _LANGUAGE_FLAG_PREFIXES and the environment variable in language_argv.py, which together cover --lang and the spliced --flag=LANG spellings no test currently uses (Terra xhigh fixes and refactors)

## Scope

- `dev/quality/`

## Changes

- Added `dev/quality/locale_bound_assertions.py` with declaration-derived language flags, equals prefixes, and output-language environment key.
- Joined absence literals against the complete per-locale catalogue corpus supplied by the gate and retained only literals unique to a non-ambient locale.
- Bound pin state by same-scope AST traversal order, including preceding same-line assignments without borrowing nested scopes.
- Restricted helper and assignment propagation to causally proven output/environment values; mixed returns, unrelated arguments, nested mappings, and unknown dynamic f-string values remain unpinned.

## Verification

- `uv run pytest dev/quality/tests/test_locale_bound_assertions.py -q -k "not no_locale_bound_absence_survives_the_two_locale_axis"` -> `51 passed`.
- `uv run ruff check dev/quality/locale_bound_assertions.py dev/quality/tests/test_locale_bound_assertions.py` -> pass.
- `uv run ruff format --check dev/quality/locale_bound_assertions.py dev/quality/tests/test_locale_bound_assertions.py` -> pass.
- `uv run ty check dev/quality/locale_bound_assertions.py dev/quality/tests/test_locale_bound_assertions.py` -> pass.
- Formal review independently reproduced the complete-catalogue, same-line ordering, mixed-return, unrelated-argument, and unknown-dynamic-value controls and approved S114 with no HIGH/CRITICAL findings.

## Residual handoff

- The complete real-tree sweep reports eight live locale-bound absence assertions: seven on the Spanish ambient axis and one on the English axis. They remain deliberately visible as S115 repair input.
- Review: `[[2026-09-07-quality-gate-zero-closure-s114-locale-bound-detector-implementation-review-audit]]`.
