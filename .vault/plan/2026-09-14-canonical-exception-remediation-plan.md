---
tags:
  - '#plan'
  - '#canonical-exception-remediation'
date: '2026-09-14'
tier: L3
related:
  - '[[2026-09-14-canonical-exception-remediation-adr]]'
modified: '2026-09-14'
body_schema: body-v2
body_hash: 'sha256:21db06fe4b6054df7d59303453e8ecd359255401bff3a37db21d605f27229ca2'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- RETIRED: P03, P05, S05, S06, S07, S08, S09 -->

# `canonical-exception-remediation` plan

## Steps

## Wave `W01` - Inventory and taxonomy

Establish the complete direct-root and descendant closure and lock canonical categories before mutation.

### Phase `W01.P01` - Reconcile live exception ownership

Cross-check source definitions, catches, registry identities, and protocol boundaries.

- [x] `W01.P01.S01` - Reconcile direct roots and descendant closure; `src/cadrumo`.
- [x] `W01.P01.S02` - Record canonical bases categories and retryability; `.vault/reference/2026-09-14-canonical-exception-remediation-production-inventory-reference.md`.

## Wave `W02` - Parallel bounded migrations

Migrate non-overlapping package families while one writer enrolls the shared registry and localization contract.

### Phase `W02.P02` - Migrate package-owned exception families

Replace bare ancestry and broad internal catches without moving defining modules.

- [x] `W02.P02.S03` - Migrate application exception families; `src/cadrumo/application`.
- [x] `W02.P02.S04` - Migrate core domain adapter and entrypoint families; `src/cadrumo`.

### Phase `W02.P04` - Enroll error contracts

Bind each migrated identity once and supply localized envelope messages.

- [x] `W02.P04.S10` - Enroll unique layer registry codes; `src/cadrumo/core/errors/registry`.
- [x] `W02.P04.S11` - Add localized envelope messages; `src/cadrumo/locales`.

## Wave `W03` - Cross-cutting reconciliation

Re-run global inventories and reconcile catches imports envelopes and residual interoperability evidence.

### Phase `W03.P06` - Reconcile exception contracts

Prove the residual source population and downstream machine contract.

- [x] `W03.P06.S12` - Reconcile bare roots catches and canonical imports; `src/cadrumo`.
- [x] `W03.P06.S13` - Verify unique codes and localized envelopes; `src/cadrumo/core/errors`.

## Wave `W04` - Acceptance

Run the focused exception gates hierarchy and envelope checks final core collection and formal review.

### Phase `W04.P07` - Prove campaign acceptance

Collect and execute only the authorized exception-related validation surfaces.

- [x] `W04.P07.S14` - Run focused exception gates and envelope tests; `src/cadrumo/core/errors/tests`.
- [x] `W04.P07.S15` - Collect the complete core test surface; `src/cadrumo/core`.
- [ ] `W04.P07.S16` - Complete formal remediation review; `.vault/audit/2026-09-14-canonical-exception-remediation-final-review-audit.md`.
