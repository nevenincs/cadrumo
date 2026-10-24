---
tags:
  - '#plan'
  - '#component-on-demand'
date: '2026-10-24'
tier: L1
related:
  - '[[2026-10-18-dependency-provisioning-unified-setup-adr]]'
  - '[[2026-10-24-rust-component-provisioning-reference]]'
modified: '2026-10-24'
body_schema: body-v2
body_hash: 'sha256:3e275de52cd0d6c25b3cce8babf486ed989271b157535e6f530b4aee5e262a65'
---

# `component-on-demand` plan

When a feature needs the browser or the local AI and it is not ready, every surface says what is missing and offers its setup.

## Description

Approved 2026-10-24. Basis: the owner's reply "all approved, implemnet" to the presented plans and `2026-10-24-rust-component-provisioning-adr`.

The owner requires the application to be on demand: calling a feature that needs a provisioned component must show the person that the component is needed. `2026-10-24-rust-component-provisioning-reference` verified the state on 2026-10-24.

- The browser has a launch guard that names `operator.provision.browser`. MCP and the desktop agent route it to setup. The CLI prints raw action lines, and the TUI prints a command string.
- The local AI does not route to setup at all. The reader probe builds no-action verdicts (`src/cadrumo/application/local_reader.py:457-477`), and readers probe only after they fail. Column mapping fails silently. The desktop routes only agent tool refusals.

Decision coverage: `2026-10-18-dependency-provisioning-unified-setup-adr` already governs this work. Its D9 covers the closed categories and the one action. D10 covers the blocked-feature prompt that names the item and opens setup on it. D8 covers the recovery action named by every dependency refusal. No new costly decision is involved.

The work is independent of the proposed `2026-10-24-rust-component-provisioning-adr`. It keeps the item ids and recovery actions that record preserves, so it holds before and after the engine moves to Rust. S01 to S05 are product-side verdicts and wording; S06 to S08 are surface routing; S09 is the gate.

## Steps

- [x] `S01` - Name operator.provision.local_ai in the reader probe verdicts for runtime unreachable and role model not installed; a role the catalogue cannot serve on this hardware keeps its no-action verdict; `src/cadrumo/application/local_reader.py, src/cadrumo/application/provisioning_contracts.py and tests`.
- [x] `S02` - Check the role's reader before the first effect in evidence draft extraction and ledger classification, refusing with that verdict instead of a generic classifier error; `src/cadrumo/application/ledger/invoice_draft_extraction.py, src/cadrumo/entrypoints/ledger_llm_composition.py, src/cadrumo/application/ledger/batch_ingest.py and tests`.
- [x] `S03` - Turn a missing column-mapping or supply-nature model into a typed advisory naming the local AI item instead of a silent decline; `src/cadrumo/adapters/outbound/llm/column_role_mapping.py, src/cadrumo/application/ledger/column_roles.py, src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py and tests`.
- [x] `S04` - Check the browser item at the start of every tax agency read and sign-in operation, before any certificate or secret loads; `src/cadrumo/adapters/outbound/aeat/browser/session.py, src/cadrumo/adapters/outbound/aeat/browser/factory.py, the live capture operation preflights under src/cadrumo/application/live/ and tests`.
- [ ] `S05` - Word the browser and reader refusals and the label-fallback notice with the component's name and its setup action in four languages, and register a REFUSED error code with a message key for a missing browser so a no-effect browser refusal settles REFUSED; `src/cadrumo/core/errors/error_codes.py and its catalogue, the provisioning and ledger subtrees of src/cadrumo/locales/*/ through the dev.locales workflow, src/cadrumo/application/dependency_wording.py, src/cadrumo/adapters/outbound/aeat/browser/session.py (code only) and tests`.
- [x] `S06` - Render a provisioning verdict on the CLI as the sentence plus the exact setup command instead of raw precondition action lines; `src/cadrumo/entrypoints/cli/config/status_rendering.py, the shared CLI refusal renderer and tests`.
- [x] `S07` - Route a provisioning verdict from the TUI operation modal to the Setup screen on that item; `src/cadrumo/entrypoints/tui/operations/run_result.py, src/cadrumo/entrypoints/tui/operations/refusal_explanation.py, src/cadrumo/entrypoints/tui/setup/ and tests`.
- [x] `S08` - Route every desktop refusal whose verdict names operator.provision to the setup prompt on that item, and give the Readers tab a set-up action; `native/desktop/frontend/src/shell/ledger.ts, native/desktop/frontend/src/App.tsx, native/desktop/frontend/src/components/ledger/documents/DocumentPanels.tsx, native/desktop/frontend/src/components/ledger/documents/DraftReview.tsx, scenarios and stories`.
- [ ] `S09` - Add the consumer gating gate: every browser and model-role consumer declares its item and refuses with operator.provision.<item> before any effect; `src/cadrumo/application/tests/test_dependency_consumer_gating.py`.
- [x] `S10` - Carry the column reader refusal through invoice bulk intake instead of turning every error into a silent decline, and make the reader probe check the model the mapper actually sends; `src/cadrumo/entrypoints/invoice_intake_operation_composition.py, src/cadrumo/adapters/outbound/llm/column_role_mapping.py, src/cadrumo/application/local_reader.py and tests`.
- [ ] `S11` - Keep the reader verdict on the outer evidence extraction refusal so it routes to setup, and carry the local AI recovery action on the reader readiness projections; `src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py, src/cadrumo/application/ledger/invoice_evidence_readiness_operation.py, src/cadrumo/_data/operations/contract_manifest.json and tests`.

## Parallelization

Ordering and parallel lanes:

- S01 lands first, because every later Step consumes its verdict.
- S02, S03 and S04 may run in parallel after it; their write sets are disjoint.
- S05 follows S01 to S04, because it words their verdicts.
- S06, S07 and S08 may run in parallel after S05. They are the CLI, TUI and desktop lanes, with disjoint write sets.
- S09 is authored early against S01's verdict shape and is expected to fail until S02 to S04 land.
- All work stays in the shared `tui` worktree. Each Step commits only its own paths through a private index built from HEAD.

## Verification

- Each Step's focused tests pass through the real resolver and probe, against an injected missing model, an unreachable runtime and a missing browser build. A mocked probe is not acceptance evidence.
- The S09 gate fails on a representative defect in an isolated fixture: a consumer with no pre-check, and a verdict without an action.
- `just check-locales`, `just check-operation-contract-manifest`, `uv run --no-sync lint-imports --config .importlinter --no-cache`, `just check-style`, `just check-format` and `just check-types` pass on the touched scope.
- Desktop: `npm run check` and `npm run test` in `native/desktop/frontend`, and a scenario per refusal route.
- No rendered sentence carries a category, an operation id or internal vocabulary (unified-setup D9).
- The plan is complete when every Step is closed and the integrated plan-close review passes.
