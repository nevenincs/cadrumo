---
name: 2026-06-03-suite-redgreen-longtail-discovery-audit
description: Longtail error cluster grouping from suite-final-1.log (reds 110-220)
date: 2026-06-03
tags:
  - '#audit'
  - '#suite-redgreen-longtail-discovery'
related:
  - '[[2026-06-03-cli-bucket-session-test-isolation-audit]]'
  - '[[2026-06-02-suite-redgreen-plan]]'
---

# Suite redgreen burndown — longtail discovery (`suite-redgreen-longtail-discovery`)

**Scope:** Grouping of ~120 longtail failures (reds 110-220) from suite-final-1.log by error shape and triage classification. This is a read-only discovery pass; no code edits or plan mutations.

**Status:** INCOMPLETE — Full file-level mapping pending. Error stems extracted and classified; detailed test-to-file mapping requires additional parsing of full error context from log.

## Error Clusters by Triage Category

### ARCHITECTURAL (Registry/Calculation Engine Regressions)

**Cluster A: M303 resultado-regimen-general computation (15x)**
- Error stem: `VERIFIED-FAIL [...]: engine resultado-regimen-general Decimal('0.00') != extracted Decimal(...)`
- Pattern: Engine computes zero, fixture expects positive value
- Affected files: `test_verification_chain.py` (many periods: 2021-2T through 2022-4T, 2023-1T through 2023-4T)
- Root cause suspect: M303 régimen simplificado engine formula missing or binding wired incorrectly (related to recent M303 formula authoring work)
- Triage: **ARCHITECTURAL** — requires formula/engine verification against Orden EHA/3786/2008 art. 1 (box 46 = box 27 − box 45)
- Related task: #169 (CRITICAL — M303 régimen simplificado authoring)

**Cluster B: M303 box 66 and box 71 carry-forward (15x across periods)**
- Error stem: `VERIFIED-FAIL [20XX-YT]: engine box 66/71 Decimal('0.00') != extracted Decimal(...)`
- Pattern: Quarterly IVA computation returning zero against fixture expectations
- Affected files: `test_modelo_303_compensacion_carry_forward_continuity.py`, `test_verification_chain.py`
- Root cause suspect: M303 compensacion/carry-forward logic incomplete or offset binding path broken
- Triage: **ARCHITECTURAL** — carries forward from recent M303 work; may indicate cross-period state not propagated
- Related task: Task #164 (M303 wallet-seed)

**Cluster C: Storage integrity / profile-bound runtime (15x)**
- Error stem: `Integrity. Storage runtime is not ready for profile-bound storage: No active bucket...`
- Pattern: Configuration/initialization error at application startup
- Affected files: Multiple CLI and setup tests: `test_atomic_create_roundtrip.py`, `test_cli.py`, `test_setup_status_reports...`
- Root cause suspect: Profile lifecycle or bucket manifest initialization broken (recent bucket-session changes or profile-custody binding change)
- Triage: **ARCHITECTURAL** — affects application initialization path; blocks setup/profile operations
- Related task: #244 (CRITICAL P0 — bucket manifest missing required lifecycle status)

### MECHANICAL (Source Code Violations / Rationale Markers)

**Cluster D: Missing rationale markers — CAST-RATIONALE, ANY-PARAM, type-ignore (28x total)**
- Error stems:
  - `3 cast() call(s) lack a CAST-RATIONALE-* marker:` (10x)
  - `28 parameter-Any site(s) found without a rationale marker:` (7x)
  - `14 new type-ignore drift site(s) found without a rationale marker:` (6x)
- Pattern: Source code inventory ratchets failing due to missing documentation markers
- Affected files: 
  - `entrypoints/cli/_app_live.py` (11 type-ignore sites)
  - `entrypoints/cli/_app_config.py` / workflow adapters
  - `adapters/outbound/google_drive.py` (4 missing ANY-RETURN markers)
  - `application/setup/answers.py` (2 missing ANY-RETURN markers)
- Root cause: Recent edits (likely from W26.P59 or other concurrent work) added new cast/type-ignore/parameter-Any sites without documenting rationale
- Triage: **MECHANICAL** — add missing markers to existing lines; no logic change required
- Gate failure: Inventory ratchet tests (`test_cast_rationale_inventory`, `test_any_param_rationale_inventory`, `test_type_ignore_rationale_inventory`)
- Related task: W12.P61 (typed-boundary), W26.P59 (if active)

**Cluster E: Missing rationale markers — ANY-RETURN (4x)**
- Error stem: `missing 'ANY-RETURN-RATIONALE-...'` in `_google_drive.py`, `setup_answers.py`
- Pattern: Google Drive integration and setup answer parsing functions lack return-type rationale
- Root cause: Either:
  a. Bare `Any` return type added without rationale documentation
  b. Recent refactor changed return type from typed to Any without marker
- Triage: **MECHANICAL** — add inline marker comment; no logic change
- Related task: Likely coupled to Google Sheets/Drive integration work

### TAUTOLOGICAL-RATCHET (Test Assertion Ratchets)

**Cluster F: Inventory ratchet failures (6x)**
- Error stem: `Inventory ratchet 'aeat.test_*_rationale_inventory' failed.` + `assert <count> == 0`
- Pattern: Test enforces a zero-count on new violations; count is non-zero
- Affected ratchets:
  - `test_cast_rationale_inventory`: 3 new cast() sites
  - `test_any_param_rationale_inventory`: 28 new parameter-Any sites
  - `test_type_ignore_rationale_inventory`: 14 new type-ignore sites
- Root cause: Recent WIP commits added violations without documenting them; ratchets are doing their job (preventing silent accumulation)
- Triage: **TAUTOLOGICAL-RATCHET** — Ratchets are functioning correctly; failures indicate incomplete documentation burden
- Gate type: Hard-fail (honesty gate — prevents drift from piling up)

### PEER-WIP (Uncommitted State / Cross-Commit Regression)

**Cluster G: Profile/config schema mutations (4x)**
- Error stems:
  - `Unknown profile: tester.`
  - `profile create failed: ...`
  - `"classification" not in <dict>`
- Pattern: Setup or profile-creation path hitting missing enum value, schema field, or init order issue
- Root cause suspect: 
  a. Recent profile schema axis addition (e.g., irpf_special_regime, start_date from #162) not hydrated in test setup
  b. Lifecycle status enum or bucket manifest status field not initialized by profile-create flow
  c. Cross-domain binding (M100 → profile) missing axis that setup tests assume
- Triage: **PEER-WIP** — looks like incomplete feature rollout; related to #162 and #244
- Related task: #162 (Profile schema axis), #244 (bucket manifest lifecycle)

**Cluster H: CLI verb registration/wiring (2x)**
- Error stem: `Usage: aeat app modelo work calculate [OPTIONS] WORK_UNIT_ID` (appears in unexpected test context)
- Pattern: CLI verb invoked with wrong signature or subcommand missing
- Root cause suspect: Recent CLI restructuring or verb reorganization incomplete
- Triage: **PEER-WIP** — verb wiring or command hierarchy incomplete

## Summary by Root Cause and Dispatch Priority

| Root Cause | Cluster | Count | Triage | Dispatch Owner |
|-----------|---------|-------|--------|----------------|
| M303 engine formula chain | A, B | 30 | ARCH | Registry authority specialist |
| Storage init / bucket manifest | C | 15 | ARCH | Storage/profile curator |
| Rationale marker backlog | D, E, F | 28 | MECH | Source code janitor |
| Profile schema / setup flow | G | 4 | PEER-WIP | #162/#244 owner |
| CLI verb wiring | H | 2 | PEER-WIP | CLI curator |
| **TOTAL MAPPED** | | **79** | | |

**Unmapped:** ~41 reds remain in tail (reds 190-220); require full error message extraction from log (currently have test paths only).

## Discovery Constraints and Next Steps

- **Full file-to-error mapping incomplete:** Error stems extracted via rg; detailed test-path-to-affected-file correlation pending full log context extraction.
- **No code edits or plan mutations:** This pass is discovery + classification only.
- **Recommended next step:** Team-lead dispatch top-3 clusters (A: M303 engine, D: rationale markers, C: storage init) to respective owners; re-probe remaining 41 unmapped reds with targeted log slicing.

---

**Output:** `.vault/audit/2026-06-03-suite-redgreen-longtail-discovery-audit.md`
**Date Created:** 2026-06-03
**Session:** Suite redgreen burndown, phase 3 (longtail discovery)
