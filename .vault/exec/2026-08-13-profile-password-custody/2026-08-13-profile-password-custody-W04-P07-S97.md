---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:1d926f822daa9ee357fe2ecd23f6c3dbe14d254050747f2f31ac345d1d58f21a'
step_id: 'S97'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh remove the private duplicate of the canonical bucket-identity primitive that the authority package carries beside the one being relocated into custody, since two implementations of one identity rule can disagree about which strings name the same bucket, and fold its consumers onto the surviving canonical home

## Scope

- `src/cadrumo/application/auth/_apoderado.py`

## Description

- Re-read the plan row and the prior S97 record (2026-08-15), which had concluded the fold was unlandable because the only candidate canonical home was an unexported orphan in the storage master-key package.
- Re-verified the landscape at HEAD: `cadrumo.core.identity.canonical_bucket_id` is now promoted in `core/identity/__init__.py` `__all__` (the canonical home for the rule, raising plain `ValueError` for each caller to translate); the storage orphan `adapters/persistence/storage/master_key/_bucket_identity.py` is deleted at HEAD (peer commit `4b1cc38687`); `domain/usage_ratios/_service.py` keeps its own wrapper with a load-bearing ValueError-to-`UsageRatioPersistenceError` translation and was left untouched.
- Deleted the vestigial pure-passthrough `_canonical_bucket_id` in `src/cadrumo/application/auth/_apoderado.py` (it returned `canonical_bucket_id(bucket_id)` verbatim) and repointed its four call sites (repository binding, `_repository_for`, `status`, `clear`) at the imported canonical function; no observable behaviour change since the wrapper already deferred to it.
- Consolidated `src/cadrumo/application/modelo/_review_package_signing.py` and `src/cadrumo/application/modelo/_review_package_recipient_encryption.py` onto the imported `canonical_bucket_id`: deleted each module's private `_BUCKET_ID = TypeAdapter(BucketId)` and `_canonical_bucket_id` wrapper, extended each `core.identity` import, and renamed the shadowing `canonical_bucket_id` locals to `normalised_bucket_id`. The exception boundary shifts from `pydantic.ValidationError` to `ValueError`; `ValidationError` subclasses `ValueError` and no consumer catches `ValidationError` specifically around these calls (verified by grep), so observable error behaviour is preserved with no CadrumoError translation to add.
- Repointed `src/cadrumo/application/auth/tests/test_apoderado.py` (import plus three usages) at `canonical_bucket_id` from `core.identity`; assertions are unchanged and still assert `ValueError` refusals.
- Verified `_canonical_bucket_id` and `TypeAdapter(BucketId)` remain only in `domain/usage_ratios/_service.py` (untouched seam) after the sweep.

## Outcome

The private duplicate is removed from all three in-scope modules and every consumer now resolves the bucket-identity rule through the one canonical `cadrumo.core.identity.canonical_bucket_id`, so no two implementations of one identity rule can disagree about which strings name the same bucket. `usage_ratios` keeps its typed-refusal seam by design.

Gates run sequentially with full log capture: `uv run --no-sync ruff check` on the four touched files — "All checks passed!" (exit 0); `uv run --no-sync ruff format --check` on the same — all formatted. Targeted pytest (core/identity tests, `test_apoderado.py`, and the review-package test modules: signing, recipient-encryption, namespace-binding, feedback, counter-sign, collab-audit): 212 passed, 7 failed. The 7 failures are pre-existing at HEAD and unrelated to this diff: they error in `isolated_runtime_profile` fixture setup (`UUID(str(profile_id))` rejects the tests' non-UUID `"recip-enc-keypair-owner"` target bucket id) before any changed code runs; the test files and fixture are byte-identical to HEAD, and commit `150f90351f` (UUIDv4 fixture hardening) itself documents this class ("36 fail on their own merits"). `dev/quality/import_hygiene_scan.py` shows 0 cross-package private imports attributable to this change; its exit-1 comes from a pre-existing legacy-TUI census drift, and the `dev/tests/test_import_hygiene_gate.py` failures (6) are pre-existing census drift over files outside this diff (0 mentions of the touched files). No test was weakened, skipped, or stubbed.

## Notes

- The stale 2026-08-15 record concluded the row was unlandable; that premise lapsed when the canonical home was promoted to `core.identity` and the storage orphan was deleted, both by peer commits. This record supersedes it.
- Scaffold of this record required `--force` because the stale record occupied the canonical path; the verb refused without it.
- Pre-existing failures reported, not chased per dispatch: 7 review-package tests broken by the UUIDv4 capsule-fixture hardening (non-UUID target bucket ids at `test_review_package_signing.py:322`-area and `test_review_package_recipient_encryption.py:686`), and the import-hygiene gate's wrapper-exemption / test-debt / TUI-census drift in peer-owned files.
- Commit `91925f5b3b` "refactor(identity): fold the surviving private bucket-id wrappers onto canonical_bucket_id" — one pathspec commit naming only the four touched files; peer WIP left intact.
