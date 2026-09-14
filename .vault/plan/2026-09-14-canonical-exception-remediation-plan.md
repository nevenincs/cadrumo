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
body_hash: 'sha256:fdf871f478a146232c9f30ec27fe0ca5ca17ea91b7b180998398b623b577f3a7'
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

- [ ] `W01.P01.S01` - Reconcile direct roots and descendant closure; `src/cadrumo`.
- [ ] `W01.P01.S02` - Record canonical bases categories and retryability; `.vault/reference/2026-09-14-canonical-exception-remediation-production-inventory-reference.md`.

## Wave `W02` - Parallel bounded migrations

Migrate non-overlapping package families while one writer enrolls the shared registry and localization contract.

### Phase `W02.P02` - Migrate package-owned exception families

Replace bare ancestry and broad internal catches without moving defining modules.

- [ ] `W02.P02.S03` - Migrate application exception families; `src/cadrumo/application`.
- [ ] `W02.P02.S04` - Migrate core domain adapter and entrypoint families; `src/cadrumo`.

### Phase `W02.P04` - Enroll error contracts

Bind each migrated identity once and supply localized envelope messages.

- [ ] `W02.P04.S10` - Enroll unique layer registry codes; `src/cadrumo/core/errors/registry`.
