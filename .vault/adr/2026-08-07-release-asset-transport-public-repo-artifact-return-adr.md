---
tags:
  - "#adr"
  - "#release-asset-transport"
date: '2026-08-07'
related:
  - "[[2026-07-20-release-asset-transport-adr]]"
  - "[[2026-07-20-release-asset-transport-audit]]"
supersedes:
  - '2026-07-20-release-asset-transport-adr'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:0cf6d81c4a78bb962276db580b62344aca1ba32a3aab918dd5ffc1cb89924775'
---
# `release-asset-transport` adr: `evidence and cohort transport returns to Actions artifacts` | (**status:** `accepted`)

## Problem Statement

The transport decision of `2026-07-20-release-asset-transport-adr` moved every
inter-workflow payload off Actions artifact storage and onto per-run draft GitHub
releases in a reserved evidence namespace. That decision rested on one load-bearing fact
stated in its own problem statement: the repository was private on a GitHub Free plan for
a User account, where included artifact storage caps near 500 MB and the
multi-hundred-MB cohort exhausted it on essentially every packaging leg, hard-failing
uploads. Release assets were the only zero-cost durable store the platform offered that
account.

The repository is public. Public repositories get free, effectively unlimited Actions
artifact storage, so the constraint that forced the workaround no longer exists. The
prior record itself named the artifact-based shape (its option 7, cargo-dist-style
scratch transport with a transactional final release) the industry-preferred design and
rejected it *solely* as structurally unavailable under the Free-plan constraint. It is
available now.

The operator's ruling on 2026-08-07 is the proximate driver: machine scaffolding must not
appear on the repository's releases page at all. Seventy-one evidence drafts had
accumulated, every one titled to disclaim itself, and the packaging workflows minted more
on each dispatch.

## Considerations

- The prior design held exactly as specified: all 71 containers were drafts, none was
  published, and the remote carried zero tag refs. Drafts are visible only to accounts
  with push access. The measured state is recorded in
  `2026-07-20-release-asset-transport-audit`.
- Owner-visible is not nothing. The releases page is the operator's own surface; a
  namespace of machine scaffolding on it is a standing cost paid on every glance, and no
  amount of self-disclaiming title text removes it.
- The prior record anticipated this event twice: it rejected prereleases because they
  would be publicly visible if the repo went public, and it deferred build-provenance
  attestation to be revisited when the repo was public. Both clauses have now fired.
- The manifest layer (its D2) existed because a release asset is not intrinsically bound
  to the run that produced it. An artifact is. The binding the manifest reconstructed is
  native to the replacement, so removing it loses no provenance.
- The single-creator topology (its D1) existed because GitHub permits duplicate drafts
  for one tag name, a documented race. Artifacts have no creation race, which lets the
  dedicated creator job and the matrix gating disappear. Artifacts do collide on *name*,
  so per-leg naming becomes the property that keeps concurrent matrix legs independent.
- Artifacts expire; drafts did not. Retention is 90 days, this account's maximum, and a
  promotion attempted past it fails at download with no expiry-specific message. This is
  a genuine regression against the prior design and the only one.
- The release *candidate* soak deliberately holds bytes for days beyond a campaign and is
  unaffected: it rides its own draft release precisely because it must outlive a
  retention clock, and it was never part of the per-run packaging transport.
- Least privilege is the durable form of the ruling. The contents-write permission is
  what makes the releases API reachable; removing the calls without removing the grant
  would leave the capability one edit away.

## Considered options

1. **Keep the draft transport, delete the accumulated drafts periodically.** Rejected by
   operator ruling: the workflows repopulate the namespace on the next dispatch, so this
   is a recurring manual chore that never converges, and it retains a permission and a
   garbage-collection workflow whose only purpose is to manage self-inflicted debris.
2. **Strip the release calls from packaging workflows without a replacement transport.**
   Rejected: it satisfies the ruling and breaks the pipeline, since the cross-host oracle
   legs and the acquisition lanes genuinely need cloud transport for their inputs.
3. **External object storage.** Rejected for the same reasons the prior record rejected
   it: it violates the minimal-cloud-cost mandate, adds a credential and an availability
   dependency, and discards the free run-to-artifact-to-API provenance triangle.
4. **Return to Actions artifacts.** Accepted. The constraint that made this unavailable
   is gone, the prior record already named it preferable, and it strictly simplifies the
   provenance story rather than weakening it.

## Constraints

- Depends on the repository remaining public. Reverting it to private would restore the
  storage cap and invalidate this decision; that reversal must reopen this record rather
  than silently degrade the pipeline.
- The 90-day retention bounds the promotion window. Nothing in the platform warns as it
  closes, so the operator runbook carries the window explicitly.
- Cryptographic attestation remains deferred. Its stated trigger (a public repository)
  has now been met, so it is actionable rather than blocked, but it is out of scope here
  and unaffected either way.

## Implementation

**D1 — Payloads ride the producing run's artifacts.** Each of the four packaging
workflows uploads its outputs with the pinned upload-artifact action and consumes
same-run inputs with the pinned download-artifact action. Cross-workflow consumption (the
acquisition lanes reading a smoke cohort, and both publication gates) uses a run-scoped
artifact download against the source run id, which remains the operator's only handle.
The dedicated draft-creating job, the create-if-absent probes, and the two terminal seal
jobs are deleted rather than adapted.

**D2 — Run identity is the whole provenance binding, checked before any byte moves.**
Because an artifact cannot be attached to a run that did not produce it, the layered
release-to-run and manifest checks collapse to the Actions-API identity assertion that
was always the anchor: workflow path and a successful conclusion, plus the acquisition
lanes' existing stronger check on branch, event, main-ancestry and head SHA. The sealed
manifest asset and its emit and verify verbs are removed.

**D3 — The releases API is unreachable from CI, by permission as well as by call.** No
packaging workflow calls any release verb, and no packaging job holds contents-write at
workflow or job level. Exactly one job in the repository creates a release: the
publication gate, creating the one real version release. The operator's locally-minted
claude evidence release is unchanged; it has no backing run, so it stays a release
download.

**D4 — The transport helper shrinks to its one live purpose.** With the drafts gone, the
seal, verify, download and garbage-collect surfaces have no callers. The module is
reduced to the publication leak sweep and renamed accordingly; the sweep itself is
unchanged and still fail-closed. The garbage-collect verb, which could delete releases,
is removed rather than left dormant.

**D5 — The conformance gate is inverted, and proven by mutation.** The gate previously
required a draft create per packaging workflow and forbade artifact actions. It now
forbids the releases API and contents-write in packaging workflows, asserts a single
release creator repository-wide, requires artifact actions pinned to a commit SHA, and
adds a per-workflow artifact-name disjointness check standing in for the retired
single-creator topology. Reintroducing a draft create, restoring the write grant, and
colliding two artifact names were each confirmed to red the corresponding gate.

**D6 — The evidence garbage-collection workflow is deleted.** It bounded a namespace
nothing fills any more.

## Rationale

The decision is not that the prior record was wrong; it was correct for the constraint it
faced, and it held in production exactly as designed. The decision is that its
justification expired. A workaround outlives its reason silently, and the cost of not
noticing is paid in a surface the operator sees every day.

Returning to artifacts wins on the merits independently of the ruling. It restores the
shape the prior record itself preferred; it deletes an entire class of failure (the
duplicate-draft race and the single-creator topology built to dodge it); and it makes the
provenance binding structural rather than reconstructed, which is strictly stronger than
a manifest that had to be checked for agreement. The one honest regression, artifact
expiry, is bounded, documented, and does not touch the soak candidate that most needed
durability.

A note on how this record came to be written, because it bears on how the next one
should be: the initial assessment of the operator's report was that the drafts were
non-public and therefore not urgent. That was true and beside the point. The objection
was to machine scaffolding occupying a human surface, which does not require a
confidentiality breach to be worth fixing, and the expired premise underneath it was
discoverable from the prior record's own problem statement without any prompting. The
premise of an accepted decision should be re-checked when the world it names changes,
not when someone complains about a symptom.

## Consequences

- CI cannot create a release. The capability is removed at the call site and at the
  permission, and pinned by a gate proven to bite.
- Provenance improves: the run-to-payload binding is structural instead of asserted, and
  the identity check now precedes any download rather than accompanying it.
- Roughly 1,700 lines go: a garbage-collection workflow, a transport helper and its
  suite, four create-or-seal job definitions, and the manifest format.
- The promotion window becomes bounded at 90 days from the smoke run. This is the one
  capability lost, it fails with a download error rather than an expiry message, and the
  runbook now states it.
- Standing release-asset storage drops to whatever published versions carry; the
  keep-window policy and its dispatch-only GC are no longer needed.
- The deferred attestation ruling has met its stated trigger and is now actionable.
- Reverting the repository to private would reinstate the original constraint. That event
  must reopen this record; the pipeline would otherwise begin failing uploads exactly as
  it did before the prior decision.

## Amendment 2026-08-08 — D4's no-callers premise was false for the download surface

D4 states that with the drafts gone "the seal, verify, download and garbage-collect
surfaces have no callers". That is correct for three of its four surfaces and wrong for
the fourth. It is contradicted by D3 in this same record, which preserves the operator's
locally-minted evidence release unchanged because it has no backing run, and therefore
"stays a release download". A release download needs a release-download transport, so
the download surface had a caller at the moment this record was accepted.

Three modules import it and did so throughout: `dev/release/release_candidate.py`,
`dev/release/seal_candidate.py` and `dev/release/soak_promoter.py`. Between them they
take `download_release_assets`, `list_releases`, `resolve_gh`, `run_gh_with_retry`,
`EvidenceLane` and `evidence_tag`.

D4 is not rewritten. It was true when written for the surfaces it was reasoning about,
and its ruling on those stands: seal, verify, manifest emission and garbage collection
are retired, and the garbage collector is removed rather than left dormant because it
could delete releases. Only the download surface is exempted from the no-callers claim.

The consequence recorded here is not the error itself but what the error did. A reader
executing D4 literally deletes what D3 requires, and that is what happened: the module
was deleted, the workflow was repointed and the rename landed, while the three consumers
were never swept. The developer tree then failed collection outright, which blocked
every test in the release package rather than only the deleted module's own — and that
in turn masked seven unrelated failures in the publish-workflow gate for as long as the
break stood.

The remedy keeps both decisions true. The surviving transport moved to
`dev/release/_asset_transport.py`, beside the three consumers that need it and out of
the packaging package, whose remaining evidence concern is the publication leak sweep.
The retired surfaces stayed deleted, and a property gate now refuses any developer-harness
module that can delete a release, so D4's ruling on the collector is enforced by
construction rather than by the absence of one file.

Two general points are worth carrying out of this record. A ruling whose stated premise
is contradicted by a sibling decision in the same document does not bind on the
contradicted point, and the contradiction is only visible to a reader holding both
decisions at once. And a decision that rules on code is not self-executing: the rows
implementing it must be opened in the same action as the decision, or the record reads
as in force while the tree carries the shape it rejected.
