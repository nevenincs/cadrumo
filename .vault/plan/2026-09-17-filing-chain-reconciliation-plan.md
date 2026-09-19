---
tags:
  - '#plan'
  - '#filing-chain-reconciliation'
date: '2026-09-17'
tier: L1
related:
  - '[[2026-09-17-filing-chain-reconciliation-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:bfee0b483b9d310ee24d38fff101854ed7c9f27cb8413697fd973c66968d6410'
---

# `filing-chain-reconciliation` plan

Filing chain, AEAT reconciliation and audited overrides, delivered through the CLI and TUI.

## Description

Approved 2026-09-17. Basis: the operator pre-authorised every approval gate for this feature and asked for autonomous delivery.

Deliver the filing chain, AEAT reconciliation and audited manual overrides decided in `2026-09-17-filing-chain-reconciliation-adr`, grounded in `2026-09-17-filing-chain-reconciliation-reference`. Decision coverage: that ADR governs every Step, and no other decision is involved.

Ownership:
- **Backend worker:** S01 to S04 (domain, application and persistence, plus their existing tests and error and event registries).
- **Surfaces worker:** S05 to S07 (CLI, composition seam, TUI, CLI locales, the generated CLI reference and the scenario test).
- **Orchestrator:** integration, scoped checks and commits.

## Steps

- [x] `S01` - Add chain-entry origin, confirmation, declaration kind and register ref to the filing record with catalogue helpers and forward migration; `src/cadrumo/domain/modelos/filing_record.py`.
- [x] `S02` - Add the reconciliation service with its register-entry input and five outcomes; `src/cadrumo/application/modelo/filing_chain_reconciliation.py`.
- [x] `S03` - Split the observation store into official and pending-local layers and replace the displacement guard with audited overrides; `src/cadrumo/adapters/persistence/profile/calculation_observations.py`.
- [x] `S04` - Rewire file, amend, import and live pull through the chain transitions and the reconciliation service; `src/cadrumo/application/modelo/amendment_actions.py`.
- [x] `S05` - Expose chain, outcomes, layers and overrides in the CLI and add the Sede port factory seam; `src/cadrumo/entrypoints/cli/_modelo_records_cli.py`.
- [x] `S06` - Show chain columns and reconciliation and override events in the TUI filing history; `src/cadrumo/entrypoints/tui/declarations/filing_history.py`.
- [x] `S07` - Add the multi-period CLI-driven reconciliation scenario with a recorded pull port; `src/cadrumo/entrypoints/cli/tests/test_filing_chain_reconciliation_cli.py`.

## Parallelization

- The backend worker first lands the S01 and S02 contract: domain types and the service signature.
- The surfaces worker then starts S05 to S07 against that contract while the backend worker completes S03 and S04. The two write sets are disjoint.
- S07's final run waits for S04.
- Workers run no git. Each worker runs only the test files it creates or edits, sequentially. The orchestrator runs lint, types and the scoped suites once, after handoff.
## Verification

The success criterion is `src/cadrumo/entrypoints/cli/tests/test_filing_chain_reconciliation_cli.py`. It drives only the real CLI (`invoke_cached_cli`, `--json`) against an isolated profile, over three consecutive M130 quarters taken from the support envelope. AEAT pull events come from a recorded in-memory Sede port installed at the composition factory. The scenario:

1. Pull originals for Q1 and Q2. Both outcomes are `APPENDED` and `CONFIRMADA`.
2. Amend Q1 (complementaria). The chain shows `PENDIENTE` amending the confirmed original. Q3 calculate carries the amended Q1 value, and Q3 file is blocked by `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`.
3. Re-pull with only the Q1 original. The outcome is `ALREADY_RECORDED`, and the amendment stays `PENDIENTE` (no false confirmation).
4. Amend Q1 again. The first amendment becomes `DESCARTADA`, and the new one amends the confirmed original.
5. Pull a matching Q1 complementaria. The outcome is `CONFIRMED`, the pending layer is cleared, and Q3 file succeeds as `PENDIENTE`. A Q3 pull then returns `CONFIRMED`.
6. Amend Q2, then pull a Q2 complementaria with different content. The outcome is `CONTRADICTED` with the differing casillas, the AEAT entry is in force and the local entry is `DISCREPANTE`.
7. Override a Q2 observation value with `observe-local --reason`. `filing-record view` shows the override audit and both layers, and the dependent gate flags it. `--clear` restores the official layer.

Also required:
- A declarations-screen pilot test shows the chain columns and events.
- The owning suites for the touched modules pass, and lint and types are clean on the touched files.
- The generated CLI reference is regenerated through its generator.
