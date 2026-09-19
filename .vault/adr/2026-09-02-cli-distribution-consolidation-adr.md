---
tags:
  - '#adr'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:f1ec7ba45cd5f4fda67be670dc3ab30fcd05befd023647d3814631d204390877'
related:
  - "[[2026-07-25-account-distribution-standard-adr]]"
  - "[[2026-07-27-canonical-release-pipeline-adr]]"
  - "[[2026-08-02-release-pipeline-full-automation-adr]]"
  - "[[2026-07-19-post-release-distribution-adr]]"
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
  - "[[2026-07-03-claude-ecosystem-packaging-adr]]"
  - "[[2026-07-16-distribution-harness-identity-adr]]"
  - "[[2026-06-28-product-packaging-adr]]"
  - "[[2026-07-25-standalone-executable-tier-adr]]"
  - "[[2026-09-02-cli-distribution-consolidation-research]]"
---
# `cli-distribution-consolidation` adr: `cadrumo ships as one PyPI-first CLI distribution` | (**status:** `accepted`)

## Problem Statement

Cadrumo's packaging describes four products where there is one, and encodes the
project's own launch planning as data the build reads. The result has never
published a release, while two sibling products in the same account publish
routinely from a much smaller pipeline.

A decision is needed now because the remaining distribution work is blocked on which
shape it is building toward: twenty-six distribution features have accumulated
without converging, and each further increment of the current design adds surface to
something that has never shipped.

## Considerations

- Cadrumo is a command-line application. Its full-screen surface is a rendering mode
  of the same command graph, not a second application.
- PyPI is the language-native registry and the only channel where dependency
  resolution happens; every other channel installs what it serves.
- The account already operates a proven pure-Python release path, and cadrumo's own
  entry in the canonical fleet manifest already declares the target shape
  (`2026-09-02-cli-distribution-consolidation-research`).
- A codebase records what the software is, not the development conditions under which
  it was built. Launch-phase state, tier registers and incident narration are not
  software facts.
- The publication path must not depend on runner availability, which the fleet cannot
  guarantee.

## Considered options

**Adopt the account release path and collapse to one distribution.** Chosen. Replaces
bespoke orchestration with the sibling pair, merges the agent surface into the product
wheel, and reduces the channel set to the three that install the same artifact.

**Keep the bespoke orchestrator and fix it forward.** Rejected. The orchestrator's
failure modes are properties of its design - it blocks on runs it dispatched onto a
single-runner fleet - and repairing it preserves a second, unproven implementation of
something the account already runs.

**Split the agent harness into its own repository.** Rejected. It matches the stated
separation but diverges from the account convention, where the MCP server is a second
console script in the product wheel, and it keeps a second release cadence for a
component with one-way coupling and no independent consumers.

**Ship standalone executables alongside the wheel.** Rejected for now. That is a
`frozen-native` packaging decision, orthogonal to a pure-Python product's channels,
and the account's implementation of it lives in a separate workflow that this decision
does not need.

## Constraints

- Landing the release path opens a release pull request on the next push to the
  default branch, so it requires operator sign-off rather than incremental merging.
- A Trusted Publisher binding takes one of two forms, and which one is decided by the
  index rather than by preference: a name with no project behind it takes the pending
  form, which also reserves it, while a name the index already carries takes the
  ordinary project-level form. The primary name is held by a pending publisher; the two
  corpus distributions already exist and therefore still owe the project-level form. An
  upload of all three is refused until every one of them is bound.
- Three structural CI gates currently pass and would refuse the adopted path: the
  self-hosted runner requirement, the Actions-artifact prohibition, and the workflow
  filename pins. Each needs its invariant restated, not suppressed.
- A structural gate proves the shape of a workflow, never that it works. No workflow in
  the adopted path has executed, so every claim about it rests on local measurement
  until one run exists.
- Two versions are permanently burned and cannot be reminted.

## Implementation

The product becomes one wheel with two console scripts: the application, and the MCP
server that exposes it. The full-screen surface is reached through the application's
existing root option rather than a second script, and gains a headless self-test so an
installed artifact can be proven to start. The agent harness distribution dissolves
into the product wheel; the two host-extension channels are removed rather than
relocated, because the manual connection path they were replacing already exists and
is already documented.

Publication adopts the account pair: a release-please workflow on the default branch
that computes the version and dispatches, and a publish workflow that builds the three
distributions, proves them on each supported platform, and uploads to PyPI. Both run on
hosted runners. The self-hosted fleet keeps every lane that proves behaviour on a real
target platform. Install proof moves from nested containers to an isolated environment
holding only the artifact under test, which removes the daemon dependency that has kept
one target unproven.

The channel descriptor becomes a flat inventory of the three channels the product
publishes to, carrying identity, platform, install commands and the evidence rows each
owes. The tier rule, the availability states, the claim derivation and the pending-tier
register are removed, along with the sealed release record's field naming them. Target
roles and runner selectors are already owned by the canonical fleet manifest and are
not restated here.

Capability is demonstrated by compiling to the targets and running what comes out.
Every declared distribution and channel artifact builds from one command, each file is
checked against the index cap that governs it, and both console scripts are started from
the built wheel in an environment holding only the artifact under test. A gate that
parses a workflow, a descriptor that lists a channel, and a plan Step that is checked
are all statements of intent; the built artifact that runs is the evidence. Publication
is the natural end of that chain rather than a separate act.

The same standard decides what is deleted. A development or release module whose only
consumer is its own test has no target left to serve, and keeping it preserves the shape
of a path the product no longer takes. Reachability is measured from the workflows, the
recipe surface and production imports - never from a test, and never from a document
that itself describes a retired path.

## Rationale

The decisive fact is that the account already runs this exact shape for two products
of the same packaging class, and cadrumo's own entry in the canonical fleet manifest
already describes it (`2026-09-02-cli-distribution-consolidation-research`). Adopting
it is convergence on a proven path, not a new design.

Every other option preserves a second implementation of something the account has
already solved, and the current one has produced no release across the period in which
the siblings produced over a hundred.

The merge of the agent surface wins over a repository split on the same grounds: the
convention exists, it removes the component's leverage over the product's channel set
more completely than a split would, and it collapses the user's connection
configuration to a single command name.

## Consequences

The publication path stops depending on runner availability, and the product a user
installs stops advertising binaries and channels that do not resolve.

Removing the claim derivation removes the rule that an unclaimed channel does not block
a claimed one. Every channel in the inventory then owes its evidence rows, which makes
one currently-unproven target blocking; it is dropped from the inventory with its
technical reason recorded, and returns when the runner can serve it.

The three restated CI gates become narrower in one dimension and wider in another: the
runner requirement gains a workflow-level exemption for the release path, and the
artifact prohibition gains a positive assertion that nothing reads an artifact from
another run. Both are stricter where it matters and neither is suppressed.

The retired surfaces are large, and their tests retire with them. Work already invested
in the bespoke orchestration, the host-extension acquisition lanes and the launch-phase
descriptor is not carried forward. That is the cost of converging, and it is paid once.

Standalone executables and a community Windows package remain unbuilt. They stop being
declared as pending tiers in product data and become ordinary future work.
