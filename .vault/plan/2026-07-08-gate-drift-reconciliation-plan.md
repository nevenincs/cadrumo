---
tags:
  - '#plan'
  - '#gate-drift-reconciliation'
date: '2026-07-08'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-08-gate-drift-reconciliation-audit]]'
  - '[[2026-07-07-iva-prorrata-complexity-plan]]'
  - '[[2026-06-09-docstring-google-style-plan]]'
  - '[[2026-07-08-mcp-protocol-hardening-plan]]'
  - '[[2026-07-02-arch-remediation-engine-lifecycle-plan]]'
  - '[[2026-07-10-gate-drift-reconciliation-adr]]'
  - '[[2026-07-10-gate-drift-reconciliation-research]]'
---
# `gate-drift-reconciliation` plan

Burn down only the genuinely untracked drift the 2026-07-08 full-gate health snapshot surfaced, priority-ordered from the architectural inversion outward.

## Description

This plan reconciles the full read-only health snapshot captured in the gate-drift-reconciliation audit against the ten plans currently in flight, and schedules ONLY the residue that no in-flight plan owns. A five-agent sonnet reconciliation fleet (RAG plus rg plus plan-doc plus git-log grounded) established the ownership split, so this plan deliberately excludes the red that is already owned: the ledger complexity growth in the iva-ledger, invoice-models, and ledger-add surfaces belongs to the iva-prorrata-complexity plan (its open step W02.P03.S21); the single biggest complexity offender, the MCP build-server at 455 lines against a 341 budget, belongs to the mcp-protocol-hardening plan (its open step P04.S15); and the broad format, type-diagnostic, and baselined-complexity noise across 5657 dirty files is campaign work-in-progress that clears when the owning campaigns commit. Two closed plans left untracked test-fixture residuals that now hard-fail and are scheduled here: the arch-remediation-engine-lifecycle plan tightened per-bucket storage-session binding without sweeping two shared test fixtures, and the cross-period-filing-clean-state plan tightened the profile-create contract without sweeping one shared config-test helper. The docstring links this plan schedules are absent from the docstring-google-style plan checklist because those modules were scaffolded after it. The registry authority itself verifies clean (73 modelos, 15705 casillas), so the priority is the architectural inversion whose blast radius is widest, then shadow and duplication, then the fixture regressions, then documentation regeneration, then the small static leftovers, then a gated verification pass. The full evidence, the tracked-versus-untracked map, and the corrections (notably that the 36-leaf OutputSchema failure is stale test-fixture debt, not a production gap) live in the related audit.

## Steps

### Phase `P01` - invert the prorrata layering dependency

Close the untracked application-to-adapters inversion via prorrata_register by introducing a domain-side port, the priority-one fix because calculation, persistence, and verification all sit atop it.

- [x] `P01.S01` - Add a domain-side port protocol for the prorrata register; `src/aeat/domain/prorrata_register/_protocols.py`.
- [x] `P01.S02` - Retype the iva-ledger prorrata_register dependency onto the port; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `P01.S03` - Retype the revision-persistence prorrata_register dependency onto the port; `src/aeat/application/modelo/_revision_persistence.py`.
- [x] `P01.S04` - Retype the prorrata-regularizacion register and storage dependencies onto ports; `src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `P01.S05` - Reconcile the importlinter allowlist to the sanctioned construction edge and confirm the layered contract is green; `.importlinter`.

### Phase `P02` - burn down the shadow and duplication surface

Resolve the one confirmed shadow and the promotable duplication clusters the semantic mapping fleet confirmed, before they accrete further.

- [x] `P02.S06` - Delete read_active_profile and migrate the two wizard call sites onto WorkflowState.active_profile_record; `src/aeat/application/user_profile/_orchestration.py`.
- [x] `P02.S07` - Promote the duplicated PDF-extraction-coverage error constructor to a single canonical home; `src/aeat/domain/justificante/_errors.py`.
- [x] `P02.S08` - Promote the duplicated per-perceptor replace-observations loop to a shared helper; `src/aeat/application/aggregation/_percepciones_observations_repository.py`.
- [x] `P02.S09` - Migrate the fourteen CLI Typer-argument clone pairs onto the shared option and argument aliases; `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py`.
- [x] `P02.S10` - Investigate the two-member drift between the enrolled source-kinds set and the source mesh; `src/aeat/application/calculations/_calculation_source_policy.py`.

### Phase `P03` - fix the storage and profile fixture regressions

Repair the real, untracked test-fixture residuals left by closed refactor plans that now hard-fail.

- [x] `P03.S11` - Align the seeded bucket id in the work-resume isolated-backend fixture with the storage span it opens; `src/aeat/entrypoints/cli/tests/test_work_resume.py`.
- [x] `P03.S12` - Align the seeded bucket id in the overview-calendar test support fixture with the storage span; `src/aeat/entrypoints/cli/tests/_overview_calendar_support.py`.
- [x] `P03.S13` - Add the required identity flags to the shared create-profile config-test helper; `src/aeat/entrypoints/cli/_config/tests/test_config.py`.
- [x] `P03.S14` - Update the ledger canonical-spine roster and count for the shipped exclude and llm-diagnostics verbs; `src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py`.
- [x] `P03.S15` - Replace the human-readable profile id literal with a canonical UUID in the M100-M190 retenciones CLI test; `src/aeat/entrypoints/cli/tests/test_modelo_100_m190_retenciones_cli.py`.
- [x] `P03.S16` - Decide the M390 export refusal ordering between cross-period clean-state and missing-layout and align gate or test; `src/aeat/application/modelo/_export.py`.
- [x] `P03.S31` - Sweep the profile-creation identity-flag drift across all config and CLI test helpers (add entity-type/name/surnames), extending S13; `src/aeat/entrypoints/cli/_config/tests/`.

### Phase `P04` - regenerate the documentation surfaces

Clear the docs-check failures by regenerating the CLI reference, adding the missing docstring links, and fixing the stale conformance list and Sphinx cross-references.

- [x] `P04.S17` - Regenerate the CLI reference for the new prorrata verbs and options; `docs/cli/app.rst`.
- [x] `P04.S18` - Add the core-struct docstring cross-link to the prorrata regularizacion module; `src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `P04.S19` - Add the core-struct docstring cross-links to the calculation source-staging public functions; `src/aeat/application/modelo/_calculation_source_staging.py`.
- [x] `P04.S20` - Refresh the stale payload-module import list in the CLI-reference conformance test; `dev/docs/tests/test_cli_reference_conformance.py`.
- [x] `P04.S21` - Module-qualify the two unresolved Sphinx cross-references; `src/aeat/adapters/persistence/profile/transactions.py`.

### Phase `P05` - clear the untracked static and governance leftovers

Fix the small untracked style, dead-code, surplus-kwarg, line-budget, and unreachable-module items no in-flight plan owns.

- [x] `P05.S22` - Fix the D411 See-Also blank-line lint in the verification-predicates validator; `src/aeat/domain/calculations/registry/_validate_verification_predicates.py`.
- [x] `P05.S23` - Remove the unused noqa and resolve the S607 partial executable path in the MCP call-runtime; `src/aeat/entrypoints/mcp/_call_runtime.py`.
- [x] `P05.S24` - Remove the surplus kwarg on the diagnostics telemetry bad-tier path; `src/aeat/entrypoints/cli/_diagnostics.py`.
- [x] `P05.S25` - Remove the four dead-code unused variables flagged by vulture; `src/aeat/adapters/outbound/google/_document_link_resolver.py`.
- [x] `P05.S26` - Bring the untracked loader module within its line budget or record a reviewed baseline; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P05.S27` - Make the three unreachable diagnostics modules test-reachable or remove them; `src/aeat/entrypoints/cli/tests/test_test_inventory.py`.

### Phase `P06` - re-run gated verification and confirm green

Obtain a true integration and security reading with the passphrase set, triage the residual real failures, and confirm the reconciled gates pass.

- [x] `P06.S28` - Re-run the integration suite and semgrep interactively with the passphrase set and record the true failure and security counts; `src/aeat`.
- [x] `P06.S29` - Triage the residual real integration failures in the agent-eval and ledger clusters into tracked or untracked; `src/aeat/agent/eval/tests/test_lifecycle_contradiction_golden.py`.
- [x] `P06.S30` - Confirm the layered contract docs-check and the two fixture-regression suites are green after the earlier phases; `.importlinter`.

## Parallelization

P01 is the priority-one prerequisite and lands first: its steps carry a hard internal order (S01 defines the port before S02, S03, and S04 retype onto it, and S05 reconciles the importlinter contract only once the retypes land). P02 through P05 share no hard interdependency and may be executed in parallel by separate workers once P01 is in flight, with two exceptions that pair tightly: P03.S11 and P03.S12 are the same fixture defect in two files and should land together, and P04.S17 (CLI-reference regeneration) must precede P04.S20 (the conformance-list refresh) only if both touch the same generated surface, otherwise they are independent. P06 is the closing gate and runs last, after every earlier phase is closed. Within P02, P04, and P05, each Step is independently committable. Do not fix the owned-elsewhere red (the iva-prorrata ledger complexity, the MCP build-server split, the broad format and type noise); those belong to their in-flight plans named in the Description.

## Verification

The plan is complete when every Step is closed. Per-phase success criteria: P01 is verified when `uv run --no-sync lint-imports` reports the AEAT layered-architecture contract KEPT and the unit test `test_application_to_adapters_pin_count_does_not_grow` passes. P02 is verified when `read_active_profile` no longer exists, its two former call sites resolve through `WorkflowState.active_profile_record`, and `just audit-duplication` shows the promoted clusters gone. P03 is verified when the 12 `test_work_resume` errors, the 10 `test_overview_calendar_verb` failures, the 3 `test_config` switch failures, the ledger canonical-spine tests, and the M100-M190 retenciones test all pass, and the M390 refusal-ordering decision is recorded. P04 is verified when `just docs-check` passes end to end (docs pytest, doc8, and interrogate all run) and `python -m dev.docs.apidocs scaffold --check` stays clean. P05 is verified when `just check-style` is clean, `just audit-dead-code` shows the four variables gone, and the loader line-budget and unreachable-module ratchets pass or carry a reviewed baseline. P06 is verified when an interactive re-run with `AEAT_SECRET_PASSPHRASE` set records a true integration and semgrep count, the residual real failures are each mapped to tracked or untracked, and the layered contract plus docs-check plus the two fixture-regression suites are confirmed green. Registry authority correctness is out of scope and already verified clean in the related audit.
