---
tags:
  - "#plan"
  - "#inventory-management"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-29-inventory-management-research]]"
  - "[[2026-04-29-inventory-management-adr]]"
---

# Inventory Management Hardening Plan

Topic: Kent-facing CLI inventory/amortization UX and compliance hardening after WIP #216 was merged.

Audit surface: current `aeat profile assets`, `aeat profile inventory`, Anexo D ledger overlay, Path A JSON persistence, #216 governed persistence substrate, and legal calculation behavior for technical kit purchases spanning years and VAT rates.

Rewrite scope: hardening plan artifact only; no runtime code changes.

## Objective

Bring the inventory and amortization feature to a Kent-ready baseline after WIP #216 by replacing unsafe persistence shortcuts, tightening legal calculation behavior, implementing real valuation semantics, and improving the CLI UX around technical kit inventory.

Current decision gate: the existing v1 is not production-ready for Kent's real technical kit inventory.

Legal source anchors: LIS BOE-A-2014-12328, LIRPF BOE-A-2006-20764, RIRPF BOE-A-2007-6820.

## Governed #216 Persistence And Security Opt-In

Actions:

- Move asset and inventory ledgers off plaintext Path A JSON under `~/.config/aeat`.
- Route stores through the governed Settings/root persistence model.
- Store financial ledgers using #216 `SensitivityClass.FINANCIAL`.
- Persist through Envelope-backed AES-GCM encrypted envelopes.
- Bind encryption to HKDF context and classification-bound AAD.
- Add lock-aware writes for ledger mutation.
- Define rotation behavior for existing local stores.
- Provide explicit migration handling for existing plaintext Path A files.
- Prevent silent duplicate replacement during migration and normal writes.

Acceptance gates:

- Asset and inventory records are not readable as plaintext at rest.
- Persistence paths are governed by the configured root/settings model.
- Duplicate asset or ledger IDs cannot silently overwrite existing records.
- Concurrent writes are lock protected.
- Migration has an auditable before/after result and a rollback-safe failure mode.

## VAT And Base Decomposition

Actions:

- Model purchase gross amount, VAT rate, VAT amount, deductible/non-deductible VAT treatment, and amortizable base separately.
- Support technical kit purchases spanning different years and VAT rates.
- Make CLI input explicit enough that Kent can see whether values are gross, net, VAT, or amortizable base.
- Carry decomposed values into asset records and downstream Anexo D overlay calculations.
- Emit validation errors for inconsistent gross/net/VAT combinations.

Acceptance gates:

- A laptop or NAS purchase can be entered with year-specific VAT details.
- Amortization uses the correct amortizable base rather than an ambiguous purchase amount.
- The CLI displays stored monetary components clearly.
- Invalid decomposition is rejected with actionable errors.

## Legal Amortization Engine Hardening

Actions:

- Replace raw `useful_life_years` trust with validated legal constraints.
- Enforce LIS table-compatible caps for supported asset classes.
- Replace raw `libertad` boolean behavior with an explicit governed rule path.
- Exclude future amortization entries from current cumulative amortization.
- Make repeated amortization recording idempotent with truthful CLI output.
- Record calculation trace data sufficient for audit and debugging.
- Keep BOE anchors concise and stable: LIS BOE-A-2014-12328, LIRPF BOE-A-2006-20764, RIRPF BOE-A-2007-6820.

Acceptance gates:

- Future amortization entries do not affect current-year cumulative totals.
- Re-recording an existing amortization entry reports unchanged or already recorded, not newly recorded.
- Unsupported useful-life values are rejected or require an explicit governed exception.
- Calculation output includes enough trace data to explain base, rate, period, cumulative amount, and remaining value.

## Real Inventory Valuation Layers

Actions:

- Replace signed movement arithmetic with real valuation layer logic.
- Implement FIFO layers for stock inflow/outflow.
- Implement PMP/coste medio behavior where supported.
- Keep LIFO refused and correct any citation drift.
- Track quantity, unit cost, remaining layer quantity, movement date, and valuation method.
- Reject inventory movements that would create unsupported negative stock unless an explicit governed policy allows it.
- Ensure Anexo D overlay receives values derived from actual valuation logic.

Acceptance gates:

- FIFO retail inventory depletion consumes the oldest available layers.
- PMP/coste medio recalculates weighted average cost after purchases.
- Method labels correspond to actual computation behavior.
- LIFO remains unavailable with a clear and legally anchored message.
- Ledger summaries reconcile quantities and valuation totals from movement layers.

## Kent CLI UX Improvements

Actions:

- Add shorter aliases or guided selectors for asset classes while preserving canonical stored values.
- Improve validation messages for bad date, bad asset class, bad decimal, missing ledger, and missing asset.
- Make duplicate asset/ledger creation require explicit replacement intent.
- Make command success output distinguish created, updated, unchanged, migrated, and refused outcomes.
- Improve trilingual coverage for commands Kent sees during setup, entry, validation, and summaries.
- Add summary views for technical kit assets showing purchase date, VAT/base decomposition, amortization status, and remaining value.

Acceptance gates:

- Kent can add `laptop-2024` and `nas-2025`-style assets without memorizing long enum strings.
- The CLI never reports `recorded` for a no-op amortization write.
- Duplicate IDs produce a protective prompt or explicit refusal unless replacement is intentional.
- Error messages give the invalid value, the expected shape, and the next corrective action.

## M100 Compatibility

Actions:

- Verify that inventory/amortization outputs preserve M100 expectations.
- Ensure Anexo D overlay writes `0155` and `0173` only from validated asset/ledger inputs.
- Preserve fallback caller values only when no governed overlay data is available and make that behavior explicit.
- Add compatibility checks for mixed manual caller values and generated overlay values.
- Document which values are source-of-truth when ledgers/assets are supplied.

Acceptance gates:

- Supplying validated ledgers/assets produces deterministic `0155` and `0173` overlay values.
- Missing ledgers/assets do not silently imply validated zeroes.
- Fallback caller values remain distinguishable from generated ledger-derived values.
- M100 output remains backward-compatible for callers that do not opt into the new ledgers.

## Tests And Audits

Actions:

- Add real-behavior CLI tests for asset creation, inventory ledger creation, amortization recording, duplicate handling, and validation failures.
- Avoid tautological tests and shortcut fakes.
- Cover bad date, bad asset class, bad decimal, LIFO refusal, missing ledger, and missing asset.
- Cover repeated amortization recording and require truthful output.
- Cover encrypted persistence behavior without asserting implementation trivia.
- Cover FIFO and PMP/coste medio calculations using multi-layer inventory examples.
- Cover VAT/base decomposition across different purchase years and VAT rates.
- Add audit fixtures for `laptop-2024`, `nas-2025`, FIFO retail inventory, and 2025 amortization values `450.00` and `151.23`.

Acceptance gates:

- Tests fail against the current unsafe/plaintext and arithmetic-only behavior.
- Tests pass only when persistence, valuation, amortization, and CLI messaging match the hardened requirements.
- Audit output can reproduce the manual roleplay outcomes at summary level.
- No tests rely on mocks, stubs, monkeypatch shortcuts, `skip`, or `xfail` to pass.

## Non-Goals

- Do not build a general accounting system.
- Do not support LIFO valuation.
- Do not quote BOE legal text at length in CLI output or vault artifacts.
- Do not rework unrelated M100 filing behavior outside the inventory/amortization overlay.
- Do not add unsupported asset classes only to make examples pass.
- Do not preserve plaintext Path A JSON as an acceptable production store for financial ledgers.
- Do not treat shallow trilingual strings as complete localization.

## Completion Gate

The feature can move toward completion only when all of the following are true:

- Financial asset and inventory ledgers use the #216 governed persistence/security substrate.
- VAT/base decomposition is explicit and audited.
- Amortization calculations are legally constrained and traceable.
- FIFO and PMP/coste medio labels map to real valuation logic.
- Kent-facing CLI flows prevent silent overwrite and misleading success output.
- M100 overlay behavior is deterministic and source-aware.
- Real-behavior tests cover the manual roleplay evidence and the identified failure cases.
