---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S03'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---




# DONE. The channel matrix is now derived data rather than a per-product list, the descriptor carries a matrix block holding the three product properties and every channel declares its tier, and derived_tiers evaluates the account rule over them. The descriptor refuses at load when the declared channels disagree with the derived set, in either direction, so neither dropping a channel nor acquiring one the rule excludes can pass unseen. Cadrumo evaluates to registry plus standalone-executable plus the three managed installers plus host-extension, and the two tiers it does not yet ship are declared in pending_tiers so the gap is visible data rather than a silent absence

## Scope

- `docs/_data/download_channels.toml`
- `dev/docs/download_matrix.py`

## Description

- Add a `[matrix]` block to the channel descriptor carrying the three product properties the account rule consumes.
- Add a `tier` field to every channel so each declares which kind of channel it is.
- Add `ChannelTier` as a closed enum and `derived_tiers` as the rule evaluating the three properties.
- Add a descriptor-level validator refusing any disagreement between declared channels and the derived set, in both directions.
- Declare `pending_tiers` for the two tiers the rule selects that cadrumo does not yet ship.

## Outcome

The channel set is derived rather than chosen. A sibling product copies the descriptor, sets three booleans, and its channel set is computed rather than argued, which is the property that survives to a product nobody has described yet.

Cadrumo evaluates to six tiers: registry, standalone-executable, shared-tap, shared-bucket, community-windows, and host-extension. Two of those, standalone-executable and community-windows, have no channel yet and are declared pending.

The validator has teeth in both directions. A channel declaring a tier the rule excludes refuses at load, and a tier the rule selects with neither a channel nor a pending declaration refuses too, so a silently dropped channel cannot pass.

## Notes

The `pending_tiers` mechanism was added after noticing the honest alternative was worse. Cadrumo genuinely does not ship standalone executables or a community Windows package, so the rule selects two tiers with no channel. Declaring a phantom channel row would have satisfied the validator while lying about what ships; failing the load outright would have blocked the tree on unbuilt work. Naming the gap as data does neither.

Semantic search was degraded throughout this campaign. The code index was serving roughly a fifth of the tree while reporting itself healthy with an empty degraded-reasons list, and a probe for distribution evidence returned unrelated configuration and tax-pull modules. Every conclusion here rests on direct file reads.
