---
tags:
  - '#audit'
  - '#auth-frontend-uniformity'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:c31fcba2bbf18de492ffab3e91fe6059822f4cff362bf0888793af53d0ba3526'
related:
  - "[[2026-10-02-auth-frontend-uniformity-plan]]"
---

# `auth-frontend-uniformity` audit: shared authentication configuration

## Scope

Review S01-S03 against accepted profile-auth, TUI supervision, and certificate lifecycle decisions. Base 3d40c2a658; candidate 28fd5c3a76 and f1503bc78f plus S02 review corrections and S03 integration tests and capture refresh. Trace configuration through encrypted profile facts, operational state, CLI, installed TUI worker, registered operation, public observation, and result projection. Preserve concurrent filing and locale edits.

## Findings

### profile-subject | high | Bind delayed saves to the displayed profile before admission

The shared submission helper reconstructed its subject from the current active bucket. A delayed worker launched from an older profile screen must retain that screen's exact profile subject so the executor's active-profile guard refuses a switch. This requires an explicit profile identity at shared submission and composition, passed from the installed account closure and CLI admission. Initial status: REVISION REQUIRED pending the scoped correction and a real profile-switch refusal proof.

### failure-taxonomy | high | Preserve public failure category and retryability

Forwarding all supervised codes through CoreValidationError reclassified failures as integrity errors and discarded canonical retryability. The correction uses a registered core PublicErrorProjectionError carrying only a registered code and an optional validated diagnostic hash. The common envelope resolves the original code's category, message key, retryability and runbook; no private executor exception or context is recreated. Anonymous failures retain INTERNAL_INVARIANT with their opaque diagnostic reference. Status pending final error-contract verification.

## Recommendations

Verify both corrections within S02, then complete S03 visual and contract evidence before the final review verdict.
