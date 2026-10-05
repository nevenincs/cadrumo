---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-10-03'
body_hash: 'sha256:29bd9e8fd613e624549aed7b783e503a0e7cf0020e2ba68c11d1f024e102c509'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S385` Review

## S385-007 | FIXED | Period-scoped status uses the canonical no-active-profile refusal

`overview_status` uses `resolve_active_bucket_id()` to skip `_state()` when no active
profile is selected. The `--period` branch now raises `_no_active_profile_refusal()`
instead of `_bad(tr("cli.config.errors.no_active_profile"))`, so it no longer produces
Click's `Invalid value:` wrapper for the no-active-profile condition. The cold-start
contract covers `app overview status --period 2026Q1` and asserts that the operator sees
profile-create recovery guidance without the bad-parameter wrapper.

## S385-001 | PASS | Overview is a read-only local CLI surface

The retired module renders status, calendar, agenda, backlog, and
explain outputs from local application services. The inspected paths do not persist new
profile, filing, ledger, or live-read state.

## S385-002 | PASS | Active-profile access uses shared refusal and state helpers

The active-profile paths call the shared CLI `_state()` helper or
`resolve_active_bucket_id()` before reaching bucket-bound storage. Missing active profile
state refuses through the localized no-active-profile path instead of opening a root or
empty storage route.

## S385-003 | PASS | All-profiles calendar is manifest discovery

The `--all-profiles` calendar path calls `list_profile_buckets()` to enumerate bucket
manifests, filters active manifests, and opens each encrypted profile record inside
`profile_storage_session(bucket_id)`. This is a manifest-discovery caller, not a
runtime-default repository factory.

## S385-004 | PASS | Local live-snapshot read failures are logged

Local live snapshot enrichment catches unreadable bucket snapshot state only around the
local optional enrichment and emits a warning with `exc_info=True` before returning no
events. The failure is not silent, and the overview calendar remains read-only.

## S385-005 | PASS | Validation

- the historical check passed.
- the historical check passed with 38 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-rag search "overview all profiles list profile buckets profile storage session ProfileRepository load manifest discovery" --type code --port 8766 --max-results 5` returned manifest scan, `list_profile_buckets`, and profile repository list evidence.
- the historical check passed after the S385-007 fix.
- the historical check passed with 48 tests after the S385-007 fix.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed after adding the cross-lane `cli.ledger.errors.invalid_category` locale leaves through `python -m aeat.locales set`.

## S385-006 | INFO | Broader backend-boundary suite has unrelated open failures

the historical check
failed on pre-existing and parallel-lane surfaces outside `_overview.py`: ledger review help
vocabulary, modelo work resume `NameError`, two retired moved-test path guards, and existing
skip/xfail/stub language detections. These failures are not introduced by S385 and should be
handled by the active ledger/modelo/test-topology backlog rather than hidden in this row.

Reviewer note: mandatory reviewer pass found `S385-007`; it was repaired and covered by
the cold-start contract.

Disposition: close `AFR-283` as `manifest-discovery`.
