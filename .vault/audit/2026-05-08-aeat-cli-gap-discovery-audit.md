---
tags:
  - '#audit'
  - '#aeat-cli-gap-discovery'
date: '2026-05-08'
related:
  - "[[2026-05-08-aeat-cli-hardening-plan]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
