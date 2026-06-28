---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S10
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P01.S10`

Added unit-tier validation tests for `ProfileName` (and, in the
same module, `BucketId` — the same alias under a different name).

- Created: `src/aeat/domain/profile/test_constants.py`

## Description

Twelve real-behaviour tests exercise the alias from inside a
`pydantic.BaseModel` field so every test runs the constraint
validator pydantic generates from the `StringConstraints`. Coverage:

- Empty / whitespace inputs raise `ValidationError`.
- Strings longer than 128 chars raise `ValidationError`.
- Typical operator labels accepted.
- Surrounding whitespace stripped.
- Alias parity asserted (same string is a valid `ProfileName` and
  a valid `BucketId`).

Module-level marker `pytestmark = [pytest.mark.unit,
pytest.mark.domain_model]` carries the test through the project's
mandatory pytest marker policy. No mocks, no stubs, no skips.

## Tests

`uv run --no-sync pytest src/aeat/domain/profile/test_constants.py
-x -q` → 12 passed.
