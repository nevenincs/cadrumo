---
tags:
  - '#research'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - '[[2026-07-27-canonical-release-pipeline-adr]]'
  - '[[2026-07-27-publication-lane-consolidation-adr]]'
  - '[[2026-07-27-pipeline-config-topology-adr]]'
---

# `canonical-release-pipeline` research: `measured state of the docs, landing, and marketplace delivery surfaces`

## Findings

**The docs site is live on AWS and fifteen days stale; nothing automates it.**
`https://cadrumo.neve.md/` and `https://cadrumo.neve.md/docs/` return HTTP 200
with `Server: AmazonS3` headers; the docs `Last-Modified` is
2026-07-12 17:43:06 GMT (measured 2026-07-27). `https://neve.md/` returns 200
with `Server: cloudflare`. The only reference to the deploy tooling anywhere
under `.github/` is a comment in `publish-release.yml` (verified by `rg` across
`.github/`, 2026-07-27); no workflow invokes it.

**The deploy tooling is complete and manual by design.**
`dev/deploy/docs_static_site.py` owns the fixed stack (`STACK_NAME =
"cadrumo-docs"`, `STACK_REGION = "us-east-1"`, `CANONICAL_DOCS_BASE_URL =
"https://cadrumo.neve.md/docs"`), with verbs `provision` and `publish` behind
literal `--confirm` phrases, an ACM single-certificate lookup, CloudFront alias
pinning, strict-build artifact/sitemap/Pagefind validation, a `--delete` sync of
the whole HTML tree into the `docs/` prefix, one `/docs/*` invalidation, and
endpoint verification of 200/404/403 plus the legacy 308 redirect.
`_require_human_publish_environment` refuses to run when `CI` or
`GITHUB_ACTIONS` is set. `dev/deploy/frontend_static_site.py` publishes the Vite
landing page to the same bucket's root, excludes `docs/*` (with a dry-run mode
that refuses any touch of it), and asserts `/`=200, missing=404, `/docs/`=200,
direct S3 access=403. Both have tests under `dev/deploy/tests/`. The `justfile`
verbs are `docs-stack-deploy`, `docs-deploy`, `frontend-deploy`.

**The release-to-docs handshake is a one-way pull.** `publish-release.yml`
emits `download-latest.json` (schema `cadrumo.download-latest.v1`, a read-only
projection of the sealed cohort manifest plus release asset URLs, leak-swept)
and attaches it to the `v<version>` release. `_refresh_download_latest` in the
docs publisher pulls it from the fixed latest-release asset URL at the next
publish, schema-checks it, writes it into `docs/_static/`, and degrades to the
offline Tier-1 channel table on any failure — it never raises.

**Localized roots are all-or-nothing today.** `_build_language_roots` builds
`es`/`ca`/`hu` (derived from the shared `TARGET_LANGUAGES`) sequentially after
the English root; every build and validation completes before any upload; any
`SystemExit` refuses the whole publish. Each root carries its own Pagefind
index.

**The 2026-06-25 hosting decision, read verbatim.** The operator's private
planning vault records a hosting decision dated 2026-06-25 (read verbatim on
2026-07-27; the source's identifiers are deliberately withheld — cross-project
detail stays out of this repository). It chose Cloudflare Pages plus
Workers/D1/R2 for the account front at baseline cost EUR 0, and rejected
"AWS (S3 + CloudFront / Lambda) — egress charges + complexity make cost
unpredictable. Rejected for core." The `neve.md` apex DNS is delegated to
Cloudflare (Free plan, zone active, universal SSL). The decision never
mentions `cadrumo.neve.md`; it predates the subdomain. The divergence — the
docs subdomain shipped on the rejected stack — is recorded nowhere.

**Cost grounding, read 2026-07-27.** CloudFront's Free plan includes 100 GB
per month of data transfer and one million requests
(`aws.amazon.com/cloudfront/pricing`; AWS has moved CloudFront to plan-based
pricing, so the account's actual plan is an open operator confirmation).
Cloudflare Pages Free caps a deployment at 20,000 files and 25 MiB per file;
paid tiers reach 100,000 files (`developers.cloudflare.com/pages/platform/limits`).
A compiled Pagefind index for this docs corpus previously measured ~63 MB /
~16k files (the committed-index finding behind
`2026-06-15-docs-terminology-search-adr`); the deployed site is four
Pagefind-indexed roots, so the full object count plausibly exceeds the Pages
Free cap. No fresh full build existed to inventory (the worktree's
`docs/_build/html` held 75 files, no Pagefind output) — the comparison is
bounded, not freshly measured.

**Marketplace state.** `nevenincs/neve-marketplace` carries a stale
`plugins/aeat` subtree from 2026-07-04 under the old product identity,
referencing `aeat-cli 0.1.1` — a distribution the current sealed cohort
(v0.2.1, run `30216592706`) does not publish. `dev/packaging/marketplace_publish.py`
replaces only the plugin subtrees the cohort declares and preserves every other
path and index entry by design (sibling protection); it refuses cross-owner
name takeovers via `published_by` and treats publisher-less entries as
claimable. The cohort publishes under the `cadrumo` identity, so no publication
will ever touch the stale `aeat` entry.

**Release gate state (measured 2026-07-27).** `CADRUMO_PUBLISH_ENABLED` unset;
the `release` environment exists with no protection rules; sealed cohort
`30216592706` = v0.2.1 with complete evidence; 0.2.1 free on all three PyPI
projects; `nevenincs/homebrew-tap` holds `Formula/` and `bucket/` with only
`.gitkeep` (correct bootstrap state).

**Version-identity collision: two builds both stamped v0.2.1 (verified
2026-07-27).** A non-draft GitHub release `v0.2.1` was published
2026-07-21T12:46:11Z, `target_commitish` `9235e8cabcc7d0ed4777623722d15b00303cf8b1`,
carrying 8 assets (all six python distributions, `cadrumo-0.2.1.mcpb`, and an
evidence manifest) — from packaging-smoke run `29810372590` (coordinator
measurement: linux cohort sha256 `36584851…`, 347,206,213 bytes). The sealed
candidate cohort is run `30216592706`, head `490f625c95338a68cdbb7fa0241e46e331f5d62f`
(coordinator measurement: linux cohort sha256 `bb3ba313…`, 392,874,897 bytes).
Same version string, different commits, different bytes. Root cause verified:
`pyproject.toml` `version = "0.2.1"` and `.release-please-manifest.json`
`{".": "0.2.1"}` were never advanced after the 2026-07-21 release;
release-please is configured (`release-type: python`,
`bump-minor-pre-major: true`, manifest-driven) but wired only to a manual
`justfile` target that invokes `release-pr --dry-run` — no workflow runs it.

**The promotion failure this arms (step order verified).**
`publish-release.yml` Gate 2 guards the destination with `--check-pypi-only`;
its promote job orders: PyPI Trusted-Publishing upload, then
`gh release create "v$VERSION"`, then the docs payload, Scoop, Homebrew,
marketplace. PyPI 0.2.1 is genuinely free on all three projects, so a dispatch
of the sealed cohort passes the guard, irreversibly uploads the new bytes as
0.2.1, then fails at release creation because non-draft `v0.2.1` already
exists; nothing after runs. PyPI has no un-publish.

**A second live PyPI lane.** `.github/workflows/pypi-upload.yml` selects among
the `pypi` / `pypi-data-manuals` / `pypi-data-official` environments by input
and carries an explicit retirement charter: it exists solely to deliver Python
distributions of already-published `v*` releases (concretely the owed v0.2.1
fast-follow), is gated on the same `CADRUMO_PUBLISH_ENABLED` variable as the
sole publication authority, and its deletion trigger is the first successful
Gate 3 PyPI publication (tracked as open issue #618, which also names deleting
the three Trusted-Publishing registrations). Its `release_tag` input defaults
to `v0.2.1` but is a free string — the lane is not version-pinned. Arming the
one variable therefore arms two PyPI authorities that would ship different
bytes under the same version.

**Marketplace identity collision, decoded live (verified 2026-07-27).** The
live `nevenincs/neve-marketplace` index (`.claude-plugin/marketplace.json`)
carries name `neve`, owner `AEAT tax assistant project`, description naming
"the aeat Spanish-tax assistant", and a single plugin entry
`{name: "aeat", source: "./plugins/aeat"}` with NO `published_by` field — it
predates ownership tracking, so under the merge tool's rules it is claimable
by any product. The in-tree cohort manifest
(`packaging/marketplace/.claude-plugin/marketplace.json`) carries the same
marketplace name `neve`, owner `CADRUMO tax assistant project`, a bilingual
description naming Cadrumo, and the single plugin `{name: "cadrumo"}`. The
merge takes account-level metadata (name, description, owner) from the cohort
and preserves every entry and path the cohort does not declare — so publishing
v0.2.1 as-is would flip the account metadata to CADRUMO while leaving the
broken `aeat` plugin (pinned to the unpublished `aeat-cli 0.1.1`) live beside
`cadrumo`.

## Sources

- Live headers: `cadrumo.neve.md`, `cadrumo.neve.md/docs/`, `neve.md`
  (HTTP GET, 2026-07-27).
- `dev/deploy/docs_static_site.py`, `dev/deploy/frontend_static_site.py`,
  `dev/packaging/marketplace_publish.py`, `.github/workflows/publish-release.yml`,
  `justfile` (direct reads at the current tree, 2026-07-27).
- The operator's private planning vault, 2026-06-25 hosting decision (read
  verbatim, 2026-07-27; source identifiers withheld by the repository
  boundary rule — cadrumo is cadrumo only).
- `aws.amazon.com/cloudfront/pricing` and
  `developers.cloudflare.com/pages/platform/limits` (fetched 2026-07-27).
- Semantic search was degraded during this pass (code index mid-rebuild);
  every conclusion rests on direct reads, live HTTP measurements, and the
  dispatching coordinator's same-day measurements re-verified where load-bearing.
- `gh release view v0.2.1`, `gh api repos/nevenincs/neve-marketplace/...`
  (read-only API queries, 2026-07-27); `pyproject.toml`,
  `.release-please-manifest.json`, `release-please-config.json`,
  `.github/workflows/pypi-upload.yml`, `packaging/marketplace/.claude-plugin/marketplace.json`
  (direct reads, 2026-07-27); cohort byte counts and sha256 prefixes are the
  dispatching coordinator's same-day measurements, not re-derived here.
