---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S75'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S75 AEAT Auth Adapter Decomposition

Scope: decompose AEAT auth adapters by Cl@ve Móvil and authenticator persistence concerns behind the outbound AEAT auth facade.

## Description

- Extract Cl@ve Móvil persisted session metadata into `src/aeat/adapters/outbound/aeat/auth/_clave_movil_metadata.py`.
- Extract certificate-auth persisted session metadata and invalidation reason helpers into `src/aeat/adapters/outbound/aeat/auth/_authenticator_persistence.py`.
- Keep the registry-bound persisted-session error class in `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` so its declared error-code binding remains stable.
- Update same-package auth adapter tests to import the moved Cl@ve metadata record from its new private metadata module.
- Preserve the public outbound auth facade in `src/aeat/adapters/outbound/aeat/auth/__init__.py` without adding new consumer-facing private-module imports.

## Outcome

AEAT auth adapter persistence records were split out of the Cl@ve Móvil and certificate authenticator workflow modules while preserving the top-level auth package facade and existing error-code registry identity.

## Notes

An initial attempt moved the persisted-session error subclass into the new persistence module. The error registry rejected that changed qualified class path during import. The final implementation keeps that subclass in its original module and moves only non-registry metadata and helper logic.
