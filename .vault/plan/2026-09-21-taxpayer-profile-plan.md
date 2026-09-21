---
tags:
  - '#plan'
  - '#taxpayer-profile'
date: '2026-09-21'
tier: L2
related:
  - '[[2026-08-13-profile-session-lifecycle-successor-adr]]'
  - '[[2026-08-13-profile-state-aggregate-successor-adr]]'
  - '[[2026-07-23-profile-setup-flow-adr]]'
  - '[[2026-07-23-tui-wizard-substrate-adr]]'
  - '[[2026-08-19-profile-setup-completion-adr]]'
modified: '2026-09-21'
body_schema: body-v2
body_hash: 'sha256:728fc743fc5f5763b3c461ee04899235e25f9c706213615e0dcb78aba248ec7c'
---

# `taxpayer-profile` plan

Audit and close taxpayer-profile capability, parity, and usability gaps across the shared backend, CLI, and TUI.

## Description

Approved 2026-09-21

The user explicitly assigned PROFILE-01 revision 0.1 for audit, evaluation, and code fixes that make the backend, CLI, and TUI parity-capable and usable. The session consumes session-policy revision 1.7 and ACCEPTANCE-01 revision 1.6. Provider is Codex; provider-assigned cc number and UUID remain pending and are not invented.

Accepted decisions already govern profile session identity, encrypted semantic record ownership, the profile setup flow, shared wizard substrate, setup completion, and repeatable activity modelling. P01 measures current behavior and ownership before edits. P02 and P03 implement only reproduced gaps within those decisions. P04 proves the result with synthetic isolated stores and installed entrypoints. The proposed censal repeatable-required-field decision is not implementation authority. Undefined historical resolution, merge precedence, representation authority, or a real certificate layout requires a compact decision packet before dependent work proceeds.

## Steps

### Phase `P01` - audit current profile capability and ownership

Establish current source ownership, frontend writer coverage, one filing-critical fact trace, and reproducible gaps before any product fix.

- [x] `P01.S01` - Record bounded delta, ownership coordination, and profile field writer consumer matrix; `.agents/session-briefs/handoffs/2026-09-21-taxpayer-profile-checkpoint.md`.
- [x] `P01.S02` - Record focused synthetic reproductions for clearing, stale writes, entity switching, census precedence, and frontend writer gaps; `.agents/session-briefs/handoffs/2026-09-21-taxpayer-profile-checkpoint.md`.
- [x] `P01.S03` - Establish current versus historical filing context and escalate any undefined temporal contract; `profile binding and profile projection modules`.

### Phase `P02` - repair canonical backend profile contracts

Fix only reproduced backend validation, persistence, selection, provenance, readiness, or temporal-boundary defects through existing owners.

- [x] `P02.S04` - Repair reproduced canonical profile mutation, projection, selection, and readiness defects; `application and domain user_profile packages`.
- [x] `P02.S05` - Preserve encrypted persistence, provenance, and filing consumer boundaries under profile changes; `profile storage and modelo profile binding modules`.

### Phase `P03` - close CLI and TUI usability parity

Expose shared backend behavior through independent CLI and TUI adapters with honest save, selection, provenance, and capability messaging.

- [x] `P03.S06` - Complete CLI profile configuration, selection, typed editing, and actionable diagnostics; `application user_profile section rows and entrypoints CLI config packages`.
- [x] `P03.S07` - Complete TUI profile configuration, typed editing, switching safety, provenance, and acquisition affordances; `entrypoints TUI profile, app, and registration modules`.
- [x] `P03.S08` - Align localized operator copy without coupling CLI and TUI adapters; `src/cadrumo/locales`.

### Phase `P04` - prove secure cross-entrypoint operation

Run focused gates and isolated installed frontend continuations, then complete integrated review and handoff by PROFILE-01 acceptance ID.

- [ ] `P04.S09` - Implement isolated PROFILE-01 acceptance scenarios and sanitized receipts; `dev/acceptance profile scenario area`.
- [ ] `P04.S10` - Run reserved focused tests, affected quality gates, and installed CLI TUI continuations; `taxpayer profile affected source and acceptance areas`.
- [ ] `P04.S11` - Complete integrated review and PROFILE-01 handoff; `.vault/audit and taxpayer profile checkpoint`.

## Parallelization

P01 is sequential because its matrix and reproductions determine the safe implementation scope. Within P02, distinct backend fixes may run concurrently only after file ownership is explicit and disjoint. P03 CLI, TUI, and locale Steps may run concurrently after shared backend contracts land, again with one writer per file. P04 acceptance implementation follows stable product behavior; verification and final review are sequential. The shared worktree requires coordination with active income, IVA, assets, calendar, and TUI owners before touching overlapping files.

## Verification

- The bounded schema field matrix identifies CLI writer, TUI writer, canonical validator, encrypted persistence owner, downstream consumer, provenance, clear behavior, and unsupported status for each filing-critical field.
- Focused synthetic tests reproduce or disprove cleared-fact resurfacing, stale writes, in-flight entity switching, census precedence, and typed frontend editing before fixes are selected.
- Directed tests run with exact node IDs, explicit applicable markers, and `-n 0` under the global reservation list; commands, source state, counts, exits, and sanitized artifact pointers are retained.
- Affected ruff, ty, strict typing, import-boundary, locale, and registry contract gates pass once after integration.
- CLI-only, TUI-only, CLI-to-TUI, and TUI-to-CLI journeys use separate isolated encrypted stores and fresh processes, without live AEAT access or private data.
- PR1 through PR12 are each reported as proven, failed, blocked, or not exercised, with remaining limitations and downstream impacts.
- The final integrated code review has no unresolved critical or high findings, and every Step is closed.
