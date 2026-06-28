---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: "S176"
date: 2026-05-27
modified: '2026-05-27'
commit: dc4f07386
related: []
---

# S176: Art. 82 LIRPF situacion_familiar axis

## What was done

Implemented the full `situacion_familiar` wizard axis for Lourdes F2:

- Added `SituacionFamiliar(StrEnum)` in `src/aeat/domain/profile/_renta_codes.py` with 5 members (CASADO, PAREJA_HECHO_REGISTRADA, PAREJA_HECHO_NO_REGISTRADA, SOLTERO, SEPARADO_DIVORCIADO) and helpers `conjunta_eligible()` / `requires_spouse_or_partner()`.
- Re-exported from `src/aeat/domain/profile/__init__.py`.
- Added `situacion_familiar` and `unidad_familiar_descendientes_exclusivos` fields to `SetupAnswers` in `_setup_answers.py` with blank-passthrough validators.
- Added `_check_joint_taxation_situacion_familiar` in `_verifier.py`: refuses `taxation_type="2"` (conjunta) with ERROR severity when `PAREJA_HECHO_NO_REGISTRADA` is declared (Art. 82.1.2° LIRPF).
- Added `situacion-familiar` WizardQuestion in `_catalogue.py` with 5 choices using `tr()` for all labels.
- Added locale keys in es.yml, en.yml (already in sweep commit 5bc2ae042), ca.yml (already in sweep commit), and hu.yml (redirect-key pattern).
- 17 unit tests in `test_situacion_familiar.py` covering enum helpers, field validation, all verifier branches, and anti-tautology proof.

## Verification

```
pytest src/aeat/application/wizard/test_situacion_familiar.py -v
# 17 passed in 0.xx s

python -m aeat.locales audit
# ca.yml ok  en.yml ok  es.yml ok  hu.yml ok
```

## Files changed

- `src/aeat/domain/profile/_renta_codes.py`
- `src/aeat/domain/profile/__init__.py`
- `src/aeat/application/wizard/_setup_answers.py`
- `src/aeat/application/wizard/_verifier.py`
- `src/aeat/application/wizard/_catalogue.py`
- `src/aeat/application/wizard/test_situacion_familiar.py`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/hu.yml`
