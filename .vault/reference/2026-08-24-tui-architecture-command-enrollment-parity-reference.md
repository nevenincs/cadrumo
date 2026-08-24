---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7ba5234554805d9ed4c63ef40d0c98c64a2edb2416ea54b0bc070283676d0e44'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-interface-adr]]"
---

# `tui-architecture` reference: `TUI command enrollment parity`

This audit joins the executable command graph to every production full-screen
launch site. It distinguishes a screen that exists and is callable today from
the still-unbuilt dedicated `cadrumo.entrypoints.tui` topology.

## Summary

The production command graph originally declared only `config_profile_create`
and `config_profile_edit` as `TuiCapability.AVAILABLE`. Both declarations point
to real screens through `with_manager_frontend`, `present_registration`, and
`present_profile_manager`.

Six further graph nodes also reach real full-screen implementations:

- `config_login` reaches `run_login_tui` through `login_screen_is_available`.
- `config_profile_status` reaches `StatusApp.run` through `present_status_tui`.
- the executable `config_profile_descendiente` group reaches `run_form_tui`
  through `present_form`; its `add`, `list`, and `remove` children do not.
- `config_auth_apoderado_configure` reaches `run_form_tui` when its interactive
  field collection arm is selected.
- `app_modelo_work_wizard` and `app_modelo_work_amend_wizard` select the
  full-screen flow frontend when the host reports `FULL_SCREEN` capability.

The truthful implemented-screen set is therefore eight command nodes. The
exported `ModeloWorkReviewApp` is not in that set: no production command handler
constructs or runs it. Lower-level credential, form, flow, and dialog classes
are substrates rather than separate command routes.

`AVAILABLE` currently proves that an existing CLI command can reach an existing
full-screen implementation. It does not prove the accepted future topology:
`cadrumo.entrypoints.tui` and `cadrumo.entrypoints.tui.launcher` do not exist,
and the current consumers still import `cadrumo.adapters.inbound.tui` in
process. The accepted interface ADR presently conflates those two facts by
requiring a dedicated launcher before enrollment. That decision must either be
amended to represent current callable availability separately from migration
completion, or all eight routes must remain refused until the package migration
lands.

The only operator option is the root `--tui`. A leaf-local option on profile
create/edit makes option placement path-dependent and contradicts the global
contract. Explicit requests also need incompatibility rules for JSON output,
machine-secret channels, scripted/defaulted input, and command-field input;
otherwise an enrolled command can silently take its non-screen arm. Help and
version are eager introspection paths and currently take precedence over the
runtime capability policy, which should be stated explicitly or changed.

The fixed-point test should compare the entire `AVAILABLE` key set with the
audited eight-node inventory. Per-screen tests remain necessary to prove the
runtime launch behavior; metadata assertions alone cannot establish it.
