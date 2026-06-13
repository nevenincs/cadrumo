---
tags:
  - '#exec'
  - '#draft-approval-staleness'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-draft-approval-staleness-plan]]'
---

# `draft-approval-staleness` `phase4` `ux-followup`

Closed the manual-testing regressions and operator-guidance gaps discovered
while verifying the approval/staleness rollout.

- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/review/__init__.py`
- Modified: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`
- Modified: `src/aeat/entrypoints/cli/review/test_review_cli.py`

## Description

Live CLI verification against a real persisted draft found that `aeat filing
build` emitted a Unicode arrow in its success message and crashed on the native
Windows cp1252 console after the draft was written. The fix converts the filing
CLI success messages to ASCII-only output and adds explicit next-step guidance
across the filing and review surfaces so operators can move directly from build
to review to preflight without reverse-engineering the workflow. The review
commands still accept both draft IDs and explicit paths, but the default UX now
pushes draft-ID driven usage consistently.

## Tests

Validated with:

- `uv run ruff check src/aeat/entrypoints/cli/filing/__init__.py src/aeat/entrypoints/cli/review/__init__.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/review/test_review_cli.py`
- `uv run pytest src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/review/test_review_cli.py`
- Manual CLI flow covering `aeat filing build` -> `aeat review approve` -> `aeat filing validate` -> transaction-catalogue drift -> `aeat review show` -> `aeat review stale` -> `aeat submission preflight`
