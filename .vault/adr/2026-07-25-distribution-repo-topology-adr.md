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

# `distribution-repo-topology` adr: `Distribution channels are shared and product-neutral, and Scoop needs no repository at all` | (**status:** `accepted`)

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
  subdirectory when present, so any repository — including the product's own —
  can serve as a bucket while carrying unrelated content. A dedicated Scoop
  bucket repository was therefore never necessary at all.
- A single tap holding many formulae under `Formula/` is fully supported and is
  the observed convention among maintainers who ship more than one tool. The
  canonical template is the HashiCorp account tap, which serves 33 formulae —
  terraform, vault, consul, nomad, packer and the rest — from one repository,
  installed as a product path within the tap. Per-product taps are not the
  convention.
- Both managers reach their repository by ordinary git clone, so a private
  target is unusable by any user without push credentials — the private state
  of the current bucket and tap is what blocks the acquisition evidence rows,
  not a tooling gap.
- The homebrew-core self-submission notability bar is far above this product's
  current position — the self-submission tier is three times the ordinary one —
  so core submission is not a reachable endgame within this campaign's horizon.
  The tap is the terminal state for that channel, not a waypoint toward core.
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
- **A dedicated account-scoped Scoop bucket repository.** One bucket repo
  serving every product, so a user adds one bucket and reaches all of them.
  Rejected by the operator: it still creates a distribution repository, and the
  standing objection is to distribution repositories as such, not merely to
  their per-product multiplication. Since Scoop reads a `bucket/`
  subdirectory, the repository buys a marginal user convenience at the cost of
  the very thing being retired.
- **Drop the tap and bucket entirely and ship only the Python channels and
  release assets.** Honest and cheap, and defensible for a Python CLI.
  Rejected as the primary ruling — the artifacts, the generators, and two of
  the three Homebrew evidence rows already exist and pass, so retiring them
  discards working, evidenced capability. Retained in part: the channels stay
  supplementary and are not claimed in documentation without evidence.
- **Zero Scoop repository, one shared tap, marketplace kept, landing
  repository retired (chosen).** Scoop is served from this repository's own
  `bucket/` directory, so no bucket repository exists at all; Homebrew gets one
  product-neutral `homebrew-tap` for the account, because its mandatory
  `homebrew-` prefix leaves no in-repo option; the existing account marketplace
  is kept and corrected; the artifacts landing repository is retired. One
  distribution repository total, and it does not grow per product.

## Constraints

- Repository creation, deletion, and visibility changes are operator actions.
  This ruling can retarget every reference in the tree, but the public bucket,
  tap, and marketplace only become reachable when the operator creates and
  publishes them. Publication is outward-facing and effectively irreversible
  once indexed, so it stays an operator decision.
- The account is a user account, not an organization, so there are no
  account-level Actions variables and each product repository declares its own.
  The variables are nonetheless renamed off the product prefix by operator
  ruling. The mechanical gain is nil and was argued as such; the gain is that
  the configuration a sibling product copies is identical rather than
  needing a rename, which is what makes the topology transferable in practice.
  The Scoop pair disappears entirely rather than being renamed, since an
  in-repository bucket needs no target and no credential.
- Moving the tap changes the user-visible install command, because the tap
  name is derived from the repository name. Any command already published must
  be swept in the same change.
- Discovery for this record was done by direct directory listings, file reads,
  and targeted pattern search, not by semantic search: the code index was
  serving roughly a fifth of the tree while reporting itself healthy, so a
  semantic miss was not evidence of absence. The one conclusion that depended
  on absence — that no existing packaging module already published a plugin
  tree or merged a marketplace index — was confirmed against the real module
  listing and their declarations rather than a search result.
- The product repository is public and its release assets are anonymously
  downloadable, verified by an unauthenticated fetch of a v0.2.1 asset. The
  generated bucket manifest and tap formula point at those release URLs, so
  the only remaining obstacle to a working acquisition is the bucket and tap
  repositories' own absence and visibility — not the assets they reference.
- That same fact retires the artifacts landing repository's rationale rather
  than merely leaving it unreferenced: it was created to serve public binaries
  for a private source, and the source is no longer private.
- The Windows community package channel needs an installer URL served directly
  from the publisher's own release location, which the public product
  repository now does provide. That channel is therefore newly viable, but it
  is recorded as a follow-on and is not claimed here — it needs its own
  manifest, submission, and evidence row.

## Implementation

Scoop is served from this repository's own `bucket/` directory. No bucket
repository exists, so the push takes no repository variable and no personal
access token: it targets the workflow's own repository using the job's built-in
token. Every sibling product repeats the identical layout in its own
repository, which is what holds the per-product distribution-repository count
at zero rather than merely reducing it.

The tap is one product-neutral account repository carrying the mandatory
`homebrew-` prefix, with formulae under `Formula/`, so the install command
addresses the product as a path within the account's tap. A second product adds
one formula file and nothing else.

The two remaining channel variables are renamed off the product prefix so a
sibling product copies the same configuration verbatim. Every site naming the
old targets is retargeted in one sweep — the channel descriptor that is the
single source of truth for install commands, the acquisition entry points that
carry defaults, the publish authority's variables and refusal text, and the
workflow conformance expectations.

The bucket and tap push steps stage exactly one product-scoped path each, which
is what makes a shared channel safe. That property is pinned by a conformance
gate asserting each push names its own file and carries none of the sweeping
forms — stage-everything or a wholesale delete of the checkout — that would
take a sibling product's file with it. That gate is the acceptance test for the
design, and it fails against the previous workflow.

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
follows — it was applied once, to one product, and not repeated. The external
template points the same way: the canonical multi-product tap serves 33
formulae from one repository.

The Scoop finding is what makes this more than a consolidation. A bucket
repository was never required in the first place, because Scoop reads a
`bucket/` subdirectory of any repository. The three repositories that existed
for this product were not an over-application of a necessary pattern; one of
them answered a requirement that does not exist.

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

One repository replaces four, and the count stays flat as products are added.
The tap and marketplace become reachable by ordinary users once the operator
creates and publishes the tap, which unblocks the acquisition evidence rows
that have been blocked on private targets rather than on any missing
capability. Scoop needs no such step at all.

The in-repository bucket carries one operational consequence worth stating: a
publication now commits to this repository's default branch. If branch
protection later requires reviews or checks on that branch, the rule must admit
the publish workflow or the Scoop push fails.

The install commands change shape, addressing the product within an
account-scoped bucket and tap. Because nothing has been published, no user is
carrying the old commands, so this is a rename with no migration cost — a
window that closes permanently at first publication.

The marketplace fix is the one place where consolidation exposes a defect
rather than merely relocating a name: a wholesale tree replacement is safe for
a single-product marketplace and destructive for a shared one, and the shared
case is the one this ruling commits to.

Two things remain outside this ruling and stay open. The Windows community
package channel is now viable, because the release location it needs is
public, and the account already holds a merged publisher namespace there for a
sibling product; pursuing it is a follow-on that needs its own manifest,
submission, and evidence row. And the supplementary standing of the tap and
bucket relative to the Python channels means a future decision to retire them
remains available at low cost.

One caution is worth recording because it bit this record's own drafting: the
product repository's visibility changed from private to public during the
review, and an early reading of the account's repository listing was already
stale by the time it was used. Any later work here should re-read repository
visibility at the moment it acts rather than trusting a listing taken earlier
in the same session.
