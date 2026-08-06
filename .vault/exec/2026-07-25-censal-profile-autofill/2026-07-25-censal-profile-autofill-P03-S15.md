---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:522bfc629d970474f926957fc7745e2615232c19c5f2dcace56ec7fc1d43e9e5'
step_id: 'S15'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Offer the censal pull as a manager action gated on the auth mode having everything it needs, unavailable with an instructive refusal until the credentials are complete

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`

## Description

- Offer the censal pull as a manager action, third of three, after the authentication action that unblocks it.
- Read through the live facade's censal door and project the read through the shared reconciliation.
- Commit through the censal apply authority onto the single cotejo door, adding no second write path.
- Gate the action on the same credential predicate the authentication page uses, against the stored auth facts.
- Refuse before the read rather than after, so an incomplete setup costs the operator no second factor.
- Report all three outcomes, deriving unchanged from the read total, and name the paths AEAT disagrees on.
- Compose the fixture's source URL from the configured host suffix and censal path instead of a literal.

## Outcome

The screen can now do the thing it exists for. An operator says how they
identify to AEAT, and the next action fills their profile in from what
AEAT already publishes.

The gate needed no new predicate, which was the part worth getting
right. It asks the same question the authentication page asks, so
"complete" here means what the live session entry means by it. That
makes it track the route rather than the mode: an operator on the
default QR route is ready without a contraste, because the route they
will use never reads one. The certificate mode passes carrying no Cl@ve
half because the session entry asks nothing of it either - checked
against that entry rather than assumed, so the permissiveness is
agreement rather than a hole.

Nothing on the path can file, and nothing can aim it. The reader
navigates and parses, and takes its taxpayer from the authenticated
session's own identity, so the action offers no subject and accepts no
parameter. Both are pinned rather than asserted.

Fourteen cases pass, fifty across both of this executor's modules.
`ruff check`, `ruff format --check` and `ty check` pass. The owning
suites run whole and serially at 332 passing across both lanes, the
locale drift check is clean in all four catalogues, and the locale
honesty gate passes.

## Notes

Two things the work turned up, both now pinned. A read whose NIF differs
from the profile's declared `identity.tax_id` is reported as a
divergence rather than adopted - silently rewriting whose profile it is
would be worse than any address being stale, and nothing tested it. And
the third outcome has to be derived: a field AEAT agrees with is emitted
as neither adopted nor diverging, so an operator told only the other two
would see a pull that appears to have done nothing.

The fixture's source URL was a literal naming a numbered host that does
not serve that path. It is now composed from the configured host suffix
and censal path, so it asserts no host at all, and the route-literals
gate passes. It had been copied from a sibling test helper, which is how
a host pin propagates without anyone deciding to pin a host.

Landing this took an hour of index contention rather than any
disagreement about the code. Two agents were editing the same four
locale catalogues while the shared index held the other's staged work,
and each believed it could not get out of the way because `git reset` is
forbidden here. It is not needed: `git apply --cached -R` withdraws
staged hunks from the index alone, leaving the working tree untouched.
Sharing that unblocked the other half. The final commit was made only
after the index held exactly this Step's six files, verified in the same
command as the commit.
