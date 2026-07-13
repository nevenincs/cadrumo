# Releasing Cadrumo

This runbook is for maintainers who version, publish, verify, or recover a
Cadrumo release. Every push, publication, yank, and patch decision is manual.
The publish workflow uses Python Package Index (PyPI) Trusted Publishing through
OpenID Connect (OIDC). It never uses a repository token.

## Current release blockers

The canonical repository slug is **`nevenincs/cadrumo`** (operator ruling
2026-07-14; the `cadrumo/cadrumo` organization move is deferred — if it ever
happens, re-register every Trusted Publisher first, because PyPI matches the
exact owner/repository claim in the OIDC token). Public publication remains
blocked by these gates:

- Issue [#612](https://github.com/nevenincs/cadrumo/issues/612) must contain
  the complete `W05.P11.S61` external name reservation evidence — the three
  `cadrumo*` pending Trusted Publishers, marketplace identifiers, and the
  domain/trademark review — and record the gate as cleared.
- The former-name PyPI projects `aeat-data-manuals` and `aeat-data-official`
  (0.1.0–0.2.0) must be removed or fully yanked before the `cadrumo` cohort
  publishes; see "Former-name package cleanup" below.
- `W05.P13.S73` release-note command canonicalization: verified 2026-07-14 —
  `docs/_release_notes_template.md` and `docs/updates.md` already use the
  canonical surface per the `cadrumo-cli-executable` ADR (`aeat` human CLI,
  `cadrumo` package/distribution, `cadrumo-mcp` MCP command).

Don't dispatch [`.github/workflows/publish.yml`](.github/workflows/publish.yml)
until the publication gates are clear. Local builds, green tests,
name-availability searches, and a successful readiness command don't clear
external gates.

## Release authorities and references

The committed
[`cadrumo-product-rename` architecture decision record (ADR)](.vault/adr/2026-07-12-cadrumo-product-rename-adr.md)
governs product identity and the publication stop. The following sources define
the remaining release mechanics:

- [`docs/_release_checklist.yaml`](docs/_release_checklist.yaml) defines soak,
  versioning, hotfix timing, rollback triggers, and readiness checks.
- [`.github/workflows/publish.yml`](.github/workflows/publish.yml) defines the
  only OIDC publication jobs and artifact guards.
- [`.github/workflows/packaging-smoke.yml`](.github/workflows/packaging-smoke.yml)
  defines the clean Linux artifact checks and retained evidence.
- [`docs/_release_notes_template.md`](docs/_release_notes_template.md) and
  [`docs/updates.md`](docs/updates.md) are the release-note authorities; both
  were verified canonical against the `cadrumo-cli-executable` ADR on
  2026-07-14 (`aeat` human CLI, `cadrumo` distribution).
- [`SECURITY.md`](SECURITY.md) defines private vulnerability reporting.

The release comprises three version-locked PyPI distributions:

| Distribution | Contents | Installed command |
| --- | --- | --- |
| `cadrumo` | Core product wheel | `aeat` and `cadrumo-mcp`; running `cadrumo-mcp` requires `cadrumo[agent]` |
| `cadrumo-data-manuals` | Reviewed manual corpus | None |
| `cadrumo-data-official` | Reviewed official and normative corpus | None |

Version and publish all three distributions as one release cohort. The core
wheel's `corpus-sources` extra pins both companions to the same exact version.
The workflow builds one wheel per dispatch and refuses artifacts over PyPI's
100 megabytes (MB) per-file limit. The core wheel must not contain companion
sources in Portable Document Format (PDF), legacy Microsoft Excel Spreadsheet
(XLS), or Microsoft Excel Open XML Spreadsheet (XLSX) formats.

## Publication prerequisites

### Former-name package cleanup

The pre-rename companion projects `aeat-data-manuals` and `aeat-data-official`
are live on PyPI. Before publishing the `cadrumo` cohort: delete both projects
(project **Settings → Delete project**) or, if preservation is preferred, yank
every release and remove their Trusted Publishers so nothing can publish under
the former identity. Also remove any account-level *pending* publishers still
registered for former `aeat*` names. Record the action in issue #612.

### External reservation evidence

Issue #612 must identify the evidence, reviewer, and confirmation date for each
of these items:

- The PyPI names `cadrumo`, `cadrumo-data-manuals`, and
  `cadrumo-data-official`.
- The `nevenincs/cadrumo` repository position.
- The Cadrumo marketplace identifiers and executable expectations.
- Relevant domains and the Spanish and European Union trademark position.
- One PyPI Trusted Publisher for each of the three distributions.

An availability query isn't reservation evidence. If any item is missing,
ambiguous, expired, or contradicted by current external state, stop.

### Trusted Publisher configuration

Configure each PyPI project or pending project with its own Trusted Publisher.
All three registrations must use these exact values:

| Setting | Required value |
| --- | --- |
| PyPI project | The matching distribution name |
| GitHub owner | `nevenincs` |
| GitHub repository | `cadrumo` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

The GitHub `pypi` environment must exist. Required-reviewer protection is not
available for this private repository on the current billing plan, so the
human gate is the manual `workflow_dispatch` itself (issue #612 records the
acceptance); add required reviewers if the plan or visibility ever changes.
The workflow must retain `id-token: write` and `contents: read` on
the publish job. Trusted Publishing supplies a short-lived OIDC credential.
Don't create or store a PyPI application programming interface (API) token for
this release path. Don't add a PyPI token or `UV_PUBLISH_TOKEN` to GitHub, a
local file, or a maintainer profile.

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
- GitHub CLI (`gh`), authenticated to `nevenincs/cadrumo`
- Permission to push the release tag, dispatch Actions, and approve the
  `pypi` environment

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

If Python reports a version other than 3.13 or a tool is unavailable, stop. If
`gh` can't read `nevenincs/cadrumo`, stop. If the remote doesn't match the S61
evidence or `git status --short` isn't empty, stop.

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
- Cadrumo doesn't read, move, re-key, or delete former product state. It starts
  with new state or refuses detected old state.

Call this cut out in the release notes. Test the published release against a
fresh local root. Never use a maintainer's real taxpayer profile for release
verification.

## Prepare and version the release

Run every command from the repository root. If a command fails or reports an
unexpected advisory, stop.

1. Update `main`, then run the machine-readable readiness gate:

   ```console
   git switch main
   git pull --ff-only
   just release-readiness-json
   ```

   If the gate reports a blocking failure, stop. A zero exit code isn't enough:
   unavailable GitHub state and missing packaging evidence are advisories.
   If GitHub issue state is unavailable, a `priority:P0-blocker` issue is open,
   or current packaging evidence is absent or failed, stop. Independently
   confirm that issue #612 records the S61 external reservation gate as cleared.

2. Run the release and packaging checks:

   ```console
   uv sync --frozen
   just packaging-smoke-dependencies
   just check-dependencies
   just packaging-smoke
   just packaging-smoke-docker
   uv run --no-sync python dev/packaging/smoke_plugin_validate.py
   uv run --no-sync pytest src/cadrumo/tests/test_release_config.py dev/release/tests -q
   ```

   If a command fails, stop. Review the newest manifests under
   `var/packaging-smoke/`. If any exercised lane doesn't record success, stop.
   The Claude validation result must explicitly report `validated`. Treat
   `skipped`, unavailable tooling, or any indeterminate result as a failure.

3. If the `just release` target and the cleared S61 evidence both name
   `nevenincs/cadrumo`, preview the release-please proposal:

   ```console
   just release
   ```

   If the command fails or targets anything other than the repository cleared
   by S61, stop. Review `var/release/release-please.log` against the commits
   since the preceding tag. If S73 is clear, also compare the log with the
   release-notes template.

4. Set one `X.Y.Z` version in all six release surfaces:

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
   ```

   If the version, project name, lock, changelog, or tests drift, stop.

5. Commit all release surfaces together:

   ```console
   git add .release-please-manifest.json pyproject.toml packaging/cadrumo_data_manuals/pyproject.toml packaging/cadrumo_data_official/pyproject.toml src/cadrumo/__init__.py CHANGELOG.md uv.lock
   git commit -m "chore(release): vX.Y.Z"
   ```

   `uv.lock` is a mandatory release surface. Always regenerate, validate, and
   stage it. Confirm it resolves the root and both companions at `X.Y.Z`, even
   if regeneration produces no textual change. Inspect the staged diff before
   committing. If it contains any unrelated path, stop.

### Optional diagnostic: stale release-apply helper

Run `just release-apply` only as an additional readiness probe. Its printed
checklist omits the two companion versions and their exact pins. It also omits
mandatory lockfile regeneration.

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

2. Run `just packaging-smoke` and `just packaging-smoke-docker` against that
   commit. Install the built core wheel into a scratch environment and exercise
   `cadrumo` with fictional data and fresh Cadrumo state.
3. Hold the candidate for at least 48 hours. If any packaging lane fails, a
   `priority:P0-blocker` issue opens, or changelog review finds an omitted
   user-visible change, stop the soak.
4. If the soak fails, fix forward, delete only the local RC tag, and restart as
   `vX.Y.Z-rc.2`. If it passes, create the final tag:

   ```console
   git tag -a vX.Y.Z -m "Cadrumo vX.Y.Z"
   ```

Emergency hotfixes may skip the soak. Use the cycle times in
`docs/_release_checklist.yaml` and record why the exception was necessary.

## Publish with Trusted Publishing

Recheck issue #612 immediately before pushing. If S61 isn't still complete,
stop without pushing or dispatching.

1. Push only the reviewed `main` commit and the one final tag:

   ```console
   git push origin main
   git push origin refs/tags/vX.Y.Z
   ```

   Never use `git push --tags`. Confirm no `vX.Y.Z-rc.N` tag exists on the
   remote before dispatching publication.

2. Dispatch the core distribution from the final tag:

   ```console
   gh workflow run publish.yml --repo nevenincs/cadrumo --ref vX.Y.Z -f distribution=cadrumo
   ```

3. Inspect and approve the `pypi` environment deployment. Confirm the job uses
   the tagged commit, builds exactly one `cadrumo-*.whl`, passes the artifact
   guard, and obtains its PyPI credential through OIDC. If anything differs,
   stop.

4. Verify the core index entry before publishing either companion:

   ```console
   uvx --refresh --from cadrumo==X.Y.Z aeat --version
   ```

5. Dispatch and verify each companion as a separate manual job:

   ```console
   gh workflow run publish.yml --repo nevenincs/cadrumo --ref vX.Y.Z -f distribution=cadrumo-data-manuals
   gh workflow run publish.yml --repo nevenincs/cadrumo --ref vX.Y.Z -f distribution=cadrumo-data-official
   ```

   Wait for the first companion job to finish before dispatching the second.
   For each job, confirm the tag, single-wheel name, size guard, OIDC exchange,
   and PyPI project before continuing.

6. Verify all three index pages show `X.Y.Z` and their uploaded wheel hashes.
   Then verify dependency resolution and corpus integrity from the public index:

   ```console
   uvx --refresh --from "cadrumo[corpus-sources]==X.Y.Z" aeat app registry verify
   ```

   If resolution uses a local path, either companion is missing, versions
   differ, or registry verification refuses, stop.

7. Generate the Claude plugin from the published version. Run
   `claude plugin validate --strict`. Publish the marketplace change only after
   S61 confirms its external identifier. The generated plugin must invoke
   `cadrumo` or `cadrumo-mcp`, never a former product command. Require an
   explicit successful validation result. A skipped validator, missing Claude
   executable, or ambiguous result is a release failure.

8. If S73 hasn't canonicalized and verified `docs/_release_notes_template.md`
   and `docs/updates.md`, stop. After that gate, create the GitHub Release from
   the template and update `docs/updates.md` when filing behavior changes.

PyPI distributions are immutable. Never rerun a successful distribution job for
the same version. If a job's outcome is unclear, inspect PyPI before retrying.

## Report release problems

Use a public GitHub issue for packaging failures, command regressions, index
resolution failures, and documentation defects. Include the version, operating
system, Python and `uv` versions, failing command, and redacted output. Include
the Uniform Resource Locator (URL) for the workflow run. Use fictional data,
and remove taxpayer identifiers, credentials, and session state.

Treat suspected vulnerabilities, secret exposure, or taxpayer-data exposure as
private security incidents. Follow `SECURITY.md`; don't disclose technical
details in a public issue. If private vulnerability reporting is unavailable,
open only a detail-free request for private contact.

## Rollback procedure

Use rollback for data loss or corruption, a security vulnerability, a widespread
regression, or a supported-environment miscalculation.

> **Stop: the rollback helper is not authoritative.**
> `just release-rollback X.Y.Z` currently describes only the root distribution
> and prints a broad tag push. Don't rely on it until it explicitly covers all
> three distributions and pushes only named tags. Use the reviewed manual
> sequence that follows.

1. Stop announcements and marketplace promotion. Preserve workflow logs, wheel
   hashes, and the redacted reproducer.
2. For a public defect, open or update the public incident issue. For a security
   defect, keep coordination in the private channel defined by `SECURITY.md`.
3. Review and record the disposition of `cadrumo`, `cadrumo-data-manuals`, and
   `cadrumo-data-official`. Yank every affected `X.Y.Z` distribution on PyPI.
   A yank prevents default resolution but preserves the artifact for explicit
   pins and investigation. Don't delete artifacts.
4. Revert the release commit with a new commit if source rollback is required.
   Create and push only the explicit rollback marker:

   ```console
   git revert <release-commit-sha>
   git tag -a vX.Y.Z-rollback -m "Rollback Cadrumo vX.Y.Z"
   git push origin main
   git push origin refs/tags/vX.Y.Z-rollback
   ```

   Never rewrite published Git history, delete the public final tag, use
   `git push --tags`, or push an RC tag.
5. Prepare a new patch version across all three distributions. Never overwrite
   or reuse `X.Y.Z`. Apply the hotfix timing from
   `docs/_release_checklist.yaml`, then repeat readiness, packaging, publishing,
   and index verification.
6. Update the GitHub Release and `docs/updates.md` with the yank, affected scope,
   mitigation, and corrected version. Keep embargoed security details private
   until coordinated disclosure is approved.

The release tooling never files with AEAT, automatically publishes, executes a
rollback, yanks a release, or migrates former product state.
