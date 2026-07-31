---
tags:
  - '#exec'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:7b3a2d4923df5e1fccd3e364f7f024a32e2bac31590a6adbbecdd5d94a46f5db'
step_id: 'S04'
related:
  - "[[2026-07-25-account-distribution-standard-plan]]"
---

# DONE. The required evidence set now derives from the channels a release actually claims, computed as the union of those channels' declared evidence rows, floored at the language-native registry so it can never collapse to nothing and leave the readiness gate measuring zero. No gate was weakened and no row was removed, all eleven rows survive as ALL_DISTRIBUTION_ROWS and a channel still cannot be claimed without its passing row, what changed is only that an unclaimed channel no longer blocks a claimed one. The documentation claims gate was deliberately re-anchored on the FULL set rather than the claimed subset, because a documentation claim is itself the act of claiming a channel, and it gained an anti-vacuity test asserting every declared row is reachable by some claim pattern

## Scope

- `dev/release/readiness.py`
- `dev/docs/download_matrix.py`
- `dev/docs/tests/test_distribution_claims.py`

## Description

- Declare each channel's `evidence_rows` in the descriptor, so a channel's proof obligation has one home.
- Add `claimed_channels` and `required_evidence_rows`, deriving the required set from the channels a release claims and flooring it at the language-native registry.
- Replace the hardcoded eleven-row constant with the derived set, keeping the full set available as `ALL_DISTRIBUTION_ROWS`.
- Re-anchor the real-client honesty guard's parity test on the full set, since it governs how a row is minted rather than whether it is claimed.
- Re-anchor the documentation claims gate on the full set and add an anti-vacuity test that every declared row is reachable by some claim pattern.

## Outcome

Evidence is proportional to claims. With no channel currently marked available, the required set is the three registry rows rather than eleven, so a first release can prove the registry alone without waiting on acquisition workflows that have never succeeded.

No gate was weakened and no row was removed. All eleven rows survive, a channel still cannot be claimed without its passing row, and flipping a channel to available in the descriptor immediately re-arms every row it owns. What changed is only that an unclaimed channel no longer blocks a claimed one.

## Notes

Two downstream consumers had to be anchored on the full set rather than the claimed subset, and getting either backwards would have silently disabled a gate.

The documentation claims gate is the sharper case. It exists to stop a page advertising a channel ahead of its proof, so it must keep teeth for exactly the channels a release does NOT claim. Anchoring it on the claimed set would have let a page claim an unclaimed channel with no row required at all, which is the precise failure it was built to prevent. The two gates are complements: readiness asks whether the channels you claim passed, the claims gate asks whether you are claiming one that did not.

The registry floor exists for the same reason. Without it a descriptor with nothing marked available would require zero rows and the readiness gate would pass while measuring nothing, which is the false-green shape this campaign has already shipped twice. A test pins that the floor is always in the required set.

Semantic search was degraded throughout; the required-row set was located by direct read after a semantic probe for it returned unrelated modules.
