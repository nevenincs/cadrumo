---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:1e3e4d6bce603c561b0cc62f2e689e986fc3ec97e00cc446662917d23ebce7ec'
step_id: 'S55'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# W04.P07.S55 DP30301 scalar authority closure

## Scope

- `src/cadrumo/core/`, `src/cadrumo/domain/deadlines/`, and `src/cadrumo/domain/prorrata_register/` define the typed profile, tax-territory, observation-role, and durable prorrata-transition authorities.
- `src/cadrumo/application/filing/`, `src/cadrumo/application/modelo/`, `src/cadrumo/application/aggregation/`, and `src/cadrumo/application/calculations/` consume those authorities through immutable producer snapshots and explicit work-unit-bound repositories.
- CLI, persistence, registry selectors, locales, and direct production-behavior tests carry the same hard-cutover contract without compatibility defaults or aliases.

## Description

- Close DP30301 A16-A30 with typed profile, filing-evidence, observation, prorrata, insolvency, applicability, and derived-volume owners.
- Require secure version-2 prorrata documents, explicit repository injection, bucket identity, complete sector and activity coverage, and canonical M303 profile scope before calculation persistence.
- Preserve supplier-regime affiliation across Q1 informational and Q2 settlement observations while keeping deduction and 74/75 routing separated by the explicit observation role.
- Require full canonical Bienes regularisation equality and withhold received-invoice IVA projection until the classified ledger supplies exact deduction authority and provenance.
- Delete implicit repositories, raw-key/default/fallback authorities, retired revision tokens, duplicate profile owners, and contradictory legacy gates.

## Outcome

- Final immutable implementation candidate: `e7cb1c55c6739d4a21e0dffe670f5fe7d750e8ab`, parent `7e8f59f032a91f91fb069c0a451a5775f9f80c93`, tree `285226e9e27d38c3f9ecd344520e7fdf3b0d233a`; exactly one commit and 304 scoped paths.
- Formal Luna review: `APPROVE`; unresolved critical `0`, high `0`, medium `0`.
- Immutable test evidence: 126 scalar/authority tests, 150 secure/prorrata/Renta tests, 159 profile/readiness tests, plus targeted A21, settlement, BIR, A18, reverse-charge, static-role, and refusal gates.
- Changed Python Ruff, formatter, and compile checks pass. `git diff --check`, path scope, default/alias, duplicate-authority, and legacy-surface censuses pass.
- Exact `aeat` CLI help surfaces and registry verification pass; the registry reports 73 modelos and 94 revisions.

## Notes

- The initial candidate was blocked by received-invoice deduction-authority construction, profile-to-evidence scope bypass, underdeclared Bienes result identity, and stale strict-cutover tests. All were corrected and independently re-reviewed before closure.
- Broad timed-out runs remain unclaimed. Only completed commands listed above constitute acceptance evidence.
- Lifecycle closure is limited to this audit, this Step Record attestation, and the CLI-owned S55 checkbox. It does not alter production code, tests, or registry semantics after formal approval.
