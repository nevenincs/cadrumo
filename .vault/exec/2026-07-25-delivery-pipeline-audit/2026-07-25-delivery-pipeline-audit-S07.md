---
tags:
  - '#exec'
  - '#delivery-pipeline-audit'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S07'
related:
  - "[[2026-07-25-delivery-pipeline-audit-plan]]"
---

# D4, derive shipped-manifest author identity from PRODUCT_IDENTITY while preserving the pyproject legal author as a distinct fact, since the two are different claims and collapsing them loses the legal one

## Scope

- `packaging/`
- `dev/packaging/`

## Description

Verify that shipped-manifest author identity derives from the product-identity authority while the pyproject legal author survives as a distinct fact.

- Confirm the derived product author string has one declaration and that consumers read it through the owning package's public facade rather than a private module.
- Confirm the shipped manifest carries the derived value and that both the stamp path and the template drift gate enforce it.
- Confirm the legal author fact is intact in all three pyprojects and that neither claim has leaked into the other.

## Outcome

Complete at HEAD, with both claims intact and distinct.

Product identity: the single derivation `PRODUCT_AUTHOR_NAME` is declared once in `src/cadrumo/agent/_workspace.py` from the product-identity display name, and is exported through the `cadrumo.agent` package facade. The plugin manifest, the marketplace manifest, the shipped MCPB manifest, and the distribution-identity verifier all read that one declaration; the verifier imports it from the public facade, not from the private module. The MCPB manifest's committed author is the derived value, and `packaging/mcpb/build.py` enforces it on both sides, stamping the author from the derived value and refusing a committed template whose author diverges, so the previously hand-authored literal can no longer silently drift back.

Legal person: all three cohort pyprojects carry the PEP 621 author as the pseudonymous legal person with the project contact address, per the amending ruling that replaced the operator's real name on shipped surfaces. This is the copyright-holder fact under the licence and is a different referent from the product string.

The crossover check runs in both directions and is clean. No pyproject `authors` entry carries the product string, and the product string is nowhere sourced from a legal-person name. The legal author fact survived the identity derivation, which was the specific risk the ruling was written to prevent.

The identity assertion in the verifier's test suite collects and passes in isolation.

## Notes

One test in the distribution-identity suite fails at HEAD and is not owned by this step. The verifier pins a digest over the model-facing description inventory, whose sources include the CLI entrypoints and the locale catalogues, and refuses when that surface is dirty against HEAD, on the correct ground that a digest computed over uncommitted work bakes it into a committed gate. A concurrent campaign holds live uncommitted work across seven CLI entrypoint files and all four locale catalogues, which is what trips the refusal.

The attribution was confirmed rather than assumed: the shipped-manifest surface this step owns is clean against HEAD, and the identity assertions pass in isolation. The remaining failure is a shared-worktree condition that clears when the concurrent campaign lands, not a defect in the author derivation. It is recorded here rather than left to be rediscovered as an unexplained red.
