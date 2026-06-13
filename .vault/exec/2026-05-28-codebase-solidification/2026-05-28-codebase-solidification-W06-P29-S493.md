---
step_id: S493
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S493

**Step**: extract _CERT_PASSWORD_SECRET_ENV and _CLAVE_MOVIL_DNI_NIE_ENV Final constants in auth modules.

## Outcome

- `_authenticator.py`: `_CERT_PASSWORD_SECRET_ENV: Final[str] = "AEAT_CERTIFICATE_PASSWORD_SECRET"` extracted; health_summary f-string uses the constant
- `_clave_movil.py`: `_CLAVE_MOVIL_DNI_NIE_ENV: Final[str] = "AEAT_CLAVE_MOVIL_DNI_NIE"` extracted; error message uses the constant

## Files

- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`

## Commit

5b45dd58c
