---
tags:
  - '#research'
  - '#exception-quality-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:c65b9460d0a8765f4f3d960f25d51d66ad707f38dde237806307c2efd10de455'
related:
  - "[[2026-09-04-reachability-burndown-adr]]"
---
# `exception-quality-burndown` research: `Exception quality burndown`

The question is not whether every Python exception must be replaced. The relevant quality risk is a Cadrumo-created failure crossing an owned operator or transport boundary without the code, category, context, redaction, and rendering contract supplied by the registered error hierarchy. The evidence favors a site-by-site escape-contract decision over a global replacement or inventory gate; the ADR must settle that scope and the campaign's closure rule.

## Findings

### The registered hierarchy is an operator contract, not a universal Python replacement.

`CadrumoError` binds each subclass to the error-code registry at class creation and carries structured context plus a translation key. Registry identity is the fully qualified class name, so re-rooting a public error changes both its hierarchy and its required registry declaration. `CoreValidationError` deliberately also inherits `ValueError`, and `EInvoiceXmlParseError` demonstrates a registered, operator-facing refusal that preserves Pydantic compatibility. `src/cadrumo/core/errors/hierarchy.py:111-337`, `src/cadrumo/core/errors/error_codes.py:222-321`, `src/cadrumo/core/errors/registry/_core.py:101-108`, `src/cadrumo/adapters/inbound/einvoice/xml.py:56-76`, `src/cadrumo/core/errors/registry/_adapters_part2.py:91-98`.

### Bare exceptions are legitimate only with an evidenced local containment or bootstrap reason.

The existing hygiene contract identifies classes rooted only in builtin exception bases, requires their own `__bare_base_rationale__`, and rejects a rationale after rebasing. Its narrow static companion covers optional-import fallbacks only; live registry enforcement imports production modules and verifies real subclass binding. Existing contained examples include operation-observer signals, corpus-manifest payload carriers, previous-filing binding absence, and product-state bootstrap projection. `src/cadrumo/core/errors/tests/test_exception_base_hygiene.py:46-210`, `src/cadrumo/core/errors/tests/test_registry_enforcement.py:108-222`, `src/cadrumo/application/operations/observation.py:101-186`, `src/cadrumo/core/corpus_manifest/manifest.py`, `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py:223-324`, `src/cadrumo/core/config_state_root.py:76-103`.

### The CLI already proves the intended boundary behavior through live contracts.

`command_error_boundary` preserves registered errors and separately projects persisted-data drift, Pydantic validation, and unexpected failures. `emit_error_and_exit` uses the registered category and one rendering route. Tests exercise nested-error unwrapping, corrupt persisted input propagation, text/JSON output, and no-traceback behavior. These behavior tests are the precedent for individual remediations; broad source counting would not prove a candidate leaks. `src/cadrumo/entrypoints/cli/errors.py:473-541`, `src/cadrumo/entrypoints/cli/errors.py:679-849`, `src/cadrumo/entrypoints/cli/errors.py:935-1246`, `src/cadrumo/entrypoints/cli/tests/test_error_boundary_unwrap.py:37-236`, `src/cadrumo/entrypoints/cli/tests/test_ledger_exception_propagation.py:108-143`, `src/cadrumo/entrypoints/cli/tests/test_json_error_contract.py:203`.

### A source inventory is useful for discovery but cannot close the campaign.

The initial inventory found direct builtin and apparently custom exception sites, but review of the `borrador` family showed that a syntactic classification can miss inheritance through an intermediate Cadrumo-derived base. Each lead therefore needs a full trace from definition through catches and its actual public renderer before it can be remediated or retained. `src/cadrumo/adapters/inbound/borrador/errors.py`, `src/cadrumo/core/errors/hierarchy.py:111-167`.

### The first remediation candidates are containment defects, not bulk hierarchy conversions.

`AeatSyncWorkspaceProjectionError` can reach workbench generation without the sibling source-level containment path, making one malformed AEAT Sync source capable of disrupting the workbench. TUI navigation's local `Destination*` and `NavigationContractError` failures can escape screen creation from `navigate_to`, causing a Textual event failure instead of the fail-closed UI state. Both need real adverse-input tests; neither is evidence that every local error type must become a Cadrumo error. `src/cadrumo/application/aeat_sync/workspace.py:51`, `src/cadrumo/application/workspace_reader.py:411`, `src/cadrumo/application/workbench_generation.py:622`, `src/cadrumo/entrypoints/tui/launcher.py:401`, `src/cadrumo/entrypoints/tui/navigation.py:49-70`, `src/cadrumo/entrypoints/tui/navigation.py:297-343`, `src/cadrumo/entrypoints/tui/app.py:245-253`.

### The ADR must choose a boundary-quality policy and reject two unhelpful alternatives.

The favored option is an escape-contract policy: register a Cadrumo-created exception that can cross an owned CLI, TUI, operator, API, AEAT, financial, or persistence boundary as itself; retain a builtin-rooted carrier only with a class-local reason and a focused containment or bootstrap proof. A blanket conversion is clearer but risks changing Pydantic, protocol, and catch behavior without evidence. A rationale-only status quo leaves real boundary leaks unaddressed. Uninvestigated: every inventory lead; they remain discovery inputs, not an accepted defect census.

## Sources

- `src/cadrumo/core/errors/hierarchy.py:111-337`
- `src/cadrumo/core/errors/error_codes.py:222-321`
- `src/cadrumo/core/errors/tests/test_exception_base_hygiene.py:46-210`
- `src/cadrumo/core/errors/tests/test_registry_enforcement.py:108-222`
- `src/cadrumo/entrypoints/cli/errors.py:473-1246`
- `src/cadrumo/entrypoints/cli/tests/test_error_boundary_unwrap.py:37-236`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_exception_propagation.py:108-143`
- `src/cadrumo/application/aeat_sync/workspace.py:51`
- `src/cadrumo/entrypoints/tui/navigation.py:49-343`
