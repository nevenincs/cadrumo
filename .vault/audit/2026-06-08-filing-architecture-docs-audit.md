---
tags:
  - '#audit'
  - '#filing-architecture-docs'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - "[[2026-06-08-filing-architecture-docs-plan]]"
---



# `filing-architecture-docs` audit: `Filing Architecture Documentation Gaps and Narrative Transitions Audit`

## Scope

This audit evaluates the narrative, user-facing documentation surface of `aeat` under `docs/` against two primary dimensions:
1. Navigation and index structures in `docs/index.md` and `docs/how-to/index.md`.
2. Conceptual transition gaps between the ledger/classification stage and the modelo calculation/verification stage.

The goal is to identify underdescribed CLI commands, missing recipes, and abrupt transitions that hinder newcomer onboarding and progression.

## Findings

### Finding F01: Missing Modelo 130 How-to Guide
While Modelo 130 is utilized in the on-rails tutorial (`docs/tutorials/index.md`), there is no dedicated how-to guide for Modelo 130 under `docs/how-to/` to match `docs/how-to/modelo-303.md` and `docs/how-to/modelo-390.md`. A user wanting a goal-oriented recipe specifically for Modelo 130 has to extract it from the tutorial context.

### Finding F02: Complete Absence of live-read Command Documentation
The CLI commands under `aeat app live` (such as `aeat app live borrador`, `aeat app live expedientes`, `aeat app live verify`, `aeat app live portals`, and `aeat app live notifications`) are not documented in any narrative guide. The read-only integration with the AEAT portal is a core feature, but is currently a blind spot.

### Finding F03: Missing Documentation for IVA Wallet and Compare Verbs
- The IVA compensation wallet (`aeat app modelo iva-wallet balance`, `aeat app modelo iva-wallet seed`) is briefly mentioned in `docs/how-to/modelo-303.md` but has no dedicated documentation explaining how to view balances or seed historical compensation.
- The comparison utility `aeat app modelo compare` (used to compare draft revisions or draft vs filed states) is completely undocumented.

### Finding F04: Abrupt Conceptual Transition from Ledger to Calculation
The transition from classified ledger transactions to modelo calculations is underdescribed. Newcomers lack a clear explanation of:
- How the engine converts quarterly period tokens (e.g. `1T`) to ledger date ranges (e.g. `2026Q1` or `2026-01-01` to `2026-03-31`).
- How registry bindings map transaction categories to official form box numbers (*casillas*).
- How mixed-use ratios are applied at both the transaction level (`--business-pct`) and the category level (`aeat app ledger ratios set`).

### Finding F05: Abrupt Conceptual Transition from Draft to Verification
The distinction between `aeat app modelo work calculate` and `aeat app modelo work verify` is poorly bridged. The documentation does not sufficiently explain:
- Why verification is a separate step that generates detailed reports.
- What findings represent (ADVISORY vs BLOCKING_RULE).
- The fact that verification captures a ledger snapshot and evidence row set to detect downstream ledger modifications (staleness), ensuring filing-artifact integrity.

### Finding F06: Navigational Gaps in the Landing Page
The landing page `docs/index.md` fails to link to several important how-to guides, including:
- `docs/how-to/censo-update.md` (which links Modelo 036 facts that govern profile readiness and ratios).
- `docs/how-to/review-calculation-values.md` (which covers manual inputs and offsets).
- `docs/how-to/reconcile.md` (which covers justificante comparison).
- `docs/how-to/authenticate-with-aeat.md` (which covers auth setup).

## Recommendations

1. **Create `docs/how-to/modelo-130.md`:** Author a goal-oriented recipe for preparing, calculating, and verifying a Modelo 130 quarterly return.
2. **Create a conceptual bridge document:** Author `docs/explanation/ledger-to-calculation.md` to explain the bindings, period conversions, mixed-use ratios, and the transition from transaction ledger to calculated draft.
3. **Expand `docs/how-to/filing-spine.md`:** Enrich this page to explain the verification gate, findings, snapshot evidence capture, and the recovery commands (`runs`, `resume`).
4. **Create a how-to guide for live AEAT portal operations:** Author `docs/how-to/live-portal-queries.md` to cover `aeat app live` commands.
5. **Update `docs/index.md`:** Add cards or links to censo updates, manual calculation inputs, and authentication to resolve the landing page gaps.

## Codification candidates

State: None. No findings meet the three durability criteria for new project rules. The gaps identified are documentation coverage and transition clarity, which are resolved by drafting the recommended pages rather than enforcing new codebase constraints.

## Campaign Close Honesty Review

Reviewing the campaign as a new developer inheriting the codebase:

### 1. Assessment of Completed Work
- **Overview data pipeline and ledger-to-calculation logic**: Fully detailed in `docs/explanation/ledger-to-calculation.md` and `docs/explanation/index.md`. The explanation uses simple, non-demanding, non-technical language as required by the taxpayer-centric guidelines.
- **Cross-referencing**: Structured links have been added across the main index, quickstart, and core how-to guides.
- **CLI conformance**: Automated verification via `test_documented_command_conformance.py` is fully clean.

### 2. Missing, Vague, or Assumed-but-Unverified Items
- **F01 (Missing Modelo 130 How-to Guide)**: Although the quickstart and registry bindings cover the underlying mechanics, a dedicated how-to guide for Modelo 130 is missing.
- **F02 (Absence of live-read Command Documentation)**: Commands under `aeat app live` (expedientes, borrador, verify, portals, notifications) remain completely undocumented.
- **F03 (IVA Wallet and Compare Verbs)**: The compensation wallet and draft comparison utilities are undocumented.

### 3. Resolution and Deferrals
To declare the `filing-architecture-docs` campaign structurally complete, these outstanding findings are formally deferred to follow-up campaigns:
- **Deferred to `#aeat-cli-userdocs-hardening`**: 
  - **F01 (Modelo 130 How-to Guide)**: To be authored under the user docs hardening campaign.
  - **F03 (IVA Wallet and Compare Verbs)**: Dedicated documentation to be added.
- **Deferred to `#live-censo-calendar-reconciliation`**:
  - **F02 (live-read Command Documentation)**: Since the censo/calendar reconciliation campaign directly integrates live AEAT portal data, the live-read command family guides belong to its scope.

