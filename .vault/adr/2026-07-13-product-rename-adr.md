---
tags:
  - '#adr'
  - '#product-rename'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:7bbbc6e98e7f4c907f9a85a3b7d1f9ef03e1441691c93aee3611fa6660ca9408'
related:
  - '[[2026-07-12-cadrumo-cli-executable-adr]]'
  - '[[2026-07-12-cadrumo-product-rename-research]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
---

# `product-rename` adr: `Cadrumo release, repository, and publication identity` | (**status:** `accepted`)

## Problem Statement

The public product is Cadrumo, while historical distribution, repository, and
marketing surfaces used the tax authority's acronym as product identity. That
weakened the product/authority distinction and made publication metadata
inconsistent. The rename must cover product-owned release surfaces without
rewriting authority-owned AEAT vocabulary or creating a second naming authority
for executables, Python imports, MCP identities, or environment variables.

## Decision

This ADR governs only distribution, repository, marketplace, marketing, legal,
and publication surfaces:

- the root distribution is `cadrumo`;
- mandatory data companions are `cadrumo-data-manuals` and
  `cadrumo-data-official`;
- the repository is `nevenincs/cadrumo`;
- release metadata, marketplace copy, package descriptions, install guidance,
  and product prose use Cadrumo; and
- official AEAT/BOE material is described as authority-owned content and is not
  relicensed or rebranded as first-party product material.

The complete runtime naming tuple is intentionally out of scope here. The
accepted `2026-07-12-cadrumo-cli-executable-adr` is its single authority:
product prose `Cadrumo`, identity casing `CADRUMO`, human executable `aeat`,
Python root `cadrumo`, MCP executable/prefix/scheme `cadrumo`, product
environment prefix `CADRUMO_`, and authority-owned vocabulary `AEAT`.

## Constraints

- The installed `aeat` entry point is the sole human command and resolves
  directly to `cadrumo.entrypoints.cli:main`. It is not a deprecated alias.
- `import cadrumo` is supported; an `aeat` Python package or import shim is
  forbidden.
- Product-owned distribution and artifact names use Cadrumo. AEAT remains
  correct for official endpoints, credentials, protocols, evidence, registry
  authority, legal provenance, modelos, and casillas.
- Publication promotes the exact immutable Cadrumo cohort defined by the
  distribution-installation-readiness ADR. It does not rebuild renamed
  substitutes.
- Trademark clearance remains an operator-owned legal follow-up; repository
  architecture does not claim registration.

## Implementation

`pyproject.toml`, both companion projects, release workflows, packaging cohort
builders, channel generators, repository metadata, and marketing/legal copy use
the Cadrumo distribution identity. The root metadata pins both companions at
the exact root version. GitHub, PyPI, marketplace, MCPB, Scoop, Homebrew, and
documentation promotion consume the same cohort identity and hashes.

Historical references may retain old project names only when they are necessary
to explain a past artifact or redirect. Active requirements and examples use
the current names and never instruct maintainers to preserve an old Python or
MCP identity.

## Rationale

Scoping this ADR to public release identity prevents it from competing with the
runtime naming authority. The product name becomes coherent wherever users
acquire or evaluate it, while authority-owned AEAT terminology remains precise
and the singular `aeat` operator command remains truthful.

## Consequences

- Public artifacts and repository references share one Cadrumo identity.
- Reviews must classify `aeat` by referent instead of enforcing a blind
  zero-occurrence rule.
- Any future change to executable, import, MCP, or environment naming must
  supersede the runtime naming ADR, not amend this release-surface decision.
