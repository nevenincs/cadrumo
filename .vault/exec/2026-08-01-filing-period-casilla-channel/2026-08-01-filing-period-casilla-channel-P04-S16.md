---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:3c4a0f6b25c431ed5eb4c13b451d97420985ec6c727781ddbea73976f75dd876'
step_id: 'S16'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Confirm with the M369 landing campaign that the token fill unblocks EXT-period validation and hand the end-to-end coverage back to it

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/369`

## Description

- State the structural blocker that existed and why the token representation removes it rather than special-casing the extended quarters.
- Name the existing proof that the extended quarter now reaches the text channel.
- Draw the handback boundary explicitly, listing what belongs to the extended-period surface rather than to this campaign.
- File the handback as a tracked issue and record that the confirmation half of the action is outstanding.

## Outcome

Tracked as repository issue 625.

The unblocking is proven rather than asserted. The retired ordinal projection returned nothing for every extended token, so the extended quarter had no representable value and the fill raised instead of producing one. The token is total over every declared period form, so the extended quarters become expressible structurally. An existing test resolves an extended first-quarter snapshot and asserts the token reaches the text channel; it passes. The partial projection has since been deleted outright, so it cannot be reintroduced by accident.

The handback boundary is drawn explicitly: end-to-end validation across the four extended quarters, any registry consequences now that those quarters reach the engine with a real value, and whatever coverage the owning campaign considers sufficient for its own gates.

## Notes

Half of this Step's action did not happen as written, and the issue says so rather than glossing it.

The action asks for confirmation FROM the extended-period landing campaign that the token fill unblocks its validation. That campaign was not addressable from this agent, so no confirmation was obtained. What was delivered is the handback and the unblocking proof; the acknowledgement is routed through the coordinator instead.

The issue therefore carries an explicit instruction not to close it on the unblocking proof alone. Closing it on this campaign's evidence would convert an unanswered question into a settled one, which is the failure this Step exists to prevent: the proof establishes that the token reaches the channel, not that the boundary is where the owning campaign expects it.
