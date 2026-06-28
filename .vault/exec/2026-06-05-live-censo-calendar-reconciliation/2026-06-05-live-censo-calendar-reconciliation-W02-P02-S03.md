---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S03'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W02.P02.S03 - focused gates and live verification

## Focused Gates

- `.\.venv\Scripts\ruff.exe check src/aeat/application/user_profile/_censo_sync.py src/aeat/application/user_profile/__init__.py src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/_config/_profile_censo_payloads.py src/aeat/application/user_profile/tests/test_censo_sync.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
  - Result: passed.
- `.\.venv\Scripts\pytest.exe src/aeat/application/user_profile/tests/test_censo_sync.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -m "hex_application or hex_entrypoint" -q`
  - Initial result: 25 passed in 69.25s.
  - Post-review remediation result: 27 passed in 75.76s.
- `.\.venv\Scripts\pytest.exe src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "hex_application or hex_entrypoint" -q`
  - Initial result: 71 passed in 62.87s.
  - Post-review remediation result: 71 passed in 75.41s.
- `.\.venv\Scripts\python.exe -c "... yaml.safe_load(...) ..."` over `src/aeat/locales/{en,es,ca,hu}.yml`
  - Result: locale YAML parsed successfully.
- `git diff --check -- ...`
  - Result: no whitespace errors; Git warned that `_censo_sync.py` will normalize CRLF to LF when touched.

## Live Verification Commands

- `.\.venv\Scripts\aeat.exe config auth status`
  - Result: provider `clave_movil`; configured/authenticated/available all `True`.
  - Health summary: ready but requires operator-mediated Cl@ve completion.
- `.\.venv\Scripts\aeat.exe config profile status`
  - Result: active profile `live-iva-readonly-20260602`; profile has hashed tax id, activity description `Servicios profesionales`, `iva.regime = GENERAL`, and `tax_residence.ccaa = madrid`.
  - Current profile status does not include taxpayer-model axes needed for calendar obligation derivation.
- `.\.venv\Scripts\aeat.exe config profile censo show`
  - Result: refused because no censo snapshot has been captured for the active profile.
- `.\.venv\Scripts\aeat.exe app overview calendar --from 2024-01-01 --to 2026-12-31 --allow-incomplete`
  - Result: refused because the active profile does not declare the taxpayer model.
- `.\.venv\Scripts\aeat.exe config profile censo refresh`
  - Result: refused after the AEAT G313 surface returned no readable censo for the active profile.
  - CLI message: "La sede de la AEAT (G313) no devolvió ningún censo legible para el perfil <profile-id>; confirma que tu certificado o Cl@ve está registrado para este NIF."
- Post-remediation live-state recheck:
  - `config auth status`: still configured/authenticated/available, with operator-mediated Cl@ve completion required.
  - `config profile censo show`: still refused because no censo snapshot exists.
  - `app overview calendar --from 2024-01-01 --to 2026-12-31 --allow-incomplete`: still refused because taxpayer-model facts are absent.

## Result

The local backend and CLI path is verified. Live read-only censo retrieval is not verified complete for the active profile because AEAT G313 did not return a legible censo snapshot for the configured NIF. Calendar generation also correctly refuses the live profile while taxpayer-model axes remain undeclared, so the implementation does not silently fabricate Modelo enrolment.
