# Releasing Cadrumo

This runbook is for maintainers who prepare, verify, or recover a Cadrumo
release candidate. Public publication is not implemented yet. The retained
candidate workflow validates tested Python artifacts but has no upload
permission, publishing environment, or package-index command.

## Current release blockers

The canonical repository slug is **`nevenincs/cadrumo`**, as declared by the
local release authorities and tooling. The `cadrumo/cadrumo` organization move
is deferred. If it ever happens, re-register every Trusted Publisher first,
because PyPI matches the exact owner and repository claim in the OIDC token.

Every PyPI publication remains blocked while the
[`S61 external reservation gate (W05.P11.S61)`](.vault/plan/2026-07-12-cadrumo-product-rename-plan.md)
is open. S61 closes only after a named reviewer
confirms the required records in the release-reservation evidence issue.

- The
  [release-reservation evidence issue #612](https://github.com/nevenincs/cadrumo/issues/612)
  must identify the evidence and reviewer. It must cover the `cadrumo`,
  `cadrumo-data-manuals`, and `cadrumo-data-official` Trusted Publishers,
  marketplace identifiers, executable expectations, domains, and trademark
  review.
- Former-name PyPI cleanup is complete. Deletion is the accepted stronger
  state, not pending yank or tombstone work. Follow
  [Former-name package cleanup](#former-name-package-cleanup) for the recorded
  completion evidence and monitor both names for reappearance.
- The
  [`S73 release-note gate (W05.P13.S73)`](.vault/plan/2026-07-12-cadrumo-product-rename-plan.md)
  remains open. It updates and verifies the release template, checklist, and
  current release evidence. It does not block PyPI publication; after all three
  PyPI distributions are published, it blocks only GitHub Release creation.

The manual [`.github/workflows/publish.yml`](.github/workflows/publish.yml)
dispatch is validation-only. It cannot publish. Local builds, green tests,
name-availability searches, and a successful readiness command do not create
publication authority.

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
- [`.github/workflows/publish.yml`](.github/workflows/publish.yml) validates a
  retained tested Python candidate and deliberately contains no publication
  job.
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

Version and publish all three distributions as one immutable tested Python
cohort. The core distribution's mandatory base dependencies pin both data
distributions to the same exact version.

A successful `Cadrumo Packaging Smoke` run builds the cohort once from a clean
source snapshot. It retains three wheels, the root source distribution,
`python-cohort.json`, and the installed CLI and MCP oracle evidence for 14
days. The manifest binds the source commit, version, filenames, and SHA-256
digest of every distribution file. A future publication authority must consume
those retained bytes without rebuilding them.

Every artifact must remain below PyPI's 100 megabytes (MB) per-file limit. The
core wheel must not contain companion sources in Portable Document Format
(PDF), legacy Microsoft Excel Spreadsheet (XLS), or Microsoft Excel Open XML
Spreadsheet (XLSX) formats.
The companion parity gate
`dev/packaging/tests/test_cadrumo_data_distribution.py::test_companion_version_matches_root_distribution`
must prove that both companion versions match the core distribution.

This workflow covers Python candidate validation only. Publication remains
blocked until the plugin, MCPB, Scoop, Homebrew, marketplace, GitHub Release,
Python, client, platform, and public-reacquisition evidence form one complete
release authority.

## Publication prerequisites

### Former-name package cleanup

The pre-rename companion projects `aeat-data-manuals` and `aeat-data-official`
were removed from PyPI on 2026-07-14: the operator deleted both projects and
their 0.1.0 and 0.1.1 releases outright and removed their Trusted Publishers,
so nothing can publish under the former identity. Both project endpoints now
return not-found.

This runbook originally prescribed the weaker action: yank every release and
preserve both project pages as tombstones. The operator chose deletion instead
and recorded the deviation on the reservation evidence issue as strictly
stronger for the cleanup goal. Accept that record as the completed state; the
one property tombstones would have added, holding the former names against
third-party re-registration, is covered instead by monitoring the former-name
endpoints for reappearance during the publication window.

If a former `aeat*` name resurfaces anywhere else, remove any account-level
pending publisher registered for it and record the action and evidence under
S61.

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

### Publication authority

No publication authority currently exists. Do not configure a workflow,
environment, local recipe, API token, or Trusted Publisher as a substitute.
The future implementation must be a protected, manual, retained-byte authority
for the complete cross-channel cohort and must pass the open distribution
readiness plan before this section gains operational commands.

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

   Update the two mandatory exact companion dependency pins in the root
   `[project].dependencies` array at the same time. Then rerun:

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
   base dependency pins, lockfile, and changelog must all name `X.Y.Z`. If any surface
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

### Optional diagnostic: release-apply helper

Run `just release-apply` as an additional readiness probe. Its printed
checklist lists all seven release surfaces, including both companion versions
and their exact pins, the mandatory `uv lock` / `uv lock --check`
regeneration, and separate `git push origin main` /
`git push origin refs/tags/vX.Y.Z` push instructions. It never prints a
broad tag push.

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

## Publication is blocked

Do not push a final release tag, dispatch an upload workflow, create a public
package release, publish a marketplace entry, or attach an extension bundle.
The current workflow may be dispatched only to validate one retained Python
candidate. It does not authorize or perform publication.

Publication instructions belong here only after the distribution readiness
plan has complete cohort, client, platform, acquisition, evidence aggregation,
protected promotion, and public reacquisition records. Until then, stop after
candidate preparation and preserve the validation evidence.

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

> **The rollback helper is a printed checklist, not an executor.**
> `just release-rollback X.Y.Z` prints separate `main` and named-rollback-tag
> pushes and all three PyPI yank locations (`cadrumo`, `cadrumo-data-manuals`,
> `cadrumo-data-official`). It stages, commits, tags, and pushes nothing
> itself. Use the reviewed manual sequence that follows; a human still runs
> and confirms each command.

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

The successful packaging-smoke run is the build authority for the retained
Python candidate. Readiness and rollback helpers perform no outward action,
and there is no local or CI package upload path. The release tooling never
files with AEAT, automatically executes a rollback, yanks a release, or
migrates former-product state. Public promotion remains unimplemented until
all release channels share one complete evidence-backed authority.
