---
step_id: S05
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#cross-domain-continuity"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
commit: 8984a9186
---

# cross-domain-continuity P01.S05 — StoredProfileDriftError + repository wrap

## Deliverables

- `src/aeat/domain/user_profile/_errors.py` — added `StoredProfileDriftError(UserProfileError)` carrying `profile_id: str` and `original_exception: ValidationError`; uses `errors.storage.stored_data_validation_boundary` locale key with `aeat config repair` suggestion.
- `src/aeat/domain/user_profile/__init__.py` — exported `StoredProfileDriftError` in imports and `__all__`.
- `src/aeat/application/user_profile/_repository.py` — wrapped `Envelope[UserProfileRecord].model_validate_json` in `UserProfileLifecycleRepository.load()` and `iter_records()` with `try/except ValidationError → raise StoredProfileDriftError`.
- `src/aeat/core/errors/registry/_application.py` — registered `StoredProfileDriftError` with `ErrorCode(code="INTEGRITY_STORED_PROFILE_DRIFT", category=ErrorCategory.INTEGRITY)`.

## Outcome

All gates pass. The domain error class is correctly typed and propagates the original `ValidationError` for downstream discriminators.
