# Releasing `aeat-cli`

Every release is HUMAN-GATED: no automation pushes, no tokens live in the
repository. Two publish lanes exist, both human-triggered: the local
`just publish` recipes (token via `UV_PUBLISH_TOKEN`), and the
operator-approved Trusted Publishing workflow (`.github/workflows/publish.yml`,
manual `workflow_dispatch` only, PyPI environment `pypi`, registered by the
operator as the project's pending publisher on 2026-07-03). The release lane joins three surfaces that already exist —
release-please versioning (`just release` / `just release-apply`), the
packaging smoke lanes (`just packaging-smoke*`), and the publish recipes
(`just publish` / `just publish-data`) — plus the Claude plugin/marketplace
push.

The project ships as three PyPI distributions built from the one source tree:

- **`aeat-cli`** — the product (import package and CLI stay `aeat`): code, extracted legal text, normative html,
  registry, terminology, and the agent harness. Slim (~40 MB), under PyPI's
  100 MB default file cap; no size grant needed.
- **`aeat-data-manuals`** and **`aeat-data-official`** — the corpus source
  binaries (official AEAT PDF/XLS/XLSX), split along the corpus directory seam
  into two sub-cap companions so each wheel stays under the 100 MB cap and NO
  size grant is required: `aeat-data-manuals` ships `corpus/manuals` (~77 MB
  wheel), `aeat-data-official` ships `corpus/aeat_official` + `corpus/normatives`
  (~62 MB wheel). Both are built from `packaging/aeat_data_manuals/` and
  `packaging/aeat_data_official/`, contribute subtrees to the same `aeat_data`
  namespace package, and are consumed together via the `aeat-cli[corpus-sources]`
  extra. Without both installed, the registry integrity gate surfaces a loud
  advisory and the `aeat app registry` verification verbs refuse with the
  install hint; every other surface is unaffected.

## One-time setup (first release only)

Create a PyPI account, then an API token. Until the projects exist the token
is account-scoped; after the first upload, replace it with per-project scoped
tokens. Put the token in the `UV_PUBLISH_TOKEN` environment variable for the
publish session only — never in a file, never in the repo.

## Name claim sequencing (first release)

Each name is claimed by its first upload (the operator registered `aeat-cli` as
the Trusted Publishing pending project). Because both data companions are sub-cap
there is no size grant on the critical path, so the order is simply:

1. Publish the slim `aeat-cli` wheel first (`just publish yes-publish-to-pypi`).
   It is under every default limit; this claims the name and creates the
   project.
2. Publish both data companions (`just publish-data yes-publish-to-pypi`, which
   builds and uploads `aeat-data-manuals` and `aeat-data-official` in one gated
   run). Each wheel is under the 100 MB cap, so the first upload of each claims
   its name and creates its project with no prior placeholder or grant needed.

The plugin delivery is NOT blocked on the data companions: the plugin's server
runs from the slim `aeat-cli` wheel; the companions only feed the registry
verification verbs and byte-provenance surfaces.

## No file-size grant needed

The earlier plan required a PyPI per-file size grant for a single ~139 MB
`aeat-data` companion. That is retired: the corpus binaries are split along the
directory seam into two sub-cap companions (`aeat-data-manuals` ≈ 77 MB,
`aeat-data-official` ≈ 62 MB), each comfortably under PyPI's 100 MB default cap.
No `github.com/pypi/support` limit-request issue is filed, and nothing in the
release schedule waits on a grant. If a companion ever approaches the cap
(corpus growth), rebalance the seam partition or carve a third companion rather
than requesting a grant — the CI artifact guard and the distribution gate both
fail loudly at 100 MB.

## Per-release checklist

Run from a clean `main` checkout, in order. Stop at the first failure.

1. **Version + changelog** — `just release` (dry-run preview), then
   `just release-apply` and follow its printed checklist: bump
   `.release-please-manifest.json`, `pyproject.toml`,
   `src/aeat/__init__.py`, prepend `CHANGELOG.md`, commit
   `chore(release): vX.Y.Z`, tag `vX.Y.Z`. Also bump the synced version in
   BOTH `packaging/aeat_data_manuals/pyproject.toml` and
   `packaging/aeat_data_official/pyproject.toml` (the parity test fails the
   suite if either drifts).
2. **Gates** — `just packaging-smoke-dependencies`, `just check-dependencies`,
   `just packaging-smoke` (full lane on Linux/WSL; includes the split-install
   lane proving the companion-absent advisory path and the both-companions
   byte-identical path), and the plugin gate
   `uv run --no-sync python dev/packaging/smoke_plugin_validate.py`.
3. **Push the release commit + tag** — human decision only:
   `git push origin main --tags`.
4. **Publish `aeat-cli`** — `UV_PUBLISH_TOKEN=... just publish
   yes-publish-to-pypi`. Verify the version page renders on pypi.org and
   `uvx --from aeat-cli==X.Y.Z aeat --version` resolves on a machine without the checkout.
5. **Publish the data companions** — `just publish-data yes-publish-to-pypi`
   (builds and uploads both `aeat-data-manuals` and `aeat-data-official` in one
   gated run; no grant needed). Verify `pip install "aeat-cli[corpus-sources]"`
   pulls both and `aeat app registry verify` runs clean.
6. **Regenerate + push the plugin/marketplace** — materialise the plugin
   tree pinned to the just-published version
   (`uv run --no-sync aeat app agent --layout plugin -o <marketplace
   checkout>/plugins/aeat`), run `claude plugin validate --strict` on it,
   commit and push the marketplace repository. Installed plugins update on
   the version bump.
7. **Announce** — update `docs/updates.md` per its critical-updates
   contract if the release changes filing behaviour.

## What is deliberately out of scope

- **Automatic release triggers** — publish.yml runs on manual dispatch
  only; tag-push or scheduled publishing stays out.
- **Live AEAT anything** — releases never touch AEAT services; the
  application never files live.
