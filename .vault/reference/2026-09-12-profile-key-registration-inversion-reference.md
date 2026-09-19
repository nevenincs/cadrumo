---
tags:
  - '#reference'
  - '#profile-key-registration-inversion'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:7d015f47fefbbfeaf42f83aef27531fc701e0ef51498078b4d40f65ae39585c9'
related: []
---

# `profile-key-registration-inversion` reference: application-owned catalogue

The implementation audit traced the profile-key read path, its wizard source,
and the boundary checks that exposed the inversion. The former design put the
`ProfileKey` record and a process-global registration slot in
`src/cadrumo/domain/contribuyente/keys.py`; `src/cadrumo/application/wizard/compiler.py`
compiled `WIZARD_FLOWS` and pushed into that slot during import. Domain test
fixtures imported the compiler only to trigger that push. The production
readers were application profile validation and workflow-health projections,
so the domain slot was not domain authority.

## Summary

The stable ownership mapping is:

- `src/cadrumo/application/wizard/catalogue.py` remains the sole authoring
  source in `WIZARD_FLOWS`.
- `src/cadrumo/application/wizard/compiler.py` is a pure
  `compile_profile_keys(flows)` projection and imports the application-owned
  `ProfileKey` model laterally.
- `src/cadrumo/application/user_profile/profile_key.py` owns the strict,
  frozen `ProfileKey` shape and validation invariants.
- `src/cadrumo/application/user_profile/profile_keys.py` owns the resolver.
  Its cached `profile_keys()` function imports `WIZARD_FLOWS` and the pure
  compiler only when called, and `profile_key(raw)` normalises then performs
  explicit lookup. No push API, registration slot, or bootstrap import is
  needed.
- `src/cadrumo/application/user_profile/keys_validation.py`, workflow health,
  wizard status, CLI surfaces, and harness identity reads consume the resolver
  directly or through the validation projection.

The domain schema and registry facts remain in their existing domain modules;
the application catalogue contains no copied schema rows or wizard questions.
The former domain module, registration error, compiler bootstrap, and domain
fixture side-effect imports are retired. Genuine model/catalogue tests belong
under `src/cadrumo/application/user_profile/tests/`.

The cold-reader smoke imported only the application resolver and validation
surface in a fresh interpreter. It produced 81 entries, identical totals from
`profile_keys()` and `list_profile_key_records()`, and resolved the
case-normalised key `IDENTITY.TAX_ID` to `identity.tax_id`. Targeted Python
compilation and `git diff --check` completed for the touched implementation
areas; the whole repository still contains unrelated concurrent generated-doc
drift, so API stubs were not hand-edited.
