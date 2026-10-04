---
tags:
  - '#plan'
  - '#live-reconciliation-repair'
date: '2026-10-04'
tier: L1
related:
  - '[[2026-06-10-live-justificante-reconcile-adr]]'
  - '[[2026-07-01-reconcile-value-comparison-adr]]'
  - '[[2026-07-25-reconcile-evidence-relocation-adr]]'
  - '[[2026-09-07-tuimodelo-reconcile-verify-adr]]'
  - '[[2026-09-17-filing-chain-reconciliation-adr]]'
modified: '2026-10-04'
body_schema: body-v2
body_hash: 'sha256:6474313d54d006f07a6f16534bd12ccd5e0c61d9787b64ac4a7914fb3f971282'
---

# Live reconciliation repair

## Description

Approved 2026-10-04

The user explicitly authorized fixing all failures observed during authenticated 2024 Q1 Modelo 303 reconciliation and verifying CLI and TUI counterpart and drift visibility. Restore existing accepted contracts: exact-period evidence capture, persist-before-reconcile, grounded comparisons, encrypted history, and shared frontend projections. No new ledger or financial adjustment authority. The live-justificante decision governs capture; value-comparison and evidence-relocation govern comparison and storage; tuimodelo governs presentation; filing-chain reconciliation governs confirmation. Preserve unrelated export and registry edits.

## Steps

- [x] `S01` - Preserve nullable scalar values through populated workbench transport; `src/cadrumo/application/operations/_public_mirror_projection.py and generation tests`.
- [x] `S02` - Retrieve exact-period justificantes from authoritative declaration register controls; `src/cadrumo/application/live/justificante.py and receipt ports adapters tests`.
- [x] `S03` - Restore captured submitted-file parsing against source-grounded framing; `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py and framing owner tests`.
- [x] `S06` - Expose explicit pulled declaration reconciliation against saved local calculation using persisted official casillas and existing comparison records; `src/cadrumo/application/modelo reconciliation operation and src/cadrumo/entrypoints/cli reconciliation pull source selection plus tests`.
- [x] `S04` - Show persisted counterpart comparisons and grounded drift in shared CLI TUI projections; `src/cadrumo/application/aeat_sync and workbench composition tests`.
- [ ] `S07` - Align official IVA result-disposition enrollment with canonical export headers while preserving declared legacy observations; `src/cadrumo/_data/registry/aeat/facts/2025/mapping carry disposition fact and calculation observation ingress tests`.
- [ ] `S05` - Verify real runtime CLI pull and populated TUI comparison and review integrated repairs; `var/reconciliation-check-20261004 redacted evidence and regression checks`.

## Parallelization

Delegate S01 public mirror projection and tests to mirror_fix. Delegate S02 justificante selection and adapters/tests to receipt_fix. After S01, mirror_fix owns S03 inbound submitted-file parsing and tests, preserving prior parser edits. Delegate independent S04 AEAT Sync reconciliation reader/projection/tests to drift_surface; final integration follows S01-S03. Lead owns S05 actual runtime acceptance and integrated review. All workers preserve others edits; lead serializes vault metadata and commits.

After S02, receipt_fix owns S06 explicit declaration-source pull and local comparison operation. It may implement independently of S04, which consumes the existing persisted record format. S05 verifies both source paths after integration.

Lead reassigns S04 review corrections to mirror_fix, including public transport schema parity; lead owns the AEAT Sync overview navigation repair. After S06, receipt_fix owns S07 governed disposition-header enrollment repair and compatibility tests. Lead publishes an isolated authority artifact and performs live acceptance.

## Verification

Reproduce null casilla serialization, exact-period receipt selection when procedure-tree entries are missing, and actual captured submitted-file framing. Run focused tests, style, format, types and import boundaries. Verify actual CLI reconciliation pull and populated-profile Textual pilot against the retained isolated profile and saved synthetic calculation, with explicit counterpart identity, drift values and unavailable-versus-match distinction. Repeated pulls must retain stable evidence. Private evidence stays encrypted; reports are redacted. No AEAT submission. Complete integrated review before reporting success.
