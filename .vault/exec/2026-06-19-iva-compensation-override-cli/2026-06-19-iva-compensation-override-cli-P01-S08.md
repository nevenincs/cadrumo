---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:754cf88b8cf46006e9fcb74effdbb00790f6b99a8ad390a50d4ccba190943f14'
step_id: 'S08'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

# Precondition: promote IvaCompensationOverride to the domain.iva_compensation package __all__ re-export so the application recorder consumes it via the top-level facade, not the private submodule

## Scope

- `src/aeat/domain/iva_compensation/__init__.py`

## Description

- Promote `IvaCompensationOverride` to the domain IVA-compensation package top-level `__all__` re-export.
- Consume the value through the package facade from the application recorder, not the private submodule.

## Outcome

- The application recorder imports `IvaCompensationOverride` from the owning package's public facade, satisfying the top-level re-export ownership rule.
- The symbol is enumerated in the package `__all__` and cross-referenced in the package docstring.

## Notes

- Precondition for the S01 recorder, which depends on the facade re-export.
- The re-export was present at HEAD; this Step verified it and closed it with an execution record.
