---
tags:
  - '#plan'
  - '#agent-service-boundary'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-10-13-agent-attachments-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:7836cd5d105ff1378b0cfee3c900eee5cbbe6cda8277f492edd6334f5df123cd'
---

# `agent-service-boundary` plan

## Description

Approved 2026-10-14

User explicitly authorized the agent boundary deletion/migration, after Luna audits and Sol digests, medium-reasoning delegation, existing ADR amendments and no tests. No new ADR is authorized. Existing accepted records are amended to govern this refinement; history and proposed statuses remain intact.

S01 reconciles the finite decision set in `.tmp/agent-boundary-audit/adr-digest.md`. Provider-settings and attachments govern S02-S03; canonical environment governs S03-S05; application sign-in and MCP authentication govern generic runtime admission in S02 and desktop attendance in S04; harness refoundation governs separate MCP ownership in S03. Code evidence is `.tmp/agent-boundary-audit/code-digest.md`, `python.md` and `native.md`.

The tax root `src/cadrumo` has zero LLM-agent or harness awareness. The sibling service `src/cadrumo_agent_service` manages agents/providers/stores; `src/cadrumo_harness` owns MCP. Runtime retains generic login, encrypted custody and authorization. Preserve existing ciphertext through descriptor-allowlisted opaque custody, no DEK export, exact verified native service/session/tree proofs. Tax-domain model extraction remains.

## Steps

- [ ] `S01` - Reconcile existing ADRs and canonical ownership guidance; `.vault/adr, .vaultspec/rules, .vaultspec/skills/cadrumo-start`.
- [ ] `S02` - Introduce generic runtime custody, session and peer contracts and remove agent-specific runtime behavior; `src/cadrumo, src/cadrumo_harness/runtime_client`.
- [ ] `S03` - Migrate agent orchestration, credentials, stores and conversation policy to a separate service and complete harness ownership; `src/cadrumo_agent_service (new), src/cadrumo_harness, transferred tests and locales`.
- [ ] `S04` - Adapt native desktop and deterministic development consumers to the verified service and person channel; `native, dev/runtime_lifecycle, dev/packaging/native`.
- [ ] `S05` - Reconcile package manifests, dependency boundaries, shared inventories and locale loading; `pyproject.toml, native package contracts, dev/quality, shared resources`.
- [ ] `S06` - Review and verify the integrated boundary and reconcile final governance source links; `.tmp/agent-boundary-audit, .vaultspec, affected production surface`.

## Parallelization

S01 prepares governance. Runtime worker owns S02 (`src/cadrumo` and neutral runtime/client contracts). Service worker owns S03 (sibling service, transferred agent files, harness protocol, agent locales/tests). Their files are disjoint by explicit transfer coordination; S02 freezes generic APIs before dependent S03 implementation, while preparations proceed concurrently. S04 follows published service interfaces; S05 follows file moves. Governance owns `.vault` and `.vaultspec`; root owns shared verification, ledgers, Step closure and commits. Final source locators are reconciled after actual migrations. Workers preserve all concurrent edits.

## Verification

User override: no tests. Verify static syntax/imports/boundaries, exact native verified peer/session/tree proofs, allowlisted opaque custody and preserved ciphertext, service/agent hosting frames, separate MCP ownership and actual package inclusion. Run configured non-test lint/format/type/import checks and necessary builds where applicable. Report failures/unavailable checks without claiming passes. Root performs integrated final review and owns all Step ledgers and closures; no Step closes before actual verification.
