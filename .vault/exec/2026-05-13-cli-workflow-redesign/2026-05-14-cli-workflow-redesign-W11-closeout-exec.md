---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W11.P051..W11.P055'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-aeat-cli-config-vs-setup-namespace-adr]]"
---

# `cli-workflow-redesign` W11 closeout (config vs setup namespace)

Closed plan rows: every row of `W11.P051..W11.P055` (`S0301..S0330`).

## Delivered state (pre-existing)

The W11 ADR's directive — rename the operator-facing setup
domain to config — is already in effect:

- The `aeat setup` Typer root is absent from the live command
  tree. Operator-facing initialisation is `aeat config init`.
- The canonical backend service is
  `aeat.application.setup.initialize_workspace` with typed
  Pydantic command/result contracts (`InitializeWorkspaceCommand`,
  `InitializeWorkspaceResult`) in
  `application/setup/_contracts.py` and `_service.py`.
- Error codes are registered (`SetupResetUnconfirmedError` in
  `core/errors/registry/_application.py`).
- The `entrypoints/cli/test_apex_workflow_verification.py::test_rejected_aliases_do_not_reach_apex_workflow_services`
  test pins `setup` (and `auth`, `financial`, `filing`,
  `app invoice`, `app declaration`, `app archive`, `config set`,
  `config status`) as rejected root-level commands.

## Per-phase rationale

- `P051` backend implementation: `application/setup` package
  carries the canonical `initialize_workspace` service with
  Pydantic contracts and routed persistence; no further backend
  wiring required.
- `P052` shadow duplicate removal: the legacy `aeat setup` root
  is gone; `application/setup` does not duplicate the
  user-profile backend (it composes it).
- `P053` de-shim/de-stub: no compatibility aliases survive; no
  stubbed paths.
- `P054` real behavior verification: covered by
  `test_rejected_aliases_do_not_reach_apex_workflow_services`,
  the wizard runner tests, and the `config init` end-to-end
  test in `test_workflow_surface.py::test_config_init_profile_set_deadlines_and_filing_runtime_share_profile_bucket`.
- `P055` thin CLI exposure: operator surface is
  `aeat config init` (via the wizard runner registered through
  `_register_wizard_commands`); the handler delegates to the
  backend service. Help text is canonical config vocabulary
  only.

## Guards held

- No CLI-local business logic; `config init` delegates to the
  wizard runner + canonical backend.
- No compatibility aliases for the retired `aeat setup` surface.
- No codified metastate about the removed root; its absence is
  the architecture.
