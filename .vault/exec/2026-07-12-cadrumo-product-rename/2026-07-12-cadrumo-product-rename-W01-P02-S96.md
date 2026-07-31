---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:f5cad9832ffc8c7b005e8a43f487a3ff5915f941eaff60bedb511e2a275a734a'
step_id: 'S96'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Document the whole-ADR supersession attempt later corrected to preserve the accepted Stage-A role

## Scope

- `.vault/adr/2026-07-13-product-rename-adr.md`
- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `.vault/plan/2026-07-12-cadrumo-product-rename-plan.md`
- `S96 execution record`

## Description

- Ground the graph defect in audit commit `bb97babbd5dfec1d17dd68269107d21ff06633c7` and the live ADR corpus.
- Record the Vaultspec supersession transaction that connected the binding CLI ADR to the July 13 rename ADR reciprocally.
- Preserve the then-current superseded-state evidence while identifying it as a graph state later corrected by S87.
- Keep the binding CLI ADR body unchanged, including the absence of the false status note removed by S95.
- Preserve every existing plan checkbox while adding and closing only S96 through the Vaultspec plan CLI.

## Outcome

- At the S96 commit, the accepted CLI ADR temporarily superseded both `2026-07-12-cadrumo-product-rename-adr` and `2026-07-13-product-rename-adr`.
- S87 later removed the July 13 edge and restored that ADR to accepted Stage-A scope; this record preserves the supersession attempt rather than asserting the live graph.
- Both ADR modified stamps are maintained by the supersession command at `2026-07-13`.
- S95 remains checked, all previously open authority and casing lanes remain open, and S96 is the only newly completed Step.

## Notes

- The staged marketplace README and dirty S58 execution record are foreign concurrent work and remain outside this Step's commit.
- Independent re-review of the combined S95/S96 authority graph follows this remediation.
- Focused ADR frontmatter, modified-stamp, and Markdown checks pass. Repository-wide ADR status retains only two unrelated pre-existing quoting warnings.
- Plan validation retains the known non-monotonic `PLAN022` warning; graph inspection confirms both reciprocal supersession pairs.

## Graph correction from S94

The Description and Outcome above record the S96 graph transaction as it was
executed; they are not the current authority state. S87 later corrected that
whole-ADR supersession: `2026-07-13-product-rename-adr` is accepted for its
Stage-A release-surface scope, and the CLI ADR is the single binding authority
for casing, imports, executables, and machine identities. S96 remains checked
as completed historical remediation, not as a live instruction to supersede
the accepted Stage-A role.
