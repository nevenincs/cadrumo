---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
---



# `cli-workflow-redesign` W06 Output Rendering Code Review

Status: REVISION REQUIRED


W06-001 | HIGH | Registry CLI still owns backend contracts, service orchestration, and domain policy

`src/aeat/entrypoints/cli/registry.py` still defines Pydantic report contracts in the CLI layer, including `RegistryTreeReport`, `RegistryRevisionDetailReport`, `FiledDataCaptureReport`, `FiledDataListingReport`, and `FiledStateVerificationReport` at lines 79-207. The same module also owns registry inventory aggregation, live-session capture orchestration, filed-state calculation inputs, source-observation resolution, and filing-period fallback policy across lines 224-356 and 464-665. Tests import and exercise those functions directly from the CLI module, for example `select_declarations_for_capture`, `_filed_data_listing_row`, and `verify_filed_state` in `src/aeat/entrypoints/cli/test_registry_cli.py`. This violates the W06 plan and output-rendering ADR boundary that CLI handlers must remain argument parsing plus backend delegation, with business logic, schema conversion, validation policy, orchestration, persistence, and provider behavior owned by core/application/domain services. Move these contracts and operations behind centralized backend services, then leave the Typer handlers to call those services and pass the returned payload plus text lines to `_emit`.

W06-002 | HIGH | Invalid root `--format` becomes an internal unexpected error instead of a registered validation/refusal

The root callback stores any arbitrary `--format` string in `ctx.obj` at `src/aeat/entrypoints/cli/__init__.py` lines 103-115, while `render_command_output` coerces it with `OutputFormat(...)` at `src/aeat/core/output_rendering.py` line 46. An invalid value such as `--format xml` raises a raw `ValueError`, which the command error boundary wraps as `CliUnexpectedBoundaryError` and emits as an internal failure with exit code 6. This violates the root `--format json|text` contract and bypasses the registered `OutputRenderingError` path introduced for renderer failures. The root option should be constrained to `json|text` or the renderer should raise a registered `AeatError` for invalid formats, and the test suite should cover invalid root format behavior through a real Typer invocation.

W06-003 | HIGH | Registry still exposes filed-data live reads under the rejected registry surface

`src/aeat/entrypoints/cli/registry.py` still registers `list-filed-data`, `capture-filed-data`, and `capture-source-filed-data` at lines 206, 254, and 312. Those commands call `list_filed_data`, `capture_filed_data`, and `capture_source_filed_data` in `src/aeat/application/registry/__init__.py`, where the service opens an authenticated AEAT session through `_active_verified_session`, `require_live_read`, and `operation="registry-live-read"` at lines 345-451 and 726-731. The app-registry-boundary ADR explicitly requires those live filed-declaration reads to move out of registry into `aeat app live filed` and requires removal of the old registry filed-data registrations in the same refactor. There is no `app live filed` surface in the current CLI tree, and `src/aeat/entrypoints/cli/test_registry_cli.py` still blesses the rejected registry paths at lines 422-518. Move these workflows to the accepted live-filed application/CLI owner, remove the registry command registrations, and replace the registry tests with absence checks for the old paths plus real behavior checks for the new `app live filed` grammar.

W06-004 | HIGH | Declaration review keeps a command-local output selector that bypasses root `--format`

`src/aeat/entrypoints/cli/_declaration.py` still declares `declaration_review(..., format_: str = typer.Option(_FORMAT_TABLE, "--format", ...))` at lines 215-220, then treats a command-local `--format json` as authority to mutate `ctx.obj["format"]` at lines 234-235. The output-rendering ADR rejects command-local format selectors and makes root `--format json|text` the only output-mode selector. This also preserves a third local mode, `_FORMAT_TABLE`, that is not part of the accepted root contract. Remove the command-local `--format` option from declaration review and let `_emit` read only the root format captured by the root callback; add a real CLI regression asserting `aeat app declaration review --format json` is rejected while `aeat --format json app declaration review ...` remains the supported path.

## Re-review 2026-05-13

Status: REVISION REQUIRED

Requested W06 closure checks are confirmed against the scoped files.

- W06-001 is closed for the scoped registry CLI boundary: `src/aeat/entrypoints/cli/registry.py` now imports typed services from `aeat.application.registry` at lines 10-18 and its handlers only call those services plus `_emit`; registry report contracts and filed-state orchestration now live in `src/aeat/application/registry/__init__.py`.
- W06-002 is closed: `src/aeat/core/output_rendering.py` catches invalid `OutputFormat` coercion at lines 50-53 and raises registered `OutputFormatRefusedError`; `src/aeat/core/errors/registry/_core.py` registers it as `REFUSED_OUTPUT_FORMAT` at lines 17-27. `src/aeat/core/test_output_rendering.py` asserts the registered code and exception at lines 52-56, and `src/aeat/entrypoints/cli/test_registry_cli.py` asserts a real `--format xml` invocation exits through the refused error path at lines 305-322.
- W06-003 is closed: `src/aeat/entrypoints/cli/registry.py` registers local registry commands only, with no `list-filed-data`, `capture-filed-data`, or `capture-source-filed-data` commands; `src/aeat/application/registry/__init__.py` exports only local registry inspection, verification, workbook, parity, oracle audit, and local filed-state verification services at lines 453-466. The moved live filed services live in `src/aeat/application/live/__init__.py` and call `require_live_read()` before authenticated session creation at lines 290-296.
- W06-003 live shape is present with no registry aliases: `src/aeat/entrypoints/cli/__init__.py` mounts `_live_module.app` under `app live` at line 212; `src/aeat/entrypoints/cli/_live.py` mounts `filed_app` under `live filed` at line 40 and registers `filed list`, `filed capture`, and `filed capture-sources` at lines 47, 86, and 129. `src/aeat/entrypoints/cli/test_registry_cli.py` asserts the new help path and old registry aliases are rejected at lines 424-443.
- W06-004 is closed: `src/aeat/entrypoints/cli/_declaration.py` declares `declaration_review` with only `ctx`, `--period`, `--modelo`, and `--id` at lines 213-219; `src/aeat/entrypoints/cli/test_backend_boundary.py` asserts the function has no `format_` parameter at lines 173-184.

Verification run: `uv run --no-sync pytest src/aeat/core/test_output_rendering.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_registry_cli.py -q` passed with 26 tests.

W06-005 | HIGH | Production `app live` CLI imports the dev-only `pytest` dependency

`src/aeat/entrypoints/cli/_live.py` imports `pytest` at line 9 and calls `pytest.skip()` from `requires_live_enabled()` at lines 17-26. That module is no longer test-only: `src/aeat/entrypoints/cli/__init__.py` imports `_live` while building the production app tree at lines 55-62 and mounts it under `aeat app live` at lines 203-215. Because `pytest` is not a project runtime dependency and is declared only in the dev dependency group, an installed runtime without dev dependencies will raise `ModuleNotFoundError` during CLI app import and make the `aeat app` surface unavailable. Move the live-test skip helper out of the production CLI module, or make it avoid importing `pytest` at module import time, so the accepted `aeat app live filed` surface does not depend on the test runner.

## Final closure 2026-05-13

Status: CLOSED

W06-005 is closed: the production live command surface lives in `_app_live.py`, while `_live.py` is again only the live-test gate helper. The production root imports `_app_live` for `aeat app live` and does not import `_live` while building the runtime app tree.

Direct static checks confirm the registry command module no longer registers `list-filed-data`, `capture-filed-data`, or `capture-source-filed-data`; `declaration_review` has no `format_` parameter; invalid output formats raise the registered `OutputFormatRefusedError`; and the only old registry filed-data strings in the scoped tests are negative alias-rejection assertions.

Verification run: `uv run --no-sync pytest src/aeat/core/test_output_rendering.py src/aeat/application/operator_surface/test_contract.py src/aeat/application/overview/test_calendar.py src/aeat/application/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_root_help_shape.py src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/entrypoints/cli/test_registry_cli.py src/aeat/core/i18n/test_output_language.py -q` passed with 83 tests.
