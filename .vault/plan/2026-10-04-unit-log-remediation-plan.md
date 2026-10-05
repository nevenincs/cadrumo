---
tags:
  - '#plan'
  - '#unit-log-remediation'
date: '2026-10-04'
tier: L1
related:
  - '[[2026-09-09-facts-registry-governed-fact-catalogue-adr]]'
  - '[[2026-09-10-registry-authority-artifact-boundary-adr]]'
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
  - '[[2026-09-17-filing-chain-reconciliation-adr]]'
modified: '2026-10-04'
body_schema: body-v2
body_hash: 'sha256:fcb8e55e0017f624d78a73124b36a44f0ab97765ffdd60a9b993f68d2e887f7e'
---

# `unit-log-remediation` plan

## Description

Approved 2026-10-04. Complete remediation of the failure patterns in `.logs/unit-tests-20261004-180702.log`, using autonomous GPT-6.1 Sol medium/high coding agents while the lead handles the hardest issues. The user subsequently authorized test reruns and requested iteration on `.logs/unit-tests-20261004-212139.log` (120 failed, 27,927 passed, 151 skipped; no worker crash). This supersedes the initial static-only restriction. Preserve unrelated active work and accepted authority, freshness, filing-chain and storage contracts.

Complete source and consumer repairs, required named generated targets, and canonical runtime authority adoption. Lead serializes generated-target and final authority publication; never manually overwrite the authority descriptor or generated targets. Run focused verification, integrate deliveries, then rerun the full unit suite.

## Steps

- [x] `S01` - Repair logging redaction format safety and core structural drift; `src/cadrumo/core/logging.py redaction rules and core tests`.
- [x] `S02` - Repair operator-interface failures and stale structural inventories; `TUI CLI operation catalogue and documentation/provenance test targets`.
- [x] `S03` - Repair generation-bound PDF presentation and export identity capability; `application/modelo/calculation_summary_presentation.py calculation_report_verification.py export.py and callers`.
- [x] `S04` - Adjudicate registry export semantic failures and review integrated remediation; `M303 M190 M180 M145 M130 M111 registry/export contracts and integrated static review`.
- [x] `S05` - Repair browser provisioning fixtures and failure-aware cancellation readiness; `src/cadrumo/adapters/outbound/aeat tests and browser support plus custody/tests/test_kdf_supervision.py`.
- [x] `S06` - Repair deterministic wallet authority evaluation and coherent filing fixtures; `application/modelo/iva_wallet_gate.py calculation and verification callers plus profile persistence fixture support`.

## Parallelization

Workers receive autonomous scoped assignments with shared-workspace preservation instructions. No interaction or wait commands while they run. Follow-on assignments occur after delivery. Lead alone writes vault records, runs the full unit suite, and serializes canonical generated-target and authority publication. Scoped -n0 tests are permitted to workers. No commits.

Initial autonomous ownership covered logging/core, CLI/TUI, browser/native lifecycle, M145/M180, M303 source bindings, and wallet clock tests. Lead owned wallet operation-time/persistence ordering, filing lifecycle fixtures, PDF/export identity contracts, and M190 source-pinned profiles/generation.

120-failure iteration: Sol6.1 high runtime worker repaired native trust/cleanup and now owns M369/M100/M130-negative/NACE fixtures; Sol6.1 medium structural worker repaired canonical types, hashing/HTML/nofollow and now owns M347 source identifier migration; Sol6.1 high interface worker repaired CLI/projection/persistence inventories and now owns receipt capture and wallet pull/calculation fixtures. Lead owns M303 shared export fixtures, M180 assertions, retired refusal-key inventories, registry adoption and integrated review. Generated M347 export regeneration and authority adoption remain lead-only.

## Verification

User now authorizes runtime tests and iterative repair. Use focused source review, scoped lint/type, and affected -n0 tests while independent workers implement nonoverlapping scopes. Capture command output under .logs. Lead integrates and reviews each delivery, then runs just test-unit from the stable combined source. Preserve production guards and canonical generated-target/authority publication boundaries; never mark unexecuted or failing checks passing. Do not commit the shared dirty tree.

On the 2026-10-05 continuation, live source mutation persisted across the gate and one new fixture ownership violation appeared. Repair the concrete violation with focused checks. Complete reproducible integrated import verification against an isolated captured source/configuration snapshot with a retained manifest and unchanged canonical gate; report its exact scope and distinguish it from subsequently edited live source. This avoids repeated mixed-input scans while other authorized workstreams continue.

## Context

The completed original rerun recorded 120 failures. `.logs/remediation-fresh-original-coverage-20261005.json` now reconciles actual fresh recorded outcomes: 110 unchanged cases and six explicit replacements pass; four obsolete locale-key assertions without producers/catalogue entries are separately retired. Zero original failures are unaccounted for.

The integrated full rerun recorded 27,995 passed, six failed and 152 skipped, and worker loss made it incomplete. All six failed paths subsequently passed in an 87-test fresh-process run. Recovery passed 145 tests with one existing POSIX-only Windows skip; all 146 selected nodes have outcomes, with the node reserved for lead covered by the 87-test run. This does not constitute a single uninterrupted green full-suite run.

Original repairs cover native admission/cleanup, browser fixtures, wallet time/evidence consistency, filing fixtures, PDF/export identity, registry wire/binding defects, structural inventories and the redaction recovery algorithm/authority lease. Canonical M347 regeneration and authority adoption completed earlier (`.logs/iteration-120-final-authority.log`, generation be79d7dfce199013af9b628143a6628b3fa060dd6fb3f59715b71e02077e944a); this identifies that publication, not the later active pointer.

Continuation fixed public certificate and financial-custody test-support ownership, M180/M190 semantic replay assertions retaining independent totals/exact wire bytes, and financial-operand error registration with four locale messages. It verified concurrent corpus ownership, M720 canonical source-owner migration and Google evidence-acquisition withdrawal without overwriting the owning workstreams. Focused checks and scoped static checks pass; details and exact counts are retained in the audit. The accepted Google app-identity decision governs removal of remote pull/pull-all while local evidence batch remains tested. M720 structural currentness does not establish complete legal conformance; the audit preserves broader pre-existing semantic findings.

Final captured import attempt 0005 passes with exit 0: all 15 architecture contracts kept, both graph censuses 10,296 files, all 4,407 non-test modules loaded, zero hard findings/architectural debt/pending retirement and unchanged captured hashes. The 19,534-file snapshot and canonical generated metadata are retained under `.logs/remediation-snapshot-20261005/attempts/0005`, with stable graph digest b9d3b85aaf26afe91a0bee743bc1ab959c9275cc7c287a8418126233839a4f77. All 16 checked latest repair files match the capture. Four unrelated paths changed later and are listed in verification.json; they are outside this certificate. Earlier failed attempts remain preserved. Integrated scoped review PASS; no commits.
