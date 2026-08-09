---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:5d74cd1ea6e05681b42ac002c865beef756b4ab8ffe57d6ca3fd55e46ea90a7a'
step_id: 'S01'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Add label, legal_refs, and modelos fields to ProfilePreflightRequirement

## Scope

- `src/cadrumo/application/user_profile/_commands.py`

## Description

Added `label: str` (required, min_length=1, max_length=512), `legal_refs: tuple[str, ...] = ()`, and `modelos: tuple[str, ...] = ()` to `ProfilePreflightRequirement` in `_commands.py`, alongside the existing `selector`/`section_key`/`field_key`. `label` has no default deliberately - every real requirement row must carry one, and the anti-tautology test in `P01.S03` proves the strict model actually refuses a payload missing it.

## Outcome

Landed as designed. The follow-up code review (`2026-08-09-profile-requirement-grounding-audit`) found the *semantics* of `modelos` were wrong at the population site (P01.S02), not the field declaration here; this Step's shape held unchanged through that fix.

## Verification

`pytest src/cadrumo/application/user_profile/tests/ -m "unit or integration"` green at every re-run this session (最終 597/597 across the broader affected set). No dedicated model-shape test beyond the roundtrip and anti-tautology tests scaffolded under `P01.S03`.

## Notes

This session could not reliably use `git` (a shared `.git/index.lock` in this actively multi-agent worktree was unavailable for hours); this record cites file content and test runs rather than a commit SHA.
