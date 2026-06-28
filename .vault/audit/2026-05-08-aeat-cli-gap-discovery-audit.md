---
tags:
  - '#audit'
  - '#aeat-cli-gap-discovery'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-aeat-cli-hardening-plan]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
---



# `aeat-cli-gap-discovery` audit: `AEAT CLI UX root-cause analysis and gap inventory`

This artifact imports the 2026-05-08 CLI audit supplied as rollout input and
anchors it for execution. The controlling implementation checklist is the
hardening plan. This audit keeps the root-cause statement, surface inventory
classes, issue index, and action mapping stable so later execution records can
refer to audit ids without relying on chat history.

## Root Cause

The current AEAT CLI behaves as a transactional command surface. Commands run an
action, exit, and print minimal output. It does not yet behave as a
self-documenting, discoverable, stateful product surface that can diagnose
environment state, explain next steps, expose available modelos, or recover from
errors with concrete fixes.

The primary engineering implication is that CLI hardening is not only copy or
command registration work. Missing backend APIs, missing schema ownership,
missing profile readiness contracts, missing registry introspection, and weak
test signals are in scope whenever the CLI would otherwise have to implement
business logic locally.

## Surface Inventory Summary

The audit enumerates 64 user-facing or user-visible surfaces:

- root surfaces: `aeat`, `aeat --help`, `aeat --version`, global format flags,
  missing `doctor`, missing `init`, missing topic/help/config roots;
- setup surfaces: setup root, init, status, auth provider/config/login/status/
  reset/whoami/logout, profile use/show/list-keys/get/set/unset/validate/list,
  and missing setup reset;
- app surfaces: app root, overview status/calendar, ledger import/review/edit,
  invoice import/review/edit/match, declaration calculate/review/status/edit/
  approve/validate/preview/export/verify, registry inspect/verify/capture/
  parity/workbooks, and missing modelo introspection commands;
- cross-cutting surfaces: internal warnings leaking to stderr and one-line
  errors without recovery guidance.

## Issue Index

| audit_id | Severity | Headline | Required action ids |
|---|---|---|---|
| UX-001 | HIGH | Stale-dependency traceback on first invocation. | A1, A2 |
| UX-002 | HIGH | No root version flag. | A3 |
| UX-003 | HIGH | No guided onboarding wizard; help ordering is not workflow-shaped. | A4, A5, A6 |
| UX-004 | HIGH | Help text quality is inconsistent and lacks examples. | A7, A8 |
| UX-005 | HIGH | Internal warning logs leak into every command. | A9, A10, A11 |
| UX-006 | HIGH | Profile validation reports valid with only minimal required keys. | A12, A13, A14, A15 |
| UX-007 | HIGH | Profile registry exposes only RENTA-shaped keys. | A16, A17, A18 |
| UX-008 | HIGH | Calendar silently omits modelos when profile facts are absent. | A19, A20 |
| UX-009 | HIGH | App overview strips the next-action pointer. | A21 |
| UX-010 | MEDIUM | Overdue filings lack recovery guidance. | A22 |
| UX-011 | LOW | Cosmetic and consistency gaps in setup/auth/profile reset/show surfaces. | A23, A24, A14 |
| UX-012 | HIGH | Errors lack suggestions, fixes, and learning pointers. | A25, A26 |
| UX-013 | MEDIUM | Format/provider catalogues and invoice kind values are undocumented or drifting. | A27, A28, A29 |
| UX-014 | HIGH | No environment/state diagnostics command. | A1, A30 |
| UX-015 | HIGH | No conceptual help/topic system. | A31, A32 |
| UX-016 | MEDIUM | No central configuration surface. | A33, A34 |
| UX-017 | HIGH | No modelo introspection surface. | A35, A36 |

## Action Index

| action_id | Verb | Action |
|---|---|---|
| A1 | ADD | Add `aeat doctor`. |
| A2 | WRAP | Wrap import/startup failures in a user-facing diagnostic. |
| A3 | ADD | Add `--version`, `-V`, and `aeat version`. |
| A4 | ADD | Add root `aeat init` onboarding. |
| A5 | REORDER | Group setup commands by workflow phase. |
| A6 | ADD | Add root quickstart help. |
| A7 | AUDIT | Audit every setup/app flag help surface. |
| A8 | ADD | Add examples, format hints, and discovery pointers. |
| A9 | REROUTE | Route internal logs to user log files. |
| A10 | SUPPRESS | Suppress or fix the short-plaintext hashed lookup warning leak. |
| A11 | ADD | Add global `--verbose` and `--debug`. |
| A12 | REPLACE | Replace boolean validity with per-modelo readiness. |
| A13 | ADD | Add `--for-modelo` readiness filtering. |
| A14 | ADD | Add all-key/unset profile display. |
| A15 | SHOW | Show completeness ratios. |
| A16 | EXTEND | Extend schema/profile keys for IVA, IRPF, modelo enrolment, SII, Verifactu, and ROI. |
| A17 | EMIT | Emit cross-regime coordination warnings from backend validation. |
| A18 | ROUND-TRIP | Route profile mutation through typed backend models consumed by engines. |
| A19 | EMIT | Emit calendar warnings and completeness blocks. |
| A20 | REFUSE | Refuse incomplete calendars unless explicitly allowed. |
| A21 | ADD | Add backend next-action computation to app summaries. |
| A22 | ADD | Add recovery fields to overdue calendar entries. |
| A23 | TRANSLATE | Translate `auth reset` description to Spanish. |
| A24 | ADD | Add scoped `aeat setup reset`. |
| A25 | WRAP | Render structured CLI errors with suggestions and fixes. |
| A26 | REGISTER | Register per-error fix templates. |
| A27 | FIX | Align invoice `--kind` help with accepted values. |
| A28 | ADD | Add topics for formats, providers, and regimens. |
| A29 | ADD | Add shell completion surface. |
| A30 | ADD | Expand doctor to env, registry, profile, auth, data, and network diagnostics. |
| A31 | ADD | Add `aeat topic` and `aeat help <topic>`. |
| A32 | AUTHOR | Author initial conceptual topics. |
| A33 | ADD | Add `aeat config` family. |
| A34 | UNIFY | Unify profile, auth, registry, format, verbosity, and language config. |
| A35 | ADD | Add app modelo list/describe/casillas/bindings/formulas commands. |
| A36 | IMPLEMENT | Implement typed registry query Python API. |

## Review Mandates

- CLI code must remain transport-only.
- Backend behavior is in scope whenever CLI hardening uncovers missing
  diagnostics, validation, readiness, registry, profile, error, or output APIs.
- Tests must verify behavior that can fail for real regressions; tautological
  assertions and test-only shortcut layers are not acceptable closure evidence.
- Every implementation slice requires a code review pass before it is treated as
  closed.

## Recompile (2026-05-08)

The CLI was re-driven against the worktree at rev `d0132eb5`. The drift since
the prior pass is substantial: seven HIGH findings have closed, two are
partial, three remain open, and four new findings are introduced.

### Closed since the prior pass

| audit_id | Status | Evidence at rev `d0132eb5` |
|---|---|---|
| UX-002 | CLOSED | `aeat --version` returns version plus 25 modelos / 14948 casillas / 1027 formulas summary. `aeat version` subcommand also exists. |
| UX-005 | CLOSED | No `WARNING` line printed on any of the 12 commands re-probed. Logs route to user log file. `--quiet`, `--verbose`, `--debug` global flags present. |
| UX-009 | CLOSED | `aeat setup status` emits `Siguiente: aeat app overview status`. `aeat app declaration calculate` emits `Siguiente: resolve-blockers`. The `Siguiente` line is wired across the surfaces UX-009 named. |
| UX-014 | CLOSED | `aeat config doctor` exists and returns a structured 7-row check list with overall verdict. |
| UX-016 | CLOSED (namespace) | `aeat config` family namespace wired; only `doctor` verb present so far; the wider `list/get/set/unset/configurations` shape is still future work. |
| UX-017 | CLOSED | `aeat app modelo {list,describe,casillas,bindings,formulas}` all present and return rich tabular data. |
| UX-018 | CLOSED | Two-step calculate then status across separate shell invocations resolves the same draft id. Drafts persist across CLI invocations. |

### Partial

- UX-003: A6 (root quickstart line) is shipped. A4 (interactive `aeat init` at root) and A5 (workflow-phase reorder of `aeat setup` subcommands) remain open.
- UX-006: `aeat setup status` now emits `Completitud: N/22` alongside `Falta: -` and `Perfil listo: si`. The completeness ratio is real progress; the boolean `Perfil listo: si` still oversells readiness when only a small subset of keys are set.

### Still open

| audit_id | Severity | Current evidence |
|---|---|---|
| UX-007 | HIGH | `aeat setup profile list-keys` returns 22 personal-identity keys. Direct probe `aeat setup profile set iva.regime general` returns `Clave de perfil desconocida: iva.regime`. PROFILE_KEYS still does not represent IVA, IRPF, modelo enrolment, regime, SII, Verifactu, intracomunitario axes. |
| UX-012 | HIGH | `aeat app declaration calculate --modelo 130 --period 2026Q1` still returns `binding 'irpf.previous_year_economic_activity_net_income' has no supplied value`. `aeat app modelo bindings 130 --period 2026Q1` reveals the binding is sourced from `previous_filing` but `declaration calculate` still has no `--binding KEY=VALUE` flag and the error is not rewritten with a fix pointer. |
| UX-004 | HIGH | `aeat setup init --help` still emits surface-only flag descriptions. No examples, no format hints, no valid-value pointers. |
| UX-001, UX-010, UX-011, UX-013, UX-015 | UNVERIFIED | Not re-probed at rev `d0132eb5`. Status carried over from prior pass. |

### New findings

| audit_id | Severity | Headline | Surfaces |
|---|---|---|---|
| UX-019 | HIGH (REGRESSION) | AES-256-GCM tag verification failure on read paths. | `aeat app overview status`, `overview status --calendar`, `declaration review`. |
| UX-020 | MEDIUM | Declaration verbs have inconsistent flag surfaces. `status` accepts `(--modelo, --period)`; `approve` and `validate` reject those flags. | `aeat app declaration status`, `approve`, `validate`. |
| UX-021 | MEDIUM | Blockers enumerated by count only. `Bloqueos: 2` is opaque; `Siguiente: resolve-blockers` is a recipe token, not a runnable command, and the natural follow-up `declaration review` is currently broken by UX-019. | `aeat app declaration calculate`, `declaration status`. |
| UX-022 | LOW | Auth-readiness diverges between `setup auth status` (reports `Listo: no`) and `config doctor` (reports `ok auth.session`). Two readiness predicates in the same backend. | `aeat setup auth status`, `aeat config doctor`. |

UX-019 is the new load-bearing finding. Ship it before any remaining UX-001 to UX-018 polish, because it currently breaks the most basic CLI surface (`aeat app overview status`) regardless of what other work has landed.

### Updated reading order

- Tier 1 (backend-first): UX-019 (read-path integrity regression), UX-007 (regime keys), UX-012 (M130 binding supplier surface).
- Tier 2 (CLI-shape): UX-020 (verb flag-surface inconsistency), UX-021 (blocker enumeration), UX-004 (help-text uplift), UX-006 (boolean `Perfil listo` oversells).
- Tier 3 (low / unverified): UX-001, UX-010, UX-011, UX-013, UX-015, UX-022.
