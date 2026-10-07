---
tags:
  - '#audit'
  - '#modelo-runtime-performance'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:0526cc2e1299932adf02c11f2143718ed9394b9741f1ace9b8899864701a4981'
related:
  - "[[2026-10-07-modelo-runtime-performance-plan]]"
  - "[[2026-10-07-blocking-code-quality-repair-audit]]"
---

# `modelo-runtime-performance` audit: `Modelo runtime latency and completion review`

## Scope

Measure and repair shared production startup, calculation-catalogue load/validation and export work on the real native Modelo100 route. Review base is `f0be8532f5` plus the existing dirty peer tree. The approved plan records disjoint ownership and invariant coverage; no persisted schema or protocol change is authorized. Old diagnostics are historical evidence, not current-tree timing.

## Findings

### m100-baseline-completion-margin | high | Current real fixture takes nearly the full 300-second deadline

The canonical current-tree three-test run passed at baseline, but shared fixture setup took 292.95 seconds and total pytest time was 300.37 seconds. Command: `uv run --no-sync pytest -n 0 --basetemp=.tmp/pytest-m100-performance-baseline -m 'unit or integration' dev/docs/tests/test_sequence_goldens.py::TestModeloExportReleaseMaskHonesty --tb=short`. Log: `var/storage/development/.logs/test-runs/2026-10-07/20261007T104323.727426Z-pytest-60344-f0c9a8f6/run.log`. The fixture executes two real Modelo100 startup/authentication/calculate/export sequences for release-mask assertions. A pass only seven seconds below the per-item setup timeout is not adequate completion or production-latency evidence. Previous canonical and isolated runs timed out during real export response waits; one bounded instrumented run lost the runtime connection after durable calculation. No separate single-model-load timeout was measured. S01 must attribute current full catalogue/registry work before S02/S03 fixes; final closure requires measured reduction and genuine complete native-route passes.

### m100-current-phase-attribution | high | Repeated full encrypted catalogue validation dominates the measured native route

Fresh current-fixture instrumentation completed one genuine five-frame M100 sequence on `b3c3ea62fc94f15b43b77b8856463b6c43869896` plus preserved peer edits. Frame walls were profile edit 15.35 s, work creation 13.24 s, calculation 27.87 s, verification 55.54 s and export 46.17 s; complete sequence 170.73 s, process-tree CPU 155.88 s (parent 19.00 s, descendants 136.88 s). The worker performed 24 calculation catalogue loads plus four revisioned loads (three empty), taking 74.16 s cumulatively. Twenty-five full encrypted Envelope decodes, each about 14.87 MB, took 72.76 s; nested RegistrySnapshot decode took 19.77 s within that total, not in addition. The first decode was cProfiled and inflated to 5.35 s versus ordinary decodes around 2.8–3.0 s; final normal timing must be unprofiled. Parent and native worker each built 266 registered definitions with 1,266 strict-schema calls; their two registry builds totaled 8.87 s. Actual calculation and export bodies took 8.97 s and 11.38 s; frame costs also include admission, guarded currentness and private result disclosure. Evidence: `.tmp/modelo-runtime-profile-current-3` safe metric files and `.tmp/modelo-performance-probe-3.txt`; copied native worker was confirmed retired by its fixture owner. A prior copied-probe indentation error failed before child metrics and is discarded as instrumentation failure, not a new production defect.

### schema-generation-repair | low | Exact operation contracts are retained with a measured faster naming path

S02 adds a collision-free Pydantic definition-remapping fast path and delegates ambiguous names to the original algorithm. Both schema modes and all strict/frozen/closed checks still run; decorated model methods, live model graph/config/metadata/core rebuild checks and build-scoped memo lifetime remain authoritative. In matched alternating production builds, median wall time fell from 3.151 s to 2.484 s and CPU from 3.109 s to 2.438 s. All 481 real closed schemas, 266 definitions and canonical validated public digests are identical. The 297 focused cases and three configured focused type engines plus Ruff/format passed on stable source; exact commands and log are `.tmp/perf-s02-schema-evidence.txt` and `var/storage/development/.logs/test-runs/2026-10-07/20261007T111711.080535Z-pytest-49756-c27374b1/run.log`. The protected Pydantic remapping extension is a bounded implementation coupling; durable default-generator parity, naming collision and mode/recursive/generic/alias/decoration cases cover dependency upgrades. No private type import, suppression, mutable/global schema cache, dependency or public identity change is added. The earlier public paired-generation candidate was slower and was discarded. Whole native-route and aggregate verification remain S04.

### complete-registry-serialization-repair | low | Full saved registry JSON retains parity with less Python traversal

S03 replaces recursive Python JSON projection with an isolated copied-core-schema serializer. It retains every persisted registry field, preserves authored predecessor serialization, ignores presentation-only model serializers exactly as the previous traversal did, and leaves Python-mode behavior unchanged. There is no shared snapshot cache or input schema mutation. Thirty full saved-rendering and repository round-trip tests passed, including exact 100/303/131/720 bytes and digests, computed/excluded/alias/prebuilt-serializer cases and existing refusal coverage. Focused Ruff/format/ty/pyrefly/basedpyright checks passed. Production alternating median catalogue load fell from 2.147 s to 1.600 s; revisioned load from 1.917 s to 1.702 s. Profiled full M100 load fell from 2.972 s to 1.553 s; Python projection from 1.527 s to 0.228 s, removing 453,979 Python visits. Profiling and normal timings are separate evidence. The existing independently declared pydantic-core>=2.46 floor supports the serializer flag; the actual floor was verified without changing dependencies. Evidence: .tmp/s03-runtime-performance-manifest.json and .tmp/s03-runtime-performance.patch; pytest log var/storage/development/.logs/test-runs/2026-10-07/20261007T111740.282034Z-pytest-61148-cec89111/run.log.

### canonical-completion-still-unresolved | high | Faster one-run evidence does not establish double-run completion

The ordinary unchanged 300-second canonical after run still timed out during verification reply wait in the shared double-run fixture. Command and stack are .tmp/m100-performance-after.txt; durable log var/storage/development/.logs/test-runs/2026-10-07/20261007T112521.912299Z-pytest-5328-e2966a37/run.log. Original retained metadata cannot identify which iteration was waiting. A subsequent unprofiled promoted native benchmark completed one full M100 journey in 128.59 s with process-tree CPU 123.19 s: profile edit 14.80 s, work creation 10.37 s, calculation 25.39 s, verification 37.42 s and export 34.74 s. Worker schema-call snapshots show only 1,277 calls and 2.59 s cumulatively; compilation is no longer a dominant repeated cost. Both fixture and benchmark preserve normal settings and native custody; benchmark preimports some production modules before its whole-sequence clock, and pytest collection has distinct GC/authority pinning. These are source-supported context differences, not measured causes. Exact canonical per-iteration observation is required before completion closure. Evidence .tmp/modelo-runtime-after-current; no timer increase, skip or validation bypass.

## Recommendations

Profile fixed safe phase names, wall/CPU time and repetition counts. Preserve exact schema identities, snapshot/evidence/digest and generation/currentness validation, encrypted custody and runtime authority. Optimize measured duplicate work within settled owners; do not lengthen timers or remove validation to hide the failure. Final review is pending implementation and before/after evidence.

## Context

The user explicitly expanded authorization from static quality repair to production performance on 2026-10-07. The previous blocking-quality audit remains historical; its accepted unverified-fixture limit does not satisfy this performance plan. Existing peer runtime and desktop work is preserved. RAG service is unavailable, with semantic vault search still usable and known code ownership confirmed through exact source reads.
