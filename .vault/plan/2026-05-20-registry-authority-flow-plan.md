---
tags:
  - '#plan'
  - '#registry-authority-flow'
date: '2026-05-20'
modified: '2026-05-20'
tier: L3
related:
  - '[[2026-05-20-registry-authority-flow-adr]]'
  - '[[2026-05-20-registry-authority-flow-research]]'
---


# `registry-authority-flow` registry authority flow rollout plan

## Wave `W01` - inventory and classify registry entry points

This wave establishes the complete call-site map before migration, separating compiler tests, source-audit tooling, authority-backed production consumers, and production code that still reaches around the authority.

### Phase `W01.P01` - map direct loader usage

Identify every direct registry loader entry point and classify whether it is compiler-test, source-audit tooling, or production orchestration debt.

- [x] `W01.P01.S01` - Inventory direct raw loader imports; `src/aeat`.
- [x] `W01.P01.S02` - Classify registry package raw loader tests; `src/aeat/domain/calculations/registry`.
- [x] `W01.P01.S03` - Classify production raw loader consumers; `src/aeat/application src/aeat/adapters src/aeat/domain`.

### Phase `W01.P02` - define allowed boundary imports

Convert the inventory into an explicit allowlist for compiler internals and tests before adding enforcement.

- [x] `W01.P02.S04` - Define raw loader allowlist policy; `src/aeat/domain/calculations/registry/test_public_api_boundaries.py`.
- [x] `W01.P02.S05` - Record authority boundary rule coverage; `.codex/rules/aeat-registry-authority-flow.md`.

## Wave `W02` - stabilize authority invariants

This wave fixes the correctness issues that make the authority boundary unsafe to enforce: stale cache invalidation, nested export field identity, and focused tests for both behaviours.

### Phase `W02.P03` - repair authority cache invalidation

Thread complete registry tree fingerprints through the authority cache so path-stable registry edits cannot serve stale compiled data.

- [x] `W02.P03.S06` - Thread registry fingerprints into authority cache keys; `src/aeat/domain/calculations/registry/_authority.py`.
- [x] `W02.P03.S07` - Prove authority reloads changed fragmented TOML; `src/aeat/domain/calculations/registry/test_authority.py`.
- [x] `W02.P03.S08` - Align filing runtime provider cache with authority fingerprints; `src/aeat/application/filing/runtime.py`.

### Phase `W02.P04` - repair nested export identity

Reject duplicate export field ids when same-record fragments append field arrays.

- [x] `W02.P04.S09` - Reject duplicate nested export field ids; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `W02.P04.S10` - Cover duplicate export field fragments; `src/aeat/domain/calculations/registry/test_loader_directory_mode.py`.

## Wave `W03` - migrate production registry consumers

This wave moves production call sites behind ValidatedRegistryAuthority or repository facades while preserving raw loader access only for compiler tests and tooling that explicitly audits source files.

### Phase `W03.P05` - migrate filing runtime consumers

Move filing runtime schema-provider orchestration fully behind the validated authority cache contract.

- [x] `W03.P05.S11` - Migrate filing schema provider to authority-only loading; `src/aeat/application/filing/runtime.py`.
- [x] `W03.P05.S12` - Verify filing runtime provider snapshots; `src/aeat/application/filing/test_filing.py`.

### Phase `W03.P06` - migrate adapter and application consumers

Replace production raw-loader orchestration in adapters and application services with authority-backed access.

- [x] `W03.P06.S13` - Migrate Google config registry loading; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `W03.P06.S14` - Migrate Sede declaration registry loading; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W03.P06.S15` - Migrate application registry service loading; `src/aeat/application/registry/__init__.py`.

## Wave `W04` - enforce and verify the boundary

This wave adds structural enforcement, cleans or scopes registry gates, and documents the residual package-wide verification posture so future work cannot reintroduce duplicate orchestration paths.

### Phase `W04.P07` - add structural enforcement

Add tests that prevent new production raw-loader imports outside approved compiler and authority boundaries.

- [x] `W04.P07.S16` - Add production raw-loader import guard; `src/aeat/domain/calculations/registry/test_public_api_boundaries.py`.
- [x] `W04.P07.S17` - Add authority snapshot boundary assertions; `src/aeat/domain/calculations/registry/test_authority.py`.

### Phase `W04.P08` - stabilize verification gates

Document and run the focused gates for this rollout, and isolate unrelated package-wide lint or timeout failures.

- [x] `W04.P08.S18` - Run focused authority and loader gates; `src/aeat/domain/calculations/registry`.
- [x] `W04.P08.S19` - Run filing and adapter migration gates; `src/aeat/application src/aeat/adapters src/aeat/entrypoints`.
- [x] `W04.P08.S20` - Record residual package-wide gate status; `.vault/audit/2026-05-20-registry-orchestration-review.md`.

## Wave `W05` - residual gates and fragment hardening

This wave tracks the work left after the authority rollout: package-wide registry gates, oversized M200 fragment reduction, and vault-wide hygiene that remains outside the focused rollout.

### Phase `W05.P09` - stabilize registry package gates

Convert residual registry package lint and timeout caveats into explicit gates with clear status.

- [x] `W05.P09.S21` - Clean package-wide registry ruff residuals; `src/aeat/domain/calculations/registry`.
- [x] `W05.P09.S22` - Run package-wide registry pytest with chunked diagnostics; `src/aeat/domain/calculations/registry`.

### Phase `W05.P10` - finish M200 fragment-size hardening

Mechanically split the remaining oversized M200 TOML fragments and lower the fragment-size threshold after real registry coverage passes.

- [x] `W05.P10.S23` - Split oversized M200 export and construct fragments; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes`.
- [x] `W05.P10.S24` - Lower registry TOML fragment line threshold; `src/aeat/domain/calculations/registry`.
- [x] `W05.P10.S25` - Verify M200 registry and fragment-size gates; `src/aeat/domain/calculations/registry`.

### Phase `W05.P11` - track vault-wide residual hygiene

Keep vault-wide pre-existing validation failures visible without confusing them with the registry authority implementation.

- [x] `W05.P11.S26` - Separate vault-wide pre-existing hygiene from this rollout; `.vault`.

### Phase `W05.P12` - diagnose suspicious registry performance

Treat unexpectedly slow registry verification as a defect to profile, reduce, and gate explicitly before this residual wave can close.

- [x] `W05.P12.S27` - Profile registry test collection and load hot paths; `src/aeat/domain/calculations/registry`.
- [x] `W05.P12.S28` - Reduce redundant committed registry loads in slow tests; `src/aeat/domain/calculations/registry`.
- [x] `W05.P12.S29` - Establish suspicious-performance gate budget; `src/aeat/domain/calculations/registry`.
- [x] `W05.P12.S30` - Bring slow registry chunks under the performance budget; `src/aeat/domain/calculations/registry`.
