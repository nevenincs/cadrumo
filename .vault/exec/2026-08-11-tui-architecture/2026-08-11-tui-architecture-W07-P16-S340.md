---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:7756a10097409f6327ba7fe1694e9a130fe29d81ca40df02795c75ebbc53c535'
step_id: 'S340'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Route the spreadsheet export command through the operation supervisor instead of reaching around it into the service: the modelo spreadsheet command composes the export service directly and calls its execute method with a request, bypassing the supervisor entirely -- even though that export is a fully registered operation with a definition, a journal, a lease and a recovery action. So a live operator path executes an operation OUTSIDE the platform that exists to govern it: the run is not journalled, holds no lease, cannot be cancelled, cannot be resumed after a crash, and produces no observation any frontend can watch. Every safety property the operations platform provides is absent on the one path an operator actually takes for this export. Submit through the supervisor as the censal path does, and prove the run is journalled and leaseable rather than merely that it succeeds. NOTE deliberately NOT to encode a matcher for this shape: a rule forbidding a frontend from calling execute on an application service would match a NAME rather than a structure, which is the fourth such gate this campaign has found and rejected; if a gate is wanted here it must judge whether a registered definition exists for the work being done, not what the call is spelled; `the modelo spreadsheet export command's execution path and a journalled-and-leased proof of the routed run`. [A 'PREMISE CORRECTED' BLOCK ONCE STOOD HERE AND WAS RETRACTED; its three claims were all wrong and the row's original text is correct. Root cause kept because it outlives the error: the definition search grepped the literal kwarg form definition_id="...", which only TEST fixtures use, while every real registration builds an OperationDefinition from a module-level constant -- so the search enumerated a SPELLING and reported it as the population. A grep that finds nothing proves nothing until the pattern is shown to match a known-present case.] ROUTE CONFIRMED IMPLEMENTABLE 2026-08-31, with every piece located. The definition is registered with the supervisor the CLI would submit to: entrypoints/operation_composition.py:166 installs build_google_sheets_export_operation_registration, and :136 its definition. The bypass is entrypoints/cli/_modelo_spreadsheet_cli.py, in execute_google_sheets_export, which calls compose_google_sheets_export_service().execute(GoogleSheetsExportOperationRequest(...)) and returns (active, result). The exemplar for submit-and-start is entrypoints/cli/_config/_custody.py:281 -- compose_operation_dependencies(), await services.submission.submit(request, actor_ref=...), await services.submission.start(receipt.operation_id), bridged from Typer by asyncio.run, with services.shutdown() in a finally. RESULT RETRIEVAL, which the row's history left uncertain and which is the reason this is not a call-site swap: the logout exemplar needs NO result and so demonstrates none. The export does -- its envelope prints value_cells_written, formula_cells_written, protected_ranges_written and tab_count off a typed GoogleSheetsExportOperationResult, and the definition declares result_type accordingly. The mechanism EXISTS: OperationResultProjectionService.resolve at application/operations/projection_services.py:609, reachable as composed.result. Note it currently has no production caller, which is the same reach-without-a-surface shape W07.P17.S338 measures and W06.P12b.S77 carries as its one open clause -- so this row would be its FIRST consumer. THE UNSOLVED PART, and it is a design question rather than plumbing: the bypass maps four executor exceptions to typed CLI refusals -- GoogleSheetsExportCapabilityDisabledError, GoogleSheetsExportRootFolderRequiredError, GoogleAuthError and OutboundStorageError. Through the supervisor those stop being exceptions the caller catches and become FAILED OPERATIONS, so each refusal must be reconstructible from the failure the platform records or the operator loses four distinct, actionable messages in exchange for a generic one. Settle that before routing; a submission that journals correctly while degrading every refusal to 'export failed' trades one safety property for another. TUIMODELO_SCOPE: RETAINED_BY_SOURCE_OWNER; modelo-subject and PARTIALLY overlapping. Tuimodelo's W02.P06.S25 gives the spreadsheet round trip an application service and moves its staleness refusal off the outbound adapter, which is the application-service half only; routing the command through the operation supervisor is a different subject and stays here.

## Scope

- `the modelo spreadsheet export command's execution path and a journalled-and-leased proof of the routed run`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

- `M` `src/cadrumo/application/export/google_operation.py`
- `M` `src/cadrumo/application/operations/frontend_contracts.py`
- `M` `src/cadrumo/application/operations/models.py`
- `M` `src/cadrumo/application/operations/observation.py`
- `M` `src/cadrumo/application/operations/supervisor.py`
- `M` `src/cadrumo/application/operations/tests/test_public_contracts.py`
- `M` `src/cadrumo/application/operations/tests/test_supervisor.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_cli.py`
- `M` `src/cadrumo/entrypoints/tests/test_google_operation.py`
- `verify:` `.venv/Scripts/python.exe -m pytest -n0 -q -m "" src/cadrumo/application/operations/tests/test_supervisor.py -k "registered_executor_refusal or unexpected_executor_failure or registered_non_refusal"` -> `pass`
- `verify:` `.venv/Scripts/python.exe -m pytest -n0 -q -m "" src/cadrumo/application/operations/tests/test_models.py src/cadrumo/application/operations/tests/test_public_contracts.py src/cadrumo/core/errors/tests/test_registry_enforcement.py` -> `pass`
- `verify:` `.venv/Scripts/python.exe -m pytest -n0 -q -m "" src/cadrumo/entrypoints/tests/test_google_operation.py` -> `pass`
- `verify:` `.venv/Scripts/python.exe -m ruff check <S340 paths>` -> `pass`
