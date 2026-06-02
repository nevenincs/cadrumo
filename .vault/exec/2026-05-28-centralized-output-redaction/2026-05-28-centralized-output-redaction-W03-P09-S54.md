---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
step_id: 'S54'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# W03.P09.S54 profile lifecycle redaction expectations

Scope: update profile lifecycle CLI tests where centralized output redaction now owns profile-id placeholders and current localized confirmation labels.

## Description

- Replace local `<profile-id>` literals with the shared CLI profile placeholder constant.
- Keep operator-facing profile labels visible in lifecycle text output.
- Update quiet create/edit confirmation assertions to match the current localized status labels.
- Extend central text redaction to tab-separated profile-id fields so profile and bucket identifiers are placeholdered before generic NIF hashing can touch UUID-shaped values.

## Outcome

S54 is implemented for the current `test_profile_lifecycle_verbs.py` surface.

## Notes

Focused ruff and pytest passed for core redaction and `test_profile_lifecycle_verbs.py`. A central redaction-order defect was fixed after the lifecycle tests exposed malformed `sha256:<profile-id>` output for some tab-separated profile-id lines.

Verification:

- `uv run --no-sync ruff check` passed for the S54 redaction files plus the shared PDF primitive surface that previously blocked collection.
- `uv run pytest -q` passed for shared PDF primitive tests, core redaction tests, and profile lifecycle tests: 75 passed.
- The broader redaction/repair privacy collection passed after the current worktree's PDF import surface was present: 54 passed.
- Mandatory follow-up review reported no HIGH or CRITICAL findings.
