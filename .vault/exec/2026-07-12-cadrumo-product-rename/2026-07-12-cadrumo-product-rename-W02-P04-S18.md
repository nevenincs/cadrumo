---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Move the platform application-data root to Cadrumo and refuse detected former-product state

## Scope

- `src/cadrumo/core/_config_state_root.py`
- `src/cadrumo/core/tests/test_config_state_root.py`

## Description

- Derive the installed application directory from canonical Cadrumo product identity.
- Detect a sibling former-product application root before returning installed state.
- Raise a typed refusal without opening, moving, re-keying, deleting, or adopting former state.
- Preserve the checkout-local `var/storage` development root unchanged.
- Exercise fresh Cadrumo reuse and former-state refusal through real temporary filesystem trees.

## Outcome

Installed resolution now returns `<platform-user-data>/cadrumo/storage` on Windows, Linux, and macOS. Checkout resolution remains `PROJECT_ROOT/var/storage`. Before an installed root is returned, the resolver checks only for the existence of the sibling retired application directory and raises `FormerProductStateError` when detected. The refusal happens before a Cadrumo directory is created and performs no former-state content access or mutation.

The focused clean-environment test run passed all ten state-root tests. The real-filesystem refusal proof retained the former marker bytes and directory while confirming that no Cadrumo directory appeared. Fresh Cadrumo state was created by the test consumer, read back, and resolved to the same sole root without a fallback.

## Notes

The canonical Step scope was expanded through the plan CLI to include the cohesive root test file required by the Step contract. The literal former directory name remains only as a refusal detector; it is not an alias, fallback, migration source, or accepted state root.
