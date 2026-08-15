---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:aeb2f57a7d0a5d20b9f7ed2a791caa9107a14140b737f748990fc8ffe7cb078b'
step_id: 'S114'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh repair the two stale schema tests the build crash was masking, one asserting a required profile argument on a command whose parameters are all optional and which resolves to a different verb, the other parametrised against a command key carrying zero production declarations, both unreachable while the coverage gate crashed and neither attributable to the step that revealed them

## Scope

- The row's stated path `src/cadrumo/entrypoints/mcp/tests/` is itself stale: the MCP
  entrypoint relocated to the `cadrumo-harness` package before this row was written. The
  live location is `src/cadrumo-harness/src/cadrumo_harness/mcp/tests/`
  (`test_action_projection.py`, `test_tools_and_dispatch.py`).

## Description

- Reproduced the full package under the `unit`/`integration` markers, captured to disk,
  and located the two tests by evidence rather than by name-guessing.
- Test 1, `test_action_projection.py::test_mcp_action_projection_refuses_an_orphan_target_and_insufficient_sources`:
  its `insufficient_catalogue` sub-case targets `config.profile.edit` expecting a
  "insufficient action argument specifications" refusal from zero declared argument
  specifications. Probed the live schema: `config.profile.edit`'s `required_input_names`
  is empty — every wizard field, including `profile_name`, is a schema-optional CLI
  argument (`str | None`, default `None`), with required-ness enforced in the command
  body (`_require_profile_name`) rather than the advertised schema — the same
  headless-dispatch shape already used by `modelo.work.*`. Zero declared specifications
  trivially cover zero required names, so the refusal never fires; the test's premise
  (this command has a schema-required input) is stale. Git-blamed the change: commit
  `d18e37c27409c782786c21d1a5e49d7e1244f710` (2026-08-10) retyped `profile_name` to
  optional; this test was authored later (at the MCP relocation) and never re-verified
  against that shape, so it was never green on the live surface, not merely masked.
  Fix: kept the orphan sub-case on `config.profile.edit` (identity mismatch does not
  depend on required-ness) and re-founded the insufficient sub-case on
  `config.auth.certificate.remove`, whose `name` argument is genuinely schema-required —
  confirmed by probing `build_verb_input_schemas`. The test still proves the real
  refusal path fires on a live command with a real required input.
- Test 2, `test_tools_and_dispatch.py::test_closed_value_axes_reach_the_mcp_schema_as_enums[registry.audit_oracles-environment-...]`:
  `KeyError: 'registry.audit_oracles'` — the command key is not a descriptor at all.
  Swept `src/cadrumo/entrypoints/cli/registry.py` (the entire `registry` CLI app:
  `inspect`, `verify`, `verify-filed-state`, `diff-revisions`, plus `citations`/`manuals`
  subgroups) and grepped the whole tree: no `audit-oracles`/`audit_oracles` CLI, MCP, or
  application-layer command exists or ever existed under any name.
  `OracleEnvironment` is real and `audit_oracle_bindings`/`audit_registry_oracle_bindings`
  are real, but both are pure internal domain functions
  (`domain/calculations/registry/_live_parity.py`) with zero callers outside their own
  test suite — never wired to an operator-facing verb. Git history confirms the
  parametrize entry has exactly one commit (the relocation) — it was never a live case
  that later broke; it was aspirational from authoring. This is the "zero production
  declarations" side, not a lost declaration: the production surface is not
  under-declared, the test names a verb that was never built. Fix: retired the entry
  from the parametrize list with an inline comment recording why, rather than deleting
  the assertion logic or the surrounding test — the other five parametrize cases
  (`diagnostics.telemetry.*`, `modelo.filing_record.import`, `review.queue`,
  `app.live.borrador.100.list`) are untouched and still exercise real live commands.
- Neither fix touched production MCP or CLI surface modules — both were genuine
  stale-test repairs on the test side, per ownership.

## Outcome

- `test_action_projection.py`: 8 passed (previously 1 failed, 7 passed).
- `test_tools_and_dispatch.py`: 29 passed under `-m integration` (previously 1 failed, 29
  passed — the fixed parametrize case now passes cleanly).
- Full package re-run (`-m "(unit or integration) and not external_tool and not
  os_keychain and not serial"`): 43 failed, 318 passed — down from 45 failed, 317 passed
  before this row's changes. The delta is exactly the two rows fixed here; no new
  failures were introduced and no other test's pass/fail state changed.
- Row can be marked complete: both named tests are fixed and verified.

## Notes

- The remaining 43 red tests in the package are **not** attributable to this row and were
  left untouched, per the ownership boundary (no production MCP/CLI edits) and per the
  instruction not to chase `W04.P07.S112`:
  - A large cluster (`test_identity_gate.py`, `test_serving_gates.py`,
    `test_harness_delivery.py::test_floor_tool_call_returns_the_active_persona_payload`
    and `test_whoami_identity_is_null_when_no_profile_is_active`,
    `test_meta_tools.py`, `test_inprocess_runtime.py`, `test_client_handshake.py`,
    `test_server_loop_responsiveness.py`, `test_warm_wedge_fallback.py`, two
    `test_inprocess_envelope_parity.py` cases) all crash on the SAME production
    `ValueError: orphan mounted family declaration config passphrase from
    OperatorSurfaceContract.command_families`, raised from
    `cadrumo.application.operator_surface._manifest.reconcile_operator_surface_inventory`
    via `resolve_cli_precondition_action`. This is precisely the "six surfaces must agree
    a verb exists and none is authoritative" defect the plan already tracks as
    `W04.P07.S112` — it bears directly on that row's evidence (a `config passphrase`
    family is orphaned in `OperatorSurfaceContract.command_families`), not on this one.
  - A second large cluster (`test_corpus_resource.py`, `test_corpus_tools.py`, and one
    `test_inprocess_envelope_parity.py` case) crashes on a live `RegistryValidationError`
    from the bundled registry (missing export layouts, an unresolved layout-authority
    source, a mis-tiered orden excerpt, and a `y-siguientes` revision whose own window
    closes) — the ongoing "registry: continue authority-grade sweep" campaign's territory,
    unrelated to MCP schema tests.
  - A third set are genuine, currently-open regressions distinct from both of the above
    and from this row's two: `test_risk_table_parity.py` (20 exposed commands — mostly
    `app.live.*`, `ledger.evidence.*`, `ledger.counterparty.*` — carry no declared risk
    row), `test_inprocess_envelope_parity.py::test_read_verb_success_envelope_is_byte_identical_across_transports`
    (`registry.inspect` is emitted as `app.registry.inspect` on one transport),
    `test_tool_naming_budget.py`, `test_result_size_budget.py`,
    `test_closed_value_axis_gate.py::test_every_exemption_still_describes_a_real_bare_axis`.
    None of these were named in this row's scope and none share this row's root cause
    (stale test premise); flagging them here so they are not lost, not fixing them under
    this row's authorization.
