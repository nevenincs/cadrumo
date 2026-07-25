---
tags:
  - "#adr"
  - "#shared-distribution-repository"
date: '2026-07-25'
related:
  - "[[2026-07-25-distribution-repo-topology-adr]]"
  - "[[2026-07-25-account-distribution-standard-adr]]"
  - "[[2026-07-22-scoop-runner-topology-adr]]"
  - "[[2026-07-25-account-distribution-standard-research]]"
  - "[[2026-07-17-post-release-distribution-plan]]"
supersedes:
  - '2026-07-25-distribution-repo-topology-adr'
modified: '2026-07-25'
---
# `shared-distribution-repository` adr: `One shared account distribution repository, superseding the per-product topology and answering the sibling-serving and no-precedent objections` | (**status:** `accepted`)

## Problem Statement

The product-scope topology record ruled that Scoop should be served from each
product repository's own `bucket/` directory, and it rejected a shared bucket
repository on two stated grounds. That record was subsequently rewritten in
place — same filename, same date, still marked accepted, with only its title
changed — to describe the opposite arrangement. Two harms follow, and both are
procedural rather than technical.

The first is that the record now documents a decision other than the one its
history executed, so a reader cannot reconstruct what was decided or when. The
second is worse: the original rejection reasoning was deleted rather than
refuted. An objection that is removed has not been answered, and a future reader
who independently rediscovers it finds no reply in the corpus — which is exactly
how a settled question reopens.

This record exists to close both. It supersedes the topology record through the
pipeline so the historical account stands unedited, and it answers the two
deleted objections on their merits. Its account-wide substance — the derived
channel matrix, the release mechanism, the naming rule, evidence proportional to
claims — is not restated here; that is owned by
`2026-07-25-account-distribution-standard-adr`, and this record is the topology
half of it applied at the scope the superseded record occupied.

## Considerations

- Homebrew's `homebrew-` repository-name prefix is mandatory for the
  one-argument tap form, so exactly one distribution repository is unavoidable
  for the account regardless of what is decided about Scoop. Established in
  `2026-07-25-distribution-repo-topology-adr`.
- Scoop imposes no repository-name constraint and scopes manifest discovery to
  a `bucket/` subdirectory when one is present. A repository name and a bucket
  directory are therefore disjoint constraints, which is what permits one
  repository to serve both ecosystems.
- The operator's standing objection is to distribution repositories as such, not
  merely to their per-product multiplication, per the same record. The binding
  reading is to minimise the count to the ecosystem-forced floor.
- The in-repository bucket writes to a public product repository's default
  branch at release time, and multiplies the user's one-time bucket-add by the
  number of products. Both costs were undercounted when it was chosen.
- `2026-07-22-scoop-runner-topology-adr` also rules on Scoop, and its
  relationship to this record has never been stated. Reconciled explicitly under
  Implementation.
- Discovery for this record was performed with the code index degraded — it was
  serving roughly a fifth of the tree while reporting itself healthy, and a
  semantic probe for distribution evidence returned unrelated modules. Every
  conclusion below rests on direct file reads and structured API queries. No
  ruling here depends on a semantic-search miss.

## Considered options

- **Leave the in-place rewrite standing.** Zero work. Rejected: the record
  contradicts its own execution history, and the deleted objections stay
  unanswered, so the question reopens the moment anyone rediscovers them.
- **Amend the topology record again in place.** The scaffold's own convention
  permits amendment for refinement. Rejected: this is a pivot, not a
  refinement — the ruling inverted — and a second in-place rewrite would compound
  the defect it is meant to correct.
- **Fold the answer into the account-scope standard record.** Tempting, since
  that record already governs account-wide. Rejected: it would leave the
  superseded record carrying no `superseded_by`, and it would bury a
  procedural correction inside a substantive ruling where no reader looking for
  the topology decision would find it.
- **A new record that supersedes through the pipeline and answers both
  objections explicitly (chosen).** The historical account stands unedited, the
  supersession is machine-readable, and each deleted objection gets a reply a
  future reader can evaluate.

## Constraints

- Repository creation and visibility are operator actions. The shared repository
  does not yet exist — a structured API query for it returned 404 at the time of
  writing — so the Homebrew and Scoop legs stay blocked on that creation
  regardless of what lands here. The publish authority is already configured
  against the shared slug, so the configuration is correct and the target is
  absent, which is a failure mode that reads as a code defect and is not one.
- Four of the five products live in repositories this session must not push to.
  For them this record is a specification, adopted under each product's own
  review.
- Nothing here authorises a publish, a registry upload, a community-repository
  submission, or a visibility change.

## Implementation

**The supersession.** The topology record is marked superseded and carries a
`superseded_by` pointer to this one, set through the owning pipeline verb. Its
body is left exactly as it stands: it is the historical account of what was
decided at product scope, and editing it again would destroy the evidence this
record exists to preserve.

**Answering the sibling-serving objection.** The superseded record rejected a
shared bucket repository partly on the ground that an in-repository `bucket/`
keeps the maintainer repository count at zero rather than merely reducing it.
The answer is that an in-repository bucket is product-scoped by construction and
therefore cannot serve a sibling product at all. It fixes the repository count
while preserving the fragmentation that prompted the review: every product still
carries its own bucket, every user still runs a distinct bucket-add per product,
and every release still writes to a public product repository's default branch.
The shared repository answers this directly — one bucket serves every product,
a user adds it once and never again, and no product repository's default branch
is written at release time. The count the in-repository option optimised was the
wrong count: it minimised repositories created while leaving per-product user
commands growing linearly.

**Answering the no-precedent objection.** The superseded record rejected the
shared arrangement partly because separate bucket and tap repositories are the
convention in both ecosystems and no precedent for combining them was known.
That objection was answerable and is now verified at source: the account
`verda-cloud/homebrew-tap` carries, at its root, a `Formula/` directory, a
`README.md`, and a `bucket/` directory, with `Formula/verda-cli.rb` and
`bucket/verda-cli.json` both populated with real content rather than
placeholders. One repository, both ecosystems, in production. The precedent
exists; the objection does not survive it. This was confirmed by direct
structured queries against the repository's contents, not inferred from
documentation.

**Reconciling the Scoop runner record — unaffected, and why.** A reader
encountering two accepted Scoop decisions should not have to derive their
relationship. `2026-07-22-scoop-runner-topology-adr` rules on *which runner
executes* the Scoop acquisition evidence lane: it places that lane on a native
Windows runner under a dedicated non-admin user rather than on the shared Docker
daemon, because Docker Desktop's container modes are mutually exclusive and a
mode switch would tear down the standing Linux runners. This record rules on
*where the Scoop manifest lives* once it is published. The two axes are
orthogonal: the evidence lane installs from a published bucket wherever that
bucket is hosted, and the bucket's hosting says nothing about which machine runs
the install. Retargeting the bucket from the product repository to the shared
account repository changes the URL the lane's `scoop bucket add` names and
nothing else — not the runner, not its labelling, not its profile reset between
runs. The runner record therefore stands accepted and unamended, and its
operator gate (provisioning the labelled runner) remains the sole outstanding
blocker on the `scoop-windows-x86-64` row, independent of this ruling.

**The arrangement itself.** The account carries exactly one distribution
repository, public, holding `Formula/` for Homebrew and `bucket/` for Scoop.
Both channel pushes in the publication authority target it through the same
repository variable and the same credential. Each stages exactly its own
product-scoped path, so a sibling product's file is never touched; each refuses
a backward version bump before committing, because a committed manifest is a
release pointer that ordinary merge semantics could otherwise move backward and
silently un-publish a newer version; and each retries a lost push race, because
several products can release into one repository concurrently and hosted
concurrency groups are per-repository and so cannot serialise across product
repositories. All three properties are pinned by a conformance gate that parses
the real workflow, and that gate is proven non-vacuous against the pre-change
workflow rather than merely asserted to be.

A new product therefore adds one formula file and one manifest file and creates
nothing. The repository count is one at one product and one at a hundred.

## Rationale

The decisive point is that the two objections fail for different reasons, and
both failures were visible at the time. The sibling-serving objection is not
wrong about its own metric — an in-repository bucket genuinely does create zero
repositories — it is wrong about which metric matters, because it silently moves
the multiplication from repositories the maintainer creates to commands the user
runs, and the user pays that cost once per product forever. The no-precedent
objection was simply an unverified empirical claim, and a single structured query
against a production account refutes it.

That asymmetry is why deleting them was the real defect. A deleted objection
teaches nothing; a refuted one teaches which metric to optimise and which claims
to verify before relying on them. This record answers both so the next reader
inherits the reasoning rather than rediscovering the question.

On topology itself the choice is more forced than it first appears. Exactly one
distribution repository is unavoidable because Homebrew's prefix admits no
in-repository option. Given that it must exist, serving Scoop from it costs
nothing, because the two ecosystems constrain disjoint things. Every alternative
costs something real: a second dedicated bucket repository creates a
discretionary distribution repository when a forced one already exists, which is
precisely the standing objection; and the in-repository bucket pays in
per-product user commands and release-time writes to public default branches.
Minimising to the ecosystem-forced floor is the strictest reading of the
objection on record, and it happens also to be the cheapest arrangement for
users. The odd sight of a Scoop bucket served from a repository named for
Homebrew is the entire price, and it is paid once, in a README.

## Consequences

The corpus becomes reconstructible. The superseded record stands as the
historical account of the product-scope decision, this record documents the pivot
and its reasoning, and the supersession pointer links them, so no reader has to
infer from a filename that a ruling was reversed.

Both previously-deleted objections now have standing answers a future reader can
evaluate and, if they disagree, argue against on the merits. That is a strictly
better position than the deletion left, and it is the durable gain here.

The cost is one more record in a corpus that already carries two on adjacent
questions, which is a real risk of exactly the fragmentation this campaign is
reducing. It is accepted deliberately: the alternative was a third in-place
rewrite, and the whole point of this record is that in-place rewriting of an
accepted decision is what produced the defect.

The Scoop runner record's orthogonality is now stated rather than derivable, so
the two accepted Scoop decisions can coexist without a reader having to work out
that they rule on different axes. Its operator gate is unchanged and still open.

One migration consequence carries forward unchanged from the account standard:
two products currently ship in-repository buckets and must move their manifests
into the shared repository, and until each adopts this under its own review the
account is standardised on paper and divergent in fact.
