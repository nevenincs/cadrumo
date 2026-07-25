---
tags:
  - '#adr'
  - '#distribution-repo-topology'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-19-post-release-distribution-reference]]"
  - "[[2026-07-22-scoop-runner-topology-adr]]"
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# `distribution-repo-topology` adr: `Distribution repositories are account-scoped and multi-product, not per-product` | (**status:** `accepted`)

## Problem Statement

The account publishing this product publishes several others under the same
name. Distribution for this product accreted four repositories — a Scoop
bucket, a Homebrew tap, a plugin marketplace, and an artifacts landing repo —
of which three are product-scoped and private, while the fourth is
account-scoped and public. None of the sibling products has any such
repository, so the shape has never been reused, and the publish authority's
marketplace target names a repository that does not exist. A topology ruling
is needed before the held publication proceeds, because publishing is what
makes these names permanent in users' install commands and in their local
package-manager state.

Three defects are load-bearing on the decision rather than incidental to it.
The marketplace repository variable names a slug that returns 404, so the
publish authority's marketplace push would refuse at Gate 3. The public
marketplace still declares its plugin under the pre-rename product name, so
the documented install command cannot resolve against it. The artifacts
landing repository carries a README and nothing else, and no code path in the
tree references it.

## Considerations

- Homebrew requires the remote repository to be named `homebrew-<name>` for the
  one-argument tap form; the two-argument form takes an arbitrary URL, and
  out-of-tap formula installs are effectively developer-only. The prefix is a
  real ecosystem constraint, not an accident of the current setup.
- Scoop imposes no name prefix and resolves manifests from a `bucket/`
  subdirectory when present, so a bucket repository may carry unrelated content
  alongside its manifests.
- A single tap holding many formulae under `Formula/`, and a single bucket
  holding many manifests under `bucket/`, are both fully supported and are the
  observed convention among maintainers who ship more than one tool.
- Both managers reach their repository by ordinary git clone, so a private
  target is unusable by any user without push credentials — the private state
  of the current bucket and tap is what blocks the acquisition evidence rows,
  not a tooling gap.
- The homebrew-core self-submission notability bar is far above this product's
  current position, and the product repository is private with no public
  signal at all, so core submission is not a reachable endgame within this
  campaign's horizon.
- For a Python CLI the dominant install channel is the Python tool installers;
  a tap and a bucket are supplementary reach, not the primary path.
- The account already carries a merged publisher namespace in the community
  Windows package repository for a sibling product, established without any
  per-product repository. That is direct evidence of the pattern the account
  already treats as standard.
- The publish authority's bucket and tap pushes already write exactly one file
  each, so they are safe against sibling content in a shared repository. The
  marketplace push instead replaces the tracked tree wholesale.

## Considered options

- **Keep per-product repositories, fix only the broken variable.** Minimal
  change; leaves four repositories for one product and a shape that multiplies
  by the number of products. Rejected — it preserves the fragmentation that
  prompted the review and teaches the next product to add two more repositories.
- **Serve the bucket from the product repository's own `bucket/` directory.**
  Mechanically supported by Scoop and removes one repository. Rejected — the
  product repository is deliberately private, so this couples the bucket's
  availability to a separate and much larger decision about publishing source.
  No real-world precedent was found for a product's primary repository serving
  its own bucket.
- **Drop the tap and bucket entirely and ship only the Python channels and
  release assets.** Honest and cheap, and defensible for a Python CLI.
  Rejected as the primary ruling — the artifacts, the generators, and two of
  the three Homebrew evidence rows already exist and pass, so retiring them
  discards working, evidenced capability. Retained in part: the channels stay
  supplementary and are not claimed in documentation without evidence.
- **Account-scoped multi-product bucket and tap, marketplace kept, landing
  repository retired (chosen).** One `homebrew-tap` and one `scoop-bucket`
  serving every product under the account, the existing account-scoped
  marketplace kept and corrected, and the artifacts landing repository retired.
  Two repositories instead of four, and the count no longer grows per product.

## Constraints

- Repository creation, deletion, and visibility changes are operator actions.
  This ruling can retarget every reference in the tree, but the public bucket,
  tap, and marketplace only become reachable when the operator creates and
  publishes them. Publication is outward-facing and effectively irreversible
  once indexed, so it stays an operator decision.
- The account is a user account, not an organization, so there are no
  account-level Actions variables. The reuse this ruling buys is the shared
  target repositories and the shared naming pattern, not a shared variable;
  each product repository still declares its own. Renaming the variables
  would therefore buy nothing mechanically and is not part of this decision.
- Moving the tap changes the user-visible install command, because the tap
  name is derived from the repository name. Any command already published must
  be swept in the same change.
- The Windows community package channel needs an installer URL served directly
  from the publisher's own release location, which the private product
  repository does not currently provide. That channel is recorded as the
  strategic Windows path but is out of scope here and is not claimed.

## Implementation

The bucket moves to one account-scoped repository whose manifests live under
`bucket/`, added by users under an account-named bucket alias rather than a
product-named one. The tap moves to one account-scoped repository carrying the
mandatory `homebrew-` prefix, with formulae under `Formula/`, so the install
command addresses the product within the account's tap rather than a
product-specific tap. Both new targets are additive for sibling products: each
later product adds one file.

Every site naming the old targets is retargeted in one sweep — the channel
descriptor that is the single source of truth for install commands, the two
post-publication acquisition entry points that carry defaults, the publish
authority's repository variables, and the acquisition test expectations. The
bucket and tap push steps need no structural change, because each already
stages exactly one file and therefore leaves sibling products' files untouched.

The marketplace push does need a structural change. It currently deletes every
tracked path except the git directory and replaces the tree from the release
bundle, which is correct only while the marketplace serves exactly one product.
Against an account-scoped marketplace that is a latent sibling-deletion defect,
so the replacement narrows to this product's own plugin subtree, and the
marketplace index entry is merged rather than overwritten.

The artifacts landing repository is retired rather than retargeted: nothing in
the tree references it, and the release assets it advertises are already served
from the product repository's own releases.

Documentation claims stay governed by the existing fail-closed claims gate.
Retargeting changes which command a channel would print, not whether it prints
one; every channel remains withheld until its evidence row passes.

## Rationale

The decisive evidence is that the account already ships a sibling product
through an account-scoped publisher namespace with no per-product repository at
all, while none of the sibling products has ever been given a bucket or a tap.
The per-product shape was therefore never a considered pattern the account
follows — it was applied once, to one product, and not repeated. Consolidating
to account scope aligns this product with what the account already does rather
than imposing a new convention on it.

The ecosystem research resolves the part of the current shape that is not a
mistake and should not be reported as one. Separate bucket and tap
repositories genuinely are the convention in these two ecosystems, and the
`homebrew-` prefix genuinely is mandatory. What is wrong is the per-product
axis, the count, the private visibility that makes the channels unusable by
anyone, and a variable pointing at nothing. Distinguishing these matters,
because a review that condemned taps wholesale would push toward discarding
working evidenced capability.

The chosen shape also removes the growth term. Four repositories for one
product is a pattern that reads, to the next product, as an instruction to
create two more; one bucket and one tap for the account is a pattern where the
next product adds one file to each.

## Consequences

Two repositories replace four, and the count stays flat as products are added.
The bucket, tap, and marketplace become reachable by ordinary users once the
operator publishes them, which unblocks the acquisition evidence rows that have
been blocked on private targets rather than on any missing capability.

The install commands change shape, addressing the product within an
account-scoped bucket and tap. Because nothing has been published, no user is
carrying the old commands, so this is a rename with no migration cost — a
window that closes permanently at first publication.

The marketplace fix is the one place where consolidation exposes a defect
rather than merely relocating a name: a wholesale tree replacement is safe for
a single-product marketplace and destructive for a shared one, and the shared
case is the one this ruling commits to.

Three things remain outside this ruling and stay open. The Windows community
package channel is recorded as the strategic Windows path but needs a publicly
reachable release location before it can be pursued. Whether the product
repository itself becomes public is a separate decision this record does not
make, and the chosen topology deliberately does not depend on it. And the
supplementary standing of the tap and bucket relative to the Python channels
means a future decision to retire them remains available at low cost.
