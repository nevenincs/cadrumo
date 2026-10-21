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
modified: '2026-10-21'
body_schema: body-v2
body_hash: 'sha256:831fc362d026efba2a9af9289f4f11a1b05c56142258356886cc89e175b0f264'
---

# `agent-service-boundary` plan

## Description

Approved 2026-10-14

User explicitly authorized the agent boundary deletion/migration, after Luna audits and Sol digests, medium-reasoning delegation, existing ADR amendments and no tests. No new ADR is authorized. Existing accepted records are amended to govern this refinement; history and proposed statuses remain intact.

S01 reconciles the finite decision set in `.tmp/agent-boundary-audit/adr-digest.md`. Provider-settings and attachments govern S02-S03; canonical environment governs S03-S05; application sign-in and MCP authentication govern generic runtime admission in S02 and desktop attendance in S04; harness refoundation governs separate MCP ownership in S03. Code evidence is `.tmp/agent-boundary-audit/code-digest.md`, `python.md` and `native.md`.

The tax root `src/cadrumo` has zero LLM-agent or harness awareness. The sibling service `src/cadrumo_agent_service` hosts the bundled cadrumo-agent and manages agent processes, stores and conversations; `src/cadrumo_mcp` owns the deterministic MCP service and serves no skill, rule or persona content; cadrumo-agent owns all authored personas, rules, skills and provisioning. (Revised 2026-10-21, drift repair toward cadrumo-agent `2026-10-15-agent-harness-adr`, authorized by the user in session TUI-REFACTOR; before that `src/cadrumo_harness` owned MCP and the authored harness content. Provider policy ownership is open item 1 of the harness boundary amendment of `2026-07-02-agent-harness-refoundation-adr` and is not settled by this plan.) Runtime retains generic login, encrypted custody and authorization. Preserve existing ciphertext through descriptor-allowlisted opaque custody, no DEK export, exact verified native service/session/tree proofs. Tax-domain model extraction remains.

## Steps

- [ ] `S01` - Reconcile existing ADRs and canonical ownership guidance; `.vault/adr, .vaultspec/rules, .vaultspec/skills/cadrumo-start`.
- [ ] `S02` - Introduce generic runtime custody, session and peer contracts and remove agent-specific runtime behavior; `src/cadrumo, src/cadrumo_mcp/runtime_client`.
- [ ] `S03` - Migrate agent orchestration, credentials, stores and conversation policy to a separate service, rename src/cadrumo_harness to src/cadrumo_mcp, and delete the authored agent content and its serving surface with no compatibility facade: _data/agent, _resources, resources, _skill_metadata, workspace, mcp/operating_layer, the harness_load tool, the cadrumo://skill and cadrumo://rule resources, the materialisation flag, dev/packaging/claude_plugin.py and the build-claude-plugin recipe; `src/cadrumo_agent_service (new), src/cadrumo_mcp, dev/packaging, justfile, transferred tests and locales`.
- [ ] `S04` - Adapt native desktop and deterministic development consumers to the verified service and person channel; `native, dev/runtime_lifecycle, dev/packaging/native`.
- [ ] `S05` - Reconcile package manifests, dependency boundaries, shared inventories and locale loading; `pyproject.toml, native package contracts, dev/quality, shared resources`.
- [ ] `S06` - Review and verify the integrated boundary, reconcile final governance source links, and confirm the former harness_load consumers are resolved: the advertised orientation core of 2026-07-08-mcp-progressive-discovery-adr P1 and the identity-read set of 2026-07-08-mcp-identity-linked-operation-adr I1 and I2; `.tmp/agent-boundary-audit, .vaultspec, affected production surface`.

## Parallelization

S01 prepares governance. Runtime worker owns S02 (`src/cadrumo` and neutral runtime/client contracts). Service worker owns S03 (sibling service, transferred agent files, harness protocol, agent locales/tests). Their files are disjoint by explicit transfer coordination; S02 freezes generic APIs before dependent S03 implementation, while preparations proceed concurrently. S04 follows published service interfaces; S05 follows file moves. Governance owns `.vault` and `.vaultspec`; root owns shared verification, ledgers, Step closure and commits. Final source locators are reconciled after actual migrations. Workers preserve all concurrent edits.

## Verification

User override: no tests. Verify static syntax/imports/boundaries, exact native verified peer/session/tree proofs, allowlisted opaque custody and preserved ciphertext, service/agent hosting frames, separate MCP ownership and actual package inclusion. Run configured non-test lint/format/type/import checks and necessary builds where applicable. Report failures/unavailable checks without claiming passes. Root performs integrated final review and owns all Step ledgers and closures; no Step closes before actual verification.
