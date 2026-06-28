---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step15-exec]]'
---

# `calculation-truth-registry` Code Review

Review result:

- Initial review found one high-severity issue:
  - Successful model-specific extraction tests still expected
    `parse_declaracion` to produce extracted filings even though the extractor
    modules and dispatch registry were deleted.
- Initial review also found one low-severity issue:
  - `DeclaracionExtractor` still documented concrete extractor registration
    and routing through `get_extractor`.
- Fixes applied:
  - Replaced the quarterly, Modelo 130, and Modelo 303 extraction suites with
    fail-closed deletion/boundary tests.
  - Updated the extractor base docstring to describe it as a structural base for
    future registry-backed adapters.
- Follow-up review result: no remaining findings.
- Additional cleanup review result: no findings after deleting the orphaned
  generic extractor engine and removing its public export.

Verification reviewed:

- ruff passed on touched files.
- full ty passed.
- Focused pytest passed with 38 passed.
- Deletion gates check that only `_extractors/__init__.py` remains in the
  extractor package, the old Modelo 100 parser directory is absent, and the
  generic extractor engine is absent.

Residual risk:

- `parse_declaracion` remains public but intentionally fails closed at
  `get_extractor` until validated registry-backed extraction is implemented.
