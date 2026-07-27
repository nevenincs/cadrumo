---
tags:
  - '#adr'
  - '#publication-lane-consolidation'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - '[[2026-07-27-canonical-release-pipeline-adr]]'
  - '[[2026-07-27-canonical-release-pipeline-research]]'
  - '[[2026-07-27-pipeline-config-topology-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-20-release-asset-transport-adr]]'
  - '[[2026-07-25-account-distribution-standard-adr]]'
---

# `publication-lane-consolidation` adr: `one publication authority per destination: 0.2.1 is abandoned and the first complete release takes a fresh version, the bump precedes the build, the guard checks every destination, and the irreversible act goes last` | (**status:** `proposed`)

## Problem Statement

The operator asked for a managed, singular pipeline and instead holds a
doubled publication leg with a forked version identity — the half of the
pipeline where a mistake cannot be undone. Measured 2026-07-27 (full
measurements in `2026-07-27-canonical-release-pipeline-research`): a
non-draft GitHub release `v0.2.1` was published 2026-07-21T12:46:11Z from
commit `9235e8ca` (smoke run `29810372590`; linux cohort 347,206,213 bytes),
while the sealed candidate cohort everyone treats as the release candidate
(run `30216592706`, commit `490f625c`; 392,874,897 bytes) is a different
build stamped with the same version. Root cause: `pyproject.toml` and
`.release-please-manifest.json` still pin `0.2.1`; release-please is
configured but wired only to a manual `justfile` target that runs
`release-pr --dry-run`, so nothing advanced the version after the release and
every later build re-stamps it.

The armed failure is concrete. The promotion guard checks one destination
(`promote_python_cohort --check-pypi-only`), and PyPI is precisely the one
destination that does not yet own 0.2.1. The promote job then orders PyPI
upload (irreversible) before the release creation step. Dispatching the
sealed cohort today would pass Gates 1 and 2, irreversibly upload new bytes
to PyPI as 0.2.1, then fail on the already-existing release; the docs
payload, Scoop, Homebrew, and marketplace steps never run. PyPI would
permanently hold bytes matching no GitHub release, and no channel would be
served — the partial, non-atomic publication that immutable-cohort promotion
(`2026-07-15-distribution-installation-readiness-adr`) exists to prevent.

A second PyPI lane compounds it: `pypi-upload.yml` (retirement charter, issue
#618) is gated on the same `CADRUMO_PUBLISH_ENABLED` variable as the sole
publication authority, and its `release_tag` input is a free string — so one
flip arms two authorities that would ship different bytes under one version.

The frame for all of it is fixed by an operator ruling of 2026-07-27,
verified first-hand the same day: no complete release has ever shipped to any
destination. PyPI `cadrumo` does not exist (HTTP 404); the two data
companions carry only `0.0.0` name reservations; the two GitHub releases
(`v0.2.0` of 2026-07-04, `v0.2.1` of 2026-07-21) are both partial,
GitHub-only artefacts; the tap and bucket hold `.gitkeep`; the marketplace
holds the stale old-identity plugin. The operator's ruling, verbatim: "0.2.1
is absolutely not something we should keep. we have never released a complete
package yet." Version 0.2.1 is abandoned, not delivered — there is no owed
delivery, no released data to protect, no user holding a complete install,
and no compatibility obligation (the compatibility regime is pre-release,
correctly). The pipeline is shaped for a first complete publication, not for
recovery.

This record rules five couplings: the disposition of the abandoned version
and its partial artefacts, who owns version advancement, what the promotion
guard must check, whether two lanes may share one arming variable, and the
ordering of the irreversible act. Its delivery
sibling is `2026-07-27-canonical-release-pipeline-adr`; together with
`2026-07-27-pipeline-config-topology-adr` they are the canonical pipeline.
Nothing here arms anything: publication remains HELD, and every ruling is a
design obligation on the un-armed pipeline.

## Considerations

- PyPI is immutable: a version, once uploaded, can be yanked but never
  replaced or reused. The version-identity ruling is decided exactly once.
- The partial `v0.2.1` release is public and non-draft, so its bytes are
  technically obtainable — but it was never advertised, never completed, and
  never reached any registry; under the operator premise it is an artefact,
  not a delivery. The readiness ADR's principle still governs the mechanics:
  bytes are never replaced under an existing version, and a version stamped
  onto bytes is never re-stamped — which now argues for a fresh version, not
  for honoring the partial one.
- `releases/latest` resolves to the partial `v0.2.1` today, so the repository
  presents a "latest release" that no one can completely install — a standing
  implicit availability claim of exactly the kind the readiness ADR forbids
  documentation to make.
- The `v0.2.1-rc.1` tag exists only in the local worktree; the remote carries
  only `v0.2.0` and `v0.2.1` (verified via the matching-refs API,
  2026-07-27). Its disposition is a local cleanup, not an outward act.
- The version string is baked into every cohort artifact's filename and
  metadata, so a sealed cohort cannot be relabelled; re-versioning means
  re-sealing a fresh cohort.
- The account standard (`2026-07-25-account-distribution-standard-adr`) makes
  the release-please manifest the single version source and deliberately
  leaves the bump trigger a per-product safety choice; cadrumo's governing
  release record mandates local-only bumping. Neither is overturned here —
  what is missing is not authority but execution: the bump is a dry-run
  target, not a step anything requires.
- The retiring lane's charter confines it to already-published tagged
  releases and names its deletion trigger (first Gate 3 PyPI success, issue
  #618), but the confinement is prose: the `release_tag` input accepts any
  string, defaulting to `v0.2.1`. The charter also forbids modifying its gate
  or hardening steps.
- The retiring lane's charter exists "solely to deliver Python distributions
  of already-published v* releases" — concretely the owed v0.2.1 fast-follow.
  Under the abandonment ruling that purpose is void: there is no owed
  delivery, so the charter's deletion trigger (first Gate 3 success) guards a
  sequencing problem that no longer exists.
- The transport ADR (`2026-07-20-release-asset-transport-adr`) already
  adopted the transactional principle — the one user-visible release is
  created at the end from verified inputs — and the promote job's internal
  order contradicts it at the margin: the sole irreversible destination write
  happens first and every reversible one after.
- The delivery sibling's rationale establishes the immutability asymmetry
  (registry bytes cannot be retried; everything else can) and is cited here,
  not restated.
- The managed channels (Scoop, Homebrew, marketplace) acquire from GitHub
  release assets, not from PyPI, so no channel's function depends on the PyPI
  leg having completed.
- The dual-authority configuration was already rejected once on principle:
  the readiness ADR's considered option 4 (allow local and CI publication
  authorities) was rejected because divergent paths cannot prove which
  authority published which bytes. Today's two-lane state is that option,
  armed by a single variable.

## Considered options

**Version disposition (ruling P1).**

- Abandon 0.2.1 entirely; the first complete release takes a fresh version
  and the partial artefacts are deleted as never-delivered. **Chosen** (the
  abandonment premise is the operator's fixed ruling; the disposition within
  it is this record's).
- Honor the partial release as v0.2.1's owner and deliver its bytes to PyPI
  via the retiring lane (this record's own first draft). Overturned by the
  operator premise: it treated the partial artefact as a delivered claim to
  honor, and nothing complete has ever shipped — there is no claim, no owed
  delivery, and no user to protect, so the recovery framing solved a problem
  that does not exist at the cost of shipping a version the operator has
  disowned.
- The sealed cohort claims v0.2.1 (newer, fully evidenced). Rejected: even
  under abandonment, publishing anything as 0.2.1 re-animates a disowned
  version and forks it against the still-obtainable partial bytes — PyPI has
  no un-publish, so the fork would be permanent.
- Keep the partial releases as historical artefacts. Rejected for the
  releases themselves: `releases/latest` would keep resolving to a partial
  artefact — a standing implicit availability claim — and the never-delivered
  history is fully reconstructible from git history and the vault without
  keeping a misleading public surface. The version NUMBERS stay burned either
  way (P3's monotonic floor), so keeping the pages buys nothing.

**Version advancement ownership (ruling P2).**

- A CI release-please workflow. Rejected: overturns the governing local-only
  bump mandate the account standard explicitly preserved, for no mechanical
  gain.
- Keep the manual dry-run target as-is. Rejected: it is what allowed two
  builds to share one version — a dry run advances nothing and requires
  nothing.
- Local release-please execution as the mandatory first runbook step of a
  release cycle, backed by a seal-time identity refusal. **Chosen.**

**Promotion guard scope (ruling P3).**

- Keep the PyPI-only guard and add a release-existence check inline in the
  workflow. Rejected: scatters the identity decision across shell steps; the
  guard must be one tested authority, or destinations drift out of its view
  again.
- One all-destination version-identity guard, run at seal time and at Gate 2.
  **Chosen.**

**Two lanes under one variable (ruling P4).**

- A second arming variable for the retiring lane. Rejected: configuration
  churn for a lane whose charter is deletion, and two variables still permit
  the same double-authority when both are set.
- Leave the shared variable with the lane unpinned. Rejected: one flip arms
  two authorities that can ship different bytes for overlapping versions —
  the readiness ADR's rejected option 4, armed.
- Version-pin the retiring lane and sequence its deletion behind the first
  Gate 3 success (this record's own first draft). Obsolete: the pin and the
  sequencing existed to protect an owed delivery the abandonment ruling
  voids.
- Delete the lane outright — workflow, conformance test, and the three
  Trusted Publishing registrations (#618), with no sequencing precondition.
  **Chosen.**

**Atomicity across the irreversible step (ruling P5).**

- Keep the current order (PyPI first) and add preflight checks. Rejected: no
  enumeration of checks makes an irreversible-first ordering safe against the
  failure it did not foresee; the residue of any surprise is an orphaned
  immutable upload.
- All-destination preflight before any write, reversible destinations first,
  the sole irreversible write last, every step idempotent. **Chosen.**

## Constraints

- The abandonment premise is the operator's ruling of 2026-07-27 and is not
  re-litigated here; this record rules the disposition inside it. Deleting
  published releases and remote tags is an outward-facing act and is the
  operator's to execute either way (OP-5); this record rules what should
  happen.
- The retiring lane's charter forbids modifying its gate or hardening steps.
  Deletion does not modify it — it executes the charter's own end state; the
  trigger condition collapses because the charter's premise (an owed
  delivery) is void, and issue #618 already names the full deletion set.
- The sealed cohort `30216592706` is a superseded candidate, not a write-off
  against a delivered release: its work re-ships re-versioned in a fresh
  cohort, and the evidence rows are re-earned on the new digests — the
  ordinary cost of any re-cut, not a loss.
- Cohort sha256 digests and byte counts are the dispatching coordinator's
  same-day measurements, attributed in the research document, not re-derived
  here. The version pins, release-please wiring, publish step order,
  PyPI-only guard scope, the published release, and the retiring lane's
  charter and free `release_tag` input were all verified first-hand on
  2026-07-27.
- Depends on the readiness, transport, and account-standard ADRs remaining in
  force; this record tightens their execution and contradicts none of them.

## Implementation

**P1 — 0.2.1 is abandoned; the first complete release is a first, at a fresh
version, and the partial artefacts go.** Per the operator's ruling, 0.2.1 is
abandoned, not delivered: nothing is owed to it, nothing recovers it, and
nothing ever publishes under it. The version-baked-into-bytes reasoning
survives with its sign flipped — the sealed cohort `30216592706` cannot be
relabelled, so it is a superseded candidate, and the first complete release
ships a freshly sealed cohort at a fresh version. That version is not
hand-picked: release-please computes it over the conventional-commit history
from the manifest floor `0.2.1` (`bump-minor-pre-major: true`; expected
minor, `0.3.0`), and a version number ever stamped on any artefact — shipped,
partial, or abandoned — is never reused, which P3's monotonic floor enforces
mechanically. Disposition of the partial artefacts: the `v0.2.0` and
`v0.2.1` releases and their remote tags are deleted as never-delivered
(operator-executed, OP-5), because `releases/latest` currently resolves to a
partial artefact — a standing implicit availability claim the readiness ADR
forbids — and their history stays reconstructible from git and the vault; the
local-only `v0.2.1-rc.1` tag is deleted as local cleanup in the implementing
plan. The evidence drafts covering those runs are untouched — they are
governed by the transport ADR's GC policy, not by this disposition. The two
data companions' `0.0.0` PyPI name reservations need nothing BEFORE the
first complete release — holding the names is their one job — and are yanked
(never deleted) AFTER it lands, as a post-publication verification step:
yanking stops any resolver from being served a stub once a real version
exists, while explicit pins keep resolving for forensics. The root project
needs no reservation disposition at all — it does not exist on the registry,
which is exactly what the pending-publisher registration (the topology
record's OP-7) handles.

**P2 — Version advancement: release-please-owned, locally executed, made
real.** The release-please manifest stays the single version source (account
standard) and the bump stays a local operator act (the governing local-only
mandate, not overturned). What changes is that it stops being a dry run: the
version-bump commit (manifest, `pyproject.toml`, changelog, the declared
extra-file) is the mandatory FIRST step of every release cycle in the
runbook, landed before any candidate cohort is built — and the cohort seal
step refuses to seal a version any destination already owns (the P3 guard
applied early, where refusal is cheap), so a collision cannot be minted again
even when the runbook is skipped. A dry-run target is not a pipeline; a
seal-time refusal is.

**P3 — The version-identity invariant, checked everywhere it can be
violated.** The invariant: a cohort is not promotable under a version that
any published release, any tag, or any package index already owns. The guard
stops being PyPI-only and verifies, before ANY destination write: the three
PyPI projects; the `v<version>` tag and release namespace, draft or published
— the check whose absence arms today's stranding; the tap and bucket pointer
manifests (the monotonic backward-bump guard the account standard already
mandates); and the marketplace preflight owned by the delivery sibling. The
guard additionally enforces the monotonic floor: the candidate version must
be strictly greater than the release-please manifest's recorded version, so
deleting a never-delivered release (P1) cannot resurrect its number — the
manifest, not the destination's live state, is what burns a version. One
tested authority implements it, and it runs twice: cheaply at cohort seal
(P2) and authoritatively in Gate 2, so a stale candidate and a fresh
collision are both refused before anything irreversible happens.

**P4 — One publication authority per destination; the second lane is deleted
outright.** The end-state is exactly one publication authority — Gate 3 of
`publish-release.yml` — and the abandonment ruling makes it reachable
immediately. `pypi-upload.yml` existed solely to deliver the owed v0.2.1;
that purpose is void, so the lane needs no version pin, no arming-variable
separation, and no sequencing behind a first Gate 3 success: issue #618
executes now — delete the workflow, its conformance test, and the three
Trusted Publishing registrations with their environments (the repo-side
deletions ride the implementing plan; the registry-side and environment
deletions are the operator's, OP-6). The two-lanes-under-one-variable hazard
disappears by deletion rather than by scope narrowing, which is strictly
stronger: a deleted lane cannot be mis-dispatched. This record's first draft
ruled pin-then-sequence; the abandonment collapses it, and the collapse is
recorded rather than silently rewritten.

**P5 — Promotion atomicity: reversible writes first, the irreversible act
last.** The promote job's internal order inverts around irreversibility:
every reversible destination write — the GitHub release with its assets and
docs payload, the Scoop push, the Homebrew push, the marketplace push, all
git-revertible or deletable — lands before the sole irreversible one, and the
PyPI upload moves from first to last. What must be proven before the first
irreversible act is then simply everything: the P3 all-destination guard has
passed, Gate 2's evidence and cohort binding have passed, and every
reversible destination write has already succeeded. Any failure before PyPI
unwinds completely; a failure at PyPI leaves every managed channel serving
release assets — none of which depend on the PyPI leg — and is retryable by
re-dispatch, every step being idempotent against its own prior success. The
immutability-asymmetry reasoning grounding this ordering is the delivery
sibling's (`2026-07-27-canonical-release-pipeline-adr`, Rationale) and is
cited, not restated; this record extends it from the docs consequence to the
promotion's internal order, completing the transactional principle the
transport ADR adopted.

## Rationale

On version disposition, the operator premise does the heavy lifting and the
reversibility asymmetry keeps its force in a new role. Nothing complete ever
shipped, so there is no delivered claim to honor and no user to protect —
which converts this record's first-draft recovery framing (honor the partial
release, deliver its bytes) into a solution without a problem. What survives
of the original reasoning is exactly the part that still binds: a version is
baked into its bytes and can never be re-stamped, so the sealed cohort
re-ships fresh rather than relabelled, and 0.2.1 stays burned forever even
though nothing honors it. The abandonment is also strictly the cheaper
branch: the 392 MB candidate was always going to be superseded by whatever
ships next; under abandonment that supersession is ordinary, not a write-off
against a delivered release. Deleting the partial releases follows from the
same honesty rule that governs the docs floor — a public "latest release"
that cannot be completely installed is an availability claim the project is
not entitled to make.

Every subsidiary ruling makes that asymmetry structural rather than
remembered. The bump becomes a precondition (P2) so two builds cannot share a
version by omission; the guard checks every destination (P3) because today's
collision lives precisely in the one destination the old guard skips, and a
guard that enumerates destinations by hand will skip another one next time;
the ordering puts the irreversible write last (P5) because a preflight can
never enumerate every failure, and only ordering makes the unforeseen ones
unwindable; and the second lane is pinned then deleted (P4) because two
authorities over one destination is the configuration the readiness ADR
already rejected — the collision merely showed what it looks like when
armed, and deletion removes it more thoroughly than any confinement could.
The first complete publication also lands on empty destinations everywhere,
which is when reversible-first ordering is cheapest to adopt: there is no
installed base against which a partial state is observable, so the ordering
can be proven on the easiest case it will ever have.

## Consequences

- The version fork dies unshipped: 0.2.1 is abandoned, nothing ever
  publishes under it, the sealed cohort is superseded rather than written
  off, and the first complete release carries one fresh identity to every
  destination. The repository stops presenting a partial artefact as its
  latest release.
- Publication-leg consolidation becomes structural: one version authority
  with a seal-time refusal, one publication authority once #618 executes, and
  an ordering under which the pipeline's only irreversible act happens after
  everything it must agree with already exists.
- The re-versioned release re-earns its evidence rows on fresh digests —
  release latency increases by one full evidence cycle, accepted as the cost
  of digest-bound proof.
- Until the implementing plan lands, the collision remains armed: nothing in
  this record changes the live workflows, so the guard blind spot and the
  irreversible-first ordering persist in the meantime. The record's teeth
  arrive with its plan; naming that gap is what keeps the interim honest.
- Operator decision points owned by this record: **OP-5** ratify the P1
  disposition and execute its outward-facing half — delete the `v0.2.0` and
  `v0.2.1` releases and their remote tags as never-delivered (the abandonment
  itself is already the operator's ruling; the deletion is the operator's
  act), and after the first complete release lands, yank the two companions'
  `0.0.0` name-reservation uploads; **OP-6** execute issue #618 now, with no sequencing precondition —
  approve the repo-side deletion of `pypi-upload.yml` and its conformance
  test, and delete the three Trusted Publishing registrations and their
  GitHub environments.
