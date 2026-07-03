# Releasing `aeat`

Every release is LOCAL-ONLY and HUMAN-GATED: no CI publishes, no automation
pushes, no tokens live in the repository. GitHub Actions is not used for any
release step. The release lane joins three surfaces that already exist —
release-please versioning (`just release` / `just release-apply`), the
packaging smoke lanes (`just packaging-smoke*`), and the publish recipes
(`just publish` / `just publish-data`) — plus the Claude plugin/marketplace
push.

The project ships as two PyPI distributions built from the one source tree:

- **`aeat`** — the product: code, extracted legal text, normative html,
  registry, terminology, and the agent harness. Slim (~40 MB), under PyPI's
  100 MB default file cap; no size grant needed.
- **`aeat-data`** — the corpus source binaries (official AEAT PDF/XLS/XLSX,
  ~139 MB), built from `packaging/aeat_data/`, consumed via the
  `aeat[corpus-sources]` extra. Exceeds the default cap; needs a one-time
  per-file size grant (below). Without it installed, the registry integrity
  gate surfaces a loud advisory and the `aeat app registry` verification
  verbs refuse with the install hint; every other surface is unaffected.

## One-time setup (first release only)

Create a PyPI account, then an API token. Until the projects exist the token
is account-scoped; after the first upload, replace it with per-project scoped
tokens. Put the token in the `UV_PUBLISH_TOKEN` environment variable for the
publish session only — never in a file, never in the repo.

## Name claim sequencing (first release)

The `aeat` name is claimed by its first upload; PyPI grants file-size
increases only to projects that already have at least one release. The order
is therefore fixed:

1. Publish the slim `aeat` wheel first (`just publish yes-publish-to-pypi`).
   It is under every default limit; this claims the name and creates the
   project.
2. Publish a small placeholder or dev release of `aeat-data` if its wheel is
   temporarily reducible below 100 MB, or skip straight to the grant request
   citing the built artifact's real size.
3. File the `aeat-data` size grant (next section). Publish the full
   companion (`just publish-data yes-publish-to-pypi`) when granted.

The plugin delivery is NOT blocked on the grant: the plugin's server runs
from the slim `aeat` wheel; the companion only feeds the registry
verification verbs and byte-provenance surfaces.

## `aeat-data` file-size grant

File an issue at `github.com/pypi/support` using the `limit-request-file.yml`
template. Request 200 MB for the `aeat-data` project. Justification to state:
the package is a reviewed, license-clean (Apache-2.0), integrity-hashed
corpus of official Spanish tax-authority binaries (PDF/XLS) that the
application verifies byte-exactly against a registry catalogue; runtime
fetching is rejected by design (offline-verifiable legal grounding), so the
bytes must ship as a package. Precedent: `torch` (500 MB/file),
routine 150 MB grants. There is no published turnaround SLA — file the
request early and do not schedule anything against it.

## Per-release checklist

Run from a clean `main` checkout, in order. Stop at the first failure.

1. **Version + changelog** — `just release` (dry-run preview), then
   `just release-apply` and follow its printed checklist: bump
   `.release-please-manifest.json`, `pyproject.toml`,
   `src/aeat/__init__.py`, prepend `CHANGELOG.md`, commit
   `chore(release): vX.Y.Z`, tag `vX.Y.Z`. Also bump the synced version in
   `packaging/aeat_data/pyproject.toml` (the parity test fails the suite if
   they drift).
2. **Gates** — `just packaging-smoke-dependencies`, `just check-dependencies`,
   `just packaging-smoke` (full lane on Linux/WSL; includes the split-install
   lane proving the companion-absent advisory path and the companion-present
   byte-identical path), and the plugin gate
   `uv run --no-sync python dev/packaging/smoke_plugin_validate.py`.
3. **Push the release commit + tag** — human decision only:
   `git push origin main --tags`.
4. **Publish `aeat`** — `UV_PUBLISH_TOKEN=... just publish
   yes-publish-to-pypi`. Verify the version page renders on pypi.org and
   `uvx aeat@X.Y.Z --version` resolves on a machine without the checkout.
5. **Publish `aeat-data`** (when the grant is in place) —
   `just publish-data yes-publish-to-pypi`. Verify
   `pip install "aeat[corpus-sources]"` pulls it and
   `aeat app registry verify` runs grant-path clean.
6. **Regenerate + push the plugin/marketplace** — materialise the plugin
   tree pinned to the just-published version
   (`uv run --no-sync aeat app agent --layout plugin -o <marketplace
   checkout>/plugins/aeat`), run `claude plugin validate --strict` on it,
   commit and push the marketplace repository. Installed plugins update on
   the version bump.
7. **Announce** — update `docs/updates.md` per its critical-updates
   contract if the release changes filing behaviour.

## What is deliberately out of scope

- **Trusted Publishing (OIDC)** requires CI; adopting it is an
  operator-level policy decision (GitHub Actions is banned on this repo),
  not a release-lane step.
- **Live AEAT anything** — releases never touch AEAT services; the
  application never files live.
