---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:73b3687d2c2e5884716dde9542de94a6125ebed93cefba14a875a5e5bf5943b2'
step_id: 'S70'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# replace the operator real name with a non-identifying stand-in throughout the conformance CLI test module, closing the committed privacy violation this campaign introduced which reds the per-push lane

## Scope

- `dev/tests/test_registry_conformance_cli.py`

## Description

- Capture the privacy gate's failing output serially before changing anything.
- Replace the operator's real name with a fictional person-shaped stand-in.
- Rename the constant for the shape it supplies rather than for a role.
- Derive the operator signoff attribution from that one constant.
- Re-run the privacy gate serially and the conformance CLI module in full.

## Outcome

The gate is green on the tracked-file scan. Before the change it named eight
lines in one module and nothing else; after it, `test_no_operator_identifying_tokens_in_tracked_files`
passes, run serially so a parallel selection cannot deselect it. The conformance
CLI module still passes in full at 74 tests, which matters because ten of the
renamed sites and five of the signoff sites are load-bearing assertions rather
than fixture text.

Two decisions beyond the substitution. The replacement value is person-shaped —
two words and a space — rather than a token like `reviewer-1`, because what these
surfaces defend against is a human name rendering identically under both review
tiers; a token-shaped value would exercise a shape production never meets, and
the tests would keep passing while proving less. And the constant was renamed
from `_OPERATOR_NAME` to a name describing the shape it supplies, because a
constant called after the operator is what invited the operator's actual name
into it; the fixture is not an operator and never was, since every assertion
using it stamps an agent-tier review.

The signoff attribution is now declared once and read back by five assertions
that previously carried it as a hand-copied literal. That was a latent defect
independent of the privacy one: a rewrite changing the seed would have left five
assertions checking the old value, and all five would still have passed.

No allowlist entry was added. The gate was right and the source was wrong.

## Notes

This was a committed privacy leak, not a pre-commit catch: it entered tracked
source in this campaign's own commit and four later commits carried it forward,
so the per-push lane has been red since it landed. Removing it now is an edit;
it is already unrecoverable from history without a rewrite. The gate itself
documents this asymmetry for untracked files and the same reasoning applies
here — the window that mattered closed at the first commit.

The privacy module has one remaining failure that is not this campaign's. A peer
commit landed a cloud role identifier in a delivery test between the two runs
made here; it was untracked during the first run and tracked by the second, which
moved the failure from the untracked scan to the cross-project tracked scan. It
is reported to the coordinator rather than fixed, since that tree belongs to a
live peer campaign.
