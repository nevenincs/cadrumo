# Releasing Cadrumo

This runbook covers the complete release lifecycle for Cadrumo maintainers.

**One dispatch drives the release.** `.github/workflows/release-orchestrator.yml` bumps
the version, runs the packaging campaign, runs whichever acquisition lanes the claimed
channels require, and seals a release candidate — all from a single `workflow_dispatch`,
with no human decision anywhere downstream of pressing Run.
`.github/workflows/release-soak-promoter.yml` then crosses the 48-72 hour soak on its own
clock and dispatches `.github/workflows/publish-release.yml`, **the sole publication
authority**, which promotes the sealed, CI-tested cohort to every public channel — PyPI,
GitHub Release, Scoop bucket, Homebrew tap, and the Claude plugin marketplace — without
rebuilding any artifact. Neither workflow reads a required-reviewer approval click in its
own logic; the publish job still runs inside the protected `release` GitHub environment
for the OIDC trust anchor that environment name provides, and that environment's
`required_reviewers` rule, if the operator has not yet removed it (**OP-9**, see
Operator actions below), is a standing GitHub setting independent of anything this
workflow reads or enforces.

Dispatching `publish-release.yml` directly with `dry_run=true` still runs Gate 2
(validate) fully but skips Gate 3 (publish), for a validate-everything-publish-nothing
rehearsal of the publication authority alone; `release-orchestrator.yml`'s own `dry_run`
input rehearses the whole chain instead, from the bump through the sealed candidate,
advancing no version and publishing nothing.

For the full pipeline review and gap analysis see
`.vault/reference/2026-07-19-post-release-distribution-reference.md`.

## Release at a glance

| Phase | Where | What |
| --- | --- | --- |
| 1. Dispatch | CI (`release-orchestrator.yml`, one `workflow_dispatch`) | Bump 7 surfaces + lock, packaging campaign, acquisition lanes, seal a release candidate |
| 2. Soak (machine-held) | CI (`release-soak-promoter.yml`, hourly cron) | Wait 48-72h against immutable bytes, re-verify readiness, dispatch publication |
| 3. Publish | CI (`publish-release.yml`) | Gate 2 validate → Gate 3 publish (behind the `release` environment) |
| 4. Post-publication verification | Local, human | Reacquisition lanes prove each channel; `just docs-deploy` closes the docs tripwire |

The one remaining local, human act ahead of a first dispatch is arming the workflow's
one-time channel prerequisites (below) — none of it happens per release.

## Repository identity

The canonical repository slug is **`nevenincs/cadrumo`**, as declared by the local
release authorities and tooling. The `cadrumo/cadrumo` organization move is deferred.
If it ever happens, re-register every Trusted Publisher first, because PyPI matches the
exact owner and repository claim in the OIDC token.

## Release authorities and references

The accepted
[`cadrumo-cli-executable` architecture decision record (ADR)](.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md)
governs product casing, imports, the `aeat` human command, and `cadrumo-mcp`. The
accepted
[`product-rename` Stage-A ADR](.vault/adr/2026-07-13-product-rename-adr.md)
governs distributions, repository, marketplace, marketing, and publication. The
superseded
[`cadrumo-product-rename` ADR](.vault/adr/2026-07-12-cadrumo-product-rename-adr.md)
does not govern active naming. The following sources define the release mechanics:

- [`.github/workflows/publish-release.yml`](.github/workflows/publish-release.yml) —
  the sole upload authority: dispatched by the soak promoter (or manually for a
  rehearsal), the protected `release` environment for its OIDC trust anchor (its
  `required_reviewers` rule is a standing GitHub setting the workflow's own logic does
  not read — see OP-9 under Operator actions), OIDC Trusted Publishing,
  promote-without-rebuild from the retained cohort bytes.
- [`.github/workflows/packaging-smoke.yml`](.github/workflows/packaging-smoke.yml) —
  runs the three-OS artifact checks, builds the immutable full release cohort once per
  run and uploads it (`cadrumo-release-cohort.tar.gz`) as a run artifact, and mints the
  per-OS oracle `DistributionEvidence` rows as their own artifacts. Its run id is the
  identity anchor for every downstream dispatch, and — because an artifact belongs to
  its producing run by construction — also the container those bytes live in.
- [`docs/_release_checklist.yaml`](docs/_release_checklist.yaml) — soak timing,
  versioning scheme, hotfix cycle times, and rollback triggers.
- [`docs/_release_notes_template.md`](docs/_release_notes_template.md) and
  [`docs/updates.md`](docs/updates.md) — release-note authorities.
- [`SECURITY.md`](SECURITY.md) — private vulnerability reporting.

The release comprises three version-locked PyPI distributions:

| Distribution | Contents | Installed commands |
| --- | --- | --- |
| `cadrumo` | Core distribution | `aeat` and `cadrumo-mcp` (the `agent` extra enables `cadrumo-mcp`) |
| `cadrumo-data-manuals` | Reviewed manual corpus | None |
| `cadrumo-data-official` | Reviewed official and normative corpus | None |

Version and publish all three distributions as one immutable tested cohort. The core
distribution's mandatory base dependencies pin both companions to the same exact
version. Every artifact must remain below PyPI's 100 MB per-file limit. The core wheel
must not contain companion sources in PDF, XLS, or XLSX formats. The companion parity
gate
`dev/packaging/tests/test_cadrumo_data_distribution.py::test_companion_version_matches_root_distribution`
must prove that both companion versions match the core distribution.

A successful `Cadrumo Packaging Smoke` run builds the cohort once from a clean source
snapshot. It retains the three wheels, the root source distribution,
`python-cohort.json`, the full release-cohort archive, the installed CLI and MCP
oracle evidence, and the per-OS `DistributionEvidence` records as artifacts of that
run. The cohort manifest binds the source commit, version, filenames, and SHA-256
digest of every distribution file. The publication authority consumes those retained
bytes without rebuilding them.

**Artifacts expire, and that bounds the promotion window.** Retention is 90 days (the
maximum this account allows), counted from the smoke run, after which the run is no
longer promotable and the campaign must be re-run to mint fresh bytes. Nothing warns
you as the window closes: a promotion attempted past it fails at download, not with a
message about expiry. Promote well inside 90 days, and treat a smoke run older than
that as gone rather than stale. A release **candidate** held for a multi-day soak is
deliberately exempt — it rides its own draft release precisely because it must outlive
this clock (see `dev/release/release_candidate.py`).

## Day one: enrolling a new product in the account distribution standard

This section is the whole cost of bringing a *new* product under the account
distribution standard. It does not grow with the number of products already
shipping — that fixed cost is the property the standard is chosen for. A product
already shipping (this one) has completed it; the checklist is here so a sibling
product can be enrolled without rediscovering the shape.

Work through it in order.

1. **Declare the version authority.** Add release-please configuration and its
   manifest. The version is single-source and is written into the product's own
   package metadata. Whether the release commit is produced by a workflow or by a
   local invocation is a per-product safety choice and is deliberately *not*
   standardised — both emit the same release commit, tag, and manifest, and
   standardising the output is what makes the pipeline transferable.

2. **Add the two workflows.** One builds and proves the immutable cohort; one
   promotes it. The promotion workflow must be dispatched explicitly and must
   declare **no tag trigger**: a tag created by a workflow's own token does not
   fire tag-triggered workflows, so a declared tag filter is inert while reading
   as a second, automatic way to publish. Remove it rather than keep it.
   `dev/release/tests/test_publish_release_workflow.py` pins this.

3. **Evaluate the channel set — do not choose it.** Answer three questions about
   the product and let the rule decide the rest:

   - Does the artifact expose a command a user invokes directly?
   - Can that user be assumed to hold the language toolchain?
   - Is the artifact an extension of a host application?

   Record the answers in the `[matrix]` block of the product's channel
   descriptor (`docs/_data/download_channels.toml` here). The derivation lives in
   `dev/docs/download_matrix.py` (`derived_tiers`) and is validated at load, so a
   descriptor whose channels disagree with the rule refuses rather than drifts.
   Every product ships its language-native registry — that is the floor and the
   only channel where dependency resolution happens. A tier the rule selects that
   the product does not ship yet goes in `pending_tiers`, so the gap is declared
   data rather than a silent absence.

4. **Add the shared-repository files, if the rule selected them.** One formula
   file under `Formula/` and one manifest file under `bucket/`, in the account's
   single shared distribution repository. **Create nothing.** The repository
   already exists — Homebrew's `homebrew-` name prefix forces it to, and Scoop
   scopes discovery to `bucket/` when present, so one repository serves both
   ecosystems. The account's distribution repository count is one at one product
   and one at a hundred.

   Each channel push must stage exactly its own product-scoped path — never
   `git add -A`, never `git add .`, never a wholesale delete of the checkout —
   because a sibling product's file lives beside it. It must also guard against a
   backward version bump (`dev/packaging/release_pointer_guard.py`) and retry a
   lost push race, since several products can release into one repository
   concurrently and hosted concurrency groups cannot serialise across
   repositories.

5. **Register workload identity federation on the registry.** Publication uploads
   under a short-lived token exchanged at run time; no long-lived credential is
   stored anywhere.

6. **Derive every user-facing name from the product name.** The repository, the
   registry package, the tap formula, the bucket manifest, and the community
   package identifier all carry it, the last qualified by the account as
   publisher. **Never claim an unqualified family name** — a published identifier
   cannot be renamed in place, so the correction is forward-only and strands the
   released version permanently.

Evidence stays proportional to claims. The required evidence-row set derives from
the channels the release actually claims, so a release claiming one channel proves
one channel. No gate is weakened and no row is removed: a channel still cannot be
claimed without its passing row. What changed is that an unclaimed channel no
longer blocks a claimed one, so a product can ship its registry first and add each
further channel when that channel's own proof passes.

## Publication prerequisites

### Former-name package cleanup

The pre-rename companion projects `aeat-data-manuals` and `aeat-data-official` were
deleted from PyPI on 2026-07-14; both project endpoints return not-found. Monitor both
former-name endpoints for reappearance during the publication window. If a former
`aeat*` name resurfaces anywhere else, remove any account-level pending publisher
registered for it.

### External reservation evidence

The
[release-reservation evidence issue #612](https://github.com/nevenincs/cadrumo/issues/612)
must identify a reviewer and confirmation date for every item. By operator
directive (2026-07-19, small-team policy), the Fable release agent is an
acceptable named reviewer for every item below: the agent gathers the
authoritative records, verifies them against the systems that own each name,
and posts the dated review on the issue. Items that carry legal judgment
(trademark clearance) are reviewed as documented searches with findings — the
agent review records facts, not legal advice, and the operator accepts the
residual risk by approving the publication run. The operator's `release`
environment approval remains the one human gate. Accept only records from the
system that owns each name:

- **PyPI projects:** Record each project's **Publishing** page showing project, GitHub
  owner, repository (`nevenincs/cadrumo`), workflow filename (`publish-release.yml`),
  and environment (`release`).
- **Repository:** Record `gh repo view nevenincs/cadrumo --json nameWithOwner,url`.
  The result must report `nevenincs/cadrumo` and its GitHub URL. A future transfer to
  another owner requires all three Trusted Publishers to be re-registered.
- **Marketplace:** Record the provider-owned listing or reservation for the exact
  marketplace and plugin identifiers; compare with the generated manifests.
- **Executables:** Record installed-wheel probes for `aeat --version` and the
  `cadrumo-mcp` launcher supplied by the sibling `cadrumo-harness` distribution.
- **Domains:** Record registrar or registry evidence identifying the exact domain and
  controlling account.
- **Trademarks:** Record the dated Spanish Patent and Trademark Office and European
  Union Intellectual Property Office search or clearance review. Name the reviewer and
  the classes reviewed.

An availability search is not reservation evidence. If an authoritative record is
absent, expired, or names a different owner, repository, identifier, environment,
domain, executable, or trademark scope, stop.

### Arm the publication workflow (one-time)

Arm `publish-release.yml` before the first publication, in this order:

1. Register PyPI Trusted Publishing for `cadrumo`, `cadrumo-data-manuals`, and
   `cadrumo-data-official` at `https://pypi.org/manage/account/publishing/`. For each
   project: publisher = GitHub Actions, owner/repository = `nevenincs/cadrumo`,
   workflow filename = `publish-release.yml`, environment = `release`.

2. Create the `release` GitHub Environment. Do **not** add a required reviewer, and
   remove the rule if one is already present — see **OP-9** below. The environment
   itself is mandatory and load-bearing: Trusted Publishing pins the workflow run's
   repository *and the environment name*, so publication fails outright without it.

There are **no per-product distribution repositories**. The account carries exactly
**one** shared distribution repository serving both Homebrew and Scoop, plus the
account Claude marketplace. Every channel variable is deliberately
**product-neutral**, so a sibling product sets the identical pair and drops in one
more formula file, one more manifest file, and one more plugin subtree with no
restructuring. No publication writes to any product repository's default branch.

3. Create the public shared account distribution repository `nevenincs/homebrew-tap`
   and set:
   - Repository variable `HOMEBREW_TAP_REPO` to its slug
   - Repository secret `HOMEBREW_TAP_TOKEN` to a PAT with write access

   The same variable and secret serve **both** the Homebrew and the Scoop pushes,
   because both land in this one repository. The `homebrew-` repository-name prefix
   is mandatory for the one-argument tap form, so the repository is `homebrew-tap`
   and the tap name users type is `nevenincs/tap`
   (`brew install nevenincs/tap/cadrumo`). One tap holding many formulae under
   `Formula/` is the standard shape — `hashicorp/homebrew-tap` serves 33 of them.

   Scoop rides along in the same repository under `bucket/`, because Scoop imposes
   no repository-name constraint and scopes discovery to that directory when it is
   present. Users add the bucket once, ever, and reach every product in it. One
   account precedent for the combined layout is `verda-cloud/homebrew-tap`, which
   carries a populated `Formula/` and `bucket/` side by side in production.

4. Use the existing public Claude plugin marketplace `nevenincs/neve-marketplace` and set:
   - Repository variable `CLAUDE_MARKETPLACE_REPO` to its slug
   - Repository secret `CLAUDE_MARKETPLACE_TOKEN` to a PAT with write access

The workflow is armed as soon as these prerequisites exist; there is no separate
opt-in variable, and there is no approval click. Publication is gated by the
mechanical guard set alone — the all-destination version-identity authority, per-run
and per-asset verification, the complete blocking evidence set, the leak sweep, the
supersession preflight, and the reversible-first destination ordering.

### Operator actions

**OP-9 — remove the `required_reviewers` protection rule from BOTH the `release`
and the `docs` environments.** This is a GitHub settings action; no agent can
perform it, and nothing in the repository can perform it on your behalf.

Remove **only** that rule. Keep both environments, and keep each environment's
`branch_policy` rule:

- The environment **name** is the Trusted Publishing trust anchor and the
  shared-runner product boundary. Deleting either environment breaks OIDC
  publication outright — this is the naive-sweep failure this note exists to
  prevent.
- `branch_policy` pins which refs may deploy. It is not a human gate and it stays.

`docs` is included because it carries the same rule class. The automated
documentation consequence would stop at an approval click the moment its
deploy-role variable lands, so removing the rule from `release` alone leaves half
the obligation standing.

Settings → Environments → *(each of `release`, `docs`)* → Deployment protection
rules → untick **Required reviewers** → Save.

**OP-10 — nominate the alerting channel.** `dev/release/alerting.py` defaults to
opening a labelled (`release-alert`) repository issue when a release-path workflow
fails or is refused, so alerting works with no configuration from the moment the
chain lands. Once you nominate a channel, set the repository variable
`CADRUMO_ALERT_WEBHOOK` to a webhook URL; when set, it **replaces** the issue path
rather than supplementing it, so the operator reads exactly one channel instead of
whichever is quieter. Nominating a channel is optional — the default issue path is
a real alerting channel, not a placeholder — but a webhook is likely preferable for
anyone not already watching the repository's issue tracker.

**Alongside OP-10 — create the `release-alert` label the default issue path
depends on.** It does not exist on this repository yet — confirmed live via
`gh api repos/nevenincs/cadrumo/labels/release-alert`, which returns a 404 — so
every default-path alert currently degrades to a run-log warning nobody reads
until it is created:

```bash
gh label create release-alert --description "Cadrumo release-chain failure alert" --color b60205
```

This is required only when relying on the default issue path; skip it if OP-10's
webhook variable is set instead, since the webhook path replaces the label path
rather than falling back to it. Verify the same way as OP-9/OP-12 — the same
read-only probe now reports the label's live status alongside the environment
inventory:

```bash
uv run --no-sync python -m dev.release.environment_inventory
```

**OP-11 — confirm the self-hosted Linux fleet carries `node`, or provision it.**
The version-bump stage shells out to `release-please` via `npx`, and whether the
self-hosted Linux runners carry a Node.js toolchain is unverified — this is stated
as an open question by the decision record itself, not settled by anything in this
repository. If `node` is absent, the very first stage of the very first real
dispatch refuses (naming this item) rather than silently proceeding; there is
nothing to test locally that would tell you the fleet's answer ahead of time.
Confirm `node --version` succeeds on the self-hosted Linux runner(s) `.github/workflows/release-orchestrator.yml`
targets, or install Node.js on them.

**OP-12 — delete the orphaned `pypi-data-official` GitHub environment.** Its
owning workflow, `pypi-upload.yml`, was deleted 2026-07-27 alongside the retired
PyPI-publish lane; the environment itself survived as a live Trusted Publishing
trust anchor naming a workflow that no longer exists — standing authority with no
owner. Two of the three retired-lane environments (`pypi`,
`pypi-data-manuals`) are already gone; this is the third.

Settings → Environments → `pypi-data-official` → Delete environment.

**Carried-forward item (from [issue #618](https://github.com/nevenincs/cadrumo/issues/618),
closed on its repository-actionable half): verify the index-side PyPI Trusted
Publisher registrations for all three retired projects.** Deleting a GitHub
environment does not delete the separate PyPI-side registration that names it —
they are two different systems. Check, for each of `cadrumo`, `cadrumo-data-manuals`,
and `cadrumo-data-official`, whether a Trusted Publisher entry naming workflow
`pypi-upload.yml` and its respective retired environment (`pypi`,
`pypi-data-manuals`, `pypi-data-official`) still exists under **Publishing** at
<https://pypi.org/manage/account/publishing/>. That check is an index-account
fact outside this repository and this forge — no agent can perform or confirm
it — so it stays a standing operator item rather than assumed clear. Remove any
surviving registration there directly; nothing in this repository can do so.

**OP-3 (narrowed) — set the docs-publish deploy-role variable on the
already-created `docs` environment.** The `docs` environment already
exists — it was created alongside `release` and carries the same
`required_reviewers` rule OP-9 above removes from it. Do **not** create it
again and do not remove its `required_reviewers` rule here: that removal is
the *second half of OP-9*, not a separate obligation, and doing it twice
under two different names is exactly the confusion this narrowing exists to
prevent. OP-3's only remaining half is setting the deploy-role variable the
`Cadrumo Docs Publish` workflow (`docs-publish.yml`) reads to assume its OIDC
role on `release: published`. Until that variable is set, the workflow stays
inert and the post-publication `just docs-deploy` remains a human act.

Verify all three actions afterwards, rather than assuming — a settings change
leaves no commit, so nothing in the tree records whether it happened:

```bash
uv run --no-sync python -m dev.release.environment_inventory
```

It reads the live `release`, `docs`, and `pypi-data-official` environments and
reports each one's rule set, plus — for `pypi-data-official` — whether any live
workflow in this tree still declares `environment: pypi-data-official`
(`OP-12 OUTSTANDING` when none does). It is read-only and carries no mutation
path. An environment it cannot read is reported `UNKNOWN`, never as satisfied,
and the command exits non-zero in that case so an unreachable forge is never
mistaken for a discharged obligation.

### Self-hosted runner fleet

EVERY workflow job runs on the self-hosted fleet — no hosted/cloud runners, ever
(operator mandate 2026-07-21; gated by
`dev/ci/tests/test_self_hosted_fleet.py`): the Windows build host (Windows
x64), the WSL Linux build host (Linux x64, containerized), and the macOS build host
(macOS arm64). The Scoop Windows-container gate runs on the self-hosted Windows host and
fails fast at its docker-mode preflight until that host runs Windows-container
mode. The Homebrew `linux-arm64` matrix row runs on the MacBook's colima arm64
container host. macOS Intel is not a supported platform (ARM-only macOS,
dropped 2026-07-21): no `macos-intel` row exists.

### Workstation and repository

Use a clean `main` checkout with Python 3.13, `uv`, `just`, Git, Node.js and `npx`,
and the GitHub CLI (`gh`) authenticated to `nevenincs/cadrumo`:

```console
python --version
uv --version
just --version
git --version
node --version
gh auth status
git remote get-url origin
git status --short
```

If `python --version` does not report Python 3.13, any command exits nonzero,
`gh auth status` does not name an account that can read `nevenincs/cadrumo`, or
`git status --short` prints output, stop. Do not work around a repository mismatch.

## Hard-cut release state

Cadrumo is a hard cut, not a compatibility release:

- `aeat` is the sole human CLI executable; it names the Cadrumo command contract. Do
  not expose `cadrumo` as a second human executable.
- `cadrumo-mcp` is the sole MCP command.
- Product imports, environment variables, plugin identifiers, resource schemes, and
  local state use the Cadrumo identity.
- AEAT remains the authority name in official endpoints, credentials, legal evidence,
  and registry classification.
- Cadrumo does not read, move, re-key, or delete former-product state. It starts with
  fresh Cadrumo state or refuses detected former-product state.

Call this cut out in the release notes. Test the published release against a fresh local
root. Never use a maintainer's real taxpayer profile for release verification.

## Operate a release

### Dispatch the release

Everything from computing the version through sealing a release candidate is one
`workflow_dispatch` of `.github/workflows/release-orchestrator.yml`, from the GitHub
Actions UI or:

```console
gh workflow run release-orchestrator.yml -f dry_run=false
```

Nothing downstream of this dispatch asks a human anything. The dispatch itself is the
deliberate act; there is no confirmation-phrase input, because typing one would
reproduce the ceremony the automation removed while protecting against nothing the
guard set does not.

`just release-readiness` (backed by `dev/release/readiness.py`) stays available for
local, pre-dispatch diagnosis of the checks that do not depend on a cohort
(`project-names-canonical`, `version-surfaces-agree`, `changelog-ready`, no open
`priority:P0-blocker` issue) — a convenience, not a mandatory step; the bump and
publication stages run the same checks themselves and refuse on their own account.

**What happens automatically, in order:**

1. **Host-extension evidence precondition.** Refuses the whole chain, before the bump,
   if a claimed channel needs operator-minted evidence it does not have. Under today's
   python-only channel descriptor no host-extension channel is claimed, so this passes
   trivially. If a `claude-*` channel is ever claimed, mint its four real-client rows
   first — the honesty guard in `dev/packaging/distribution_evidence_emit.py` refuses
   SDK-driven runs, so this stays a human act:

   ```console
   uv run --no-sync python -m dev.packaging.emit_real_client_evidence <args>
   ```

   Refer to the module's docstring for per-row arguments and the required isolation
   proof.

2. **Bump.** `dev.release.version_bump` computes the version from conventional-commit
   history — never a hand-typed number, which is the transcription error class this
   stage exists to remove — applies it to all seven declaration surfaces, regenerates
   and verifies the lock, and guards, commits, tags, and pushes. The all-destination
   identity guard runs before any ref leaves the runner, so a version an index, the
   tag/release namespace, the burned ledger, or the manifest floor already owns refuses
   before a tag exists.
3. **Packaging campaign.** Dispatches `packaging-smoke.yml` at the bumped commit and
   resolves its own run by identity (never by "the newest run of that workflow", which
   could belong to a neighbouring campaign): three per-OS smoke legs, the one immutable
   release cohort, and the three `oracle-emit-*` `DistributionEvidence` rows.
4. **Acquisition lanes.** Dispatches exactly the lanes the claimed channels require —
   derived from the same claimed-channel authority the publication gate reads, never
   hardcoded — and waits on each. Under today's descriptor this is legitimately empty.
5. **Seal.** Writes a typed release-candidate record (version, source commit, every run
   id, the claimed channel set, `dry_run`, and a soak deadline computed from
   `docs/_release_checklist.yaml`) to a reserved, GC-exempt draft-release namespace, and
   the run ends. No job holds a shared self-hosted runner across the soak.

`dry_run=true` rehearses the whole chain — bump computation, campaign, acquisition,
seal — advancing no version and publishing nothing; the bump stage stops after
computing the candidate version rather than pushing. `resume_packaging_run_id` re-enters
the chain at an existing, identity-verified `packaging-smoke.yml` run instead of
re-bumping and rebuilding, so a chain that failed after a successful campaign can
converge without burning a second version.

### Release-candidate soak (machine-held)

The release-candidate soak is a 48-72 hour wall-clock wait against an immutable cohort,
not a human review — nobody re-reads anything during it. `.github/workflows/release-soak-promoter.yml`
ticks hourly (`cron: "17 * * * *"`), reads every sealed candidate, and:

- Selects the eldest candidate whose deadline has elapsed; a candidate whose window is
  still open is left alone.
- **Re-verifies readiness against the sealed cohort immediately before dispatching.** A
  candidate whose blocking evidence regressed during its window is invalidated with a
  named refusal, never promoted on a stale green and never repaired in place — the
  fix-forward path is a fresh dispatch, which computes a fresh version.
- Dispatches `publish-release.yml` with the run ids the candidate recorded at seal time,
  pressing exactly the button an operator would; Gate 2 verifies every supplied run
  independently, exactly as it verifies a hand-typed one.
- Marks the candidate consumed once its dispatch succeeds, so an overlapping tick cannot
  double-publish the same cohort.

There is deliberately no input that shortens a window. **Hotfix carve-out:** authorised
*on the candidate*, not on the promoter — a shortened window is accepted only when the
candidate carries both an incident reference and an explicit release-owner approval,
refused at construction without both, so an emergency is recorded where it can be
audited rather than typed into a dispatch form where it cannot. See the cycle times in
`docs/_release_checklist.yaml`. A `dry_run` candidate's soak still completes on schedule,
but it is refused at promotion time and never published — the rehearsal proves this
stage too, without a real release ever crossing it.

### Publish

`publish-release.yml` runs two jobs once dispatched (by the promoter, above, or directly
for a rehearsal):

**Gate 2 — validate (no rebuild).** Verifies the source run identity (success,
`packaging-smoke.yml`, `push`, `main`, same repo, matching `head_sha`) and, with parity
checks, each acquisition run (`packaging-scoop.yml` / `packaging-homebrew.yml`,
`workflow_dispatch`, same repo, success). Identity is checked BEFORE a byte is pulled,
and it is the whole provenance binding: an artifact cannot be attached to a run that did
not produce it. Downloads the **sealed** release cohort archive
(`cadrumo-release-cohort.tar.gz` from the smoke run's artifacts — the single source of
every channel's bytes, PyPI included) and aggregates every required
`DistributionEvidence` row from its authoritative run — up to 3 python from the smoke
run, 1 scoop, 3 homebrew, and the 4 operator `claude-*` rows, as the claimed channels
demand. The per-OS smoke build cohorts are deliberately NOT part of the publication
chain. Re-points `promote_python_cohort --emit-version-only` at the sealed cohort's
`python/` bytes to guard the PyPI version against overwrite and emit the version. Runs
`dev.release.readiness --json --skip-network --cohort-dir var/promotion/release-cohort
--evidence-dir var/promotion/evidence/rows`; the sealed cohort's installed behaviour is
proven per-OS by the `DistributionEvidence` rows, not by the smoke build. Gate 2 passes
only with every required row present and verified.

**Gate 3 — publish** (`environment: release`). The job runs inside the protected
`release` GitHub environment for its OIDC trust anchor; the environment's own
`required_reviewers` protection rule, if the operator has not yet removed it
(**OP-9**, see Operator actions below), is a standing GitHub setting the job's own logic
neither reads nor requires — there is no `operator-preflight` job checking it. The
publish job re-downloads and re-verifies the sealed cohort archive and every evidence
row from the same identity-verified runs (never rebuilds), runs the fail-closed
`evidence_leak_sweep` over everything about to be attached (residual runner
metadata hard-fails the promotion), and:

- Publishes all 6 distributions to PyPI from the sealed cohort's `python/` subdir (the
  exact bytes every other channel ships and the oracle-emit legs proved) via
  `uv publish --trusted-publishing always` (OIDC; no API token needed once configured).
- Creates `gh release create vX.Y.Z --target <source_commit>` attaching every file
  found in the release-cohort directory (13 files) plus every verified evidence
  row and the per-lane evidence manifests, so the published release is
  self-evidencing and draft GC can never orphan a shipped audit trail. An empty asset
  set fails hard.
- Pushes `scoop/cadrumo.json` to this repository's own `bucket/cadrumo.json` using the
  job's `GITHUB_TOKEN`. Scoop reads a `bucket/` subdirectory, so there is no bucket
  repository, variable, or PAT.
- Clones the public Homebrew tap repo, copies `homebrew/Formula/cadrumo.rb` to
  `Formula/`, and pushes (requires `HOMEBREW_TAP_REPO` and
  `HOMEBREW_TAP_TOKEN`).
- Clones the public marketplace repo and runs `dev.packaging.marketplace_publish`, which
  replaces only the plugin subtrees the unzipped `cadrumo-marketplace-X.Y.Z.zip` declares
  and merges its entries into `.claude-plugin/marketplace.json` by plugin name (requires
  `CLAUDE_MARKETPLACE_REPO` and `CLAUDE_MARKETPLACE_TOKEN`). The marketplace is
  account-scoped, so a sibling product's plugin and index entry survive this product's
  release; the earlier wholesale tree replacement would have deleted them.

Each channel push refuses instructively when its credentials are absent. The bucket and
tap pushes each stage exactly one file, so they are likewise safe against sibling
products' files in the shared repositories.

### Post-publication verification

After publication, run the reacquisition lanes. These prove each channel serves the
correct cohort — they authorise nothing; the publish above already happened:

```console
uv run --no-sync python -m dev.packaging.acquire_pypi
uv run --no-sync python -m dev.packaging.acquire_github_release
uv run --no-sync python -m dev.packaging.acquire_mcpb
uv run --no-sync python -m dev.packaging.acquire_homebrew
uv run --no-sync python -m dev.packaging.acquire_claude_plugin
```

On Windows, also run:

```console
uv run --no-sync powershell dev/packaging/acquire_scoop.ps1
```

Each lane downloads the published artifact, verifies its digest against the cohort,
runs the installed behavior oracles, and emits a reacquisition evidence row. The
docs-claims gate (`dev/docs/tests/test_distribution_claims.py`) fails any README or docs
page that advertises a channel without a passing reacquisition row for that channel —
another verification, not an authorisation: it blocks a documentation claim, never the
release itself. Land install-claim docs updates only after all applicable reacquisition
lanes pass.

#### Distribution-complete tripwire

A release is not distribution-complete until the documentation site describes it.
Publication attaches a download payload to the release, and the documentation
site reads that payload at its next publish — so until a documentation publish
runs, the download page still describes the previous release.

This is deliberate and bounded rather than a defect. Documentation publication is
a release *consequence*, never a *gate*: a strict multi-root site build inside
the publication path would let a documentation defect strand a half-published
release, and the index upload cannot be unwound. The page falls back to its
offline channel table when the payload is absent, so it degrades to a floor and
never to a lie.

The tripwire is therefore procedural, and closing it is part of the release:

```console
just docs-deploy
```

Once the deploy-role variable is set on the already-created `docs` environment
(operator decision **OP-3**, narrowed — see Operator actions above; the
environment itself already exists, only the variable is outstanding), the
`Cadrumo Docs Publish` workflow runs this automatically on `release: published`
and this step becomes a verification rather than an action. Until then it is a
human act, and a release left without it is not finished — it is a release
whose documentation still advertises its predecessor.

## Report release problems

Use a public GitHub issue for packaging failures, command regressions, index resolution
failures, and documentation defects. Include:

- Cadrumo version
- Operating system and version
- Python version
- `uv` version
- Exact failing command
- Exit status
- Redacted standard output and standard error
- Workflow-run URL when applicable
- Expected result and observed result

Use fictional data. Remove taxpayer identifiers, credentials, tokens, local paths that
identify a person, and session state.

If the problem involves a suspected vulnerability, secret exposure, or taxpayer data,
treat it as a private security incident. Follow `SECURITY.md` and do not disclose
technical details in a public issue. If private vulnerability reporting is unavailable,
open only a detail-free request for private contact.

## Rollback procedure

Use rollback for data loss or corruption, a security vulnerability, a widespread
regression, or a supported-environment miscalculation.

> **The rollback helper is a printed checklist, not an executor.**
> `just release-rollback X.Y.Z` prints the full sequence — `main` and rollback-tag
> pushes plus all three PyPI yank URLs — for a human to review and run deliberately.
> It stages, commits, tags, and pushes nothing itself.

1. Stop announcements and marketplace promotion.

2. Preserve the workflow logs, cohort hashes, and redacted reproducer.

3. If the defect is public, open or update the public incident issue. For a security
   defect, coordinate through the private channel in `SECURITY.md`.

4. Review and record the disposition of each affected distribution: `cadrumo`,
   `cadrumo-data-manuals`, and `cadrumo-data-official`.

5. Yank `X.Y.Z` for every affected distribution. A yank prevents default resolution
   but preserves the artifact for explicit pins and investigation. Do not delete
   releases or project-page tombstones.

6. If source rollback is required, revert the release with a new commit and create the
   rollback marker tag:

   ```console
   git revert <release-commit-sha>
   git commit -m "revert: roll back vX.Y.Z"
   git tag -a vX.Y.Z-rollback -m "Rollback Cadrumo vX.Y.Z"
   git push origin main
   git push origin refs/tags/vX.Y.Z-rollback
   ```

7. For published channels: remove or retract the Scoop manifest, Homebrew formula, and
   marketplace content manually. The rollback helper prints the PyPI yank URLs; channel
   retraction is a separate manual step on each channel repo.

8. Never rewrite published Git history, delete the public final tag, use
   `git push --tags`, or push an RC tag.

9. Prepare a new patch version across all three distributions. Never overwrite or reuse
   `X.Y.Z`. Apply the hotfix cycle time from `docs/_release_checklist.yaml`, then
   repeat all six stages of the release pipeline.

10. Update the GitHub Release and `docs/updates.md` with the yank, affected scope,
    mitigation, and corrected version. Keep embargoed security details private until
    coordinated disclosure is approved.
