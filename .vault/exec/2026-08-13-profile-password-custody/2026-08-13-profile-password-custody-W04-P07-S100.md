---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:3ef3a786d99ade89b12fc33bc4dff75628e877a179d3a87b19493dfcb30e469d'
step_id: 'S100'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S100 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Have Terra XHigh name the profile-to-bucket identity conversion once in the identity package and route the twenty-eight bare string coercions through it, then settle whether the custody capsule records should carry the canonical profile identifier string or whether that identifier needs a documented object form, since three identifier shapes exist where the rules assume two and the bridge between them is currently an unnamed coercion the grounding rule already classes as a boundary leak and ## Scope

- `src/cadrumo/core/identity/ and src/cadrumo/adapters/persistence/storage/custody/_capsule_records.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh name the profile-to-bucket identity conversion once in the identity package and route the twenty-eight bare string coercions through it, then settle whether the custody capsule records should carry the canonical profile identifier string or whether that identifier needs a documented object form, since three identifier shapes exist where the rules assume two and the bridge between them is currently an unnamed coercion the grounding rule already classes as a boundary leak

## Scope

- `src/cadrumo/core/identity/ and src/cadrumo/adapters/persistence/storage/custody/_capsule_records.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

`canonical_profile_bucket_id(profile_id: str | UUID) -> str` now lives in `core/identity/_profile.py` beside `ProfileId`, exported from the facade (commit `fd1b71807b`). It validates (parses plainly, then REFUSES non-v4 — the first draft used `UUID(..., version=4)`, which silently re-types the version nibble; the refusal test caught it before it shipped) and returns the canonical lowercase string, mirroring `canonical_bucket_id`'s plain-ValueError convention. The keying/serialization sites were routed through it: custody `_paths.py` repository-id derivation, `_sentinel_contract.py`, `_recovery.py`, `_acceleration_receipt.py` (payload, bucket keying, log context) and `_capsule_records.py` payload writes, plus the shared test door `tests/profile_capsule.py`. The capsule records keep their `UUID`-typed fields (strictest shape; pydantic serialises the canonical string, so on-disk bytes are identical — no persisted-format change, no version bump). The comparison/resolver-scoping sites (class c) were deliberately NOT routed: the bucket-id-to-profile reverse bridge stays a resolver judgment because `BucketId` is looser than `ProfileId`.

## Notes

Gates: ruff clean across `core/identity/` and the custody package; identity suite 117 passed (three new agreement/refusal tests for the conversion); `tests/test_secure_sql.py` 6 passed. Pre-existing reds untouched and noted: `test_path_identity_boundary.py` fails 10 cases at HEAD because the discoverer's private `_canonical_profile_id` re-types non-v4 bucket names via `UUID(..., version=4)` (same hazard this row's refusal test pins — candidate for a follow-up row), and the keychain-environment failures in the acceleration-receipt matrix. The row's 'twenty-eight' coercion figure was stale at HEAD (42 `str(profile_id)` + 33 `bucket_id=str(...)` + 20 `UUID(str(...))`); this row routed the keying class and classified the rest — the remaining bare casts are (b) no-op casts on already-canonical strings and (c) resolver scoping, documented rather than swept.
