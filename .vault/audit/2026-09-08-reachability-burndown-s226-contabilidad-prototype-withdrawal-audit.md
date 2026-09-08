---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:def0be3752bd110abea4331e96d1f3477fb566ac5e65473357616ef099ba87e4'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S226]]"
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
  - "[[2026-09-04-reachability-burndown-reference]]"
---

# `reachability-burndown` audit: `S226 contabilidad prototype withdrawal review`

## Scope

Independent review of W05.P12.S226, covering deletion of the six-module `domain.contabilidad` prototype, four synthetic test modules, three central error registrations, the accepted Modelo 200 base-determination ADR and live registry calculation tests, exact reachability/orphan evidence, cadence guidance, and the Step Record.

## Findings

No critical, high, medium, or low findings.

The deleted package had no acquisition adapter, application service, calculation binding, composition root, CLI/TUI presentation, persistence owner, or development consumer. Its PGC account, accounting-direction, extracontable-correction, balance and trial-balance models formed a closed speculative model cluster exercised only by their own synthetic suites. The three registered error codes likewise served only exceptions inside that unreachable cluster.

The accepted Modelo 200 base-determination ADR neither names nor requires these representations. Its live implementation is registry-owned: casilla `00550` derives from resultado contable and aggregate increase/decrease correction totals, and `00552` applies compensation/reserve logic. Retained registry tests execute that formula chain, include a positive-result silent-zero killer and complete correction-subtotal behavior, and cover the broader Modelo 200 registry structure. Removing unused per-account and trial-balance prototypes does not alter those inputs or calculations.

The orphan accounting is credible. Six shipped modules disappear, moving unreachable modules from 60 to 54 without changing the 306 exact-symbol population. Three orphan findings disappear with the four test files because `test_cuenta` had a support edge to the live shared `DomainValidationError`; that import masked its otherwise self-contained dead subject, so the four deleted files produce a net 8-to-5 orphan reduction rather than four. No test carried product integration or behavioral coverage beyond constructing the deleted models.

The Step Record accurately lists every deletion and error-registry edit, clean residue and Ruff, 49 focused registry/Modelo 200 passes, and exact 54-module/306-symbol/5-orphan/2029-of-2084 evidence. The broader exception-base gate's 19 classes are unrelated live peer findings and none names `contabilidad`; the record does not absorb or misattribute them.

## Recommendations

Approve W05.P12.S226. If accounting ingestion becomes a real Modelo 200 requirement, introduce representations from the owning acquisition and registry-calculation boundary with end-to-end evidence; do not restore this isolated prototype or its dormant error vocabulary.
