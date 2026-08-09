---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:8574083fa239ed271a1ecb2b6b51e08f3e46ab753f9d4fbeac041d4ea55567b1'
step_id: 'S21'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add the undeclared taxpayer-model refusal locale string with real translations in all four catalogues

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Added `cli.overview.refused_undeclared_taxpayer_model` through the locale CLI in all four catalogues with real translations, carrying a `%{requirements}` placeholder.
- Left the pre-existing `cli.overview.taxpayer_model_undeclared` in place: it is still consumed by the application layer as the calendar's `incomplete_reason`, which is a payload field rather than the CLI refusal text.

## Outcome

The new refusal string exists in all four catalogues with real translations.

The old key was deliberately NOT removed. Unlike the two superseded keys retired earlier in this work, this one still has a live consumer: the application layer sets it as `incomplete_reason` on the calendar payload, which machine consumers read. Removing it because the CLI stopped rendering it would have broken that payload.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

The check reports no `extra` key, which confirms the retained key is still referenced rather than orphaned.

## Notes

No placeholder or self-referencing value in any catalogue.
