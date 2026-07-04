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

Run from a clean `main` checkout, in order. Stop at the first failure. The
full machine-validated checklist data (soak window, versioning discipline,
hotfix cycle times, rollback triggers) lives at
`docs/_release_checklist.yaml`; this section is the human-run sequence.

1. **Audit-state gate** — `just release-readiness` (or
   `just release-readiness-json` for a machine-readable verdict). Checks
   version-surface parity, `CHANGELOG.md` sanity, the most recent
   packaging-smoke evidence, and (best-effort via `gh`) that no open GitHub
   issue carries `priority:P0-blocker`. Read-only; no outward action. A
   blocking failure must be resolved before continuing — `just
   release-apply` runs this gate automatically and refuses to proceed on a
   blocking failure.
2. **Version + changelog** — `just release` (dry-run preview), then
   `just release-apply` and follow its printed checklist: bump
   `.release-please-manifest.json`, `pyproject.toml`,
   `src/aeat/__init__.py`, prepend `CHANGELOG.md`, commit
   `chore(release): vX.Y.Z`, tag `vX.Y.Z`. Also bump the synced version in
   BOTH `packaging/aeat_data_manuals/pyproject.toml` and
   `packaging/aeat_data_official/pyproject.toml` (the parity test fails the
   suite if either drifts).
3. **Gates** — `just packaging-smoke-dependencies`, `just check-dependencies`,
   `just packaging-smoke` (full lane on Linux/WSL; includes the split-install
   lane proving the companion-absent advisory path and the both-companions
   byte-identical path), and the plugin gate
   `uv run --no-sync python dev/packaging/smoke_plugin_validate.py`.
4. **RC soak (non-hotfix releases)** — build a local pre-release
   (`vX.Y.Z-rc.N`), run the full `just packaging-smoke` matrix against it,
   and install the built wheel into a scratch venv for a 48-72h review
   window before pushing the real tag. See "Release-candidate soak" below.
   Skip this step only for an emergency hotfix (see the cycle times in
   `docs/_release_checklist.yaml`).
5. **Push the release commit + tag** — human decision only:
   `git push origin main --tags`.
6. **Publish `aeat-cli`** — `UV_PUBLISH_TOKEN=... just publish
   yes-publish-to-pypi`. Verify the version page renders on pypi.org and
   `uvx --from aeat-cli==X.Y.Z aeat --version` resolves on a machine without the checkout.
7. **Publish the data companions** — `just publish-data yes-publish-to-pypi`
   (builds and uploads both `aeat-data-manuals` and `aeat-data-official` in one
   gated run; no grant needed). Verify `pip install "aeat-cli[corpus-sources]"`
   pulls both and `aeat app registry verify` runs clean.
8. **Regenerate + push the plugin/marketplace** — materialise the plugin
   tree pinned to the just-published version
   (`uv run --no-sync aeat app agent --layout plugin -o <marketplace
   checkout>/plugins/aeat`), run `claude plugin validate --strict` on it,
   commit and push the marketplace repository. Installed plugins update on
   the version bump.
9. **Announce** — update `docs/updates.md` per its critical-updates
   contract if the release changes filing behaviour, using
   `docs/_release_notes_template.md` as the GitHub Release body template.

## Release-candidate soak

Every non-hotfix release soaks for 48-72 hours before the tag is pushed and
published. `aeat-cli` is pre-1.0 and has not shipped its first PyPI release
yet, so there is no separate `aeat-cli-beta` PyPI project to soak against
today; the soak vehicle is a local, tagged pre-release build reviewed before
the real tag lands:

1. Tag a local pre-release: `git tag -a vX.Y.Z-rc.1 -m "aeat vX.Y.Z-rc.1"`
   (not pushed).
2. Run the full packaging-smoke matrix against it (`just packaging-smoke`
   on Linux/WSL; `just packaging-smoke-docker` for the clean-image lane).
3. Install the built wheel into a scratch venv
   (`uv venv /tmp/aeat-rc && uv pip install --python /tmp/aeat-rc/bin/python
   dist/aeat_cli-*.whl`) and exercise the CLI manually against a scratch
   profile.
4. Hold for 48-72 hours. Exit gates: the packaging-smoke matrix stays
   green, no `priority:P0-blocker` issue is opened against the RC build,
   and the changelog entry is reviewed against the conventional-commit log
   since the last tag.
5. If the soak passes, proceed to step 5 of the per-release checklist
   (push the real tag). If it fails, fix forward and restart the soak with
   `vX.Y.Z-rc.2`.

Once the first stable PyPI release ships and there is a real user base to
protect, promote this to a real `aeat-cli-beta` PyPI project (a genuine
pre-release channel Kent can opt into) rather than a purely local build.

## Rollback procedure

Trigger a rollback when any of these hold (see `docs/_release_checklist.yaml`
`rollback.triggers` for the machine-readable list): data loss or corruption,
a disclosed security vulnerability, a widespread regression, or a
compatibility mis-computation (a supported Python/OS/dependency combination
fails after the release).

`just release-rollback X.Y.Z` prints the full step-by-step procedure for the
given version (read-only — it never runs a destructive action itself). In
outline:

1. Revert the release commit and tag on `main`
   (`git revert --no-commit <sha>`, commit, tag `vX.Y.Z-rollback`, push —
   every step is human-run).
2. **Yank** the bad version from PyPI
   (pypi.org project page → the release → Options → Yank release). Yanking
   does not delete the artifact; it stops `pip`/`uv` from resolving it by
   default so new installs and unpinned upgrades skip it, while an operator
   who explicitly pinned the bad version can still reach it if truly needed.
3. Publish a corrected patch release following the emergency hotfix cycle
   time for the trigger category (`docs/_release_checklist.yaml` `hotfix`:
   24h for security/data-loss, 48h for portal-drift, 72h for other
   critical issues).
4. Update `docs/updates.md` per its critical-updates contract and note the
   rollback plus the corrected version in the GitHub Release notes.

## What is deliberately out of scope

- **Automatic release triggers** — publish.yml runs on manual dispatch
  only; tag-push or scheduled publishing stays out.
- **Live AEAT anything** — releases never touch AEAT services; the
  application never files live.
- **Automatic rollback execution** — `just release-rollback` only prints
  the procedure; every revert, tag, push, and PyPI yank is a deliberate
  human action.
