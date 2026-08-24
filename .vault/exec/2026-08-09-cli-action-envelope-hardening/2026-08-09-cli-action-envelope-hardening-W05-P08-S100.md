---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b9b5a7d1601be92e3661a753a0b83cd34f757c3bf6a8aab2f693ce944682605c'
step_id: 'S100'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace ActiveProfilePointerError authored recovery prose with the canonical typed repair action

## Scope

- `src/cadrumo/core/errors/__init__.py`
- `src/cadrumo/core/config.py`
- `src/cadrumo/core/errors/tests`
- `src/cadrumo/application/operator_actions`
- `src/cadrumo/application/workflow/_profile_health.py`
- `src/cadrumo/application/workflow/tests`
- `src/cadrumo/entrypoints/cli/__init__.py`
- `src/cadrumo/entrypoints/cli/_errors.py`
- `src/cadrumo/entrypoints/cli/tests`

## Description

- Retain only localized identity and factual pointer-corruption/root-fallback facts on the core exception.
- Move the existing pointer-repair action and binding assembler into the public operator-action authority.
- Delegate workflow health projections and CLI boundary projection to that one canonical builder.
- Route pre-Click startup pointer failures through the standard CLI refusal boundary.
- Prove the exact repair action through a fresh malformed-pointer JSON subprocess while preserving text-mode and former-product startup behavior.

## Outcome

An invalid active-profile pointer no longer emits a raw traceback or an independently authored recovery sentence. The JSON startup refusal carries factual pointer state and resolves the canonical `config.repair.profile` action with `clear_active=true`, missing confirmation, and `REQUIRES_ARGUMENTS` conditionality.

Core remains application-independent. `active_profile_pointer_repair_verdict` is the sole repair-action/binding assembler; workflow and CLI startup both delegate to it. Focused unit tests pass 53 cases, focused integrations pass three cases, and scoped Ruff and diff checks pass. Independent review found no action or binding redeclaration.

## Notes

- The original S100 execution record covered an earlier broad core migration and explicitly carried this pointer defect forward. The reconciled plan row and this replacement body record the actual remaining closure work rather than preserving stale completion prose.
- VaultSpec RAG located the private workflow builder and drove its relocation to the canonical public authority.
