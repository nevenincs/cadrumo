---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:8aaa3b280c09a45ed2ef408343620b858d33ddf8d84433727385a57e0bd082d0'
related: []
---

# `tui-architecture` audit: `headless profile create refuses twice, naming one blocker at a time`

## Scope

## Findings

## Recommendations

## Finding

`aeat config profile create NAME` on a non-interactive console refuses with:

    Refused. No passphrase channel is available. Run this verb at a terminal,
    or pass --secrets-stdin or --secrets-fd.

An operator who follows that instruction and re-runs with `--secrets-stdin`
hits a SECOND refusal:

    Rechazado. La recuperacion es obligatoria. En modo sin terminal,
    proporcione --recovery-handoff-fd y --recovery-verification-fd.

Both refusals are correct and both are instructive. The gap is that the first
names only one of the two things headless creation requires, so the documented
recovery path does not actually reach a created profile. Creation deliberately
never falls through to a password-only profile
(`_scripted_registration.py`, `_recovery_handover`), so the recovery
descriptors are not optional and their absence is knowable at the same moment
the passphrase channel's absence is.

## Why this is worth recording rather than fixing in passing

The message is localised, so changing it means real values in all four
catalogues, and what the refusal should say is a product decision about how
much of the headless contract one refusal carries. It is also not a
regression: both refusals have been there.

## Evidence

`src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py`
::`test_installed_console_profile_create_fails_fast_without_prompt_host`
asserted a `create NAME --quiet --tax-id ...` hint that no message emits; that
assertion was removed because it pinned prose the product does not produce and
which would not clear this blocker either. The negative assertions it carried
-- that a first-timer is never pushed at `config repair` / `config reset` --
were kept, and the case now asserts the channels the refusal does name.

## Status

Open. No code change proposed here; the decision is whose refusal carries the
second requirement.
