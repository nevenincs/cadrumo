---
tags:
  - '#audit'
  - '#modelo-projection-validation-performance'
date: '2026-11-15'
modified: '2026-11-15'
body_schema: 'body-v2'
body_hash: 'sha256:e7ffd8d6506f5ecb94d8926e5140a5c7dca08b73caa1be4e4f1eb3255060e0eb'
related:
  - "[[2026-11-15-modelo-projection-validation-performance-plan]]"
---
# `modelo-projection-validation-performance` audit: validated form reuse

## Scope

Review S01 for the source handoff, not completion of S02 or native latency goals. The eight owned source/test paths are recorded in `.tmp/2026-11-15-optimization-b18/final-owned-manifest-v5.json`. The five production paths are unchanged from the V4 measurements. Baseline source is commit `c5be85730b9b51312d331473c8e215c0e4e4efdc`; the recorded V4 controller was `45925ab480`, with the same production implementation apart from the documented semantics-preserving timezone-key typing extraction. Incoming mainline calculation-preparation changes were assessed by Astra and covered by a post-merge real read/edit smoke.

The operator assigned architectural rulings and coding to Astra. This audit records its accepted implementation and independent LIFECYCLE owner review. No public or persisted schema, tax logic, authority source, admission/CAS rule or GC policy is changed.

## Findings

### s01-contract-review | low | PASS for the bounded source unit

LIFECYCLE's final code-contract review confirms all eight working files match the v5 hashes, all new source and test functions are below C, and the four remaining test C/D functions predate this unit. It found no unresolved production defects. The owner reviews and dispositions are retained in `X:/code/cadrumo/.tmp/2026-11-11-prime/status/OPTIMIZATION-inbox.md`. Earlier complexity findings in the recursive visitor and two new tests were resolved through handler/test splits; no suppression was added.

The cache is one session-owned entry in `src/cadrumo/application/workbench_capture_memory.py`, populated from `src/cadrumo/application/modelo/workbench_projection_memory.py` and used by `workbench_projection.py` through the production operation composition. It accepts only the declared immutable graph and exact context/value/schema identity. Unsupported, mutable, custom and subclass shapes remain eager. Verification fact maps are admitted only for their exact owner whose validator copies the backing dictionary. Fixed-offset Pydantic timezones are admitted only as the verified immutable exact type. Different same-ISO timezone types and identities do not share a key.

### s01-proof-boundary | low | Strict form restoration is proved on fill and reused on exact hits

A miss constructs and strictly restores the form pair through the original path. A hit reuses that exact previously validated immutable inverse; it does not rerun form-subtree JSON restoration or child validation. Fresh admission, baseline issue/expiry/actions and fresh read/outer/derived semantic comparison still run on every read. The final source timing observer requires actual steady project/restore counts of zero and outer comparison count one; eager counts are one/one/one. Refused admission and build errors are not cached. Schema rebuild, exact typed value, decimal scale, context and real edit changes invalidate reuse. A deferred-schema transition may cause one safe extra miss rather than using a pre-build schema identity.

### s01-private-retention | medium | Resolved by precise retention contract and teardown proof

The module documentation now explicitly states that authenticated-session memory retains decrypted derived taxpayer values in public/canonical form graphs and a second value copy in the key. It does not claim that no decrypted data is retained. Raw decrypted catalogues, baselines, actions, receipt envelopes and refusals are not stored by this memo; no plaintext persistence or encryption change is introduced. Close, lock, lapse, handover, profile switch and drain clear the existing owner, and a late fill cannot reopen a closed slot. The real owner tests cover those boundaries.

### s01-corrupt-entry | medium | Resolved by eviction without weakening the current refusal

A cached canonical mismatch clears its entry and propagates the original mismatch on that read. A subsequent read rebuilds through the strict path. It does not silently retry a weaker path or keep an entry that repeatedly fails. Direct corruption, post-close clearing and next-read rebuild are tested.

### s01-behavior-and-timing | low | Real five-state parity and material warm savings are proven in source

V4's registered-read harness passed all five states: calculated, verified, exported, filed locally and receipt verified. Complete eager/reuse outputs compare equal after removing only baseline identifier, issue time and expiry time. Every steady candidate proves real reuse and the outer comparison. The passing test is recorded under `.tmp/logs/test-runs/2026-11-15/20261115T160433.390519Z-pytest-52884-77e29f41/`. Final nine affected tests and post-merge read/restore and reuse/edit-invalidation smoke passed under `20261115T164507.232548Z-pytest-12004-7a42678d`; earlier scoped and neighboring coverage passed 204 tests, followed by the recorded 35/36 changed-part checks.

V4 eager-to-reuse median wall seconds are 3.955 to 2.586, 4.544 to 3.428, 4.232 to 3.613, 3.620 to 3.199 and 3.178 to 2.589. CPU improves in every state. There are two samples per arm/state on a loaded 24-CPU source cohort with saved authority EB5, not installed B18's DBDD cohort. Gains are 0.421 to 1.369 seconds; this does not prove every state saves half a second or a native target. Per-read CPU, system-busy, GC, cold and warm data are in `final-timing-summary.md` and `.json`. GC durations overlap wall/CPU. The isolated miss probe explicitly records about 0.243 seconds incremental fill cost after removing discarded eligibility token trees; that tradeoff is not hidden by warm figures.

### s01-integrated-checks | low | Verification evidence and unchanged global debt are kept distinct

All eight touched paths pass Ruff, format, ty and basedpyright. Configured complete baseline and candidate type audits both exit zero with byte-identical 113 advisory diagnostics: ty 30, pyrefly 13 and basedpyright 70, zero added/removed identities and no findings on the owned paths. The evidence is `gates/type-delta.json` and `.md`. The changed-path year/production complexity delta is zero added and zero removed. All nine import-census tests pass. Generator output adds only the new module entry in the aggregate and cadrumo partition JSON files and is handed as a generator-only companion commit.

The first import gate invocation was an invalid operational result because the orchestrator omitted the virtualenv scripts directory from PATH. It is retained as a failed invocation, never counted as a contract pass. Corrected final baseline/candidate gates have authoritative stable source graphs, keep all 31 contracts with zero broken, and load 6018/6018 and 6019/6019 modules with zero failures. Global gates remain red on existing hard findings and ratchet occurrences; no suppression or baseline edit is introduced. The final exact diagnostic-identity comparison is recorded in `gates/import-delta-final.json` and `.md`; this bounded audit requires no new unit findings, not a claim that repository-wide debt was fixed.

### s02-native-followup | low | Native performance and persona post-landing proof remain open

The installed B18 baseline and exact-symbol CPython GC evidence identify the original repeated allocation cost, but B18 does not contain this change. Source measurements cannot establish installed end-to-end improvement. S02 remains open for ACCEPTANCE same-authority persona equality and DESKTOP rebuilt matched native timings. No native latency goal or full plan completion is asserted here.

## Recommendations

Hand S01 source plus its generator-only companion to INTEGRATOR as one isolated unit once the recorded final import identity comparison, owner PASS and vault checks are complete. Keep all evidence qualifications in the hand. Retain S02 open and continue optimization under Astra's technical ownership; do not substitute a session-manager design approval for the operator's authorization.
