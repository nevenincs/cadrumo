---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:a28bc81a2706630d869a50340f05afdc890fb452c269571b40aadac87b5f3f8b'
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

## Review remediation

The duplicate TUI reason, message-key, and safe-fact projection was deleted. Live feedback now consumes the same exported application projection used by registration and rotation, and every canonical refusal test proves exact equality between the live projection and submitted attempt envelope.

The original 14-scalar crash has a real headless regression covering the live strength widget and submitted status channel. It proves a typed refusal is visible while `app.error` remains empty, and excludes INTERNAL guidance, raw custody English, traceback text, the candidate, and profile persistence. A separate unkeyed worker failure proves genuine unexpected faults still retain `app.error` and render the localized INTERNAL boundary message.

The remediated registration, language-switch, and manager refusal lane passes 19 cases. Ruff check and format-check pass. One pre-existing Textual context teardown warning remains in the language-switch lane and does not fail the suite.
