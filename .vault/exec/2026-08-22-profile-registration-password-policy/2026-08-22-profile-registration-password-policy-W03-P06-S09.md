---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:094ae1ba6fd37178837822eab75f9935e651787d0060200fc6dff327c5460d4f'
step_id: 'S09'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then align TUI assessment, registration attempts, and expected-error rendering with localized secret-safe application outcomes

## Scope

- `src/cadrumo/adapters/inbound/tui`

## Description

- Render canonical prospective-password reasons from stable application keys and safe facts.
- Carry expected refusals through a typed attempt envelope until rendering.
- Re-raise unkeyed failures into the existing unexpected-error path.

## Outcome

Live feedback and submission now consume the canonical assessment. The focused lane passes 14 integration cases, collection finds 11 registration-screen cases, and Ruff passes.

## Notes

Locale content remains S10-owned. The manager frontend was the necessary non-TUI attempt-envelope consumer.
