---
tags:
  - '#adr'
  - '#pipeline-config-topology'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - '[[2026-07-27-canonical-release-pipeline-adr]]'
  - '[[2026-07-27-publication-lane-consolidation-adr]]'
  - '[[2026-07-27-canonical-release-pipeline-research]]'
  - '[[2026-07-25-account-distribution-standard-adr]]'
  - '[[2026-07-20-release-asset-transport-adr]]'
---

# `pipeline-config-topology` adr: `four homes for pipeline configuration: repo for shapes, environments for values, runners for machine state, the operator's vault for cross-project facts` | (**status:** `proposed`)

## Problem Statement

The operator has fixed a hard boundary — this repository carries cadrumo and
only cadrumo; cross-repository and account-level infrastructure detail is
private, machine-bound context that must never land here — and simultaneously
wants the runners provisioned with the secrets and configuration that make
automated docs publication and audit updates viable. Those two directives
meet at one question this record answers for every piece of configuration the
pipeline needs: where does it live, and why there. The question is live, not
hypothetical: the first drafts of this feature's own vault records breached
the boundary (a private repository name, a private note's path, a hostname,
a DNS zone identifier) and were scrubbed on 2026-07-27 — while the
repository's standing privacy gate stayed green the entire time, because the
records were untracked and the gate scans only the tracked tree. Without a
declared topology and a detector that can actually see the breach, the
boundary is re-breached by the next well-meaning record. In a repository headed for public visibility this is a
disclosure question, not a tidiness one.

This record rules the four homes, assigns every configuration item the
pipeline currently needs to one of them, states the invariant that makes the
boundary enforceable, names the detector, and rules how a product's secrets
stay scoped to that product on runner hosts that serve multiple products.
Its siblings are `2026-07-27-canonical-release-pipeline-adr` (delivery leg)
and `2026-07-27-publication-lane-consolidation-adr` (publication leg).

## Considerations

- The pipeline's execution-time configuration is already indirection-shaped:
  `publish-release.yml` reads `vars.CADRUMO_PUBLISH_ENABLED`,
  `vars.HOMEBREW_TAP_REPO` / `secrets.HOMEBREW_TAP_TOKEN`,
  `vars.CLAUDE_MARKETPLACE_REPO` / `secrets.CLAUDE_MARKETPLACE_TOKEN`, and
  PyPI Trusted Publishing carries no stored credential at all — the workflow
  files name variables, environments supply values. The topology largely
  ratifies and completes an existing shape rather than inventing one.
- The account is a User account with no organization-level variables (per
  `2026-07-25-account-distribution-standard-adr`), so identical variable
  NAMING across products is the only transferable configuration mechanism;
  the names are deliberately product-neutral.
- PyPI Trusted Publishing anchors trust in workflow-run identity plus a
  GitHub environment name; the environment NAME is load-bearing config even
  though no credential exists. The registered names today: `release` (Gate
  3), and `pypi` / `pypi-data-manuals` / `pypi-data-official` (the retiring
  lane; deleted with it under issue #618).
- The docs stack resolves its own identifiers at runtime: the deploy tooling
  reads the bucket name and distribution id from CloudFormation stack
  outputs, derives the bucket from the authenticated account id, and looks up
  the certificate by domain — only the stack name, region, and canonical
  domain are repository content, and those are product-scoped facts.
- An AWS role ARN embeds the AWS account id: account infrastructure identity,
  not product config. It can reach a workflow as an environment-scoped
  variable without ever being repository content.
- A privacy detector already exists and is well built:
  `dev/quality/tests/test_doc_privacy.py` is a repo-wide lint whose banned
  tokens are assembled from fragments at runtime, so the gate file carries no
  banned literal and the scan covers the gate itself with no self-exclusion;
  it carries an anti-tautology check and deliberately exempts the legally
  load-bearing published attribution (the public contact address and
  copyright holder in NOTICE and PRIVACY.md). The boundary detector must
  EXTEND this gate, not stand beside it as a second authority.
- The existing gate has two measured blind spots. First, it shells out to
  `git grep` over the TRACKED tree, so an untracked file carrying a banned
  token scans green — exactly how this feature's own records carried a zone
  ID undetected. Second, its banned set is scoped to operator-identifying
  data (hostnames, login handles, home paths, tailnet addresses); it has no
  notion of cross-project infrastructure identifiers — a DNS zone ID, a cloud
  account ID, a private repo name, a registrar account — so the operator's
  boundary rule currently has no detector at all.
- The evidence pipeline separately operates a fail-closed identifier
  discipline at the publication boundary (scrub-at-birth plus a leak sweep,
  per `2026-07-20-release-asset-transport-adr`); it guards what leaves as
  release content, not what enters the tree.
- The self-hosted runner hosts serve multiple products under the account
  (sibling runner registrations exist on the same machines), so runner-local
  state is itself cross-project surface: anything a product leaves on disk is
  readable by another product's next job.
- GitHub environment secrets are delivered to a job only when its workflow
  run targets that environment in this repository, and environment protection
  rules constrain who and what can target it; OIDC trust policies can pin
  repository AND environment, which makes the environment the natural
  per-product scoping boundary on shared hosts.
- The repository is private today and intended public; every boundary
  decision must be judged as if the tree were already public, because
  history is not scrubbed retroactively.

## Considered options

- **Everything in the repo, secrets excepted.** Simple and reviewable, and
  the current de-facto drift. Rejected: account-level identifiers (role ARNs,
  zone ids, private repo names, host names) are disclosure in a public repo
  and stale the moment the account reorganizes; the boundary breach this
  feature already committed is the demonstration.
- **Everything in GitHub secrets/variables, repo carries nothing.** Rejected:
  hides reviewable, product-scoped shape (which variables exist, what reads
  them, what shape a value must have) from the tree, making every workflow
  un-auditable and every fork un-runnable; secrets sprawl is its own
  disclosure surface.
- **A dedicated secret manager for everything.** Rejected for now: adds an
  availability dependency and a credential-to-reach-the-credentials problem
  the pipeline does not need at its current size; GitHub environments already
  provide scoping, protection rules, and OIDC pinning at zero cost. Revisit
  if the account outgrows per-repo environments.
- **Four declared homes with a detector (chosen).** Repo for product-scoped
  non-secret shapes; GitHub environment/repository variables and secrets for
  execution-time values; runner-host-local state for machine facts; the
  operator's private vault for cross-project facts. Enforced by a boundary
  gate, not by discipline alone.

## Constraints

- Creating environments, variables, secrets, fine-grained tokens, the OIDC
  provider, and IAM roles are operator actions on surfaces this session must
  not touch; this record specifies them (OP-7) and changes nothing live.
- The detector can only pattern-match what it can enumerate or shape-match.
  Fixed private names ride the existing gate's fragment-assembly mechanism
  (the token never appears whole in the gate source); identifier CLASSES ride
  shapes. A novel private name whose shape matches nothing evades both until
  its first incident adds it — the gate is a ratchet, not a proof, and the
  record says so rather than pretending completeness.
- No file-scanning detector sees runner-host state, and CI checkouts contain
  no untracked files, so the untracked-scan extension protects only the
  machines where the gate is actually run. Detection windows are stated
  honestly under Implementation; only discipline closes them fully.
- Shared-runner isolation below the job boundary is bounded by the OS: jobs
  of different products on one host share a user account today. The topology
  scopes secrets to environments and forbids at-rest product secrets on
  hosts, but a hostile sibling job is outside the threat model this record
  can close; the isolation-level call is the operator's (OP-8).
- Depends on the sibling records' rulings (the R4 OIDC role, the P4
  environment retirements) landing as designed; item assignments below track
  those rulings.

## Implementation

**The four homes and the assignment rule.** (a) The REPOSITORY carries
product-scoped, non-secret SHAPE: workflow definitions, the names of the
variables and environments they read, validation of value shapes, stack name,
region, canonical domain, release-please configuration, the marketplace
supersession declaration, evidence schemas. (b) GITHUB ENVIRONMENTS AND
REPOSITORY VARIABLES/SECRETS carry execution-time VALUES: everything a runner
needs at job time that is either secret or account-scoped. (c) RUNNER HOSTS
carry MACHINE state only: toolchains, caches, the local AWS session of the
interim human deploy authority — never product secrets at rest. (d) The
OPERATOR'S PRIVATE VAULT carries CROSS-PROJECT facts: account topology, DNS
zone identifiers, private repository names, host names, sibling-product
plans. The assignment rule is one sentence: the repo knows the NAMES of
things and the shapes of their values; only environments know the VALUES;
only machines know themselves; only the operator knows the account.

**The inventory, assigned.** `CADRUMO_PUBLISH_ENABLED`: repository variable
(b), read by both publication lanes until #618; its NAME is repo content, its
setting is the operator's arming act. `HOMEBREW_TAP_REPO` and
`CLAUDE_MARKETPLACE_REPO`: repository variables (b) — the values are public
repo slugs, but they are account-scoped pointers the account standard names
identically across products, so they stay values, not literals in workflows.
`HOMEBREW_TAP_TOKEN` and `CLAUDE_MARKETPLACE_TOKEN`: fine-grained personal
access tokens, each scoped to exactly its one target repository with
contents-write only, stored as secrets (b) on the environment whose jobs push
them, rotated on a calendar the operator owns. PyPI Trusted Publishing: no
credential anywhere; the environment names `release` (and, until #618, the
three retiring upload environments) are load-bearing config — names in the
repo (a), registrations on PyPI and GitHub created by the operator. The AWS
docs deploy: the role ARN is an environment-scoped variable (b) on the
protected docs environment, never repository content; the role, its trust
policy (pinned to this repository and that environment), and the OIDC
identity provider are operator-created per the delivery sibling's R4; the
stack name, region, and canonical domain stay in the repo (a) as today; the
bucket name and distribution id stay runtime-resolved from stack outputs —
they live in AWS, which is home (b)'s cloud-side analogue, and never in the
tree. Runner hosts (c) keep only toolchains and the interim human AWS
session. Everything scrubbed on 2026-07-27 — the private planning vault's
identifiers, the zone id, host names — is home (d) and stays there.

**The invariant and its detector.** The invariant: repository content —
source, workflows, docs, and the vault records alike — never carries a
credential, a token, an account-infrastructure identifier (role ARN, DNS
zone id, cloud account id outside AWS's own runtime), a private repository
name, or a host name; every workflow reaches such values exclusively through
`vars.*` / `secrets.*` indirection or runtime resolution.

The detector is the EXISTING privacy gate, extended — never a second
authority beside it, because two overlapping scanners with different banned
sets is how one of them rots unnoticed. Two extensions close the two
measured blind spots. First, a new banned CLASS joins the gate's scope:
cross-project infrastructure identifiers, detected by shape where shapes
exist — 32-hex account/zone-id shapes, cloud role-identifier shapes,
`owner/repo` references naming a repository outside the declared reference
set (this repository, the shared distribution repository, the marketplace,
pinned upstream actions), absolute paths into another product's tree — and
by the gate's fragment-assembled fixed-token mechanism for known private
names that no shape can catch. The gate's existing judgement stands
untouched: the legally load-bearing published attribution stays exempt, and
runner labels stay configuration, not machine names. Second, the scan's
scope widens from the tracked tree to tracked plus staged plus
untracked-not-ignored (`git ls-files --others --exclude-standard`), so a
leak in a not-yet-committed vault record — this feature's own breach shape —
fails the gate while it is still an edit rather than a history rewrite.

The detection windows, stated honestly. The extended gate fires wherever the
test suite runs: it catches the untracked breach on any developer or agent
machine that runs the gates, and it catches a committed breach at the first
CI run — but a CI checkout materialises no untracked files, so the
untracked-scan extension protects only machines where the gate actually
runs. A pre-commit staged-content hook was considered as the primary
mechanism and rejected: hooks are per-clone opt-in, silently absent on a
fresh clone and bypassed by a no-verify commit, so the primary detector
would be the one enforcement point that is optional — though nothing
forbids installing it as belt-and-braces. The residual, named plainly: an
author who writes, commits, and pushes without running any gate lands the
identifier in public history, where removal is a rewrite rather than an
edit. The detector shrinks that window to a single ungated push; CI-on-push
bounds the exposure time; only discipline closes the window entirely. A
finding in any layer is a hard refusal naming the file and pattern, never a
warning; the third layer — the evidence leak sweep guarding what leaves as
release content — continues unchanged.

**Shared runners: the environment is the product boundary.** Product secrets
reach a shared host only as job-scoped environment values delivered because a
run in THIS repository targeted THIS environment, under that environment's
protection rules; the OIDC trust policy pins repository and environment, so a
sibling product's job on the same host cannot assume cadrumo's role even
with a stolen workflow file. No product secret is ever written to runner
disk: checkouts keep `persist-credentials: false` (the standing posture),
tokens ride process environment and `http.extraheader`, and the evidence
leak-sweep already polices what jobs persist. What this does NOT close is
honest: jobs of different products share an OS user on today's hosts, so
at-rest artifacts of one job are readable by the next; the hard boundary
would be per-product runner users or VMs, and that isolation level is the
operator's call (OP-8) — until made, the mitigation is that nothing worth
stealing is at rest. And to say it plainly: no detector covers runner-local
state at all — the extended gate scans this repository's files, and nothing
scans a shared host's disk for one product's residue — so the runner surface
is a named residual risk carried on discipline (no-at-rest-secrets,
`persist-credentials: false`) rather than on detection.

## Rationale

The topology mostly ratifies the pipeline's best existing pattern and closes
the gaps around it. Trusted Publishing already proved the strongest shape —
identity over stored value — and the R4 docs role extends it to AWS; the
tap and marketplace tokens cannot use identity federation (GitHub-to-GitHub
has no equivalent here), so they take the weakest-acceptable form: single-
repository fine-grained tokens in environment secrets. The four-homes split
follows the failure modes actually observed, not a taxonomy for its own
sake: the repo breach that motivated the boundary was cross-project
identifiers in vault records (home d leaking into home a), and the
double-lane hazard in the publication sibling is an arming VALUE with
under-specified scope (home b under-constrained). Naming the homes is cheap;
the detector is what makes the naming mean something — this repository's own
gate discipline shows that an unenforced rule is re-broken within weeks, and
the scrub this feature performed on its own records is the local proof.

## Consequences

- Every configuration item the pipeline needs has exactly one declared home
  and a stated reason; the next item inherits the assignment rule instead of
  a judgment call.
- The boundary becomes enforceable by extending the standing privacy gate:
  one authority, two new capabilities (the cross-project identifier class and
  the untracked-file scan), fail-closed, and covering the exact breach shape
  this feature produced while that gate was green. Cost: shape allowlists
  for legitimate lookalikes (digests, commit ids, the declared cross-repo
  reference set) and per-incident token growth — a ratchet, not a proof,
  with its detection windows stated in the record rather than implied away.
- Public-repo readiness improves concretely: what the tree carries after
  this record is publishable by construction, and the disclosure surface
  concentrates in GitHub's secret store and the operator's vault.
- Shared-runner risk is named rather than hidden: job-scoped delivery and
  no-at-rest-secrets are ruled; OS-level isolation is explicitly deferred to
  the operator (OP-8) instead of being silently assumed.
- Operator decision points owned by this record: **OP-7** provision the
  topology — enable secret scanning with push protection; create the
  protected docs environment with the role-ARN variable; mint the two
  fine-grained single-repository tokens and place them as environment
  secrets; register PyPI Trusted Publishing for the sole publication
  authority under the `release` environment name (a pending publisher for
  the root project, which does not yet exist on the registry, and
  per-project publishers for the two existing data companions); and confirm
  the three retiring upload registrations and environments are deleted with
  #618. **OP-8**
  choose the shared-runner isolation level: accept job-level scoping with
  no-at-rest-secrets, or provision per-product runner users/VMs.
