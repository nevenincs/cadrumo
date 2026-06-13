---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S282
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S254]]"
---

# cross-domain-continuity W09.P45.S282 — auth env-var leak via tr()

## Outcome

Routed the two `CertificateLoadError` raises in `AeatAuthenticator._require_bundle`
through `tr()`, removing `AEAT_CERTIFICATE_PATH`, `AEAT_CERTIFICATE_PASSWORD_SECRET`
env-var names and the `CertificateBundle` class name from operator-facing error text.
Closes the G3 BLOCKER from the Round-5 B-ROSER audit findings.

### Changes

- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` — both raises now use
  `tr("application.auth.certificate.load.path_unset")` and
  `tr("application.auth.certificate.load.password_unset")` with operator-prose
  defaults. Inline `tr` import at call site matches the existing module idiom (line 773).
  Long `default=` string wrapped for E501 compliance.

- `src/aeat/locales/{en,es,ca,hu}.yml` — new `application.auth.certificate.load`
  subtree with `path_unset` and `password_unset` keys in all four locales.
  Added via locale scaffold flow; `locale audit` reports `missing=0` across all files.

### Verification

```
uv run pytest src/aeat/adapters/outbound/aeat/auth/ -q --ignore=.../test_clave_movil.py
86 passed, 6 deselected
```

```
uv run python -m aeat.locales audit
ca.yml: missing=0  en.yml: missing=0  es.yml: missing=0  hu.yml: missing=0
```

## Commits

- `2b37264f4` — Task #102: S254 manifest-status repair path fix + S282 auth env-var leak
- `cce75a107` — S282 ruff fix: wrap long default= string in _require_bundle tr() call

## Files changed

- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/hu.yml`
