---
tags:
  - '#adr'
  - '#duplication-remediation'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:09b7e7b0831466bad1524111c9882c00e22440d5398523350b884df6303f6054'
related:
  - "[[2026-10-02-duplication-remediation-reference]]"
  - "[[2026-10-02-duplication-remediation-audit]]"
  - "[[2026-07-01-import-centralization-adr]]"
  - "[[2026-06-28-product-packaging-adr]]"
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
  - "[[2026-06-01-calculation-test-oracle-discipline-adr]]"
---

# `duplication-remediation` adr: `Canonical tooling hashes and independent installed proof` | (**status:** `accepted`)

## Problem Statement

Removing `dev/packaging/hashing.py` needs a defined ownership boundary between ordinary development hashing and independent verification of installed artifact bytes. The installed-tax oracle claims stdlib-only operation while importing product support transitively; its current installed-interpreter launch can also bind support from the artifact being checked. The source trace is an import-origin risk, not an executed failure. Evidence is retained in `2026-10-02-duplication-remediation-reference` and the P08/S23 decision packet.

## Considerations

`2026-07-01-import-centralization-adr` requires one defining public owner, direct imports and atomic removal. `2026-06-28-product-packaging-adr` and `2026-07-15-distribution-installation-readiness-adr` require clean, cohort-bound installed proof. `2026-06-01-calculation-test-oracle-discipline-adr` preserves independently grounded expected numeric outcomes. These commitments do not require every controller process to be stdlib-only; they require explicit provenance and independence for the actual proof.

The reviewed P08 packet is `C:/Users/hello/AppData/Local/Temp/cadrumo-p08-canonical-hashing-decision-20261003T1605Z-4fd8c1a7.md` (raw SHA256 `0F135B677F41B459DB82AEE0F43830F08E9150D0E9D841DC135EAB01FA40E5DE`); its boundary addendum is `C:/Users/hello/AppData/Local/Temp/cadrumo-p08-current-boundary-addendum-20261003T1614Z-862bc74e.md` (raw SHA256 `AB56E442A68E2B364529E21B7461483D4AD1DE1DC289FF10097A3B7528711ED6`). Their original consumer pins are not a current source-write grant.

## Considered options

- Product hashing everywhere: rejected for independent installed-byte expectations, because the artifact under verification must not supply its own expected implementation.
- A separate public development hashing owner: rejected as duplicate authority; bootstrap needs do not justify a forwarding path.
- A wholly stdlib-only controller: rejected as a blanket requirement. It would require unrelated support rewrites while leaving the actual target and measurement boundaries unspecified.
- Canonical controller mechanics plus private independent verification: selected, with explicit controller source provenance and isolated installed-product execution.

## Constraints

Ordinary tooling and fixture construction use the existing defining owner `src/cadrumo/core/hashing.py`: `sha256_file(Path)` for raw file bytes and `sha256_hex(bytes)` for exact caller-owned byte representations. Text callers retain their existing strict UTF-8 encoding. No public development SHA service, forwarding alias, facade, new text codec or product-to-development dependency is permitted.

The controller/verifier host may use explicitly selected, pinned checkout support, including canonical inward core modules for identity, environment handling and bookkeeping. Its interpreter and imported first-party origins must be attributable to that selected support source. It must not silently bind controller support from the installed artifact under verification or a different live checkout. Do not use the target installation as an ambient source for controller imports. The host is not claimed to be stdlib-only merely because its measurement algorithm uses stdlib.

Actual independent expected calculations remain private and stdlib-based: wheel-member/payload hashes and the installed-tax oracle's executable-byte measurement may not call product hashing, target-installed implementations or a reusable competing development helper. External expected tax outcomes may not be derived from the product formula under test. Existing isolated `-I` stdlib payload measurement remains independent; the separate entrypoint-origin probe may deliberately import the installed entrypoint to identify it, but supplies no expected hashing implementation. A separate measurement subprocess is an implementation option if needed to prove these boundaries, not a universal new platform.

Installed-product commands and probes run in separate clean target processes against the pinned installed cohort, with checkout product paths and unrelated executable sources excluded. Resolve absolute interpreter/executable identities; preserve scrubbed environment and independent working/storage roots. Record actual interpreter, executable, module origins, version and cohort digests for each role. A controller's explicit checkout support is not evidence that the installed target works and must never enter the target's product import path.

These process roles refine the clean-install wording in the product-packaging and distribution-installation-readiness ADRs: their prohibition on checkout imports remains absolute for the installed product/probe whose behavior is being proved. The controller is a separately identified tool with pinned source support; its private expected integrity calculation remains independent of the product implementation. Publication authority, immutable cohort, public interfaces, required behavior, platform/client coverage and external expected tax result are unchanged. The import-centralization and calculation-oracle decisions are reused unchanged.

Preserve exact existing serialization, Unicode/newline treatment, prefixed versus raw and domain-separated identities, ordering, error behavior, hash-as-you-write effects and byte counts. Do not substitute canonical JSON hashing for a caller's different serialization recipe. No persisted fingerprint, receipt schema or evidence format migration is authorized.

## Implementation

Use canonical core hashing for the packet's 20 ordinary non-test consumers and ordinary fixture setup in its eight test consumers. Keep only the installed-tax executable measurement and existing installed payload calculations as narrow private independent verifier logic. Correct the host's bootstrap/launch provenance and its inaccurate stdlib-only claim. Update every static/dynamic consumer and receipt/manifest reference before atomically deleting `dev/packaging/hashing.py`; no transitional alias is allowed.

The packet's minimal 30-path migration is a prospective slice, not a granted reservation. Any additionally required host/launch/support path must be individually owned before implementation. Source-current receipts and exact disjoint writer handoffs are required because other S23 writers changed some consumers during investigation. Sol 6.1 medium/high owns coding; Luna Max remains read-only investigation. Root owns decision and review.

Acceptance must preserve independent byte/serialization vectors, supported bootstrap entrypoints and exact snapshot source selection. Verify real role-specific origins and refusal for deliberately altered artifact bytes or wrong-origin imports. Retain independent payload binding and the grounded installed public tax-work oracle; help/import success cannot replace behavior proof. Existing foreign writer reservations and publication gates remain in force.

## Rationale

The functional split removes the duplicate public owner while keeping the algorithm that checks installed integrity independent of the artifact it checks. Explicit host and target provenance resolves the current bootstrap ambiguity without inventing a second helper service or claiming that a dependency-rich controller is stdlib-only. Preserving distinct serializers and independent expected outcomes protects intentional differences.

## Consequences

The private verifier calculation is a role-bound exception to mechanical clone removal, not a general second hashing authority. Host bootstrap and launch provenance need coordinated implementation and real execution evidence. This ruling does not claim present startup failure, source adoption, installed correctness or completed S23 closure. Reconsider if supported launch environments cannot establish the declared host/target provenance; revise that boundary explicitly rather than restoring a compatibility hash helper.

## Authorization

The user delegated the architect's decision with "make the decisision" after the P08 ambiguity was reported. This authorization covers the recorded functional boundary and the corresponding scoped wording clarifications to the two installed-proof ADRs. It does not release a foreign writer reservation or grant external publication.

## Decision placement and acceptance (2026-10-03)

Accepted under the delegated architect authority recorded above. The new commitment is the explicit host/target provenance boundary; ordinary canonical import ownership and independent numeric-oracle discipline are reused unchanged. The corresponding product-packaging and installation-readiness wording is refined together under the same authorization, without whole-ADR supersession.

One populated-draft Jev-assisted placement pass returned the import-centralization dependency and three declared supporting records. Its bounded coverage judged 33 of a 192-candidate pool in a 535-record corpus; source input and 21 candidate inputs were truncated. Root read the whole operative import, product-packaging, installation-readiness and calculation-oracle records and reviewed the complete new ruling locally. No result is treated as approval or a complete conflict audit; no automatic link writes were requested.
