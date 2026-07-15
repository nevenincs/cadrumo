---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S70'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-14-cadrumo-product-rename-audit]]"
---

# Rewrite active user guides with `aeat` invocations, CADRUMO product prose, and preserved AEAT authority language

## Scope

- `docs/how-to`

## Description

- Rewrite the active `docs/how-to` guides landed in `ba5bc9e033`, replacing product-owned `aeat`/`AEAT`-conflated phrasing with `Cadrumo` prose, the `aeat` CLI command, `CADRUMO_*` environment variable names, and preserved AEAT authority language.
- Retitle guides such as `authenticate-with-aeat.md` to name the product performing the action ("How to authenticate Cadrumo with AEAT") rather than treating `aeat`/AEAT as interchangeable.
- Rewrite import, classification, LLM-evidence, and profile guides to distinguish the `aeat` command from the AEAT authority it talks to, and to correct stale env-var names (`AEAT_SECRET_PASSPHRASE` to `CADRUMO_SECRET_PASSPHRASE` and similar) to the current authority.
- Verify the touched guides against documented-command conformance and the mandatory nitpicky Sphinx build (recorded under `S75`).

## Outcome

Every active `docs/how-to` guide names Cadrumo as the product, `aeat` as its permanent CLI command, and AEAT as the Spanish tax authority; no residual guide conflates the two. Audit `2026-07-14-cadrumo-product-rename-audit` grants the Phase 3/Phase 8 approval this Step needed under the mandated documentation workflow, on the basis of the principal-documentation-writer session's direct token sweep of `docs/how-to` at HEAD, which found no surviving stale-branding form.

## Notes

This record documents work already committed in `ba5bc9e033` under the combined subject `W05.P13.S68-S71, S73`. No further content change was required for this Step's `docs/how-to` scope beyond what that commit shipped.
