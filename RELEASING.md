# Releasing Cadrumo

This runbook covers the complete release lifecycle for Cadrumo maintainers.

**`.github/workflows/publish-release.yml` is the sole publication authority.** It
promotes an immutable, CI-tested release cohort to every public channel — PyPI, GitHub
Release, Scoop bucket, Homebrew tap, and the Claude plugin marketplace — without
rebuilding any artifact. The workflow requires the one-time channel prerequisites below, and the
protected `release` environment's approval click is the human gate.

Dispatching publish-release.yml with `dry_run=true` runs Gate 1 (prerequisite check) and
Gate 2 (validate) fully but skips Gate 3 (publish), so the validate-everything-publish-
nothing diagnostic lives on the single authority. The former validate-only `publish.yml`
stub was retired.

For the full pipeline review and gap analysis see
`.vault/reference/2026-07-19-post-release-distribution-reference.md`.

## Release at a glance (6 stages)

| Stage | Where | What |
| --- | --- | --- |
| 0. Version + tag | Local, human | Bump 7 surfaces, `uv lock`, commit, tag, push main + tag |
| 1. Build + prove | CI (`packaging-smoke.yml`, auto-triggered by push) | 3-OS smoke, build immutable release cohort, 3 oracle-emit rows |
| 2. Channel proofs | CI (3 manual dispatches) + operator real-client captures | Scoop, Homebrew, Claude acquisition; mint 4 claude rows |
| 3. Readiness gate | Local, human | Aggregate every row the claimed channels require; `just release-readiness-json` must report `"ok": true` |
| 4. Publish | CI (`publish-release.yml`, human approval required) | Gate 1 opt-in → Gate 2 validate → Gate 3 publish → reacquire |
| 5. Reacquire + docs | Local, human | Run the reacquisition lanes, unlock the docs-claims gate, `just docs-deploy` |

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
  the sole upload authority: manual dispatch, protected `release` environment with
  required reviewers, OIDC Trusted Publishing, promote-without-rebuild from the
  retained cohort bytes.
- [`.github/workflows/packaging-smoke.yml`](.github/workflows/packaging-smoke.yml) —
  runs the three-OS artifact checks, builds the immutable full release cohort once per
  run and publishes it (`cadrumo-release-cohort.tar.gz`) to the run's draft evidence
  release `evidence-smoke-<run id>`, mints the per-OS oracle `DistributionEvidence`
  rows onto the same draft, and seals an `evidence-manifest.json` binding the run
  identity to every asset's SHA-256. Its run id is the identity anchor for every
  downstream dispatch.
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
oracle evidence, and the per-OS `DistributionEvidence` records as assets on the run's
draft evidence release (`evidence-smoke-<run id>`), sealed by its
`evidence-manifest.json`. Draft releases carry no Actions-storage retention window;
they persist until the evidence GC (`evidence-gc.yml`, keep-3-per-lane) collects
them. The cohort manifest binds the source commit, version, filenames, and SHA-256
digest of every distribution file. The publication authority consumes those retained
bytes without rebuilding them.

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
  `cadrumo-mcp` launcher supplied by `cadrumo[agent]`.
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

### Operator actions (OP-9)

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

Verify afterwards, rather than assuming — a settings change leaves no commit, so
nothing in the tree records whether it happened:

```bash
uv run --no-sync python -m dev.release.environment_inventory
```

It reads the live environments and reports each one's rule set. It is read-only and
carries no mutation path. An environment it cannot read is reported `UNKNOWN`, never
as satisfied, and the command exits non-zero in that case so an unreachable forge is
never mistaken for a discharged obligation.

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

### Stage 0: version + tag

Run every command from the repository root on a clean `main` branch.

**The bump is the first act of a release cycle, not a step you reach later.** A
cohort is stamped with whatever version the declarations hold when it is built,
so building before bumping mints a cohort under the previous release's number.
That is not a recoverable mistake once anything ships: a package index upload is
permanent, and the number is burned whether or not the upload was intended.

The version is computed, never chosen. `release-please` derives it from
conventional-commit history against the floor recorded in
`.release-please-manifest.json`; with `bump-minor-pre-major` a feature commit
takes the next minor. Do not hand-pick a number to match an expectation.

Two guards enforce this and both refuse rather than warn:

- The cohort seal step refuses to build a version any destination already owns,
  so a skipped bump is caught when the cost is one re-run.
- Publication Gate 2 asks the same question again immediately before the first
  write, covering the case where a cohort was sealed earlier and dispatched
  later.

Both consult `dev/release/burned_versions.json`, an append-only ledger of
numbers that may never be minted again. A version enters it whenever an outward
artefact carrying it is deleted, **in the same change as the deletion** —
disposing of an artefact and burning its number are one act, never two. The
ledger exists because deleting a release erases the destination-side evidence
that the number was ever exposed, while anyone who fetched those bytes still
holds them.

1. Update `main` and run the pre-bump subset of the readiness gate:

   ```console
   git switch main
   git pull --ff-only
   just release-readiness-json
   ```

   At this point in the cycle the gate is **expected to report `"ok": false`** on the
   two cohort-bound blocking checks, `distribution-evidence-complete` and
   `generated-surface-versions`. Both require a local `var/release-cohort/` built at
   the checked-out commit and carrying the tag `v{version}`, and no such cohort
   exists until Stage 1 builds it from the tagged commit — so demanding them here
   would gate the bump on a state only a post-bump release can reach. They are the
   release gate at Stage 3, where `"ok": true` is required.

   What must hold **now** is every check that does not depend on a cohort:
   `project-names-canonical`, `version-surfaces-agree`, `changelog-ready`, and — when
   `gh` can reach the tracker — no open `priority:P0-blocker` issue. If any of those
   four fails, stop.

   The same expectation applies to `just release-apply` in step 4: it refuses on the
   identical cohort-bound check, so read its printed checklist and apply the items by
   hand.

2. Run the release and packaging checks:

   ```console
   uv sync --frozen
   just packaging-smoke-dependencies
   just packaging-smoke
   just packaging-smoke-docker
   uv run --no-sync pytest src/cadrumo/tests/test_release_config.py dev/release/tests -q
   ```

   Every command must exit zero.

3. Preview the release-please proposal:

   ```console
   just release
   ```

   The command must exit zero and create a non-empty `var/release/release-please.log`.
   Compare the proposal with every commit since the preceding tag.

4. Set one `X.Y.Z` version across all **seven** release surfaces. Run `just
   release-apply` to see the printed checklist, then apply each item by hand:

   - `.release-please-manifest.json`
   - `pyproject.toml` — `[project].version`
   - `packaging/cadrumo_data_manuals/pyproject.toml` — `[project].version`
   - `packaging/cadrumo_data_official/pyproject.toml` — `[project].version`
   - `src/cadrumo/__init__.py` — `__version__`
   - `CHANGELOG.md` — prepend the release block using the dry-run log as source
   - `uv.lock` — regenerate with `uv lock && uv lock --check`

   **Do not touch `packaging/mcpb/manifest.json`.** Its tracked `"version"` is a
   synthetic sentinel (`0.0.0`); `packaging/mcpb/build.py` stamps the real cohort
   version over it at build time, and `check_version_surfaces_agree`
   (`dev/release/readiness.py`) refuses any other tracked literal because a
   real-looking value there would masquerade as an authority. The built bundle's
   stamped version is bound to the cohort by `check_generated_surface_versions`
   instead. Bumping it fails the blocking version gate.

   Also update both exact companion dependency pins in `pyproject.toml`:
   `cadrumo-data-manuals==X.Y.Z` and `cadrumo-data-official==X.Y.Z`.

5. Rerun the readiness gate and companion parity test. Confirm
   `version-surfaces-agree` now reports the new version and still passes; the two
   cohort-bound checks named in step 1 remain expected failures until Stage 3. The
   lock check and both test commands must pass outright:

   ```console
   just release-readiness
   uv lock --check
   uv run --no-sync pytest src/cadrumo/tests/test_release_config.py dev/release/tests -q
   uv run --no-sync pytest dev/packaging/tests/test_cadrumo_data_distribution.py::test_companion_version_matches_root_distribution -q
   ```

6. Stage and commit all seven release surfaces together:

   ```console
   git add \
     .release-please-manifest.json pyproject.toml \
     packaging/cadrumo_data_manuals/pyproject.toml \
     packaging/cadrumo_data_official/pyproject.toml \
     src/cadrumo/__init__.py \
     CHANGELOG.md uv.lock
   git commit -m "chore(release): vX.Y.Z"
   ```

   If the staged diff contains any path outside those seven, stop.

### Stage 0b: release-candidate soak (non-hotfix releases)

Before pushing the final tag, run a local soak against a pre-release build. RC tags are
local only — never push an RC tag.

1. Create an annotated local tag:

   ```console
   git tag -a vX.Y.Z-rc.1 -m "Cadrumo vX.Y.Z-rc.1"
   ```

2. Run `just packaging-smoke` and `just packaging-smoke-docker` against the tagged
   commit. Both commands must exit zero. Every manifest they create must contain
   `"ok": true`.

3. Install the built core wheel into a clean scratch environment. Configure a new local
   storage root so the probe starts with fresh Cadrumo state. Use only fictional
   taxpayer data. If Cadrumo detects former-product state or any existing taxpayer
   profile, stop.

4. Run the installed probes in this order:
   - `aeat --version` must print `CADRUMO X.Y.Z`.
   - `aeat --help` must exit zero and display the `config` and `app` roots.
   - A representative human workflow must run through `aeat` and report its output
     path, byte size, and SHA-256 digest.
   - When the `agent` extra is installed, the plugin launcher must invoke `cadrumo-mcp`
     without a missing-extra refusal.

5. Record every probe command, exit status, and visible result. Missing output, real
   taxpayer data, or former-product state fails the candidate.

6. Hold for at least 48 hours. If any packaging lane turns red, a `priority:P0-blocker`
   issue opens, or the changelog omits a user-visible change since the preceding tag,
   stop. Fix forward, delete only the local RC tag, and restart as `vX.Y.Z-rc.2`.

7. When every condition passes, create the final tag and push:

   ```console
   git tag -a vX.Y.Z -m "Cadrumo vX.Y.Z"
   git push origin main
   git push origin refs/tags/vX.Y.Z
   ```

Emergency hotfixes may skip the soak. Use the cycle times in
`docs/_release_checklist.yaml` and record the exception.

### Stage 1: build + prove

The push to `main` automatically triggers the `Cadrumo Packaging Smoke` workflow
(`.github/workflows/packaging-smoke.yml`). Wait for the run to go fully green. It runs:

- Three per-OS smoke legs (Linux X64, Windows X64, macOS ARM64) proving wheel
  installation, bundled data, extras, split, and browser lanes.
- `build-release-cohort`: builds the **one immutable release cohort** on exactly
  CPython 3.13, under any uv, from a fresh clean clone with `SOURCE_DATE_EPOCH` and
  `PYTHONHASHSEED=0`. The uv version is recorded in the cohort's build identity
  rather than pinned, so reproducibility is checked by comparing build identities
  instead of being enforced by refusing to build when the toolchain moves. The cohort holds 13 files: 6 Python dist files,
  `python-cohort.json`, 2 Claude plugin zips, `cadrumo.json` (Scoop manifest),
  `cadrumo.rb` (Homebrew formula), `cadrumo-X.Y.Z.mcpb`, and `release-cohort.json`.
  The cohort id is a SHA-256 over the complete artifact set; CI never rebuilds these
  bytes. The job creates the run's draft evidence release `evidence-smoke-<run id>`
  (the sole creator) and publishes the cohort as `cadrumo-release-cohort.tar.gz`.
- Three `oracle-emit-*` legs: each downloads that single cohort archive from the
  run's evidence draft, installs its wheels into a fresh venv, runs the grounded CLI
  and MCP tax oracles (Modelo 200 `DP200014:00562 == 23000.00` per the readiness
  ADR), and mints one sanctioned `DistributionEvidence` row (`python-linux-x86-64`,
  `python-windows-x86-64`, `python-macos-arm64`) onto the same draft.
- `seal-evidence-manifest`: hashes the draft's complete asset set and seals
  `evidence-manifest.json` binding the run identity to every asset digest.

**Note the run id** of the successful smoke run. It is the identity anchor for every
subsequent dispatch and for the final publish dispatch. Evidence drafts have no
Actions-storage retention window, but the evidence GC keeps only the newest three per
lane — promote (or protect the draft via the GC's keep-tags input) before it ages out
of the keep window.

### Stage 2: channel acquisition proofs

Dispatch the three acquisition workflows with the smoke run id and head commit SHA. In
the GitHub Actions UI, or via the CLI:

```console
gh workflow run packaging-scoop.yml \
  -f source_run_id=<SMOKE_RUN_ID> -f source_commit=<HEAD_SHA>

gh workflow run packaging-homebrew.yml \
  -f source_run_id=<SMOKE_RUN_ID> -f source_commit=<HEAD_SHA>

gh workflow run packaging-claude.yml \
  -f source_run_id=<SMOKE_RUN_ID> -f source_commit=<HEAD_SHA>
```

Each workflow verifies source-run identity (success, `packaging-smoke.yml`, `push`,
`main`, same repo, matching `head_sha`) before proceeding.

- `packaging-scoop.yml` (self-hosted Windows, native, pinned to the
  `windows-scoop`-labelled runner so it lands in the dedicated non-admin runner
  user's own Scoop profile and never touches the fleet's Docker daemon):
  hash-verifies and installs
  the smoke draft's cohorts, generates the Scoop manifest, runs the oracles, and
  publishes the `scoop-windows-x86-64` `DistributionEvidence` row onto its own sealed
  draft `evidence-scoop-<run id>`.
- `packaging-homebrew.yml` (matrix: self-hosted macOS ARM64, Linux X64, and
  Linux ARM64; macOS Intel is not a supported platform): installs from the tap
  snapshot on each platform, runs the oracles, and publishes its
  `homebrew-<os>-<arch>` `DistributionEvidence` row per matrix row onto the
  single sealed draft `evidence-homebrew-<run id>`.
- `packaging-claude.yml` (self-hosted Windows): runs a live Claude Code session and
  the MCPB runtime oracle; produces lane evidence, not `DistributionEvidence` rows.

**Operator real-client captures (4 claude rows):** The four `claude-*` evidence rows
require real client installations performed by a human. The honesty guard in
`dev/packaging/distribution_evidence_emit.py` refuses SDK-driven runs. Run one capture
per row using:

```console
uv run --no-sync python -m dev.packaging.emit_real_client_evidence <args>
```

Refer to the module's docstring for per-row arguments and the required isolation proof.

The 48-72 hour soak window covers the time needed for the channel proof runs and
real-client captures.

### Stage 3: readiness aggregation

The readiness gate (`just release-readiness-json`, backed by `dev/release/readiness.py`)
requires a passing `DistributionEvidence` row in `var/distribution-install-readiness/`
for every row the **claimed** channels own — the union over channels marked
`availability = "available"` in `docs/_data/download_channels.toml`, floored at the
language-native registry (`required_evidence_rows`, `dev/docs/download_matrix.py`) —
alongside a local `var/release-cohort/` at the release commit and tag.

The table below lists all eleven rows any channel *can* produce; it is not the
obligation. Flipping a channel to `available` immediately re-arms every row it owns,
so confirm the live required set before collecting:

```console
uv run --no-sync python -c "from dev.release.readiness import REQUIRED_DISTRIBUTION_ROWS; print(REQUIRED_DISTRIBUTION_ROWS)"
```

| Row | Emission path | CI automated? |
| --- | --- | --- |
| `python-linux-x86-64` | `oracle-emit-linux` job in packaging-smoke | Yes |
| `python-windows-x86-64` | `oracle-emit-windows` job in packaging-smoke | Yes |
| `python-macos-arm64` | `oracle-emit-macos` job in packaging-smoke | Yes |
| `scoop-windows-x86-64` | `packaging-scoop.yml` (row asset on `evidence-scoop-<run id>`) | Yes |
| `homebrew-macos-arm64` | `packaging-homebrew.yml` per-row emit | Yes |
| `homebrew-linux-x86-64` | `packaging-homebrew.yml` per-row emit | Yes |
| `homebrew-linux-arm64` | `packaging-homebrew.yml` per-row emit | Yes |
| `claude-code-plugin` | Operator: `emit_real_client_evidence` | Manual (operator real-client capture) |
| `claude-cowork-plugin` | Operator: `emit_real_client_evidence` | Manual (operator real-client capture) |
| `claude-desktop-plugin` | Operator: `emit_real_client_evidence` | Manual (operator real-client capture) |
| `claude-desktop-mcpb` | Operator: `emit_real_client_evidence` | Manual (operator real-client capture) |

**Aggregating the rows:** the seven CI-minted rows (three `python-*`, `scoop-windows-x86-64`,
three `homebrew-*`) ride their runs' draft evidence releases
(`evidence-<lane>-<run id>`) as flat `{row_id}-{evidence_id}.json` assets. Collect
them into `var/distribution-install-readiness/` with:

```console
just release-collect-evidence <smoke-run-id> <scoop-run-id> <homebrew-run-id>
```

The four `claude-*` rows are minted locally by the operator's `emit_real_client_evidence`
runs above and already live in that directory. Once every required row is present, verify:

```console
just release-readiness-json
```

The JSON must report `"ok": true` with `distribution-evidence-complete` PASS before
proceeding to Stage 4.

### Stage 4: dispatch the publication workflow

First transport the four operator-minted `claude-*` rows into CI: upload the local
records to a release the publish workflow can pull (a draft is fine), for example

```console
gh release create vX.Y.Z-evidence --draft --notes "claude-* rows" \
  var/distribution-install-readiness/claude-*.json
```

Then dispatch `Publish Cadrumo release`. Gate 2 **derives** which acquisition inputs a
release actually needs from the channels that release claims, so supply only those and
leave the rest empty — an input the release does not claim is not an omission. A
descriptor claiming the python (registry) channel alone carries `packaging_run_id` and
nothing else. The full four-input form below applies only when the release claims the
Scoop, Homebrew and Claude channels too: the smoke run (3 python rows + sealed cohort),
the Scoop and Homebrew acquisition runs from Stage 2 (their rows), and the evidence
release tag above:

```console
gh workflow run publish-release.yml \
  -f packaging_run_id=<SMOKE_RUN_ID> \
  -f scoop_run_id=<SCOOP_RUN_ID> \
  -f homebrew_run_id=<HOMEBREW_RUN_ID> \
  -f claude_evidence_release=vX.Y.Z-evidence
```

**Dispatch ceiling.** Every source the publish workflow pulls from is a draft
evidence release (`evidence-<lane>-<run id>`, plus the operator's `claude-*` evidence
release). Drafts have no Actions-storage retention window, but the evidence GC
(`evidence-gc.yml`) keeps only the newest three drafts per lane; a superseded draft
that has been collected is gone. Dispatch the publication while every source draft
still exists (protect a slow promotion's drafts via the GC's keep-tags input); if a
source draft was collected, Gate 2 fails on the missing draft — re-run a fresh smoke
run (and the affected acquisition dispatches) and dispatch again against the new run
ids.

Gate 2 derives each lane's evidence tag from its run-id input, downloads and
hash-verifies every draft's assets against its sealed `evidence-manifest.json` and
the Actions API run record, checks each acquisition run's identity, and re-verifies
every required row against the sealed cohort — so the local
`just release-collect-evidence` count is reproduced hard in CI, never trusted.

The workflow runs three sequential jobs:

**Gate 1 — prerequisite check.** Confirms the `release` environment carries a
required-reviewer rule, since that approval click is the human release gate.
Fails closed on a real publication; a dry run warns and proceeds.

**Gate 2 — validate (no rebuild).** Verifies the source run identity (success,
`packaging-smoke.yml`, `push`, `main`, same repo, matching `head_sha`) and, with parity
checks, each acquisition run (`packaging-scoop.yml` / `packaging-homebrew.yml`,
`workflow_dispatch`, same repo, success). Downloads and hash-verifies the **sealed**
release cohort archive (`cadrumo-release-cohort.tar.gz` from the smoke evidence draft
— the single source of every channel's bytes, PyPI included) and aggregates every
required `DistributionEvidence` row from its authoritative draft — up to 3 python from
the smoke draft, 1 scoop, 3 homebrew, and the 4 operator `claude-*` rows, as the
claimed channels demand — from the evidence release. The per-OS smoke build cohorts are deliberately NOT part of the
publication chain. Re-points `promote_python_cohort --emit-version-only` at the sealed
cohort's `python/` bytes to guard the PyPI version against overwrite and emit the
version. Runs `dev.release.readiness --json --skip-network --cohort-dir
var/promotion/release-cohort --evidence-dir var/promotion/evidence/rows`; the sealed
cohort's installed behaviour is proven per-OS by the `DistributionEvidence` rows, not
by the smoke build. Gate 2 passes only with every required row present and verified.

**Gate 3 — publish** (`environment: release`, human approval required). After the
approval click, the job re-downloads and re-verifies the sealed cohort archive and
every evidence row/manifest from the same drafts (never rebuilds), runs the
fail-closed `evidence_release leak-sweep` over everything about to be attached
(residual runner metadata hard-fails the promotion), and:

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

### Stage 5: reacquisition and docs unlock

After publication, run the reacquisition lanes to prove each channel serves the correct
cohort and to unlock the docs-claims gate
(`dev/docs/tests/test_distribution_claims.py`):

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
docs-claims gate fails any README or docs page that advertises a channel without a
passing reacquisition row for that channel. Land install-claim docs updates only after
all applicable reacquisition lanes pass.

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

Once the deploy role exists (operator decision OP-3), the `Cadrumo Docs Publish`
workflow runs this automatically on `release: published` and this step becomes a
verification rather than an action. Until then it is a human act, and a release
left without it is not finished — it is a release whose documentation still
advertises its predecessor.

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
