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
body_hash: 'sha256:eebfad2635450e80922edc5993126d48d4d54a8c381f034648b0cbe2b34c538e'
---

# `blocking-code-quality-repair` plan

## Description

Approved 2026-10-07

Authorization basis: the user requested all Justfile type and ratchet signals be run and all findings fixed, then clarified that the scope is the blocking code-quality gates. This plan authorizes routine repairs to the twelve gates in `dev/quality/suite.py`, proportionate behavior verification and in-scope corrections.

Accepted zero-closure and product-boundary decisions govern all Steps. Google outbound review governs S03 retirement of public pull, remote calculation and verify paths while preserving offline export and review publication. Runtime manager architecture governs S02 and S04 authentication boundaries. No new dependency, storage namespace, protocol or supported interface decision is proposed. S06 completes the lossless internal saved-rendering carrier by retaining its existing selected-view validation context. Existing feature authority is preserved; current consumer evidence determines repairs, and unused declarations are not artificially wired to silence a gate.

The first `just check-code` observation failed seven gates: lint, format, types, imports, module reachability, symbol usage and export consumption. Source movement invalidated the import snapshot. Refresh diagnostics and reread shared files before edits; the inventory is not an exception baseline.

Required S01 export-evidence verification exposed an existing canonical serialization defect: the complete rendering-snapshot encoder enumerated predecessor models as generic fields, although their declared serializers and validators require the compact authored representation. S06 repairs that lossless encode/readback contract within the existing immutable snapshot and Google review decisions. It does not add accepted authoring forms, alter authority content or relax persisted validators.

The first repair convergence run passed eight gates, including all configured platform type checks, but found two residual unconsumed observation prototypes and one associated orphan test. S07 retires those unenrolled value objects while preserving the existing provider selectors and actual typed filing-detail projection. S06 additionally retains the selected view's actual directory validation identities alongside its saved immutable geometry, with unchanged normal validation/digest behavior for valid existing captures that omit this supplemental context. This completes the existing self-contained snapshot commitment; directory evidence is never inferred from references or current authority.

## Steps

- [x] `S06` - Preserve authored predecessor declarations in saved rendering snapshots and verify encrypted readback; `src/cadrumo/domain/modelos/calculation_revision_rendering.py and its owning roundtrip tests`.
- [x] `S01` - Repair canonical tooling imports and typed developer fixtures; `dev/docs, dev/packaging, dev/registry excluding dev/quality/metadata`.
- [x] `S02` - Repair production and Windows fixture type contracts; `src/cadrumo/domain/calculations/registry, application/operations/terminated_owner.py, entrypoints/cli/config/tests and native desktop Python`.
- [x] `S03` - Complete retirement of obsolete Google workbook paths and repair remaining typed renderers; `Google adapters, calc_sheets, modelo spreadsheet modules and dedicated review presentation modules`.
- [x] `S04` - Reconcile authentication and storage symbols with their real production consumers; `profile authentication, secure custody and core storage_environment`.
- [x] `S07` - Retire residual unconsumed observation prototypes and reconcile their owning tests and descriptions; `gasto193_bindings.py, withholding296_bindings.py and direct typed-row consumer descriptions and tests`.
- [x] `S05` - Regenerate import enrollment and prove the integrated blocking gate result; `dev/quality/metadata and all modified source plus focused tests`.

## Parallelization

Use vaultspec-team to dispatch three workers concurrently for S01, S02 and S03 with disjoint source ownership. S01 owns developer tooling except generated import metadata. S02 owns the reported type files in domain, terminated_owner, CLI config live fixtures and native desktop Python. S03 owns Google adapters, application/export/managed_artifact_ports, calc_sheets, modelo spreadsheet modules, row-set assembly and dedicated CLI/TUI review presentation; it excludes S02 CLI config fixtures. The supervisor owns S04, generated import metadata, shared plan/ledger writes, commits and expensive full-tree checks. Workers report proposed edits outside ownership before writing. Preserve peer edits. Serialize overlapping tests and Git checkpoints. S05 follows completed source repairs.

After completing S02, its worker may implement the login-session retirement portion of S04: production login_session.py and affected test setup consumers/owning handover tests. The supervisor retains other S04 authentication declarations, storage conformance support and error catalogue. Coordinate test import-only overlaps with S03; preserve the peer-owned desktop runtime fixture. Source edits remain disjoint. The supervisor serializes S04 evidence and commit.

The S01 tooling worker also owns S06 after diagnosing the exact encoder boundary: calculation_revision_rendering.py and its owning roundtrip tests. The supervisor retains source review, shared gates and Git/vault serialization. S01 export-evidence closure depends on the S06 readback correction; S05 follows the final source writes.

After S04, its worker owns S07 residual observation prototypes and their direct references. Keep live provider/selector schemas and actual filing detail-record projection unchanged; no fake production consumer or unchecked tax behavior is introduced. The supervisor checks any residual Google helper against the current shared tree and retains final metadata/gates.

## Verification

Require zero findings from all twelve configured blocking code-quality gates, retaining every checker scope and refusal predicate. Use focused real-boundary tests for changed behavior, with lint, formatting and applicable type evidence before closing a Step. Preserve missing values and authority checks; no suppressions, baselines, test skips or fabricated consumers. Regenerate import load metadata through its owning generator after source retirement. Reuse unchanged gate evidence and run one final integrated `just check-code` on stable inputs. Record unavailable or moved-source evidence separately. Complete only after all Steps and integrated review pass; advisory audits, live OAuth, deployment and full product campaigns are outside this request.
