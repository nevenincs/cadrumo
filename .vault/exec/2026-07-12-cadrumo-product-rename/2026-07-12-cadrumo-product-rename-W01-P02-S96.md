---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S96'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Supersede the conflicting July 13 rename ADR in the binding authority graph

## Scope

- `.vault/adr/2026-07-13-product-rename-adr.md`
- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `S96 execution record`

## Description

- Ground the graph defect in audit commit `bb97babbd5dfec1d17dd68269107d21ff06633c7` and the live ADR corpus.
- Use the authoritative Vaultspec supersession command to connect the binding CLI ADR to the July 13 rename ADR reciprocally.
- Preserve the July 13 ADR's stale title-case and Stage-B body as historical evidence under an explicit superseded status.
- Keep the binding CLI ADR body unchanged, including the absence of the false status note removed by S95.
- Preserve every existing plan checkbox while adding and closing only S96 through the Vaultspec plan CLI.

## Outcome

- The accepted CLI ADR explicitly supersedes both `2026-07-12-cadrumo-product-rename-adr` and `2026-07-13-product-rename-adr`.
- The July 13 ADR is `superseded`, points back through `superseded_by`, and retains its historical body without presenting it as active authority.
- Both ADR modified stamps are maintained by the supersession command at `2026-07-13`.
- S95 remains checked, all previously open authority and casing lanes remain open, and S96 is the only newly completed Step.

## Notes

- The staged marketplace README and dirty S58 execution record are foreign concurrent work and remain outside this Step's commit.
- Independent re-review of the combined S95/S96 authority graph follows this remediation.
- Focused ADR frontmatter, modified-stamp, and Markdown checks pass. Repository-wide ADR status retains only two unrelated pre-existing quoting warnings.
- Plan validation retains the known non-monotonic `PLAN022` warning; graph inspection confirms both reciprocal supersession pairs.
