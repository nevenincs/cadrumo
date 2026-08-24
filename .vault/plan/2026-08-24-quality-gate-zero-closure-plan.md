---
tags:
  - '#plan'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
tier: L3
related:
  - '[[2026-08-24-quality-gate-zero-closure-adr]]'
  - '[[2026-08-24-quality-gate-zero-closure-static-gate-matrix-research]]'
  - '[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]'
  - '[[2026-07-14-honest-all-green-adr]]'
  - '[[2026-06-09-quality-hardening-campaign-adr]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
modified: '2026-08-24'
body_hash: 'sha256:321dcc0157b2c4d23780f3e50324e2c8f792ebb135fe85037ccb9ad64ca10593'
---

<!-- RETIRED: W01, W02, W03, W04, W05, W06, P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P15, P16, P17, P18, P19, S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S43, S44, S45, S46, S47, S48, S49, S50, S51, S52, S53, S54, S55, S56, S57, S58, S59, S60, S61, S62, S63, S64, S65, S66, S67, S68, S69, S70, S71, S72, S73, S74, S75, S76, S77, S78, S79, S80, S81, S82, S83, S84, S85, S86, S87, S88, S89, S90, S91, S92 -->

# `quality-gate-zero-closure` plan

## Description

This L3 roll-up executes the accepted `2026-08-24-quality-gate-zero-closure-adr`, grounded by `2026-08-24-quality-gate-zero-closure-static-gate-matrix-research` and `2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference`. W01 owns the fresh non-baseline snapshot, joined evidence matrix, RAG discovery, and explicit owner handoffs. W02 repairs syntax, style, format, dependency, architecture-import, and relative-import surfaces. W03 repairs type root causes at shared boundaries. W04 routes every ratchet family and repairs Vault hard errors while keeping warnings visible. W05 drives security, complexity, duplication, checkout drift, corpus-text, semantic, and composed advisory surfaces toward measured green. W06 is the only closure authority and requires a clean verification snapshot, independent review, RAG redeclaration audit, and separate out-of-scope lane evidence.

Active feature plans retain implementation authority for their paths. The coordinator records the command, owner, path scope, starting revision, dirty-path overlap, focused behavior proof, full-gate result, and disposition for every batch. No Step permits a baseline, threshold, new exclusion, suppression, skip, xfail, mock, monkeypatch, tautological assertion, or hidden allowlist to make a red signal disappear.

## Steps

## Parallelization

Waves are hard-sequenced: W01 snapshot and ownership must precede W02 hard static repair; W02 must precede W03 type closure; W03 must precede W04 ratchet and Vault closure; W04 must precede W05 advisory and corpus convergence; and W05 must precede W06 clean verification and review. Any revision or dirty-path change during a closure run invalidates the run and returns to W01 or W06 as appropriate.

Within W01, P01 precedes P02. Within W02, P03 clears syntax before P04 and P05; P04 and P05 may then proceed in parallel only on disjoint, owner-accepted paths. Within W03, P06 establishes the diagnostic matrix before P07 and P08; those two boundary phases may run in parallel when their path ledgers do not overlap, and P09 is a barrier. Within W04, P10 and P11 may run in parallel after W03, while P12 waits for the Vault repair results and warning inventory. Within W05, P13 through P16 may run in parallel after W04 only when their scanner and production path scopes are disjoint; P16's dashboard consumes the completed scanner evidence. W06 is sequential: P17 runs the clean joined matrix, P18 independently reviews it, and P19 publishes the final evidence.

Model routing is explicit in each Step: Luna max owns audits, normalized diagnostic triage, type-check reruns, mechanical sanity, Vault checks, and evidence review; Terra xhigh owns production coding, behavior-preserving refactors, and real-test repairs; Sol only handles an architecture refactor or boundary decision in W02.P04.S18 after the owning architecture plan accepts the handoff. No agent may silently edit a peer-owned path.

## Verification

The plan is complete only when all 92 Steps are checked through their canonical execution records and the independent review artifacts agree with the current tree. Closure requires the following evidence from one unchanged clean verification snapshot:

- The canonical hard checks are exact zero: style, format, all configured type checkers, architecture imports, relative imports, dependency declarations, and every ratchet family. The local dashboard and CI-scope commands must agree, and no count reduction, threshold, baseline, exclusion, suppression, skip, xfail, or allowlist may substitute for zero.
- `vaultspec-core vault check all --json` reports zero hard errors. The warning inventory remains separate and lists every warning with owner, disposition, next action, and residual risk, including annotations, orphans, feature-index drift, body hygiene, schema warnings, modified stamps, and encoding signals.
- Security, complexity, duplication, checkout drift, and corpus-text reports are measured on the intended tree and green under their existing authorities. `check-security` proves that files were scanned and has no findings; complexity and duplication have no unresolved hotspots or clone clusters; checkout drift is zero without ceiling growth; and every manual-corpus sidecar is current.
- RAG health and semantic checks are measured rather than skipped. The redeclaration audit verifies canonical homes and live consumers by meaning, records every true duplicate or justified divergence, and leaves no unowned finding or silent coordinator takeover.
- The joined report records each exact command and environment, start and end HEAD, clean status, dirty-path overlap, exit status, full diagnostic count, focused behavior proof, active owner, path scope, and final disposition. Any revision or dirty-ledger change invalidates the matrix and requires a rerun.
- The formal code review and fresh-context honesty review find no unactioned safety, intent, architecture, quality, provenance, or handoff issue. The review explicitly proves that no new suppression, baseline, skip, xfail, mock, monkeypatch, tautology, or hidden allowlist was introduced.
- Unit, integration, packaging, external-advisory, and credential-gated lanes are reported separately with their actual evidence and are never presented as green by absence. A missing or unavailable lane is an explicit out-of-scope or blocked result, not a hard-gate pass.
