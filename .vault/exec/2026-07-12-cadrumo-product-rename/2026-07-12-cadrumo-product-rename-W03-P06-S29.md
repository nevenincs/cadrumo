---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S29'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename manuals distribution metadata and repository URLs

## Scope

- `packaging/cadrumo_data_manuals/pyproject.toml`

## Description

- Inspect overtaking commit `f99ee0c821` and verify its manuals companion rename against the current root metadata and packaging decisions.
- Preserve the accepted distribution, shared namespace, version parity, corpus description, and install guidance.
- Align the companion project URLs and README root link with the canonical Cadrumo repository identity.
- Build and inspect the real manuals wheel without changing the S30 hatch mapping.

## Outcome

The manuals companion declares distribution `cadrumo-data-manuals` at root-aligned version 0.1.1, describes AEAT/BOE manuals as authority corpus material, directs operators to `cadrumo[corpus-sources]`, and identifies `github.com/cadrumo/cadrumo`. Its built wheel contains only the expected `cadrumo_data/_data/corpus/manuals` namespace payload and no former product package or namespace.

TOML parsing, root-version and URL parity assertions, real wheel metadata/content inspection, exact former-identity residue, and scoped diff checks passed.

## Notes

Step S29 was mostly overtaken by `f99ee0c821`; the live follow-up changed only three project URLs and one README link. The hatch build hook was inspected for consistency but not edited because its mapping belongs to S30.

Formal review found no issue and confirmed that all remaining AEAT/BOE references carry authority or corpus meaning.
