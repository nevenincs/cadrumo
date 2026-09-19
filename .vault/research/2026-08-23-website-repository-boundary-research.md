---
tags:
  - '#research'
  - '#website-repository-boundary'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3399a923ce1fb532213a5c3ca732a414f515892d66f4b83818b39e719081d67c'
related:
  - "[[2026-08-05-cadrumo-frontend-launch-product-page-vs-docs-landing-boundary-audit]]"
---
# `website-repository-boundary` research: `marketing website ownership migration`

The repository boundary is already materially split: the product repository no longer contains the website source, publisher, tests, CI lane, or deploy recipe, while `cadrumo-marketing` owns the complete history and operational surface. The remaining work is declarative reconciliation rather than code transport. Two accepted product-repository ADR passages still assign website work here, `RELEASING.md` retains the old release-era framing, and active comments retain migration history. The evidence favors full operational ownership in the marketing repository, but an ADR must settle the governing corpus before the release guide presents that boundary as current fact.

## Findings

### The website implementation and its operational surface have already moved as one unit

Commit `87625a433d9fd3784c88c7ddbf64cc0669e26cd0` removes `frontend/`, `dev/deploy/frontend_static_site.py`, its deploy tests, `.github/workflows/frontend.yml`, and the `frontend-deploy` Just recipe from the product repository. It also removes the `frontend/**` product-CI carve-outs and replaces positive ownership gates with inverse no-website gates. Follow-up commit `ab5b9e4aefa1164d53c764307b34cf4b93039425` makes that inverse gate test the tracked ownership marker `frontend/package.json`, so ignored build residue does not masquerade as returned source (`dev/ci/tests/test_change_class_tiers.py:202`).

The receiving merge `e69990d2aac4b6d5110f18d9586ee4a399f063da` preserves the website subtree's 34-commit history. Commit `f0f3d8680c472bf3b2d749e75e084c79317a5d29` makes the marketing repository itself the site: root-level source, package manifests, a local Just surface, a self-contained publisher, and `.github/workflows/ci.yml` (`Y:/code/cadrumo-marketing-worktrees/main/README.md:3`).

The marketing repository owns locked dependency installation, development, build, tests, preview, publisher tests, dry-run deployment, and live deployment (`Y:/code/cadrumo-marketing-worktrees/main/justfile:14`). Its CI provisions Node, runs `npm ci`, builds, tests, and runs Python publisher contracts (`Y:/code/cadrumo-marketing-worktrees/main/.github/workflows/ci.yml:37`). The publisher imports no product-repository code (`Y:/code/cadrumo-marketing-worktrees/main/dev/deploy/_aws.py:1`). Live publication is local to that repository and refuses CI (`Y:/code/cadrumo-marketing-worktrees/main/justfile:45`; `Y:/code/cadrumo-marketing-worktrees/main/dev/deploy/publish_site.py:253`).

### The surviving runtime coupling is infrastructure partitioning, not release-pipeline coupling

Both publishers address one S3 bucket and CloudFront distribution, but own disjoint paths. Marketing owns the root and excludes `docs/*` (`Y:/code/cadrumo-marketing-worktrees/main/dev/deploy/publish_site.py:52`; `:141`); the product repository owns documentation under `/docs/`. Marketing publication verifies that the documentation endpoint survives (`Y:/code/cadrumo-marketing-worktrees/main/dev/deploy/publish_site.py:237`). This is a shared delivery target with safety assertions, not a source, command, workflow, or release dependency. Commit `87625a433d9` leaves any live infrastructure split for a separate decision.

The product release remains coupled only to product documentation. The canonical release ADR says documentation publication is a downstream consequence that must not gate `publish-release.yml` (`.vault/adr/2026-07-27-canonical-release-pipeline-adr.md:260`), and `.github/workflows/docs-publish.yml:3` repeats that boundary. Removing website work from the product lifecycle does not weaken the release-to-documentation handshake.

### Accepted decisions still contain obsolete product-repository website ownership

The accepted canonical-release-pipeline ADR names the removed publisher and deploy recipe (`.vault/adr/2026-07-27-canonical-release-pipeline-adr.md:18`; `:32`) and rules independent documentation and landing verbs in R7 (`:372`). Its invariant that only documentation is a release consequence remains useful (`:379`); its website ownership no longer matches either repository.

The accepted ci-discipline ADR creates `T1-frontend` in the product repository and binds `frontend.yml` to `frontend/**` (`.vault/adr/2026-07-21-ci-discipline-adr.md:103`; `:114`). Current code implements the inverse: product CI declares no website source or lane (`.github/workflows/ci.yml:30`), while marketing CI owns all site changes (`Y:/code/cadrumo-marketing-worktrees/main/.github/workflows/ci.yml:8`).

`RELEASING.md` should preserve product documentation publication while eliminating any implication that the marketing site participates in product release. Residual migration-history comments appear in `justfile:999`, `.github/workflows/ci.yml:30`, `src/cadrumo-harness/NOTICE:17`, and `dev/audit/duplication_dispositions.toml:69`. CLI and TUI uses of Ã¢â‚¬Å“frontend" name application presentation boundaries and are unrelated to the website.

### Option 1: keep the website in the product repository

This option reverses commit `87625a433d9`, duplicates or moves back the Vite tree, publisher, tests, command surface, and CI lane, and restores product-CI path carve-outs. It conflicts with both repositories' current ownership markers and creates two plausible homes unless the marketing repository is dismantled. It also restores a second language toolchain and release-unrelated CI classification to the Python product repository.

### Option 2: split source but retain product-side website commands or workflows

This option leaves source in marketing while product Just recipes or Actions dispatch or import marketing work. It reduces source-tree mixing but divides operational ownership: product releases or CI would require cross-repository permissions, revision identity, and failure semantics for a non-product artifact. It also recreates the cross-repository code dependency removed when the publisher primitives became local (`Y:/code/cadrumo-marketing-worktrees/main/dev/deploy/_aws.py:3`). No current command or workflow requires this shape.

### Option 3: fully rehome website source, build, test, publish, CI, and commands; retain product documentation publishing only

This option describes current code after the four named commits. Marketing owns every website operation; the product repository owns product artifacts and documentation, with no website release gate or consequence. The shared bucket remains a bounded infrastructure seam protected by path exclusions and delivery checks. It can be split later without changing repository ownership.

The remaining work under this option is corpus and prose reconciliation: update or supersede obsolete ADR clauses, remove website-era commands and action descriptions from product documentation, and reduce active migration-history comments to durable boundary enforcement where needed.

## Sources

- `.vault/adr/2026-07-27-canonical-release-pipeline-adr.md:18`, `:260`, `:372`
- `.vault/adr/2026-07-21-ci-discipline-adr.md:103`, `:114`
- `.github/workflows/docs-publish.yml:3`
- `.github/workflows/ci.yml:30`
- `dev/ci/tests/test_change_class_tiers.py:202`
- `RELEASING.md:29`
- `justfile:999`
- `src/cadrumo-harness/NOTICE:17`
- `dev/audit/duplication_dispositions.toml:69`
- `Y:/code/cadrumo-marketing-worktrees/main/README.md:3`
- `Y:/code/cadrumo-marketing-worktrees/main/justfile:14`
- `Y:/code/cadrumo-marketing-worktrees/main/.github/workflows/ci.yml:37`
- `Y:/code/cadrumo-marketing-worktrees/main/dev/deploy/publish_site.py:52`, `:237`, `:253`
- `Y:/code/cadrumo-marketing-worktrees/main/dev/deploy/_aws.py:1`
- commit `87625a433d9fd3784c88c7ddbf64cc0669e26cd0`
- commit `ab5b9e4aefa1164d53c764307b34cf4b93039425`
- commit `e69990d2aac4b6d5110f18d9586ee4a399f063da`
- commit `f0f3d8680c472bf3b2d749e75e084c79317a5d29`
