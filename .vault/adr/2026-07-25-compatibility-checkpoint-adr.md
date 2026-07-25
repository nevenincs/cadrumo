---
tags:
  - '#adr'
  - '#compatibility-checkpoint'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
  - "[[2026-07-08-released-data-durability-adr]]"
  - "[[2026-07-04-release-readiness-gate-adr]]"
  - "[[2026-07-25-compatibility-checkpoint-research]]"
---

# `compatibility-checkpoint` adr: `release the pre-release regime, or defer the durability commitment` | (**status:** `proposed`)

## Problem Statement

Two correctly-labelled breaking-change footers have made the next computed version
`1.0.0`, and the compatibility tripwire refuses a 1.0 cut while the regime constant
is pre-release. The version calculator and the durability regime are therefore
mechanically coupled, but they answer different questions: the calculator observes
that a CLI flag was renamed, while the regime decides whether this project now owes
users the ability to read their encrypted financial data across every future
version. Flipping the regime freezes each durable format's floor permanently and
makes every later version bump owe a one-hop upgrader, a committed pre-bump
fixture, and a restorability test through the real read path. That obligation is
worth taking on when the formats have stabilised. The readiness pass
(`2026-07-25-compatibility-checkpoint-research`) finds they have not: two of five
durable formats cannot be enrolled at all, one versioned format is undeclared, two
evidence-bearing readers sit above the lineage policy, and the enforcement
substrate was restored to the tree one day ago after eight days of absence. A
decision is needed now because the release cannot proceed in either direction
without one.

## Considerations

- The flip's payload is only three floors. `secure_object` at 1, `bundle` at 3,
  `archive` at 3 are the sole keys the enrollment invariant admits; the research
  records each constant and locator.
- `bucket_dek` and `bucket_manifest` are declared durable and carry neither a floor
  constant nor a tier gate, and no gate asserts that a durable format carries a
  floor, so a flip omitting them passes green while excluding the document that
  unlocks every byte in a bucket.
- `blob_manifest` is a versioned persisted format absent from the durability
  inventory because enrollment discovery filters on a path kind it does not carry.
- A product-rename commit raised a durable format's version and floor together
  twelve days ago; under the released regime that same commit would have owed a
  version-aware reader and a fixture.
- The proposed `1.0.0` is an inherited tooling default, not a chosen milestone.
  The release configuration declares no stance on `bump-minor-pre-major` at either
  level, so a breaking change on a pre-1.0 version goes straight to `1.0.0` where
  the alternative setting would give `0.3.0`; the research records the observed key
  sets and the three-way confirmation of the default's semantics.
- The tripwire couples the two decisions in one direction only. It forbids a 1.0
  cut while the regime is pre-release; it never requires the flip to wait for
  1.0.0. Freezing the floors and declaring the interface stable are separable
  claims, and the gate already treats them as such.
- The regime constant is documented one-way, so the cost of flipping early is not
  symmetric with the cost of flipping late.

## Considered options

- **Flip to released at 1.0.0, freezing the three tier floors.** Satisfies the
  tripwire and honours the accepted lifecycle mechanism as written, though the
  1.0.0 it satisfies was never consciously chosen. Rejected for
  now: it publishes a durability guarantee whose scope silently excludes two
  durable formats and one undeclared one, and it freezes floors on a substrate that
  has been in its intended shape for a day.
- **Flip to released at 1.0.0 after closing the durable-format gap.** The correct
  eventual shape, and the target this record sets. Rejected as the immediate action
  because the remediation is real engineering work, not a constant edit, and it
  cannot ride the release commit.
- **Suppress or relabel the breaking-change footers to keep the calculator below
  1.0.0.** Rejected outright: the footers are accurate, and misdescribing a
  breaking change to dodge a gate corrupts the changelog users read.
- **Defer the durability commitment and release as 0.3.0 under the pre-1.0
  convention (chosen).** Keeps the regime pre-release, ships the breaking changes
  honestly labelled, leaves every floor free to chase current while the formats
  settle, and costs one configuration key.

## Constraints

- The regime is a one-way repo-committed constant by the accepted lifecycle
  decision; it must not become a setting, an environment variable, or a value a
  gate can patch. Nothing in this record relaxes that.
- The pre-release no-legacy posture continues to bar fabricating an old-version
  fixture or a real upgrader before a genuine post-checkpoint bump exists, so the
  readiness work below is limited to declarations, gates, and read-path routing.
- The flip commit must move three constants together, not two: the regime, the
  frozen floors, and the per-format current versions the coverage harness ranges
  over. Their key sets are gate-bound.
- Semantic code search was degraded throughout the grounding pass, serving a
  fraction of the tree while reporting itself healthy. Every fact this record rests
  on was established by direct file read and targeted `rg`; no claim of absence
  rests on a search miss. A reader re-verifying this record should do the same.
- Whether any installation outside the operator's own machines already holds
  persisted taxpayer data was not established. If one does, the deferral's premise
  weakens and the readiness work becomes urgent rather than merely sequenced.

## Implementation

We will defer the durability commitment and keep the release line below 1.0.0. The
release configuration declares `"bump-minor-pre-major": true` explicitly, so the
two breaking-change footers bump the minor and the next version is 0.3.0 with its
breaking changes described accurately in the changelog. `COMPATIBILITY_REGIME`
stays pre-release, `RELEASED_FORMAT_FLOORS` stays unpopulated, the tripwire stays
satisfied, and no floor freezes.

Declaring that key is part of the decision in either direction. Leaving it unset is
not a neutral position: it is the `false` default deciding a durability question on
the evidence of a renamed CLI flag, silently and without a record. Whichever way
the operator rules, the key is stated in the configuration so the version
calculator's behaviour becomes a recorded choice rather than an inherited default.

The deferral is bounded by four readiness conditions, each a gate rather than a
judgement. First, `blob_manifest` joins the durability inventory, and enrollment
discovery widens past the single path kind so no versioned format can pass by
omission again. Second, `bucket_dek` and `bucket_manifest` each acquire a named
current-version constant, a durability floor, and a tier lineage gate, or are
reclassified with a recorded rationale; the bucket manifest's version stops being a
bare literal at its write site. Third, the blob-manifest and attachment-manifest
readers route through the ceiling-and-upgrade policy instead of refusing on strict
inequality, so a registered upgrader would actually make an older record readable.
Fourth, a new predicate and gate assert the converse of enrollment: every durable
format in the inventory carries a frozen floor once the regime is released, so the
flip cannot pass green while excluding a durable format.

When those conditions hold, the flip commit contains exactly this and nothing else:
`COMPATIBILITY_REGIME` set to released; `RELEASED_FORMAT_FLOORS` populated with
every durable format's then-current floor; and the per-format current-version
mapping in the central gate populated with the same key set. It adds no upgrader and no
fixture, because at the checkpoint every format sits at its floor and there is no
old shape to read. Every subsequent bump above a frozen floor pays the full cost in
its own commit.

The version bump is deliberately not part of that commit. Data durability and
interface stability are different claims answering to different evidence, and the
tripwire's one-directional coupling permits the flip at any version. The flip lands
when the formats have stabilised; 1.0.0 is cut when the interface has, which may be
the same week or much later. The tripwire guarantees only the ordering, that 1.0.0
cannot precede the flip.

## Rationale

The decisive fact is scope, not schedule. A durability guarantee is only worth what
it covers, and a flip today would freeze floors for three formats while
`bucket_dek` and `bucket_manifest`, both declared durable, carry no floor, no
upgrader, and no tier gate, and while no gate exists that would notice their
absence. The wrapped DEK is the document that unlocks every byte in a bucket;
publishing a durability commitment that structurally excludes it, and passing every
gate green in the process, would make the guarantee less trustworthy than having
none, because a future reader would take the frozen mapping as the complete
inventory. The supporting evidence points the same way: the enforcement substrate
was absent from the tree for eight days and restored one day ago, and within the
same fortnight a product rename bumped a durable format and raised its floor with
it, a commit the released regime would have made illegal. A tree that cannot hold a
floor still for two weeks is not ready to hold one forever.

Deferral costs almost nothing and preserves the only asymmetry that matters. The
regime is one-way, so flipping late is recoverable and flipping early is not.
Releasing as 0.3.0 loses no honesty: the breaking changes ship, labelled, in the
changelog, under a convention that is standard for pre-1.0 software and already
supported by the release tooling. The version number is the cheapest thing in this
decision to be wrong about; the durability promise is the most expensive.

## Consequences

- Good: the release proceeds without a red suite and without a premature promise;
  the durable formats keep chasing current while they settle; the four readiness
  conditions convert an open judgement call into gates a later agent can satisfy
  and verify.
- Good: closing the readiness conditions has value independent of the flip. The
  undeclared `blob_manifest` and the two strict-equality readers are real gaps in
  the inventory today, not merely obstacles to a checkpoint.
- Accepted cost: 1.0.0 is deferred, and with it the signal that the interface is
  stable. Users reading a pre-1.0 version number will correctly infer that
  persisted data carries no cross-version guarantee yet, which is the true state.
- Accepted cost: `bump-minor-pre-major` also governs future breaking changes below
  1.0.0, so subsequent breaks will bump the minor until the flip. That is the
  intended behaviour, but it means the version line carries less information about
  severity; the changelog remains the accurate surface.
- Bad: this record does not close the readiness work, only names it. Until it
  lands, the durability inventory remains incomplete in the ways the research
  documents.
- Rollback: there is none in code. The regime constant is one-way by design, so if
  a flip later proves premature the frozen floors cannot be lowered and the
  obligations cannot be revoked; the only paths are to pay the upgrader cost on
  every bump, or to supersede this lineage with a record that accepts an explicit
  break and requires users to export and re-import through the profile bundle
  before upgrading, a migration users perform rather than one the code performs.
  That asymmetry is the reason this record defers rather than flips.
