---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S31'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Migrate the outbound local store sidecar write onto the atomic-write helper closing the torn object-plus-sidecar crash window

## Scope

- `src/cadrumo/adapters/outbound/storage/_local.py`

## Description

- Checked for peer WIP in `_local.py` before editing (`git diff` clean).
  This closes the deferred finding recorded in the S25 exec record: the
  sidecar write was a direct in-place `sidecar_path.write_text(...)` with
  no tempfile staging and no fsync, while the object-payload write next to
  it was already hardened in S24.
- Migrated the sidecar write to `atomic_write_text` (standard tier) --
  sufficient since the sidecar carries only `content_hash`/`byte_length`/
  `label`/`written_at` metadata, not the payload itself, so the hardened
  tier's `O_EXCL`/mode-`0o600` posture is unnecessary here.
- Updated the `put()` docstring to describe the sidecar's new atomicity
  guarantee.
- Added a real-behaviour test
  (`test_put_sidecar_write_is_atomic_and_preserves_prior_content_on_failure`)
  proving sidecar atomicity without any mock/patch: it exercises the exact
  `atomic_write_text` call `put()` now uses, directly against the sidecar
  path a real `put()` call already wrote, passing a `None` payload so the
  underlying `text.encode(...)` call genuinely raises `AttributeError`
  mid-write. Asserts the prior good sidecar content survives byte-for-byte
  and no `*.tmp` sibling lingers in the namespace directory.
- Reconciled the production file-write inventory gate: removed the now-
  stale tracked-call entry for `_local.py` `put()`'s
  `sidecar_path.write_text` (that direct call site no longer exists). No
  new entry was needed -- the `core/atomic_write.py` entries S24 already
  added cover the AST-tracked calls the shared helper makes internally,
  regardless of which caller reaches it.
- Confirmed no new deferred-import edge was introduced (this file already
  imports `core.atomic_write` eagerly at module level since S24's
  `atomic_write_hardened_bytes` migration; adding `atomic_write_text` to
  the same existing import statement introduces no new edge).

## Outcome

Landed in one commit (`5e0676d300`). The targeted test suite for `_local.py`
passes (26 tests, including the new sidecar-atomicity test). `ruff check`
clean on all three touched files. The production file-write inventory gate
passes (2/2) with its stale entry removed. The lazy-import-policy gate
passes unchanged (5/5, confirming no new edge). `pytest --collect-only -q`
on the full tree collects cleanly (12866 collected).

This closes the deferred finding S25 flagged for the W06 honesty review;
the torn object-plus-sidecar crash window no longer exists at this site.

## Notes

No incidents. The `AttributeError` (rather than `TypeError`) exception type
in the new test is a deliberate, verified choice: `atomic_write_text`
encodes its `text` argument via `text.encode(encoding)` before delegating
to the bytes tier, so a `None` payload fails on the missing `.encode`
attribute, not a bytes-vs-str type mismatch (which is what the bytes-tier
tests in `core/tests/test_atomic_write.py` exercise with a wrongly-typed
`str` payload). Both are genuine, unmocked induced failures; the exception
type differs only because of which layer the wrong-typed value reaches
first.
