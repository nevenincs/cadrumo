---
tags:
  - '#adr'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-08-23'
body_hash: 'sha256:64df373791f24202367db71c43cd58bca147e3a1d1fa8199e69ca08a5bd08a7c'
related:
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-19-post-release-distribution-adr]]'
  - '[[2026-07-20-release-asset-transport-adr]]'
  - '[[2026-07-25-account-distribution-standard-adr]]'
  - '[[2026-07-27-canonical-release-pipeline-research]]'
  - '[[2026-07-27-publication-lane-consolidation-adr]]'
  - '[[2026-07-27-pipeline-config-topology-adr]]'
---
# `canonical-release-pipeline` adr: `the docs and landing delivery leg of the canonical release pipeline: AWS stays for cadrumo.neve.md, docs publish is an automated release consequence, and the stale marketplace identity retires by declared supersession` | (**status:** `accepted`)

## Problem Statement

The publication leg of the release pipeline is decided â€” sealed-cohort promotion
(`2026-07-15-distribution-installation-readiness-adr`), release-asset transport
(`2026-07-20-release-asset-transport-adr`), the account channel standard
(`2026-07-25-account-distribution-standard-adr`) â€” but its delivery leg is not:
the documentation site, the landing page, and the marketplace's prior contents
sit outside every accepted record, and they are drifting. Measured 2026-07-27:
`https://cadrumo.neve.md/` and `/docs/` serve HTTP 200 from an `AmazonS3`-backed
CloudFront distribution, the docs `Last-Modified` is 2026-07-12 â€” fifteen days
stale â€” and no CI invokes any deploy tooling (the sole reference under
`.github/` is a comment in `publish-release.yml`). The deploy surface is
deliberately local-human: `dev/deploy/docs_static_site.py` and
`dev/deploy/frontend_static_site.py` behind `just docs-deploy` /
`frontend-deploy` with literal `--confirm` phrases, and
`_require_human_publish_environment` refuses to run under `CI` or
`GITHUB_ACTIONS`.

Two contradictions force this record now. First, the operator's
2026-06-25 hosting decision (recorded in the private planning vault, read
verbatim 2026-07-27; source identifiers withheld by the repository boundary)
chose Cloudflare Pages/Workers for the account's hosting, delegated `neve.md`
DNS to Cloudflare, and rejected AWS "for core" because "egress charges +
complexity make cost unpredictable" â€” yet the shipped docs stack is exactly
S3 + CloudFront, and the note never mentions `cadrumo.neve.md`. Nobody recorded
the divergence. Second, the first publication will write into
`nevenincs/neve-marketplace`, which still carries a 2026-07-04 `plugins/aeat`
subtree under the retired product identity, referencing an `aeat-cli 0.1.1`
distribution the sealed cohort does not publish â€” and the publish tooling's
sibling-protection design deliberately preserves every path a cohort does not
declare, so the stale identity survives every future publication untouched.

A third contradiction â€” the version identity of v0.2.1 is already forked
between a published release and the sealed candidate cohort, and a second
PyPI lane shares the one arming variable â€” was measured the same day and is
ruled in the sibling record `2026-07-27-publication-lane-consolidation-adr`;
the measurements live in `2026-07-27-canonical-release-pipeline-research`.

This record rules the seven delivery couplings: hosting, docs trigger and
ordering, the `download-latest.json` handshake, deploy credentials, localized
roots, the stale marketplace identity, and the docs/landing coupling. It
changes no publication gate and arms nothing; publication remains HELD per
`2026-07-19-post-release-distribution-adr`. The operator's stated end-state
binds this record, its publication-leg sibling, and the configuration-topology
record `2026-07-27-pipeline-config-topology-adr` together: one publication
authority, one version authority, one delivery runbook â€” a single managed
pipeline.

## Considerations

- The 2026-06-25 note predates the `cadrumo.neve.md` subdomain entirely and
  scopes its AWS rejection to "core" (the account's own front, not product
  subdomains). The
  apex and DNS are on Cloudflare exactly as it decided (zone active, universal
  SSL); only the product subdomain diverged.
- Cost grounding for the incumbent: CloudFront's Free plan includes 100 GB per
  month of transfer and one million requests (`aws.amazon.com/cloudfront/pricing`,
  read 2026-07-27); both site publishers verify the S3 origin refuses direct
  access (HTTP 403), so egress rides the CDN alone. A static docs-and-landing
  site for a niche tax CLI sits orders of magnitude below that allowance.
- Cost grounding for the alternative: Cloudflare Pages Free caps a deployment
  at 20,000 files and 25 MiB per file
  (`developers.cloudflare.com/pages/platform/limits`, read 2026-07-27). The
  site is four docs roots (English autodoc plus `es`/`ca`/`hu` user-scope),
  each carrying its own Pagefind index; a compiled Pagefind index for this
  corpus previously measured ~16k files (the committed-index finding behind
  `2026-06-15-docs-terminology-search-adr`). The full site therefore
  plausibly exceeds the Free cap â€” bounded, not freshly measured (no complete
  build existed in the worktree; the local build directory was a 75-file
  stub) â€” which prices "free" migration as a paid plan or an R2-plus-Worker
  re-architecture.
- The AWS tooling is complete, tested (`dev/deploy/tests/`), and
  self-verifying: strict multi-root build, artifact/sitemap/Pagefind
  validation, CloudFront alias pinning, a protected `docs/*` prefix on the
  root sync with a dry-run refusal, and 200/404/403/308 endpoint checks
  including the legacy-URL redirect.
- The release-to-docs handshake already exists and is one-directional:
  `publish-release.yml` emits `download-latest.json` â€” a read-only projection
  of the sealed cohort manifest plus the release's asset URLs, leak-swept like
  every attached asset â€” onto the release; `_refresh_download_latest` pulls it
  version-agnostically from the latest-release asset URL at the next docs
  publish, schema-checks it, and degrades to the offline Tier-1 channel table
  on any failure. It never raises.
- The publication authority is a manually dispatched, human-approved CI
  workflow with OIDC and no stored credentials
  (`2026-07-15-distribution-installation-readiness-adr`); the docs authority is
  a local human session that structurally refuses CI. Inverting the handshake
  must reconcile these two authorities, not merely add a job.
- Actions spend is pinned to zero and evidence transport already moved off
  Actions storage for that reason (`2026-07-20-release-asset-transport-adr`);
  docs automation adding hosted minutes or long-lived cloud secrets cuts
  against both standing choices.
- `dev/packaging/marketplace_publish.py` replaces only the plugin subtrees the
  cohort declares, keeps every other path and index entry (a sibling plugin, a
  README, a LICENSE), refuses name takeovers across `published_by` owners, and
  treats an entry with no recorded publisher as claimable. The cohort publishes
  under the `cadrumo` identity, so it will never touch the stale `aeat` entry.
- The localized roots build sequentially after the English root; every build
  and validation completes before any byte uploads, and the upload is a single
  whole-tree delete-sync â€” partial-language publication has no natural
  mechanism in the shipped design.
- The landing publisher shares the docs bucket and distribution, excludes
  `docs/*` from its sync, and asserts `/docs/` still serves 200 after its own
  publish â€” a destruction tripwire on the shared bucket, not a build
  dependency.
- `aeat` remains the product's one human CLI executable per the accepted
  product-authority naming record; what retires is the marketplace plugin
  identity of that name, not the command.

- The live marketplace `aeat` entry carries no `published_by` â€” it predates
  ownership tracking, so under the merge tool's own rules it is claimable by
  ANY product today. A supersession mechanism bounded by the same ownership
  rule therefore adds no authority over siblings that the claim rule does not
  already grant; it adds only a remove verb with identical bounds.
- The in-tree cohort marketplace manifest already carries the flipped
  account-level metadata (owner `CADRUMO tax assistant project`, a bilingual
  description naming Cadrumo), and the merge takes account metadata from the
  cohort â€” so the metadata flip mechanically rides whichever publication
  first lands, whatever is ruled about the plugin entry.

## Considered options

**Hosting (ruling 1).**

- Migrate docs and landing to Cloudflare Pages, honouring the 2026-06-25
  decision. Rejected: discards a shipped, tested, live stack for zero measured
  savings, and the destination is not free at this site's shape (20k-file Free
  cap vs. four Pagefind-indexed roots; paid plan or R2+Worker re-architecture).
- Formally split: apex and DNS stay Cloudflare as decided; `cadrumo.neve.md`
  stays on the AWS stack, recorded as a scoped supersession of the note's AWS
  rejection. **Chosen.**
- Move the apex to AWS for single-vendor symmetry. Rejected outright: the apex
  is governed by the note, works, and costs nothing.

**Docs trigger (ruling 2).**

- Publish docs on every merge to main. Rejected: arms a continuous
  outward-facing publish under a deliberately un-armed pipeline and documents
  unreleased surface.
- Docs publication as a release gate (blocks `publish-release.yml`). Rejected:
  couples an immutable registry upload to a rebuildable site build; a Sphinx
  failure would strand a half-published release.
- Docs publication as a release consequence â€” procedural now, automated
  (a release-triggered downstream workflow) as the target. **Chosen.**

**Handshake (ruling 3).**

- Keep pull-at-next-publish (latest-release asset into `docs/_static`).
  **Chosen.**
- Invert: the release workflow drives the docs publish. Rejected; failure mode
  named under Implementation.

**Credentials (ruling 4).**

- Stored AWS keys in Actions secrets. Rejected: a long-lived credential,
  against the account's no-stored-credential posture.
- Keep the deploy authority human-only indefinitely (this record's first
  draft). Overturned by the operator's 2026-07-27 directive that automated
  docs publication and audit updates be a viable path.
- GitHub OIDC federation into a least-privilege IAM role as the design
  target, with the human session as the interim authority. **Chosen.**

**Localized roots (ruling 5).**

- All-or-nothing: every language on every run, any failure refuses the whole
  publish. **Chosen** (the shipped semantics, now ratified).
- Per-language partial publish. Rejected: asymmetric truth across roots.

**Stale marketplace identity (ruling 6).**

- Leave it. Rejected: a live install path to a distribution the pipeline does
  not publish, and two product identities live at once.
- Bare one-time operator hand-removal (this record's own first draft).
  Rejected as the mechanism: unrepeatable, unauditable, and memory-less â€” the
  tool retains no knowledge of the retirement, so nothing refuses a later
  resurrection, and the publisher-less name stays claimable by anyone.
  Retained only as an acceptable bootstrap the declared mechanism then
  verifies.
- A tool-side delete list (configuration in the publisher, not the cohort).
  Rejected: standing delete authority decoupled from any release â€” the
  original sibling-deletion incident is exactly why standing authority is the
  hazard.
- Weaken the guard to permit same-account deletions generally. Rejected: the
  guard's founding incident (a wholesale tree replacement deleted every
  sibling) recurs.
- Declared supersession in the cohort manifest, executed by the merge tool
  under the unchanged ownership rule. **Chosen.**

**Docs/landing coupling (ruling 7).**

- Force-paired deploys. Rejected: neither needs the other's rebuild, and the
  pairing would double every publish for no integrity gain.
- Independent verbs with a stated bootstrap order. **Chosen.**

## Constraints

- Nothing here arms anything. Publication remains operator-HELD
  (`2026-07-19-post-release-distribution-adr`); `CADRUMO_PUBLISH_ENABLED` is
  unset and the `release` environment currently carries no protection rules â€”
  the latter is a standing operator item outside this record's scope.
- The hosting ruling leans on the CloudFront Free-plan allowance as read on
  2026-07-27; AWS has moved CloudFront to plan-based pricing, so the operator's
  actual plan and bill are the ground truth this ruling defers to (decision
  point OP-1 below).
- The Pagefind file-count comparison is bounded, not measured: no fresh full
  build existed to inventory. A future migration study starts with a real
  build-output count.
- The operator's private planning record of 2026-06-25 is the latest recorded
  intent but not necessarily the current one, and may not have been maintained
  since. The scoped supersession therefore stands as proposed until ratified
  (OP-2).
- The marketplace removal is a write to a public repository this pipeline does
  not own from this session; it is operator-executed (OP-4).
- Depends on the accepted readiness, transport, and account-standard ADRs
  remaining in force; this record changes none of their gates and contradicts
  none of them. The one accepted decision it supersedes â€” scoped to one
  subdomain â€” is external to the vault (the 2026-06-25 hosting note), and the
  supersession is stated explicitly here because that note cannot carry a
  status stamp of its own.

- The declared-supersession mechanism of R6 does not exist yet; it is a small,
  testable extension of the merge tool and must land before the first
  publication for the preflight to have teeth.

## Implementation

**R1 â€” Hosting: formal split, scoped supersession.** `cadrumo.neve.md` (docs
and landing) stays on the shipped S3 + CloudFront stack (`cadrumo-docs`,
us-east-1 ACM and stack region); the apex `neve.md` and all DNS stay on
Cloudflare per the 2026-06-25 decision. This supersedes that decision's AWS
rejection for this one subdomain, and says so plainly: the cost objection no
longer binds at docs scale â€” the origin is private and verified 403, egress
rides CloudFront's Free-plan 100 GB/month allowance, and storage for a static
site is cents â€” while the "free" alternative carries a real cost (Pages
Free-plan 20,000-file cap against four Pagefind-indexed roots, hence a paid
plan or an R2+Worker re-architecture). The divergence the builders never
recorded is hereby recorded. If the operator overturns at OP-2, migration is
tractable by design â€” both publishers are transport-thin wrappers around a
static build tree â€” but it is its own future record, not a silent drift back.

**R2 â€” Build, publish, and gates: an automated consequence, never a gate.**
Docs publication is a release CONSEQUENCE: no docs step blocks or gates
`publish-release.yml`, ever. The target mechanism â€” per the operator's
2026-07-27 directive that automated docs publication and audit updates be a
viable path â€” is a dedicated docs-publish workflow, downstream of and
separate from the publication workflow, triggered when a release is published
(and operator-dispatchable), building from the release's source commit on the
self-hosted fleet and publishing through the R4 role. Its failure alerts
loudly and never blocks, unwinds, or strands the release â€” the consequence
direction is one-way. Until the operator creates the role and environment
(OP-3), the interim bound is procedural: the release runbook carries a
required same-session `just docs-deploy` from the released source commit, and
a release is not recorded distribution-complete until docs have published, by
workflow or by hand. Merging to main still publishes nothing outward (docs
stay CI-built and gate-checked, unpublished); ad-hoc human publishes from
main remain possible and change no availability claim, because the download
payload remains whatever the latest release attached. The ordering invariant
is unchanged in both directions: the download page can never advertise an
unpublished release structurally (its payload is pulled from the latest
published release, schema-checked, and floored by the offline Tier-1 channel
table), and a completed release cannot stay indefinitely stale â€” mechanically
once the consequence workflow lands, procedurally until then.

**R3 â€” The `download-latest.json` handshake: keep the pull model; automation
changes the trigger, not the flow.** The release emits; the docs publish
pulls, version-agnostically, at its next run â€” and under R2's target state
that next run is the automatic consequence workflow, so the pull happens
minutes after publication instead of at the next human session. The rejected
inversion â€” building and publishing docs INSIDE the publication workflow â€”
stays rejected, re-argued honestly now that credentials are no longer part of
the objection: automation dissolves the credentials-in-the-publication-path
argument (the role lives in a separate downstream workflow), but the
load-bearing failure mode stands untouched â€” a multi-root strict Sphinx build
inside the publication path means a docs defect discovered after the
immutable registry upload strands a half-published release with no retry that
does not re-enter publication. Downstream-of, never inside, is the whole
ruling. The kept model's failure mode, named honestly: staleness between the
release and the next successful docs publish â€” shrunk by automation from a
human-session bound to a workflow-alert bound, and degrading toward a floor
(the offline channel table), never toward a false advertisement.

**R4 â€” Credentials: the OIDC role is the design target; the guard falls only
with it.** The operator directive makes automated docs publication a design
target, so the role moves from contingency to schedule. The mechanism is
unchanged from this record's first draft: GitHub OIDC federation into a
dedicated IAM role â€” no stored AWS keys, ever, mirroring the registry's
trusted-publishing posture â€” with least privilege enumerated:
`s3:ListBucket`, `s3:PutObject`, `s3:DeleteObject` on the one docs bucket;
`cloudfront:CreateInvalidation` and `cloudfront:GetInvalidation` on the one
distribution; `cloudformation:DescribeStacks` on the one stack; trust policy
pinned to this repository and a protected docs environment. The operator
creates exactly two things (OP-3, now scheduled rather than optional): the
GitHub OIDC identity provider in the AWS account, and that role with that
policy. The role's identifier reaches the workflow as an environment-scoped
variable, never as repository content, per
`2026-07-27-pipeline-config-topology-adr`. `_require_human_publish_environment`
is the structural guard that today makes CI publication impossible; it is
removed only in the same change that lands the role, the protected
environment, and the consequence workflow â€” never ahead of them â€” and its
purpose (no surprise CI publication) transfers to the protected environment
and the workflow's pinned identity. Until that change, the human session
remains the only deploy authority; after it, local human publishes remain
possible.

**R5 â€” Localized roots: every language, every run, all-or-nothing.** The
`es`/`ca`/`hu` roots build after the English root; every build and validation
completes before any upload; any single language failure refuses the entire
publish, and no partial site ever reaches the bucket. Partial per-language
publication is forbidden because the four roots must state one truth about one
release â€” a Spanish root advertising an older surface than the English root is
silent mis-documentation â€” and the whole-tree delete-sync makes all-or-nothing
the only mechanically clean shape anyway. The accepted cost: a broken locale
blocks an urgent English-only fix until repaired; the locale builds are strict
and CI-gated on the docs lanes, so a publish-time surprise indicates a gate
gap, not a tolerable path.

**R6 â€” The stale marketplace identity: declared supersession, ownership rule
unchanged.** The general case first, because the sibling-protection guard is
behaving exactly as designed and the gap is conceptual: the mechanism has no
way to say "this name is my own predecessor". The cohort's marketplace
manifest gains a declared supersession axis â€” a list of plugin names this
product retires (here: `aeat`). The merge tool honours it under the UNCHANGED
ownership rule: it may remove a superseded entry and its subtree only when
the entry is owned by this product (`published_by` equal) or carries no
publisher (the claimable class it may already take over wholesale by name); a
sibling-owned name in the supersession list is the same hard refusal as a
name takeover. This adds no authority over siblings the claim rule does not
already grant â€” the live `aeat` entry has no `published_by` and is claimable
by any product today â€” it adds only a remove verb with identical bounds. The
declaration is durable: it ships in every subsequent cohort manifest, the
publish preflight verifies the retired names are absent (and refuses,
naming the supersession, when one is present un-superseded), so the
retirement is an enforced invariant rather than a one-time state, and a
resurrection â€” by replay, by an older manifest, or by a stranger claiming
the abandoned name into this account's index â€” is refused loudly. A product
rename is thereby one publication: claim the new name, supersede the old,
never both live at once. The operator's one-time hand-removal commit (OP-4)
remains acceptable as bootstrap, but the declaration and preflight must exist
by first publication regardless, or the retirement is an assumption.

The account-level metadata flip (owner `AEAT tax assistant project` â†’
`CADRUMO tax assistant project`, the description naming Cadrumo instead of
aeat) is part of the same supersession event mechanically â€” the merge already
takes name, description, and owner from the cohort, and the in-tree manifest
already carries the flipped values â€” so no state exists in which the index
advertises the retired identity beside the new plugin. The preflight extends
to it: account metadata must not name a retired identity. One genuinely
separate concern is flagged for the account standard rather than ruled here:
an account-scoped marketplace description that names a single product will be
stale the moment a sibling publishes. The `aeat` CLI executable name is
untouched throughout; only the marketplace plugin identity retires.

**R7 â€” Docs and landing: independent verbs, stated bootstrap order.** The two
publishers stay separate and are never force-paired. Bootstrap order, once per
stack: provision, then docs publish, then landing publish â€” because the landing
verification asserts `/docs/` serves 200 and would correctly refuse over an
empty docs prefix. Steady-state: either runs alone; each scopes its writes (the
docs sync owns `docs/`, the root sync excludes it and dry-run-refuses touching
it), and the landing's `/docs/` check is a destruction tripwire on the shared
bucket, not a dependency. The R2 release consequence requires only the docs
publish; the landing republishes when its own content changes.

## Rationale

The through-line is choosing, at every coupling, the arrangement that changes
the least while closing every unrecorded divergence loudly.

On hosting, the knockout is that the ledger reads opposite to the note's
assumption once grounded: the "rejected" incumbent is measured at zero (private
origin, Free-plan allowance, shipped and verified tooling) while the "chosen"
alternative carries the only real migration cost in sight (the file cap, a
re-architecture, and the discard of working verification). Honouring the
note's letter would spend money and risk to satisfy a cost objection that no
longer binds; honouring its intent â€” predictable near-zero cost â€” is exactly
what staying achieves. What the note is owed is not obedience but the explicit
supersession record it never got, which this is.

On ordering, the knockout is the immutability asymmetry: registry bytes cannot
be retried, a docs build can. Any ordering that puts the rebuildable thing
inside or ahead of the irreversible one converts a docs defect into a stranded
release; consequence-after-publication is the only ordering in which every
failure is retryable where it fails. The pull-model handshake is kept for the
same reason seen from the other side: it is idempotent, version-agnostic, and
its degradation direction is a floor rather than a lie, which is precisely the
property an operator-facing surface owes under the no-silent-under-declaration
discipline.

On the marketplace, the deciding observation is that the guard and the gap
are different things: sibling protection is an ownership rule, and the rename
problem is a vocabulary gap â€” the manifest can claim a name but cannot retire
one. Declared supersession fills the vocabulary gap while binding the new
verb to the existing ownership rule, so the guard is not weakened by a single
bit: the set of entries this product can remove is exactly the set it could
already claim and overwrite. Against that, hand-deletion fails not because it
is unsafe but because it is forgetful â€” a retirement the tool cannot verify
is re-broken by the next replay or the next claimant of the abandoned name â€”
and every other alternative either grants standing delete authority or
re-opens the founding incident. The supersession must be a property of the
release that performs the rename, remembered by every release after it.

## Consequences

- The fifteen-day docs staleness gets an owner and a bound: mechanical once
  the consequence workflow lands (the target state), procedural until then
  via the required runbook step plus ad-hoc publishes at will. The residual
  cost, stated plainly: until OP-3 completes, the bound is a plan-checklist
  tripwire, not code â€” a skipped runbook step revives the gap; and after it,
  a silently failing consequence workflow would too, which is why its failure
  must alert, never merely log.
- The account stays two-vendor (Cloudflare DNS and apex; AWS delivery for one
  subdomain). That is real operational spread, accepted knowingly and recorded
  â€” no longer an unrecorded divergence a future reader trips over.
- The first publication cannot silently coexist with the retired identity:
  the supersession is declared in the cohort, executed under the unchanged
  ownership rule, verified by the preflight on every later release, and the
  account metadata flips in the same event â€” no state advertises both
  identities.
- Delivery-leg consolidation becomes structural: one delivery authority per
  surface, delivery bound to the release as an automatic consequence, and the
  human-run interim scheduled to retire with OP-3. The publication leg's
  consolidation â€” version identity, the doubled PyPI lane, promotion
  atomicity â€” is ruled in `2026-07-27-publication-lane-consolidation-adr`;
  configuration and secrets placement in
  `2026-07-27-pipeline-config-topology-adr`. The three records together are
  the canonical pipeline.
- No stored credential exists anywhere in the target state (OIDC only), no
  hosted-minute spend is added (the consequence workflow runs on the
  self-hosted fleet), and no publication gate or sealed-cohort/evidence
  apparatus changes.
- Not verified, stated honestly: a fresh full-site file inventory (the Pages
  cap comparison is bounded by a prior corpus measurement, not a new build);
  whether `aeat-cli 0.1.1` ever reached an external registry (immaterial to
  R6 â€” the entry is wrong-identity either way); which CloudFront plan the
  account is on; and whether the operator's hosting preference has moved
  since 2026-06-25. Both marketplace manifests, the deploy tooling, and the
  live site headers WERE verified first-hand on 2026-07-27; the publication
  leg's measurements are recorded and attributed in the shared research
  document and its sibling record.
- Operator decision points surfaced by this record: **OP-1** confirm the
  account's CloudFront plan and expected bill for the docs stack; **OP-2**
  ratify (or overturn) the scoped supersession of the 2026-06-25 hosting note
  for `cadrumo.neve.md`, and update that note in its own vault; **OP-3**
  now SCHEDULED as the auto-publish prerequisite per R4: create the OIDC
  identity provider, the least-privilege docs deploy role, and the protected
  docs environment, so the consequence workflow can land and the CI-refusal
  guard can fall with it; **OP-4** the marketplace
  retirement: either land the bootstrap removal commit in
  `nevenincs/neve-marketplace` or rely on the declared supersession's first
  execution â€” the declaration and preflight land either way. OP-5 and OP-6 are owned by
  `2026-07-27-publication-lane-consolidation-adr`, OP-7 and OP-8 by
  `2026-07-27-pipeline-config-topology-adr`; each is listed once, in its
  owning record.
## 2026-08-23 repository-boundary amendment

The website-specific parts of this decision are superseded by
`2026-08-23-website-repository-boundary-adr`. The product repository no longer owns a
landing-page publisher, website source, website build or test commands, or website
release coupling. The separate `cadrumo-marketing` repository is the sole authority for
that lifecycle.

This amendment does not reverse the remaining product-documentation, marketplace,
cohort, or publication decisions in this record. Product documentation may still be
published independently, but it is neither a product-release gate nor a website release
owned by this repository.
