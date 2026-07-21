---
tags:
  - '#research'
  - '#public-product-rollout'
date: '2026-07-10'
modified: '2026-07-10'
related:
  - "[[2026-07-04-release-readiness-gate-adr]]"
---

# `public-product-rollout` research: `Public product rollout`

Scope the public rollout for the local-first CLI and MCP product.

## Findings

- Keep taxpayer data local and encrypted because `README.md:59` and `README.md:107` exclude a cloud backend.
- Separate the public site from the core repository because HEAD contains no web application, Figma handoff, host, or deploy configuration.
- Treat `aeat.neve.md` as unlaunched because `README.md:11` names it as under construction.
- Provision `aeat.neve.md` before launch because `neve.md` returns HTTPS 200 while the subdomain has no DNS record on 2026-07-10.
- Define the product relationship to the live `neve nincs` parent brand because `https://neve.md` presents it as a creative code-driven design studio.
- Clear the chosen public name before adoption because `https://consultas2.oepm.es/WSLocalizador/help.action?ajax=true` and EUIPO search cover potentially conflicting marks.
- Restore delivery health before public release because CI and Packaging Smoke fail at `06f2a531bb8ca263c36c26303145f3db3c9c67b1`.
- Separate permanent charter issue `#116` from release-stopping blockers because `just release-readiness-json` cannot pass while the charter stays open.
- Reconcile the published `aeat-cli` 0.1.1 package with the HEAD 0.2.0 declaration because `https://pypi.org/pypi/aeat-cli/json` exposes a public version and identity lag.
- Correct the `v0.2.0` GitHub release narrative because it claims zero released versions while PyPI serves 0.1.1 and the release has no assets.
- Prefer Git-integrated Cloudflare Pages for the static site because `https://developers.cloudflare.com/pages/configuration/git-integration/` provides branch previews and repository checks.
- Skip R2 at launch because `https://developers.cloudflare.com/pages/functions/pricing/` makes static Pages requests free and unlimited.
- Keep optional R2 storage private by default and expose only public assets through a custom domain because `https://developers.cloudflare.com/r2/buckets/public-buckets/` treats `r2.dev` as non-production.
- Preserve the no-filing and no-AEAT-affiliation claims in every public surface because `README.md:24` and `README.md:127` define the product boundary.
- Resolve the beta and author identity conflict because `README.md:11`, `docs/index.md:12`, and `pyproject.toml:8` disagree.

## Owner decisions

- Choose the public product name and copyright owner.
- Choose whether the product is a `neve nincs` product or an independent brand.
- Confirm the `aeat.neve.md` DNS owner.
- Approve Cloudflare Pages or choose another static host and deployment identity.
- Choose the first conversion action before adding analytics or forms.

## Delivery channels

- Present `aeat-cli` as the local command-line product because `https://pypi.org/pypi/aeat-cli/json` is the public package source.
- Present `aeat-mcp` as the local stdio MCP server because `README.md:49` and `README.md:87` define its client-agnostic installation path.
- Present `aeat@neve` as the Claude plugin because `docs/verification/neve-marketplace-install-proof.md:17` records the public marketplace flow.
- Keep the MCP channel in scope because `uvx --from "aeat-cli[agent]==0.1.1" aeat-mcp` completed a live 273-tool handshake on 2026-07-10.
- Align the 0.1.0 MCPB manifest, 0.1.1 PyPI and marketplace releases, and 0.2.0 HEAD declaration before public promotion.
- Exclude MCPB from launch copy because `packaging/mcpb/build.py` marks it as a demoted unsigned secondary artifact.

## First-page scope

- Lead with the approved product name and a plain Spanish-tax workflow outcome.
- Explain that the deterministic engine computes while the assistant guides.
- Show the CLI, direct MCP, and `aeat@neve` installation routes.
- State that taxpayer data stays local and encrypted.
- State that the product never files and is not affiliated with AEAT.
- Link documentation, release notes, privacy, and support from the footer.

## Execution order

- Restore the Vault index before using it as the launch-planning source of truth.
- Separate permanent charter issues from release-stopping blocker labels.
- Clear the proposed public name through OEPM and EUIPO before locking copy.
- Regenerate `uv.lock` before rerunning Packaging Smoke.
- Repair the CI registry verification command to use a supported JSON boundary.
- Resolve current Semgrep findings before claiming core release health.
- Align GitHub release notes, PyPI metadata, marketplace metadata, and site install copy.
- Create the public-site repository after confirming the product name.
- Create the `aeat.neve.md` DNS record after selecting the static host.
- Link the canonical Figma file before implementing the landing page.
- Publish one accurate installation path for each delivery channel.
- Keep MCPB off the initial public site.
- Verify the published MCP handshake before every public release.
- Add preview and protected production deployment before publishing the domain.
- Publish only a green release candidate with matching CLI, corpus, marketplace, and site metadata.
- Add a public asset bucket only when the static host cannot serve required assets.
