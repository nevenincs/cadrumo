---
tags:
  - '#exec'
  - '#desktop-quality-repair'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:5851611f7a942c097639a8632ac3d74236c02f7806b85e1c65f13e1d09dd4a0b'
related:
  - "[[2026-10-27-desktop-quality-repair-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `desktop-quality-repair` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S02` `M` `dev/packaging/smoke_absent_llm.py`
- `S02` `M` `dev/packaging/tests/test_missing_llm_extra_refuses_instructively.py`
- `S02` `M` `dev/tests/test_lane_reachability.py`
- `S02` `M` `justfile`
- `S02` `M` `src/cadrumo/adapters/outbound/llm/client.py`
- `S02` `M` `src/cadrumo/adapters/outbound/llm/evidence_draft_text.py`
- `S02` `M` `src/cadrumo/adapters/outbound/llm/evidence_draft_vision.py`
- `S02` `M` `src/cadrumo/adapters/outbound/llm/tests/test_evidence_consent_gate.py`
- `S02` `M` `src/cadrumo/application/invoices/tests/test_catalogue_add_operation.py`
- `S02` `M` `src/cadrumo/application/ledger/invoice_draft_extraction.py`
- `S02` `M` `src/cadrumo/core/source_locator.py`
- `S02` `verify:` `just check-code` -> `fail`
- `S02` `verify:` `just check-format` -> `pass`
- `S02` `verify:` `just check-types` -> `pass`
- `S02` `verify:` `uv run --no-sync python -m dev.quality.import_gate` -> `pass`
- `S02` `verify:` `just test-components-role-windows Y:/code/cadrumo-worktrees/tui/build/windows-x64/cargo/desktop/debug/cadrumo.exe` -> `pass`
- `S02` `verify:` `pytest corrected lane-reachability selectors` -> `pass`
- `S02` `verify:` `pytest affected consent catalogue and components tests` -> `pass`
- `S02` `by:` `Terra 6.1 High; Luna Max review`
- `S01` `M` `native/desktop/frontend/src/components/HostRecordList.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ledger/movements/useMovementsView.ts`
- `S01` `M` `native/desktop/frontend/src/components/ledger/useSealedMovements.ts`
- `S01` `M` `native/desktop/frontend/src/components/setup/SetupPrompt.tsx`
- `S01` `M` `native/desktop/frontend/src/components/ui/data-grid.tsx`
- `S01` `M` `native/desktop/frontend/src/dev/ledgerFixture.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/agent-documents-panel.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/columns.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/ledger-pause.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/ledger-provisioning.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/ledger-shell.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/provider-picker.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/scenarios.spec.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/providers.spec.ts`
- `S01` `A` `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-moving-again-ca.json`
- `S01` `A` `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-moving-again-en.json`
- `S01` `A` `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-moving-again-es.json`
- `S01` `A` `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-moving-again-hu.json`
- `S01` `A` `native/desktop/frontend/src/dev/fixtures/modelo/preflight-130-1T-moving-again-stale.json`
- `S01` `A` `native/desktop/frontend/src/dev/fixtures/modelo/renew-130-1T-moving.json`
- `S01` `M` `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-moving-ca.json`
- `S01` `M` `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-moving-en.json`
- `S01` `M` `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-moving-es.json`
- `S01` `M` `native/desktop/frontend/src/dev/fixtures/modelo/modelo-130-1T-moving-hu.json`
- `S01` `M` `native/desktop/frontend/src/dev/fixtures/modelo/preflight-130-1T-moving-stale.json`
- `S01` `M` `native/desktop/frontend/src/components/ledger/movements/MovementsSection.tsx`
- `S01` `M` `native/desktop/frontend/src/shell/ledgerCommands.ts`
- `S01` `M` `native/desktop/frontend/tests/ledger-movements.spec.ts`
- `S01` `verify:` `npm run check` -> `pass`
- `S01` `verify:` `npm test -- --config playwright.scenarios.config.ts --workers=2 (998 scenario population)` -> `fail`
- `S01` `verify:` `npm test -- --config playwright.scenarios.config.ts --workers=1 tests/scenarios/ledger-benchmark.spec.ts tests/scenarios/ledger-movements.spec.ts tests/scenarios/ledger-pause.spec.ts` -> `pass`
- `S01` `verify:` `npm test -- --project product --workers=2` -> `pass`
- `S01` `verify:` `just check-rust Debug` -> `pass`
- `S01` `verify:` `desktop-host-unit-test Debug (594 cases and one existing ignored fixture)` -> `pass`
- `S01` `verify:` `just build-native Debug desktop-host-build` -> `pass`
- `S01` `by:` `Terra 6.1 High; Luna Max review`

## Notes

- `S02` The aggregate ran during concurrent runtime edits; its formatting, type and source-stability failures are resolved by current canonical format/type passes and the stable clean import run 20261027T101035.705132Z-check-import-boundaries-55844-3d5218e6. Ten remaining aggregate gates passed.
- `S02` Component type fixes, test relocations and generated load metadata were committed by the component workstream in 8679cc2016 during execution. Human-claim fixture import/type fixes remain with that workstream; this commit omits its untracked test and related lane references.
- `S02` During checkpoint the component workstream committed the human-claim test and authority backend in ec51298ef8. The final S02 commit therefore includes both Windows lane references; its earlier isolation note records the pre-commit staging boundary.
- `S01` The complete scenario run passed 988 with nine existing skips and failed only the filter benchmark. After the final scheduling correction, all 48 affected ledger scenarios passed with standard retain-on-failure tracing and unchanged budgets; final production coverage is 436 passing cases. Unchanged remaining scenario evidence is reused.
- `S01` Canonical generation supplied six missing fixtures plus five moving-baseline dependencies. Other dirty generated fixtures and provider sign-in additions belong to concurrent work and are excluded from this commit.
