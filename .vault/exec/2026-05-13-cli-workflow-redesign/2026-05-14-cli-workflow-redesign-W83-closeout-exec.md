---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W83.P400..P404'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-aeat-cli-config-vs-setup-namespace-adr]]"
---

# `cli-workflow-redesign` W83 closeout (config init backend service)

Closed plan rows: every row of W83.P400..P404 (25 rows).

## Surface evidence

The W83 ADR's intent — replace the legacy first-run setup wizard
with a canonical `aeat config init` that delegates to an
`application/setup` typed service — is in place:

- `application/setup/__init__.py` re-exports
  `InitializeWorkspaceCommand`, `InitializeWorkspaceResult`,
  `initialize_workspace`.
- `application/setup/_contracts.py` carries the strict Pydantic
  input + output contracts.
- `application/setup/_service.py` implements
  `initialize_workspace` over the canonical user-profile +
  workflow-state services.
- `aeat config init --tax-id ... --activity ... [--profile NAME]
  [--output-language] [--non-interactive] [--dry-run]` is the
  operator-facing entry point in `entrypoints/cli/_config/__init__.py`.
- W11 closeout already retired the `aeat setup` Typer mount;
  `test_rejected_aliases_do_not_reach_apex_workflow_services`
  pins `setup` as a rejected root.

## Guards held

- No `aeat setup` compatibility alias.
- No CLI-local init business logic; the handler delegates to
  the typed service.
- No metastate codification of the retired root; its absence is
  the architecture.
