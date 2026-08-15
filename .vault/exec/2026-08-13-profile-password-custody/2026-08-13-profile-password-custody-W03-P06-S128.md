---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:9babbeac28893d8aeab5705e4b0716d8e965b59f25a3eb24e911dfcbf97b91a0'
step_id: 'S128'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh correct the production listing docstring that names the per-bucket plaintext manifest as the canonical source of profile-existence truth written by every creation path, since nothing writes one and listing projects committed capsules, this being the fourth false stated reason found today and the first describing the system's own source of truth in production rather than in a test or an allowlist

## Scope

- `src/cadrumo/entrypoints/cli/_config/__init__.py`

## Description

- Traced `config_list` end to end: `list_profile_buckets` calls
  `CommittedProfileRepository.list()`, which projects only current committed
  custody capsules through the capsule adapter's discovery -- it never opens
  or reads `manifest.toml`.
- Confirmed by grep that no production writer creates a per-bucket
  `manifest.toml` anywhere in the tree; the only production references are a
  storage-taxonomy member-name declaration and the custody adapter's
  `PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS` retired-member detector,
  which exists to REFUSE finding one, not to read it.
- Rewrote the `config_list` docstring to name the real mechanism
  (`CommittedProfileRepository`) and to state the manifest's retirement in a
  way a future reader can re-check against a named, still-live constant
  rather than trusting the prose.

## Outcome

The docstring's two false claims are corrected. What was true when written
and is now false: "the canonical source of profile-existence truth is the
per-bucket `manifest.toml` file written by every profile-creation path" and
"`list_profile_buckets` reads them". Both are backwards -- nothing writes a
`manifest.toml` in production, and `list_profile_buckets` never reads one.

What is actually true, and how each clause was verified:

- `list_profile_buckets` (`application/workflow/_profile_bucket_scan.py`)
  projects `CommittedProfileRepository(...).list()` -- read the function
  body directly; its own module docstring states "It does not inspect
  manifests."
- `CommittedProfileRepository.list()` iterates
  `list_current_profile_custody_capsule_ids(...)` and loads each capsule's
  aggregate -- read `application/user_profile/_profile_repository.py:144-152`.
- Nothing writes `manifest.toml` in production: grepped `manifest.toml`
  tree-wide and read every production hit outside this file. The only two
  bucket-manifest-shaped hits are a filename declared in the storage
  taxonomy's per-bucket member list and
  `PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS = ("manifest.toml",)` in
  `adapters/persistence/storage/custody/_capsule_discovery.py`, whose own
  docstring states "`manifest.toml` was the former plaintext profile
  authority. Current capsules have no manifest member." (Every other
  `manifest.toml` hit in the tree belongs to the unrelated registry-loader
  and orden-anual manifests, a different concept sharing the filename.)
- `list_profile_buckets` unlocks no bucket: `CommittedProfileRepository.list()`
  never derives or uses a DEK, confirmed by reading the method.

The new docstring cites `CommittedProfileRepository` (the real mechanism) and
names `PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS` as the checkable anchor
for the retirement claim, so a future reader can re-verify rather than
inherit prose.

## Notes

Two adjacent, structurally identical false claims were found but are OUT OF
SCOPE (not this Step's file) and are reported rather than fixed here:
`entrypoints/cli/_config/_custody.py` (`_pin_render_language_to_target_bucket`
docstring, "resolved to its UUID through the manifest scan first: that scan
reads plaintext `manifest.toml` files") and `core/_bucket_pointer.py` (module
docstring, "`ProfileBucketPointer` records are derived from
`buckets/*/manifest.toml`"). Both describe the same retired mechanism as true
today; both consume the same now-capsule-only `read_profile_bucket` /
`read_profile_bucket_by_id` resolvers this Step traced. Flagging for the team
lead to route as a follow-up rather than editing files outside this Step's
scope.

No tests were run for this file in isolation since it changes only a
docstring; verification is the full CLI config consumer suite run under
`S129`'s record, which imports and exercises `config profile list` through
`test_config_profile_show_payload.py`, `test_profile_lifecycle_navigation.py`
and others -- none of which asserted on the removed docstring text.
