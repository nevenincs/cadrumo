---
tags:
  - '#adr'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:cf90cf933c166246314019e76ca521536796ab775242f990775d3c0ad2053b36'
related:
  - "[[2026-07-25-distribution-repo-topology-adr]]"
  - "[[2026-04-12-release-please-adr]]"
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
  - "[[2026-07-25-account-distribution-standard-research]]"
---

# `account-distribution-standard` adr: `One account distribution standard: one shared channel repository, a derived channel matrix, and evidence proportional to claims` | (**status:** `accepted`)

## Problem Statement

Five products distribute independently, and the results are recorded in
`2026-07-25-account-distribution-standard-research`. No two share a mechanism, a
naming convention, or a repository topology, and the ordering by machinery is
close to the inverse of the ordering by what a user can install. A per-product
remedy would produce a sixth arrangement rather than a standard, so the decision
has to be taken at account scope and has to hold for products that do not exist
yet.

Three things force it now rather than later. A publication binds names into users'
install commands and into their local package-manager state, so every convention
chosen after the first release is a migration rather than a choice. The
product-scope topology record settled most of its own question but explicitly
marked its Scoop transport provisional and deferred it to an account-scope record,
which is this one. And a live publisher namespace has already been consumed by a
product that does not carry its name, which is a defect that compounds with each
further submission.

The scope is what every product must share: which channels a product ships to and
why, how many repositories the account carries to serve them, how a release is
triggered and authenticated, how every user-facing name is derived, and what
proof a channel must produce before it may be claimed. Product-specific gating —
cadrumo's operator preflight, its protected environment — remains the product's
own and is not flattened here.

## Considerations

- The Homebrew `homebrew-` repository-name prefix is a real ecosystem constraint
  on the one-argument tap form, so exactly one distribution repository is
  unavoidable; Scoop constrains only directory layout, so it needs none. Both are
  established in the product-scope record `2026-07-25-distribution-repo-topology-adr`.
- The operator's standing objection is to distribution repositories as such, not
  merely to their per-product multiplication, per the same record. The binding
  reading is therefore to minimise the count to the ecosystem-forced floor, not to
  trade a forced repository for a discretionary second one.
- A repository name and a bucket directory are disjoint constraints, so one
  repository can serve both ecosystems. The product-scope record names this as the
  option it failed to consider.
- The in-repository bucket alternative holds the maintainer repository count at
  zero but multiplies the user's one-time bucket-add by the number of products,
  and writes to a public product repository's default branch at release time.
- Two independently-built products arrived at the same backward-bump guard on a
  committed release-pointer manifest, per the research. A guard two teams
  reinvent belongs to the mechanism.
- The three-file shipping mechanism the research documents is already proven in
  production twice, publishes without any stored credential, and in one product
  already carries binaries and a package-manager manifest as well as the registry.
- The evidence apparatus has two genuine fail-closed consumers and refuses to
  fabricate proof, but requires eleven rows across five channels before any single
  channel may publish — including channels whose acquisition workflows have never
  succeeded.
- Product shapes differ on two axes that actually matter: whether the artifact
  exposes a command a user invokes, and whether that user can be assumed to hold
  the language toolchain. Every other difference between the five is incidental.

## Considered options

- **Per-product distribution repositories, tidied.** Rejected. Rejected already at
  product scope, and it fails the growth test outright: the count is linear in
  products and the shape instructs the next product to add two more.
- **In-repository `bucket/` per product, one shared tap.** The product-scope
  ruling. Rejected here for the reason that record itself anticipated: it holds
  maintainer repositories at the floor only by moving the cost onto users, who
  must run a distinct bucket-add per product, and it puts a release-time write on
  each public product's default branch. Retained as the fallback if the shared
  repository is ever unavailable.
- **A dedicated Scoop bucket repository alongside the tap.** Two constant
  repositories, clearer naming, conventional in both ecosystems. Rejected: it
  creates a discretionary distribution repository when a forced one already exists
  and can serve both, which is precisely the objection on record.
- **Registry and release assets only; no tap, no bucket, no community channel.**
  Cheap and honest, and defensible for a developer tool. Rejected as the account
  rule because it is wrong for a product whose users are not developers, but
  adopted as the default tier for products whose users are.
- **One shared `homebrew-tap` repository carrying both `Formula/` and `bucket/`,
  with the channel set derived per product (chosen).** One distribution repository
  for the account, constant in product count; one tap-add and one bucket-add that
  a user performs once and never repeats; no release-time write to any product
  repository's default branch.

## Constraints

- Repository creation and visibility are operator actions. This record can retarget
  every reference in this product's tree, but `nevenincs/homebrew-tap` does not yet
  exist — the research records a 404 against the slug the publish authority is
  already configured to push to — so the Homebrew and Scoop legs stay blocked on
  that creation regardless of what lands here.
- Publication is outward-facing and effectively irreversible once indexed. Nothing
  in this record authorises a publish, a registry upload, a community-repository
  submission, or a visibility change.
- Four of the five products live in repositories this session must not push to.
  For them this record is a specification and a migration instruction, not an
  applied change; each product adopts it under its own review.
- A published community-package identifier cannot simply be renamed. The
  unqualified namespace already carries a released version, so the correction is
  forward-only and leaves an orphaned version behind.
- The account is a user account, not an organisation, so there are no
  account-level Actions variables. Every product declares its own copy, which
  makes identical variable naming the only mechanism by which configuration is
  transferable.
- Cadrumo's governing release record mandates local-only version bumping with no
  workflow. This record does not overturn it; it standardises the artifact that
  bumping produces, which that record already satisfies.
- The measurement underlying this decision was taken with semantic search
  degraded, as the research states. Every conclusion rests on direct reads and
  structured API queries; no ruling here depends on a semantic-search miss.

## Implementation

**One repository.** The account carries exactly one distribution repository,
`homebrew-tap`, public, holding `Formula/` for Homebrew and `bucket/` for Scoop.
Homebrew reaches it as an account tap and addresses each product as a path within
that tap; Scoop adds the same repository once under an account-named bucket and
addresses each product as a path within it. A new product adds one formula file
and one manifest file and creates nothing. The repository count is one at one
product and one at a hundred.

**A derived channel matrix.** A product's channel set is not chosen; it falls out
of two properties. The first is whether the artifact exposes a command a user
invokes directly. The second is whether that user can be assumed to hold the
language toolchain. Every product ships its language-native registry — that is the
floor, and it is the only channel where dependency resolution happens. A product
exposing a user-invoked command additionally ships standalone per-platform
executables on its own releases, which removes the toolchain prerequisite. A
product exposing a user-invoked command to an audience that cannot be assumed to
hold the toolchain additionally ships the shared tap, the shared bucket, and the
community Windows channel. Orthogonally, a product that is an extension of a host
application also ships that host's own channel.

Applied, this yields: the tax product at the full set plus its host marketplace,
because its users are taxpayers and advisers; the dashboard at the full set,
because it is a served interface rather than an imported one; the two developer
CLIs at registry plus executables; and the headless service at registry alone.
None of these is a per-product exception — each is the rule evaluated.

**One release mechanism, standardised on its output.** The version is owned by
release-please configuration and its manifest, single-source, with the number
written into the product's own package metadata. Publication is a dispatched
build, then a smoke test that installs and executes the built artifact standalone,
then an upload authenticated by workload identity federation with no stored
credential. The trigger is deliberately not standardised: whether the release
commit is produced by a workflow or by a local invocation is a per-product safety
choice, and both produce the same artifact — a release commit, a tag, and an
updated manifest. Standardising the output is what makes the pipeline
transferable; standardising the trigger would have overturned a governing record
for no mechanical gain.

Two properties of that mechanism are mandatory rather than incidental. Publication
must be dispatched explicitly rather than relying on a tag push to trigger it,
because a tag created by a workflow's own token does not fire tag-triggered
workflows; a declared tag trigger that the dispatch path masks is dead weight and
is removed rather than kept. And any committed release-pointer manifest carries
the monotonic backward-bump guard the research documents, because ordinary merge
semantics can otherwise un-publish a newer version with no workflow failing.

**Mechanically derived names.** Every user-facing name derives from the product
name by a fixed rule: the repository, the registry package, the tap formula, the
bucket manifest, and the community-package identifier all carry it, the last
qualified by the account as publisher. No unqualified family name is ever claimed.
The existing unqualified submission is a defect under this rule; it is corrected
forward, by submitting subsequent versions under the qualified identifier and
leaving the released version orphaned, since a published identifier cannot be
renamed in place.

**Evidence proportional to claims.** The apparatus stays. Its required row set
stops being a fixed list spanning every channel and instead derives from the
channels the release actually claims, which is the relationship the documentation
claims gate already models correctly. A release claiming one channel proves one
channel; a release claiming five proves five. No gate is weakened, no row is
removed, and no channel may be claimed without a passing row — the change is that
an unclaimed channel no longer blocks a claimed one.

**A day-one checklist.** A new product declares release-please configuration and
its manifest; adds the two workflows; evaluates the two properties to obtain its
channel set; adds one formula file and one manifest file to the shared repository
if that set includes them; and registers workload identity federation on the
registry. That is the whole cost, and it does not grow with the number of products
already shipping.

## Rationale

The decisive fact is the inversion the research measures: the two products with
the least distribution machinery are the only two a user can install, and the two
with the most publish nothing. That result does not condemn rigor, and reading it
that way would be the expensive mistake — the evidence apparatus has real
fail-closed consumers and has genuinely produced tamper-evident output. What it
condemns is building proof for a five-channel future before the first channel has
delivered a byte. Making the required row set derive from claimed channels is the
smallest change that resolves the contradiction, because it preserves every gate's
teeth while removing the only thing those teeth were biting: channels nobody was
claiming.

On topology, the choice is forced further than it first appears. Exactly one
distribution repository is unavoidable because Homebrew's prefix admits no
in-repository option. Given that it must exist, serving Scoop from it costs
nothing — the two ecosystems constrain disjoint things — while every alternative
costs something real: a second repository contradicts the standing objection, and
the in-repository bucket pays in per-product user commands and in release-time
writes to public default branches. Minimising to the ecosystem-forced floor is the
strictest reading of the objection on record, and it happens to also be the
cheapest for users. The odd sight of a Scoop bucket served from a repository named
for Homebrew is the entire price, and it is paid once, in a README.

On the channel matrix, a list would have been wrong at any length. Five products
already differ enough that any single list is either noise for the developer tools
or a gap for the tax product, and product forty-seven is not going to resemble any
of the five. Deriving the set from whether there is a command and whether the user
has the toolchain gives an answer for a product nobody has described yet, which is
the only property that survives to a hundred products.

On the release mechanism, the standard deliberately stops short of the trigger.
The temptation was to make every product run release-please in CI for consistency,
which would have overturned a governing record whose local-only mandate exists for
a product that must never publish by accident. Since both paths emit the same
release commit, tag, and manifest, standardising the output captures the entire
transferable gain and the trigger difference costs nothing. Flattening a real
safety requirement to win uniformity would have been the failure mode this record
exists to avoid.

## Consequences

The account carries one distribution repository at any number of products, and a
user runs one tap-add and one bucket-add ever. Adding the forty-seventh product
costs two configuration files, two workflows, two lines in the shared repository,
and one federation registration — a fixed cost that does not grow with the number
of products already shipping, which is the property the whole standard is chosen
for.

The cost is concentrated in migration, and it is real. Two products currently carry
in-repository buckets and must move their manifests into the shared repository, and
one of those buckets points at an asset that has never existed. Four of the five
products live outside this session's reach, so for them this record is a
specification each must adopt under its own review, and until they do the account
is standardised on paper and divergent in fact. The publish authority in this
product is already configured against the shared tap slug, so its Homebrew and
Scoop legs unblock the moment the operator creates that repository and stay blocked
until then — the configuration is correct and the target is absent, which is a
failure mode that reads as a code defect and is not one.

Proportional evidence changes what a first release looks like. The tax product can
now publish to the registry alone, proving the registry alone, without waiting on
two acquisition workflows that have never once succeeded. That is the intended
gain, and its honest cost is that the first release will claim less than the
apparatus was built to prove — the channels arrive one at a time, each when its
own proof passes, rather than together.

The namespace correction leaves a scar. A released community package under the
unqualified name cannot be renamed, so the account will carry an orphaned version
under a name that does not match its product, permanently, while subsequent
versions ship under the qualified identifier. Choosing the convention now is what
holds that scar to one version instead of accumulating one per release.

Two things stay open. The community Windows channel is newly viable for this
product because its release assets are now public, but it needs its own manifest,
its own submission, and its own evidence row, and the submission is an
outward-facing action against a repository the account does not own. And the
in-repository bucket pattern is retained as a documented fallback rather than
deleted, because if the shared repository is ever unavailable it is the only
option that keeps Scoop working without creating a repository.
