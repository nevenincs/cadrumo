---
tags:
  - '#research'
  - '#account-distribution-standard'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:639d5d7e7ea4487da0dffd5ead5b91a31be43e784830b57093c58dbacfdf4cb3'
related:
  - '[[2026-07-25-distribution-repo-topology-adr]]'
  - '[[2026-04-12-release-please-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---

# `account-distribution-standard` research: `What each nevenincs product actually publishes, measured against what its workflows claim`

The account ships five products whose distribution setups were built independently
and share no mechanism, no naming convention, and no repository topology. The
question this record answers is narrow and factual: for each product, what does
it actually publish, what does it merely claim to publish, and where do the five
diverge. It exists because a standard cannot be chosen from workflow filenames —
a workflow that has never executed looks identical, in a directory listing, to
one that ships every release.

The measurement is deliberately behavioural. For every product the run history
was read through `gh run list --json workflowName,conclusion,event`, the release
assets through `gh release view --json assets`, and the registry presence through
a direct fetch of the package index. A workflow with zero runs is reported as
zero runs regardless of how complete its YAML is.

The headline finding inverts the intuitive reading of the account. Ranked by
machinery, the order is `cadrumo` (8 distribution workflows, ~40 packaging
modules), `vaultspec-dashboard` (11 workflows), `vaultspec-core` (3),
`vaultspec-rag` (2), `vaultspec-a2a` (0). Ranked by what a user can actually
install, the order reverses almost exactly: the two products with the least
machinery are the only two on the package index, and the two with the most
publish nothing at all.

## Findings

### The two products that ship converge on one three-file mechanism

`vaultspec-core@0.1.51` and `vaultspec-rag@0.3.9` are both live on the package
index. Both reach it the same way, through three files and no stored credential.

`release-please-config.json` plus `.release-please-manifest.json` own the version
as a single source of truth; `release-type: python` lets the tool write the number
directly into `pyproject.toml`. A `release-please.yml` on `push: branches: [main]`
maintains a release pull request, and on merge — when `release_created == 'true'`
— it *explicitly dispatches* the publish workflow rather than relying on the tag
it just created:

```yaml
- name: Trigger Publish workflow
  if: steps.release.outputs.release_created == 'true'
  run: |
    gh workflow run Publish --repo "$GITHUB_REPOSITORY" --ref main \
      --field tag="${{ steps.release.outputs.tag_name }}"
```

The explicit dispatch is load-bearing, not stylistic: a tag pushed by the
`GITHUB_TOKEN` inside an action does not itself trigger `push: tags` workflows.
`vaultspec-rag` still declares a `push: tags: "vaultspec-rag-v*"` trigger, and
its run history shows every publish arriving as `workflow_dispatch` and none as
`push` — the tag trigger is dead weight that survives because the dispatch path
masks its inertness.

`publish.yml` is then a three-job chain: `build` (`uv build`), `smoke-test`
(`uv run --isolated --no-project --with dist/*.whl tests/smoke_check.py` — the
built artifact is installed and executed standalone before anything is
published), and `publish-pypi` under `environment: {name: pypi}` with
`permissions: {id-token: write}` running `uv publish`. Authentication is OIDC
trusted publishing throughout; neither repository holds a publishing token.

### The shipping mechanism has no CI gate of its own, and one product has none at all

Neither publish path re-runs the test suite. Greenness is expected to be enforced
upstream, at the moment the release pull request merges. For `vaultspec-core`
that expectation holds: `gh api repos/nevenincs/vaultspec-core/rules/branches/main`
returns a ruleset with eight required status checks. For `vaultspec-rag` the same
query returns `[]` — no ruleset exists, so nothing structurally prevents a merge,
and therefore a publish, on red CI. Two pipelines described as near-identical
diverge on the only gate either of them has.

### `vaultspec-core` already ships more channels than a filename count reveals

A count of distribution workflows put `vaultspec-core` at two. It has three, and
the third is the interesting one. `binaries.yml` matrix-builds standalone
executables for four targets via PyApp, attaching eight assets to each release —
`vaultspec-core` and `vaultspec-mcp`, each for `aarch64-apple-darwin`,
`x86_64-apple-darwin`, `x86_64-pc-windows-msvc`, `x86_64-unknown-linux-gnu` — plus
`SHA256SUMS`. It then rewrites and commits `bucket/vaultspec-core.json`, an
in-repository Scoop manifest, guarded against a backward version bump.

So the working reference implementation already demonstrates registry publication,
standalone binaries, and a package-manager manifest, and does it in three files.
This matters to the standard: the gap between the shipping products and the
non-shipping ones is not that the shippers attempt less, it is that everything
they attempt is wired end to end.

### `vaultspec-dashboard` has the most machinery and the least output

Six of its eleven workflows have never executed once: `product-release`,
`winget-publish`, `scoop-bump`, `channel-publish-gate`, `a2a-channel-feasibility`,
`a2a-product-contract`. Of the five that do run, `engine-ci` and `quality-gates`
are majority-failure over recent history.

Its latest release, `v0.1.4`, carries zero assets; the tag-push `Release` run for
it failed. Releases `v0.1.0` through `v0.1.3` do carry full asset sets, produced
by an older cargo-dist pipeline that the never-executed `product-release.yml` was
built to replace. The replacement's compose step is a hard-coded refusal, and
`winget-publish.yml`'s submission step is a stub:

```powershell
Write-Error "winget-publish: MSI artifact and winget-pkgs fork/token (cross-repo) are pending; no submission performed"
exit 1
```

`bucket/vaultspec.json` carries an all-zero placeholder digest and points at
`vaultspec-0.1.2-x86_64-pc-windows-msvc.zip`, a filename the never-run
`product-release.yml` would have produced — no asset of that name has ever
existed. The absence of the package from the Python index is not a broken
pipeline: `pyproject.toml` declares `[tool.uv] package = false` and states the
wheel was retired in favour of the Rust engine plus embedded SPA.

The one genuinely operational output is the community Windows package
`nevenincs.vaultspec@0.1.0`, whose installer manifest resolves to
`https://github.com/nevenincs/vaultspec-dashboard/releases/download/v0.1.0/vaultspec-cli-x86_64-pc-windows-msvc.zip`
— a real, still-present asset from the retired cargo-dist pipeline. It was
submitted outside this repository's tooling: the in-repo manifests under
`packaging/winget/` are authored as `vaultspec.vaultspec.*`, an identifier that
has never been published.

### The generic publisher namespace is held by the dashboard, not by core

`nevenincs.vaultspec` resolves to `vaultspec-dashboard`, confirmed by both the
installer URL above and the locale manifest's `ShortDescription: Unified
dashboard UI for the vaultspec ecosystem`. The nearest-neighbour product,
`vaultspec-core`, publishes a CLI literally named `vaultspec-core`, and the
dashboard's own binary is `vaultspec.exe`.

The consequence is a namespace collision that is cheap to fix now and permanent
after the next submission: the unqualified account-level name is bound to one
particular product rather than reserved for the family or matched to the product
whose name it is. Any convention the ADR adopts has to state whether the
unqualified slot is reserved, reassigned, or left as-is.

### `scoop-bump.yml` carries a monotonicity guard worth preserving

The one piece of hard-won engineering in the dashboard's unexecuted machinery is
a refusal to bump a committed manifest backward:

```bash
CURRENT_VERSION=$(jq -r '.version' bucket/vaultspec.json)
if [ "$(printf '%s\n' "$CURRENT_VERSION" "$VERSION" | sort -V | tail -1)" = "$CURRENT_VERSION" ] && \
   [ "$CURRENT_VERSION" != "$VERSION" ]; then
  echo "bucket is at ${CURRENT_VERSION}, refusing to bump backward to ${VERSION}"
  exit 1
fi
```

The regression it prevents is specific and non-obvious: a long-lived branch whose
copy of the manifest predates a release-time bump merges without rebasing, its
stale content wins the merge, and the published version silently regresses. The
same shape appears independently in `vaultspec-core`'s `binaries.yml`, which
guards its bucket bump against `jq -r '.version' "$MANIFEST"`. Two products
arrived at the same guard, which is the signal that it belongs to the mechanism
rather than to either product.

The generalisation: any single-file "current release pointer" committed to a
shared branch needs an explicit monotonic guard, because ordinary git merge
semantics can un-publish a newer version without any workflow failing.

### `cadrumo` gates hard, has never opened the gate, and points at a repository that does not exist

Version lives in `pyproject.toml:3` (`0.2.1`), mirrored in `src/cadrumo/__init__.py:27`
and `.release-please-manifest.json`, with agreement enforced by
`dev/release/readiness.py:check_version_surfaces_agree`. `release-please` is
present as configuration but has no workflow: the governing record mandates local
invocation only, so a release is cut by hand and the tag stays local.

`publish-release.yml` is a three-gate `workflow_dispatch` pipeline — an operator
preflight on `vars.CADRUMO_PUBLISH_ENABLED`, a validation job that verifies source
run identity and hash-verifies every evidence artifact, and a publish job behind a
protected `release` environment running `uv publish --trusted-publishing always`.
It has never run. `pypi-upload.yml` is a second path to the same index, but a
documented, issue-tracked stopgap scheduled for deletion on the first successful
Gate 3 publication; it ran once and failed.

Two acquisition workflows produce inputs `publish-release.yml` requires, and
both fail unconditionally: `packaging-homebrew.yml` at 9 dispatches and 9
failures, `packaging-scoop.yml` at 8 and 8.

The repository variables are set: `HOMEBREW_TAP_REPO=nevenincs/homebrew-tap` and
`CLAUDE_MARKETPLACE_REPO=nevenincs/neve-marketplace`. The marketplace repository
exists and is public. **`nevenincs/homebrew-tap` returns 404** — the tap the
publish authority would push to has not been created, so the Homebrew leg would
refuse at Gate 3 even with every gate opened.

Three repositories created 2026-07-21 — `scoop-cadrumo`, `homebrew-cadrumo`,
`cadrumo-dist` — are all private and referenced by nothing in the tree outside
historical vault documents. They are leftovers of a superseded per-product design.
Their risk is not functional but mimetic: the `<channel>-<product>` naming reads,
to anyone pattern-matching, as the convention to follow.

### The evidence apparatus has real fail-closed consumers and a disproportionate required set

`DistributionEvidence` (`dev/packaging/evidence.py:219`) is a frozen, strict,
`extra="forbid"` record identified by a SHA-256 over its own canonical JSON and
bound to the exact artifact digests and commit it proves. It refuses to fabricate:
`_assert_oracle_bound_to_cohort` (`dev/packaging/distribution_evidence_emit.py:145`)
rejects a record whose captured `aeat --version` output does not token-match the
cohort version, and `build_client_evidence` raises when an SDK-driven run is used
to satisfy a row that requires a real client session.

It has two genuine consumers, both fail-closed. `dev/release/readiness.py:383`
requires a passing, cohort-matched record for every entry in
`REQUIRED_DISTRIBUTION_ROWS` and is invoked directly by `publish-release.yml`
Gate 2. `dev/docs/tests/test_distribution_claims.py:193` scans the shipped
documentation for positive install commands and refuses any channel claimed
without a passing row. Five real records exist on disk from actual installed-CLI
runs, so the harness has demonstrably produced output.

The disproportion is in the required set, not the design. `REQUIRED_DISTRIBUTION_ROWS`
is a fixed eleven spanning five channels, so the first publication to any single
channel is blocked on proof for all five — including the two whose acquisition
workflows have never once succeeded. The claims gate already models the correct
relationship, claim implies evidence; the readiness gate does not, requiring
evidence for channels no release claims. That asymmetry, rather than the
existence of the machinery, is what has kept the count of shipped bytes at zero.

### Product shapes differ enough that a single channel list would be wrong

`cadrumo` is a Python distribution exposing two console scripts (`aeat`,
`cadrumo-mcp`) aimed at taxpayers and their advisers — an audience that cannot be
assumed to have a Python toolchain. `vaultspec-core` and `vaultspec-rag` are
Python CLIs for developers who already do. `vaultspec-dashboard` is a Rust
workspace embedding a built SPA, served rather than imported. `vaultspec-a2a@0.2.0`
is a headless FastAPI gateway-plus-worker with GitHub releases, no distribution
workflows, and no registry presence.

A per-product channel list would therefore be five arbitrary lists. The evidence
favours deriving the list from two properties the products genuinely differ on —
whether the artifact exposes a command a user invokes directly, and whether that
user can be assumed to hold the language toolchain — and letting the matrix fall
out. What the ADR must settle is the derivation rule and the treatment of the
unqualified publisher namespace; both are choices the evidence constrains but
does not make.

### What was not investigated

Download or install counts for the two live packages were not gathered, so
relative channel value is unmeasured. The `neve-marketplace` tree was not read,
so the plugin-name mismatch recorded in the product-scope topology record is
taken as given rather than re-verified. No workflow was executed and nothing was
published, so every claim about a pipeline's behaviour is read from its
definition plus its recorded run history, not from an observed run.

Semantic search was degraded throughout this work — the code index was serving
roughly 1027 chunks against about 4546 files while reporting no degradation — so
it was used only for pointers and every conclusion rests on direct reads,
`gh` API queries against structured JSON, and targeted pattern search. No
conclusion here depends on a semantic-search miss.

## Sources

- `Y:\code\aeat-worktrees\main\pyproject.toml:3`
- `Y:\code\aeat-worktrees\main\src\cadrumo\__init__.py:27`
- `Y:\code\aeat-worktrees\main\dev\packaging\evidence.py:219`
- `Y:\code\aeat-worktrees\main\dev\packaging\distribution_evidence_emit.py:145`
- `Y:\code\aeat-worktrees\main\dev\release\readiness.py:383`
- `Y:\code\aeat-worktrees\main\dev\docs\tests\test_distribution_claims.py:193`
- `Y:\code\aeat-worktrees\main\.github\workflows\publish-release.yml`
- `Y:\code\aeat-worktrees\main\.github\workflows\pypi-upload.yml`
- `nevenincs/vaultspec-core:.github/workflows/publish.yml`
- `nevenincs/vaultspec-core:.github/workflows/binaries.yml`
- `nevenincs/vaultspec-core:bucket/vaultspec-core.json`
- `nevenincs/vaultspec-rag:.github/workflows/publish.yml`
- `nevenincs/vaultspec-dashboard:.github/workflows/scoop-bump.yml`
- `nevenincs/vaultspec-dashboard:.github/workflows/winget-publish.yml`
- `nevenincs/vaultspec-dashboard:bucket/vaultspec.json`
- `nevenincs/vaultspec-dashboard:pyproject.toml`
- `nevenincs/vaultspec-a2a:pyproject.toml`
- https://github.com/microsoft/winget-pkgs/tree/master/manifests/n/nevenincs/vaultspec/0.1.0
- https://pypi.org/pypi/vaultspec-core/json
- https://pypi.org/pypi/vaultspec-rag/json
- https://pypi.org/pypi/cadrumo/json
