---
tags:
  - '#plan'
  - '#desktop-quality-repair'
date: '2026-10-27'
tier: L1
related:
  - '[[2026-10-23-desktop-ledger-editor-adr]]'
  - '[[2026-10-26-rust-component-provisioning-registered-operations-adr]]'
modified: '2026-10-27'
body_schema: body-v2
body_hash: 'sha256:bb0481467928004d98e4d03ea13e45e351843c0575a1ee4bdf3b922e3f516b79'
---

# Desktop and repository quality repair

## Description

Approved 2026-10-27. Authorization: the operator requested that frontend, styling, reachability, Tauri, lint and type checks pass, using Luna Max for read-only discovery and Terra 6.1 High for coding.

Repair current browser and Python quality failures under the accepted desktop ledger and registered component operation decisions. Preserve runtime authority, privacy, review and unknown-outcome constraints. No new architectural decision is required. Formatting cleanup already committed as 1e9ae46eab is prior evidence; this plan covers the remaining repairs. Preserve other in-flight changes.

## Steps

- [ ] `S01` - Repair ledger read-state behavior and failing frontend scenarios; `native/desktop/frontend`.
- [x] `S02` - Repair Python type and import boundaries and remove obsolete unused exports; `src/cadrumo, src/cadrumo_runtime tests and dev/quality metadata`.

## Parallelization

S01 belongs to the frontend Terra worker and covers ledger selection/read-state hooks, fixtures and failing browser scenarios in native/desktop/frontend. S02 belongs to the Python Terra worker and covers component operation types, obsolete extraction and URL exports, import-boundary test placement and generated import metadata. These source areas may proceed concurrently. Luna workers inspect and review without source edits. The supervisor owns shared vault records, commits, final checks, ports and browser output. Finish asset generation and builds before browser verification; hold governed Python sources stable during import verification.

## Verification

S01 requires npm run check, unchanged ledger benchmark budgets, pending-read fail-closed regression coverage and passing evidence for the complete browser population after corrections. Do not weaken assertions, timing budgets or authority checks.

S02 requires Ruff lint/format, configured ty/pyrefly/basedpyright targets, relevant Python tests and just check-code, including module/symbol/export reachability, writer coverage and import authority. Regenerate import-load metadata only through its owning generator.

Reuse applicable passing just check-rust Debug, desktop script tests, desktop-host-unit-test and desktop-host-build evidence while inputs remain unchanged. The final integrated review reports any verification gap explicitly.
