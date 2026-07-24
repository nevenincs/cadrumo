---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S27'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Persist deferred divergences as typed facts at commit and surface warning notices on later profile reads

## Scope

- `src/cadrumo/application/user_profile/`

## Description

- Add the `censo.divergencia` indexed object field to the profile schema and persist deferred cotejo decisions as `censo.divergencia.{n}.{axis,artefact_value,source}` typed facts through `apply_cotejo` in `src/cadrumo/application/user_profile/_cotejo_apply.py` — clearing facts, adopted facts, and fresh divergence rows in one atomic write.
- Replace the divergence namespace on every apply: existing rows the fresh set omits are cleared with the store's canonical `value=None` mechanism, proven ghost-free on read-back; a full adopt-all apply deliberately clears every open divergence, pinned by a direct test.
- Surface the warning notice on profile reads: `config profile show` carries the `profile.censo.divergences_open` notice (count and axes in context) while any divergence stays open, absent when clean — wired on the envelope notice channel and pinned by real-CLI round-trips both ways.

## Outcome

Landed as `8f004fcc51`, the revision `c253a117c2`, the read-surface wire `4df00869d6`, and the semantics pin `4e51620cf8`. Re-review verified the namespace-replace index-complete, the empty path regression-free, and the notice wiring on the correct read surface; the adopt-all-clears-open-divergences semantics were adjudicated correct and are now documented at the call site and pinned directly.

## Notes

- The divergence index is positional, not a stable per-axis identity — correct under namespace-replace, recorded so no future consumer treats the index as identity.
- The notice builder shipped one commit ahead of its consumer; the read-surface wire closed the builder-without-consumer gap the re-review named.
