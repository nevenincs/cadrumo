# Releasing Cadrumo

This runbook is for maintainers who version, publish, verify, or recover a
Cadrumo release. Every push, publication, yank, and patch decision is manual.
The publish workflow uses Python Package Index (PyPI) Trusted Publishing through
OpenID Connect (OIDC). It never uses a repository token.

## Current release blockers

The canonical repository slug is **`nevenincs/cadrumo`**, as declared by the
local release authorities and tooling. The `cadrumo/cadrumo` organization move
is deferred. If it ever happens, re-register every Trusted Publisher first,
because PyPI matches the exact owner and repository claim in the OIDC token.

Workflow dispatch and every PyPI publication remain blocked while the
[`S61 external reservation gate (W05.P11.S61)`](.vault/plan/2026-07-12-cadrumo-product-rename-plan.md)
is open. S61 closes only after a named reviewer
confirms the required records in the release-reservation evidence issue.

- The
  [release-reservation evidence issue #612](https://github.com/nevenincs/cadrumo/issues/612)
  must identify the evidence and reviewer. It must cover the `cadrumo`,
  `cadrumo-data-manuals`, and `cadrumo-data-official` Trusted Publishers,
  marketplace identifiers, executable expectations, domains, and trademark
  review.
- The former-name PyPI projects `aeat-data-manuals` and `aeat-data-official`
  still expose unyanked 0.1.0 and 0.1.1 releases. Yank every release, remove
  their publishers and pending registrations, and preserve the project pages
  as tombstones. Follow [Former-name package cleanup](#former-name-package-cleanup).
- The
  [`S73 release-note gate (W05.P13.S73)`](.vault/plan/2026-07-12-cadrumo-product-rename-plan.md)
  remains open. It updates and verifies the release template, checklist, and
  current release evidence. It does not block PyPI publication; after all three
  PyPI distributions are published, it blocks only GitHub Release creation.

Don't dispatch [`.github/workflows/publish.yml`](.github/workflows/publish.yml)
or publish any PyPI distribution until S61 is reviewed and closed. Local
builds, green tests, name-availability searches, and a successful readiness
command don't clear S61.

## Release authorities and references

The accepted
[`cadrumo-cli-executable` architecture decision record (ADR)](.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md)
governs product casing, imports, the `aeat` human command, and `cadrumo-mcp`.
The accepted
[`product-rename` Stage-A ADR](.vault/adr/2026-07-13-product-rename-adr.md)
governs distributions, repository, marketplace, marketing, and publication.
The superseded
[`cadrumo-product-rename` ADR](.vault/adr/2026-07-12-cadrumo-product-rename-adr.md)
does not govern active naming. The following sources define the remaining
release mechanics:

- [`docs/_release_checklist.yaml`](docs/_release_checklist.yaml) defines soak,
  versioning, hotfix timing, rollback triggers, and readiness checks.
- [`.github/workflows/publish.yml`](.github/workflows/publish.yml) defines the
  only OIDC publication jobs and artifact guards.
- [`.github/workflows/packaging-smoke.yml`](.github/workflows/packaging-smoke.yml)
  defines the clean Linux artifact checks and retained evidence.
- [`docs/_release_notes_template.md`](docs/_release_notes_template.md) and
  [`docs/updates.md`](docs/updates.md) are the release-note authorities. Their
  command canonicalization and current verification remain pending under S73.
- [`SECURITY.md`](SECURITY.md) defines private vulnerability reporting.

The release comprises three version-locked PyPI distributions:

| Distribution | Current version | Contents | Installed command |
| --- | --- | --- | --- |
| `cadrumo` | 0.2.1 | Core distribution | `aeat` and `cadrumo-mcp`; running `cadrumo-mcp` requires the `agent` extra |
| `cadrumo-data-manuals` | 0.2.1 | Reviewed manual corpus | None |
| `cadrumo-data-official` | 0.2.1 | Reviewed official and normative corpus | None |

Version and publish all three distributions as one release cohort. The core
distribution's `corpus-sources` extra pins both companions to the same version.

The workflow builds one wheel per dispatch and refuses artifacts over PyPI's
100 megabytes (MB) per-file limit. The core wheel must not contain companion
sources in Portable Document Format (PDF), legacy Microsoft Excel Spreadsheet
(XLS), or Microsoft Excel Open XML Spreadsheet (XLSX) formats.
The companion parity gate
`dev/packaging/tests/test_cadrumo_data_distribution.py::test_companion_version_matches_root_distribution`
must prove that both companion versions match the core distribution.

## Publication prerequisites

### Former-name package cleanup

The pre-rename companion projects `aeat-data-manuals` and `aeat-data-official`
are live on PyPI with unyanked 0.1.0 and 0.1.1 releases. Before publishing the
`cadrumo` cohort, yank every former release and remove their Trusted Publishers
so nothing can publish under the former identity.

Preserve both project pages as tombstones; don't delete the projects or
artifacts. Also remove any account-level pending publishers still registered
for former `aeat*` names. Record the action and evidence under S61.

### External reservation evidence

The
[release-reservation evidence issue #612](https://github.com/nevenincs/cadrumo/issues/612)
must identify a reviewer and confirmation date for every item. Accept only
records from the system that owns each name:

- **PyPI projects:** Record each project's **Publishing** page. The record must
  show the project, GitHub owner, repository, workflow filename, and environment.
- **Repository:** Record `gh repo view nevenincs/cadrumo --json nameWithOwner,url`.
  The result must report `nevenincs/cadrumo` and its GitHub Uniform Resource
  Locator (URL). A future
  transfer to another owner changes the repository slug and requires all three
  Trusted Publishers to be registered again before publication.
- **Marketplace:** Record the provider-owned listing or reservation for the
  exact marketplace and plugin identifiers. Compare those identifiers with the
  generated marketplace and plugin manifests.
- **Executables:** Record installed-wheel probes for `aeat --version` and the
  `cadrumo-mcp` launcher supplied by `cadrumo[agent]`.
- **Domains:** Record registrar or registry evidence that identifies the exact
  domain and the account that controls it.
- **Trademarks:** Record the dated Spanish Patent and Trademark Office and
  European Union Intellectual Property Office search or clearance review. Name
  the reviewer and the classes reviewed.

An availability search isn't reservation evidence. If an authoritative record
is absent, expired, or names a different owner, repository, identifier,
environment, domain, executable, or trademark scope, stop.

### Trusted Publisher configuration

Configure each PyPI project or pending project with its own Trusted Publisher.
For a pending project, PyPI identifies the publisher by GitHub owner,
repository, workflow filename, and environment. The project name isn't part of
that tuple.

Therefore, each distribution requires a distinct GitHub environment.
The workflow selects the environment from the dispatched distribution.

Register these exact values:

| PyPI project | GitHub owner | Repository | Workflow | Environment |
| --- | --- | --- | --- | --- |
| `cadrumo` | `nevenincs` | `cadrumo` | `publish.yml` | `pypi` |
| `cadrumo-data-manuals` | `nevenincs` | `cadrumo` | `publish.yml` | `pypi-data-manuals` |
| `cadrumo-data-official` | `nevenincs` | `cadrumo` | `publish.yml` | `pypi-data-official` |

All three GitHub environments must exist. On the current private-repository
billing plan, required-reviewer protection isn't available on any of them.
Therefore, manual `workflow_dispatch` is the sole human approval gate for all
three environments.

Issue #612 must record that accepted limitation. If the
billing plan or repository visibility changes, update all three environments
and this runbook before the next release.

The publish job must retain `id-token: write` and `contents: read`. Trusted
Publishing supplies a short-lived OIDC credential.
The job must publish with `uv publish --trusted-publishing always`.

Don't create or store a PyPI application programming interface (API) token for
this release path. Don't add a PyPI token or `UV_PUBLISH_TOKEN` to GitHub, a
local file, or a maintainer profile.

The `just publish` and `just publish-data` recipes are stale local-token
helpers. They can publish when deliberately invoked with a token and
confirmation, so don't run them. They remain forbidden until removed or
reconciled with the approved Trusted Publishing workflow.

Before the first public release, confirm all three pending publishers in PyPI.
After PyPI creates each project, confirm the publisher appears on that
project's **Publishing** page.

### Workstation and repository

Use a clean `main` checkout with:

- Python 3.13
- `uv`
- `just`
- Git
- Node.js and `npx`
- GitHub Command Line Interface (GitHub CLI or `gh`), authenticated to
  `nevenincs/cadrumo`
- Permission to push the release tag, dispatch Actions, and inspect all three
  publishing environments

Run these checks before release work:

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

If `python --version` doesn't report Python 3.13 or any version command exits
nonzero, stop. If `gh auth status` doesn't name an authenticated account that
can read `nevenincs/cadrumo`, stop.

If the normalized output of `git remote get-url origin` doesn't identify owner
and repository `nevenincs/cadrumo`, stop. If `git status --short` prints any
output, stop.

Don't work around a repository mismatch with a different remote or an ad hoc
release-please command.

## Hard-cut release state

Cadrumo is a hard cut, not a compatibility release:

- `aeat` is the sole human command-line interface (CLI) executable; it names
  the Cadrumo command contract (`cadrumo-cli-executable` ADR). Don't expose
  `cadrumo` as a second human executable.
- `cadrumo-mcp` is the sole Model Context Protocol (MCP) command.
- Product imports, environment variables, plugin identifiers, resource schemes,
  and local state use the Cadrumo identity.
- Agencia Estatal de Administración Tributaria (AEAT) remains the authority
  name in official endpoints, credentials, legal evidence, and registry
  classification.
- Cadrumo doesn't read, move, re-key, or delete former-product state. It starts
  with fresh Cadrumo state or refuses detected former-product state.

Call this cut out in the release notes. Test the published release against a
fresh local root. Never use a maintainer's real taxpayer profile for release
verification.

## Prepare and version the release

Run every command from the repository root. The following steps define the
required result for each command. If the observed result differs, stop.

1. Update `main`, then run the machine-readable JavaScript Object Notation
   (JSON) readiness gate:

   ```console
   git switch main
   git pull --ff-only
   just release-readiness-json
   ```

   If the JSON doesn't report `"ok": true`, stop. If any blocking check doesn't
   report `"passed": true`, stop.

   The packaging-smoke check must identify the current manifest and report
   `"passed": true`. The GitHub-backed blocker check must report no open
   `priority:P0-blocker` issue. An unavailable GitHub check or missing packaging
   evidence is an advisory in the program, but it blocks this release procedure.
   The release-reservation evidence issue must also record S61 as reviewed and
   closed.

2. Run the release and packaging checks:

   ```console
   uv sync --frozen
   just packaging-smoke-dependencies
   just check-dependencies
   just packaging-smoke
   just packaging-smoke-docker
   uv run --no-sync python dev/packaging/smoke_plugin_validate.py --json
   uv run --no-sync pytest src/cadrumo/tests/test_release_config.py dev/release/tests -q
   ```

   Every command must exit zero. Each exercised lane's newest
   `packaging-smoke-manifest.json` must contain `"ok": true` and its expected
   `lane` name. The plugin JSON must contain `"status": "validated"`.
   `"status": "skipped"`, a missing Claude executable, absent output, or a
   nonzero test result blocks the release.

3. If the `just release` target and the cleared S61 evidence both name
   `nevenincs/cadrumo`, preview the release-please proposal:

   ```console
   just release
   ```

   The command must exit zero and create a nonempty
   `var/release/release-please.log`. The log must describe a dry-run proposal
   for `nevenincs/cadrumo` on `main` and no applied change.

   Compare the proposal with every commit since the preceding tag. When S73 is
   closed, also compare it with the release-notes template. If any expected
   state is absent, stop.

4. Set one `X.Y.Z` version in all six version-source files:

   - `.release-please-manifest.json`
   - `pyproject.toml`
   - `packaging/cadrumo_data_manuals/pyproject.toml`
   - `packaging/cadrumo_data_official/pyproject.toml`
   - `src/cadrumo/__init__.py`
   - `CHANGELOG.md`

   Update the exact companion pins in the root `corpus-sources` extra at the
   same time. Then rerun:

   ```console
   just release-readiness
   uv lock
   uv lock --check
   uv run --no-sync pytest src/cadrumo/tests/test_release_config.py dev/release/tests -q
   uv run --no-sync pytest dev/packaging/tests/test_cadrumo_data_distribution.py::test_companion_version_matches_root_distribution -q
   ```

   `just release-readiness` must report `PASS` for project names, version
   surfaces, and changelog. `uv lock --check` and both test commands must exit
   zero. The core distribution, companions, manifest, import package, exact
   companion pins, lockfile, and changelog must all name `X.Y.Z`. If any surface
   names another version, stop.

5. Stage and commit all seven release surfaces together. The seventh is the
   regenerated `uv.lock`:

   ```console
   git add .release-please-manifest.json pyproject.toml packaging/cadrumo_data_manuals/pyproject.toml packaging/cadrumo_data_official/pyproject.toml src/cadrumo/__init__.py CHANGELOG.md uv.lock
   git commit -m "chore(release): vX.Y.Z"
   ```

   `uv.lock` is a mandatory release surface. Always regenerate, validate, and
   stage it. Confirm it resolves the core distribution and both companions at
   `X.Y.Z`, even if regeneration produces no textual change.

   Inspect the staged diff before committing. If it contains a path outside the
   seven paths in the staging command, stop.

### Optional diagnostic: stale release-apply helper

Run `just release-apply` only as an additional readiness probe. Its printed
checklist omits the two companion versions and their exact pins. It also omits
mandatory lockfile regeneration and prints a broad tag push. Never use that
push instruction; only named tags are allowed.

The helper doesn't edit, commit, tag, or push. Its success isn't release
approval.

```console
just release-apply
```

## Release-candidate soak

Every non-hotfix release soaks locally for 48 to 72 hours. Release-candidate
(RC) tags remain local. Never push an RC tag.

1. Create an annotated local tag:

   ```console
   git tag -a vX.Y.Z-rc.1 -m "Cadrumo vX.Y.Z-rc.1"
   ```

2. Run `just packaging-smoke` and `just packaging-smoke-docker` against the
   tagged commit. Both commands must exit zero. Every manifest they create must
   contain `"ok": true`.

3. Install the built core wheel into a clean scratch environment. Configure a
   new local storage root so the probe starts with fresh Cadrumo state. Use only
   fictional taxpayer data. If Cadrumo detects former-product state or any
   existing taxpayer profile, stop.

4. Run the installed probes in this order:

   1. `aeat --version` must print `CADRUMO X.Y.Z`.
   2. `aeat --help` must exit zero and display the `config` and `app` roots.
   3. A representative human workflow must run through `aeat` and report its
      local output path, byte size, and 256-bit Secure Hash Algorithm (SHA-256)
      digest.
   4. When the `agent` extra is installed, the plugin launcher must invoke
      `cadrumo-mcp` without a missing-extra refusal.

5. Record every probe command, exit status, and visible result. Missing output,
   real taxpayer data, or former-product state fails the candidate.

6. Hold the candidate for at least 48 hours. If any packaging lane turns red, a
   `priority:P0-blocker` issue opens, or the changelog omits a user-visible
   change since the preceding tag, stop.

7. If any soak condition fails, fix forward, delete only the local RC tag, and
   restart as `vX.Y.Z-rc.2`. If every condition passes, create the final tag:

   ```console
   git tag -a vX.Y.Z -m "Cadrumo vX.Y.Z"
   ```

Emergency hotfixes may skip the soak. Use the cycle times in
`docs/_release_checklist.yaml` and record why the exception was necessary.

## Publish with Trusted Publishing

If an immediate pre-push recheck of the
[release-reservation evidence issue #612](https://github.com/nevenincs/cadrumo/issues/612)
doesn't show S61 as reviewed and closed, don't push or dispatch a workflow.

1. Push only the reviewed `main` commit and the one final tag:

   ```console
   git push origin main
   git push origin refs/tags/vX.Y.Z
   ```

   Before running either command, confirm no `vX.Y.Z-rc.N` tag exists on the
   remote. Never use `git push --tags`.

2. Dispatch the core distribution from the final tag:

   ```console
   gh workflow run publish.yml --repo nevenincs/cadrumo --ref vX.Y.Z -f distribution=cadrumo
   ```

3. Inspect the `pypi` environment deployment. If any of these states isn't
   visible, stop:

   - The job uses the reviewed `vX.Y.Z` commit.
   - The build produces exactly one `cadrumo-*.whl`.
   - The artifact guard passes.
   - Trusted Publishing obtains the short-lived OIDC credential.
   - An authorized maintainer started the manual workflow dispatch.

4. Verify the core index entry before publishing either companion:

   ```console
   uvx --refresh --from cadrumo==X.Y.Z aeat --version
   ```

   If the command resolves from a local path, reports another version, or prints
   another product name, don't publish either companion. It must resolve from
   PyPI and print `CADRUMO X.Y.Z`.

5. Dispatch the manuals companion:

   ```console
   gh workflow run publish.yml --repo nevenincs/cadrumo --ref vX.Y.Z -f distribution=cadrumo-data-manuals
   ```

   If the job fails to use `vX.Y.Z`, build one
   `cadrumo_data_manuals-*.whl`, pass the size guard, complete the OIDC exchange,
   or publish version `X.Y.Z` to `cadrumo-data-manuals`, stop.

6. After the manuals job passes, dispatch the official companion:

   ```console
   gh workflow run publish.yml --repo nevenincs/cadrumo --ref vX.Y.Z -f distribution=cadrumo-data-official
   ```

   If the job fails to use `vX.Y.Z`, build one
   `cadrumo_data_official-*.whl`, pass the size guard, complete the OIDC exchange,
   or publish version `X.Y.Z` to `cadrumo-data-official`, stop.

7. Verify all three index pages show `X.Y.Z` and their uploaded wheel hashes.
   Then verify dependency resolution and corpus integrity from the public index:

   ```console
   uvx --refresh --from "cadrumo[corpus-sources]==X.Y.Z" aeat app registry verify
   ```

   The command must resolve the core distribution and both companions from PyPI
   at `X.Y.Z`. The registry verification must complete successfully. A local
   path, missing companion, version mismatch, or refusal blocks the release.

8. After S61 confirms the external plugin identifier, generate the Claude
   plugin from the published version. Run `claude plugin validate --strict`.

   The validator must report success. The generated MCP plugin must launch
   `cadrumo-mcp`, and every human CLI instruction must use `aeat`. A skipped
   validator, missing Claude executable, `cadrumo` human command, or ambiguous
   result blocks marketplace publication.

9. If S73 remains open, don't create the GitHub Release. After S73 closes,
   create it from the verified template. If filing behavior changed, update
   `docs/updates.md`.

10. Build the Claude Desktop extension bundle and attach it to the GitHub
    Release. The bundle self-installs `cadrumo[agent]` from PyPI via
    `uvx --from cadrumo[agent]==X.Y.Z cadrumo-mcp`, so build it only AFTER the
    core PyPI distribution is live (steps 1–7); its version and uvx pin are
    stamped from `pyproject.toml` at build time and held to the release by the
    `version-surfaces-agree` readiness gate.

    ```console
    python packaging/mcpb/build.py
    gh release upload vX.Y.Z dist/cadrumo.mcpb --repo nevenincs/cadrumo
    ```

    The build prints whether the bundle is `signed` or `UNSIGNED`. Cadrumo has no
    bundle signing identity configured, so it is UNSIGNED — attach it labeled as
    such; the builder never fabricates a signature. Confirm the attached bundle's
    pin resolves the just-published release from PyPI:

    ```console
    uvx --refresh --from "cadrumo[agent]==X.Y.Z" cadrumo-mcp --help
    ```

    The end-user story: download `cadrumo.mcpb` from the GitHub Release, open it
    with Claude Desktop, and `uv` bootstraps `cadrumo[agent]` from PyPI on first
    run — the host needs only `uv` on `PATH`, no prior `pip install`.

PyPI distributions are immutable. If a distribution job succeeded, never rerun
it for the same version. If a job's outcome is unclear, inspect its PyPI project
and release files before deciding whether a retry is safe.

## Report release problems

Use a public GitHub issue for packaging failures, command regressions, index
resolution failures, and documentation defects. Include this evidence:

- Cadrumo version
- Operating system and version
- Python version
- `uv` version
- Exact failing command
- Exit status
- Redacted standard output and standard error
- Workflow-run URL, when applicable
- Expected result and observed result

Use fictional data. Remove taxpayer identifiers, credentials, tokens, local
paths that identify a person, and session state.

If the problem involves a suspected vulnerability, secret exposure, or taxpayer
data, treat it as a private security incident. Follow `SECURITY.md` and don't
disclose technical details in a public issue. If private vulnerability reporting
is unavailable, open only a detail-free request for private contact.

## Rollback procedure

Use rollback for data loss or corruption, a security vulnerability, a widespread
regression, or a supported-environment miscalculation.

> **Stop: the rollback helper is not authoritative.**
> `just release-rollback X.Y.Z` currently describes only the core distribution
> and prints a broad tag push. Until it explicitly covers all three distributions
> and pushes only named tags, don't rely on it. Use the reviewed manual sequence
> that follows.

1. Stop announcements and marketplace promotion.

2. Preserve the workflow logs, wheel hashes, and redacted reproducer.

3. If the defect is public, open or update the public incident issue. If it is
   a security defect, coordinate through the private channel in `SECURITY.md`.

4. Review and record the disposition of each affected distribution:
   `cadrumo`, `cadrumo-data-manuals`, and `cadrumo-data-official`.

5. Yank `X.Y.Z` for every affected distribution. A yank prevents default
   resolution but preserves the artifact for explicit pins and investigation.
   Don't delete releases or project-page tombstones.

6. If source rollback is required, revert the release with a new commit. Then
   create and push only the explicit rollback marker:

   ```console
   git revert <release-commit-sha>
   git tag -a vX.Y.Z-rollback -m "Rollback Cadrumo vX.Y.Z"
   git push origin main
   git push origin refs/tags/vX.Y.Z-rollback
   ```

7. Never rewrite published Git history, delete the public final tag, use
   `git push --tags`, or push an RC tag.

8. Prepare a new patch version across all three distributions. Never overwrite
   or reuse `X.Y.Z`. Apply the hotfix timing from
   `docs/_release_checklist.yaml`, then repeat readiness, packaging, publishing,
   and index verification.

9. Update the GitHub Release and `docs/updates.md` with the yank, affected scope,
   mitigation, and corrected version. Until coordinated disclosure is approved,
   keep embargoed security details private.

The approved OIDC workflow is human-dispatched and never publishes
automatically. Readiness and rollback helpers perform no outward action. The
stale token-based publish helpers can publish when deliberately invoked and are
forbidden pending removal or reconciliation. The release tooling never files
with AEAT, automatically executes a rollback, yanks a release, or migrates
former-product state.
