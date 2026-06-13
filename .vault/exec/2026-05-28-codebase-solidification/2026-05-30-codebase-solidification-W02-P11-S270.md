---
step_id: S270
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W02.P11.S270 — Narrow bare except Exception swallows

## Scope

Narrow four `except Exception` swallows to specific typed sets:

- `_orchestration.py:143` — cleanup handler in `profile_create_storage_span`
- `_profile_health.py:146` — workflow-state load in `assess_active_profile_health`
- `_profile_health.py:163` — profile-record resolve in `assess_active_profile_health`
- `_profile_health.py:298` — best-effort session open in `_assess_with_best_effort_session`

## Narrowed exception sets

### `_orchestration.py:143`

`except (AeatError, OSError)` — AeatError covers encrypted-storage and workflow
domain failures; OSError covers filesystem pointer-write during cleanup.
Handler re-raises after restoring the active-profile pointer, so the set must
not be wider than these two well-understood failure families.

### `_profile_health.py:146`

`except (AeatError, OSError)` — `workflow_state_repository().load()` can raise
AeatError (decryption, session) or OSError (filesystem I/O of the encrypted DB).

### `_profile_health.py:163`

`except (AeatError, ValueError)` — `resolved_state.active_profile_record()` can
raise AeatError (domain/registry failures) or ValueError (including pydantic
ValidationError from strict model parsing of the stored profile record).

### `_profile_health.py:298`

`except (AeatError, OSError, ImportError)` — `get_master_key_provider()` can
raise AeatError (keyring/master-key domain failures), OSError (filesystem-backed
secret-store I/O), or ImportError (defensive guard around the dynamic import of
storage internals).

## Files touched

- `src/aeat/application/user_profile/_orchestration.py`
- `src/aeat/application/workflow/_profile_health.py`

## Collision signal

`git diff -- <target files>` before edits: no output (clean).
