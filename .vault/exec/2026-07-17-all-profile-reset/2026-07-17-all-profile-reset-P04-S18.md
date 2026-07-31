---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:0aff21e2fc2cb2309553c78d81b3a8b2da5239a7386388be3aabe30c369afed1'
step_id: 'S18'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Restrict config switch to UUIDs and exact labels including canonical sandbox labels and reject bare sandbox names

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py`

## Description

- Add `_resolve_switch_target` to `_custody.py`: resolve a `switch` target from an unambiguous UUID (`read_profile_bucket_by_id`, excluding tombstoned) or fall back to the injected exact-label resolver.
- Route `config_switch` through the new resolver so `switch` accepts a bucket UUID, an exact operator label, and a sandbox's canonical `sandbox:<name>` label, while a bare sandbox short name refuses as an unknown profile (the sandbox namespace check the removed `sandbox use` door performed).

## Outcome

`config switch NAME` is the single accepted profile selector per ADR `cli-authority-verb-conformance` Decision 3: it resolves a live UUID directly, refuses a tombstoned UUID and a bare sandbox short name through the label resolver, and preserves the typed ambiguity refusal. Proven by the sandbox CLI suite (44 passed) including the new UUID-switch and bare-name-rejection tests co-committed with S22.

## Notes

Bare-name rejection was already implied by label-only resolution; the load-bearing new capability is UUID resolution. The shared `_resolve_profile_by_label` (delete/duplicate/rename) is deliberately left label-only — the ADR narrows only `switch`.
