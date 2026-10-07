---
tags:
  - '#plan'
  - '#blocking-code-quality-repair'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-08-24-quality-gate-zero-closure-adr]]'
  - '[[2026-09-08-quality-gate-zero-closure-product-boundary-adr]]'
  - '[[2026-10-05-google-outbound-review-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:f0604602228e99971a40fe9003f3030a5b30001381e02020468f78a8802e667e'
---

# `blocking-code-quality-repair` plan

## Description

Approved 2026-10-07

Authorization basis: the user requested all Justfile type and ratchet signals be run and all findings fixed, then clarified that the scope is the blocking code-quality gates. This plan authorizes routine repairs to the twelve gates in `dev/quality/suite.py`, proportionate behavior verification and in-scope corrections.

Accepted zero-closure and product-boundary decisions govern all Steps. Google outbound review governs S03 retirement of public pull, remote calculation and verify paths while preserving offline export and review publication. Runtime manager architecture governs S02 and S04 authentication boundaries. No new dependency, persistence schema, protocol or supported interface decision is proposed. Existing feature authority is preserved; current consumer evidence determines repairs, and unused declarations are not artificially wired to silence a gate.

The first `just check-code` observation failed seven gates: lint, format, types, imports, module reachability, symbol usage and export consumption. Source movement invalidated the import snapshot. Refresh diagnostics and reread shared files before edits; the inventory is not an exception baseline.

## Steps

- [ ] `S01` - Repair canonical tooling imports and typed developer fixtures; `dev/docs, dev/packaging, dev/registry excluding dev/quality/metadata`.
- [x] `S02` - Repair production and Windows fixture type contracts; `src/cadrumo/domain/calculations/registry, application/operations/terminated_owner.py, entrypoints/cli/config/tests and native desktop Python`.
- [ ] `S03` - Complete retirement of obsolete Google workbook paths and repair remaining typed renderers; `Google adapters, calc_sheets, modelo spreadsheet modules and dedicated review presentation modules`.
- [ ] `S04` - Reconcile authentication and storage symbols with their real production consumers; `profile authentication, secure custody and core storage_environment`.
- [ ] `S05` - Regenerate import enrollment and prove the integrated blocking gate result; `dev/quality/metadata and all modified source plus focused tests`.

## Parallelization

Use vaultspec-team to dispatch three workers concurrently for S01, S02 and S03 with disjoint source ownership. S01 owns developer tooling except generated import metadata. S02 owns the reported type files in domain, terminated_owner, CLI config live fixtures and native desktop Python. S03 owns Google adapters, application/export/managed_artifact_ports, calc_sheets, modelo spreadsheet modules, row-set assembly and dedicated CLI/TUI review presentation; it excludes S02 CLI config fixtures. The supervisor owns S04, generated import metadata, shared plan/ledger writes, commits and expensive full-tree checks. Workers report proposed edits outside ownership before writing. Preserve peer edits. Serialize overlapping tests and Git checkpoints. S05 follows completed source repairs.

After completing S02, its worker may implement the login-session retirement portion of S04: production login_session.py and affected test setup consumers/owning handover tests. The supervisor retains other S04 authentication declarations, storage conformance support and error catalogue. Coordinate test import-only overlaps with S03; preserve the peer-owned desktop runtime fixture. Source edits remain disjoint. The supervisor serializes S04 evidence and commit.

## Verification

Require zero findings from all twelve configured blocking code-quality gates, retaining every checker scope and refusal predicate. Use focused real-boundary tests for changed behavior, with lint, formatting and applicable type evidence before closing a Step. Preserve missing values and authority checks; no suppressions, baselines, test skips or fabricated consumers. Regenerate import load metadata through its owning generator after source retirement. Reuse unchanged gate evidence and run one final integrated `just check-code` on stable inputs. Record unavailable or moved-source evidence separately. Complete only after all Steps and integrated review pass; advisory audits, live OAuth, deployment and full product campaigns are outside this request.
