---
tags:
  - '#research'
  - '#adr-amendment-implementing-rows'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:33a1f7c4f55e69a1a60a3fb7e9273d7082e45fe2ec153e0abb27d5cdef51e7c8'
related:
  - "[[2026-08-07-adr-amendment-implementing-rows-plan]]"
  - "[[2026-06-09-modelo-iva-routing-carry-adr]]"
  - "[[2026-08-07-rate-box-evidence-assertion-adr]]"
  - "[[2026-08-07-recargo-equivalencia-source-of-truth-adr]]"
---

# `adr-amendment-implementing-rows` research: `roll-up authorization for one cross-domain plan`

The existing cross-domain plan needs a same-feature authorization before VaultSpec Core can scaffold its execution records. The evidence favors a coordination-only roll-up ADR: the plan already bundles distinct implementing rows under one dependency-aware schedule, while VaultSpec Core 0.1.56 requires the execution feature itself to own both a plan and an ADR. Splitting the plan adds no implementation boundary, and cross-feature execution tagging misstates ownership.

## Findings

### VaultSpec Core validates the execution feature before resolving `--related`

In `vaultspec-core@0.1.56`, execution creation resolves the related records, runs feature-lifecycle validation, and only then uses the related plan as the parent. The lifecycle check hard-fails when the requested feature lacks either a plan or an ADR. Explicit parent selection and feature authorization are therefore separate checks; `--related` cannot authorize a feature whose own tag lacks an ADR. `.venv/Lib/site-packages/vaultspec_core/cli/vault_cmd.py:228`, `.venv/Lib/site-packages/vaultspec_core/cli/_add_ops.py:234`, `.venv/Lib/site-packages/vaultspec_core/vaultcore/resolve.py:221`.

### The existing plan is the coordination boundary

The plan carries the three governing ADRs once and assigns each ruling its own Step, scope, dependencies, and verification. S02 and S03 may run in parallel; S04 follows S05. The repository contract permits one plan to execute a cluster of ADRs and requires each governing ADR in `related:`. `.vault/plan/2026-08-07-adr-amendment-implementing-rows-plan.md:9`, `.vault/plan/2026-08-07-adr-amendment-implementing-rows-plan.md:36`, `.vault/plan/2026-08-07-adr-amendment-implementing-rows-plan.md:43`, `.codex/rules/vaultspec.builtin.md:81`.

### A roll-up ADR need not become a fourth domain contract

The source ADRs already own the AIC-routing, rate-box, and recargo decisions. A same-feature ADR can authorize only their coordination through the existing plan and feature tag without repeating legal, calculation, selector, or advisory facts. `.vault/adr/2026-06-09-modelo-iva-routing-carry-adr.md:207`, `.vault/adr/2026-08-07-rate-box-evidence-assertion-adr.md:232`, `.vault/adr/2026-08-07-recargo-equivalencia-source-of-truth-adr.md:93`.

### Splitting or mis-tagging adds damage without a delivery boundary

Separate plans would duplicate dependency and completion bookkeeping solely to satisfy scaffolding. Cross-feature execution records would instead separate the record's feature identity from its parent plan and Step. Neither option supplies a new implementation or release boundary; the ADR must settle whether the existing plan remains the execution boundary and receives same-feature authorization.

## Sources

- `vaultspec-core@0.1.56`
- `.venv/Lib/site-packages/vaultspec_core/cli/vault_cmd.py:228`
- `.venv/Lib/site-packages/vaultspec_core/cli/_add_ops.py:234`
- `.venv/Lib/site-packages/vaultspec_core/vaultcore/resolve.py:221`
- `.codex/rules/vaultspec.builtin.md:81`
- `.vault/plan/2026-08-07-adr-amendment-implementing-rows-plan.md:9`
- `.vault/plan/2026-08-07-adr-amendment-implementing-rows-plan.md:36`
- `.vault/plan/2026-08-07-adr-amendment-implementing-rows-plan.md:43`
- `.vault/adr/2026-06-09-modelo-iva-routing-carry-adr.md:207`
- `.vault/adr/2026-08-07-rate-box-evidence-assertion-adr.md:232`
- `.vault/adr/2026-08-07-recargo-equivalencia-source-of-truth-adr.md:93`
