---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:ddee1323edd05a814ae6ffb94acfd5753c13f5eb9f741068d5e129a823b073cf'
step_id: 'S170'
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
     The S170 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Sol Medium correct the two remaining docstrings that assert the retired plaintext manifest as the current mechanism, one describing a label-to-identifier resolution as reading manifest files and one describing the active-profile pointer as derived from them, both consuming resolvers that are now capsule-only, this being the same false-stated-reason class already corrected on the listing surface and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py and src/cadrumo/core/_bucket_pointer.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium correct the two remaining docstrings that assert the retired plaintext manifest as the current mechanism, one describing a label-to-identifier resolution as reading manifest files and one describing the active-profile pointer as derived from them, both consuming resolvers that are now capsule-only, this being the same false-stated-reason class already corrected on the listing surface

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py and src/cadrumo/core/_bucket_pointer.py`

## Description

- Traced both docstrings' consuming resolvers to their bottom before writing any replacement clause, rather than authoring a differently-worded unverified claim.
- Traced `_hint_via_label` to `read_profile_bucket` (`application/workflow/_profile_bucket_scan.py`), which resolves through `CommittedProfileRepository.list()`, itself seeded by `list_current_profile_custody_capsule_ids` (committed custody capsule discovery) — confirmed no manifest read anywhere in that chain.
- Traced `_pin_render_language_to_target_bucket`'s label-to-UUID fallback to the same `read_profile_bucket` resolver, and its bucket-local hint read to `resolve_profile_output_language_hint` -> `read_bucket_output_language_hint`, a separate bucket-local non-secret hint file, not a manifest.
- Traced the module docstring's `ProfileBucketPointer` claim the same way: `application.workflow.ProfileBucketPointer` records are built by `_pointer()` in `_profile_bucket_scan.py` from the same `CommittedProfileRepository` projection, never from a manifest file.
- Found and traced the underlying capsule reads: `list_current_profile_custody_capsule_ids` and `load_committed_profile_custody_label_record` (`adapters/persistence/storage/custody/_capsule.py`) read the capsule's commit marker and label record directly off disk via `_read_regular_file`/`_read_regular_file_fd`, with no DEK unwrap — confirming the "readable without the DEK" property the corrected clauses assert is still true of the current mechanism, not only of the retired manifest.
- Corrected the false "manifest scan" / "manifest.toml" clauses in both target docstrings to name the committed custody capsule projection instead, and corrected one further inline comment in `_custody.py` carrying the identical false claim in the same function's exception handler, discovered while verifying the surrounding code.

## Outcome

Three corrected clauses, each independently traced and verified against the current resolver chain rather than assumed:

1. `src/cadrumo/entrypoints/cli/_config/_custody.py`, `_hint_via_label` docstring: replaced "The manifest scan reads plaintext files, so it does not depend on the target bucket's DEK being intact" with a clause naming `read_profile_bucket` / `CommittedProfileRepository` / `list_current_profile_custody_capsule_ids` and stating the commit marker and label record are plain committed files read without unwrapping the DEK. Verified by reading `_profile_bucket_scan.py::read_profile_bucket` and `_capsule.py::list_current_profile_custody_capsule_ids` / `load_committed_profile_custody_label_record` in full.

2. `src/cadrumo/entrypoints/cli/_config/_custody.py`, `_pin_render_language_to_target_bucket` docstring: replaced "it is resolved to its UUID through the manifest scan first: that scan reads plaintext `manifest.toml` files" with a clause naming the committed custody capsule projection and the same commit-marker/label-record read. Verified by the same trace as (1), since this docstring's fallback calls the identical `_hint_via_label` -> `read_profile_bucket` chain.

3. `src/cadrumo/core/_bucket_pointer.py` module docstring: replaced "`ProfileBucketPointer` records are derived from `buckets/*/manifest.toml`" with a clause naming the committed custody capsule projection (`CommittedProfileRepository`, seeded by `list_current_profile_custody_capsule_ids`) as the actual source, and replaced "read a manifest" with "read a capsule" in the adjacent sentence contrasting `BucketPointer`'s narrower contract. Verified by reading `_profile_bucket_scan.py::_pointer` and its two callers (`read_profile_bucket`, `read_profile_bucket_by_id`).

A fourth, unplanned correction: the same false "plaintext manifest scan" claim also appeared as an inline comment in `_custody.py`'s `_login_through_the_prompt`, inside the `except SecretStoreError` arm that calls `_pin_render_language_to_target_bucket` on a failed unlock. This is the identical false-stated-reason class in the same file, directly adjacent to the docstrings named by this Step, so it was corrected in the same pass rather than left standing beside the fix. Verified against the same trace as (1)/(2), since the comment describes the exact same call path.

A true, unmodified statement was found and deliberately left as-is: `BucketPointer`'s own class docstring says the value object does "not read settings, open storage, inspect manifests, or resolve precedence" — this is a negative claim about what `BucketPointer` itself does not do, not an assertion that any other component currently reads a manifest, and it remains accurate.

## Notes

No mocks, stubs, or test changes required — this Step is docstring/comment-only. `ast.parse` confirmed both edited modules remain syntactically valid, and both import cleanly (`import cadrumo.entrypoints.cli._config._custody`, `import cadrumo.core._bucket_pointer`) after the edit.
