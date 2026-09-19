---
tags:
  - '#plan'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:9ac3f58ba47d2517feafd0a4a77ab89b158dcd1e6175076d2b088a15ee7a587e'
tier: L2
related:
  - '[[2026-07-17-mcp-call-latency-adr]]'
  - '[[2026-07-17-mcp-call-latency-research]]'
---

# `mcp-call-latency` plan

### Phase `P01` - Persistent validation-verdict cache (D1)

Persist a fingerprint-keyed validation verdict so a green tree skips runtime re-validation, stamp the verdict into the release wheel, and stop full-validating on modelo list.

- [x] `P01.S01` - Add a validation-verdict record keyed by the complete registry-tree, convenio, and source-evidence fingerprint tuples plus package version and outcome, with load, store, and delete-on-mismatch helpers using real filesystem behavior; `src/cadrumo/domain/calculations/registry/_validate_verdict.py`.
- [x] `P01.S02` - Read the verdict at authority load so a fingerprint match constructs with validation marked done and skips validate_registry, persist a fresh verdict after a green validate_registry, and delete the verdict then re-validate on any mismatch; `src/cadrumo/domain/calculations/registry/_authority.py`.
- [x] `P01.S03` - Stamp the bundled-tree verdict into the release build so the first end-user touch skips runtime validation, keyed by the same fingerprint tuples; `packaging/cadrumo_data_official/hatch_build.py`.
- [x] `P01.S04` - Pin the regression contract with real-behavior tests proving authority-boundary validation performs exactly one corpus-cache write, a direct RegistryValidator call performs zero, a verdict-cache hit skips validation including modelo list, and a fingerprint mismatch re-validates; `src/cadrumo/domain/calculations/registry/tests/test_validation_verdict_cache.py`.

### Phase `P02` - Shipped corpus text (D2)

Extract the manual-PDF corpus text once at release build time, ship it content-keyed with the release, and remove end-user PDF extraction.

- [x] `P02.S05` - Extract the eleven bundled AEAT manual PDFs to normalised text once at build time and commit content-keyed sidecars hashed on source bytes, extending the existing extraction-sidecar pipeline; `dev/docs/preprocess/_html.py`.
- [x] `P02.S06` - Read the shipped content-keyed manual text at runtime and remove the end-user pypdfium2 extraction so no install runs PDF text extraction; `src/cadrumo/domain/calculations/registry/_validate_evidence.py`.
- [x] `P02.S07` - Prove with a real-behavior negative test that a content-key mismatch between shipped text and source bytes refuses or recomputes rather than serving stale text; `src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py`.

### Phase `P03` - Compiled-registry cache (D3)

Persist the compiled ModeloDefinition set fingerprint-keyed so warm processes skip the TOML parse, strict-validated on load and deleted on any mismatch.

- [x] `P03.S08` - Add a compiled ModeloDefinition-set cache keyed by the registry-tree fingerprint, strict-validated on deserialisation and deleted on any mismatch or deserialisation failure, exercised against the real bundled tree; `src/cadrumo/domain/calculations/registry/_compiled_cache.py`.
- [x] `P03.S09` - Load the compiled cache when the tree fingerprint matches so warm processes skip the TOML parse, and write the cache after a fresh compile, wired through the loader; `src/cadrumo/domain/calculations/registry/_loader.py`.
- [x] `P03.S10` - Prove with a real-behavior test that mutating the compiled cache on disk makes strict load refuse and rebuild from TOML, so the cache is never a second authority; `src/cadrumo/domain/calculations/registry/tests/test_compiled_registry_cache.py`.

### Phase `P04` - Warm in-process MCP serving (D4)

Serve MCP tool calls through one warm in-process runtime with a concurrency cap and pre-provisioned launch, preserving byte-identical envelopes and idle-lock custody.

- [x] `P04.S11` - Add an in-process verb dispatch path that runs the already-importable per-verb command functions and envelope builders in one warm runtime instead of spawning a fresh aeat subprocess; `src/cadrumo/entrypoints/mcp/_inprocess.py`.
- [x] `P04.S12` - Route both the direct per-verb call and the meta-execute call through the warm in-process runtime while keeping the shared off-loop progress wrapper and the per-tier timeout ceilings; `src/cadrumo/entrypoints/mcp/_server.py`.
- [x] `P04.S13` - Replace the unbounded anyio thread-pool spawn with an explicit concurrency cap or request queue bounding concurrent in-process calls; `src/cadrumo/entrypoints/mcp/_call_runtime.py`.
- [x] `P04.S14` - Hold the warm runtime's decrypted bucket-session state under the existing idle-lock custody rules and restart a crashed runtime cleanly with no torn persisted state; `src/cadrumo/entrypoints/mcp/_server.py`.
- [x] `P04.S15` - Pre-provision the MCPB environment once and launch the interpreter directly thereafter, removing the per-session uv run resolution from the manifest launch; `packaging/mcpb/build.py`.
- [x] `P04.S16` - Prove CLI-versus-MCP envelope parity with a real-behavior oracle asserting byte-identical envelopes across the subprocess and in-process transports so D4 does not fork result shapes; `src/cadrumo/entrypoints/mcp/tests/test_inprocess_envelope_parity.py`.
- [x] `P04.S17` - Extend the loop-responsiveness regression to cover the warm path plus a custody test proving idle-lock relock and clean crash restart; `src/cadrumo/entrypoints/mcp/tests/test_server_loop_responsiveness.py`.

### Phase `P05` - Measurement and closure

Re-run the empirical benchmark table as acceptance thresholds, re-run installed oracles, and record exec closure.

- [x] `P05.S18` - Add a durable serving-path benchmark driver that measures the research call table against isolated encrypted state and asserts the projected end-state thresholds as acceptance gates, warm calculate at or under three seconds subprocess and one point five seconds server with reads and simple writes sub-second in server mode; `dev/packaging/serving_path_benchmark.py`.
- [x] `P05.S19` - Re-run the installed tax and MCP oracles after D1 through D4 land and capture the corrected warm serving behavior as installed evidence; `dev/packaging/installed_mcp_oracle.py`.
- [x] `P05.S20` - Rebuild the release cohort so the v0.2.1 train re-runs installed-behavior evidence against the new caches and warm serving; `dev/packaging/release_cohort.py`.

## Description

This plan implements the four serving-path latency decisions the ADR ruled on
(D1 through D4), grounded in the forensics decomposition that timed every second
of a warm `modelo work calculate` and named the first-touch 49.6 s cliff that
breached Claude Desktop's request timeout. The two already-landed remedies (the
batched corpus-cache flush and the C-accelerated locale loader) are out of scope
here; this plan lands the remaining removable waste: runtime re-validation of an
immutable bundled registry (D1), end-user PDF text extraction (D2), the warm TOML
parse (D3), and the per-call subprocess spawn on the agent-facing MCP surface (D4).

Each cache introduced here keys on the complete registry-tree fingerprint the
loader already computes, is derived and rebuildable, and is deleted-not-migrated
on any mismatch. The framing D1 makes explicit is that the build and continuous
integration are the validation gate and runtime asserts fingerprint identity; the
mandatory regression pin from the research (authority-boundary validation performs
exactly one corpus-cache write, a direct `RegistryValidator` call performs zero, a
verdict-cache hit skips validation, a fingerprint mismatch re-validates) locks that
inversion. D4 moves only the MCP transport to warm in-process serving; the human
CLI keeps its one-shot process model, envelope parity may not fork between
transports, and the warm runtime honours the bucket-session idle-lock custody
model for held key material. P05 re-runs the research's projected end-state table
as acceptance thresholds and re-runs the installed oracles as evidence. Every Step
demands real-behavior tests with no mocks, stubs, skips, or tautological
assertions.

## Steps

## Parallelization

P01, P02, and P03 are independent registry-layer phases that may run in parallel:
each adds a distinct fingerprint-keyed cache or build artifact and they share no
hard code dependency, though all three touch the loader/authority module family,
so their landing agents must serialise commits per the shared-worktree discipline
(check `git log --grep` and `git diff -- <file>` before editing a shared file).
Within each phase the code Step precedes its regression Step. P04 depends on
nothing in P01 through P03 for correctness (warm serving is a transport change),
but its measured benefit compounds with them, so schedule P04 alongside the
registry phases. P05 is a hard gate that runs last: the benchmark and installed
oracles can only assert the projected end-state once D1 through D4 have landed.

Suggested agent personas: the registry-cache code Steps (`P01.S01`, `P01.S02`,
`P03.S08`, `P03.S09`) and the warm-serving core Steps (`P04.S11`, `P04.S12`,
`P04.S13`, `P04.S14`) are core-logic work for `vaultspec-high-executor`. The
build-surface Steps (`P01.S03`, `P02.S05`, `P04.S15`) and the corpus-consumer
switch (`P02.S06`) are well-defined pattern work for `vaultspec-standard-executor`.
The regression and oracle Steps (`P01.S04`, `P02.S07`, `P03.S10`, `P04.S16`,
`P04.S17`, `P05.S18`, `P05.S19`, `P05.S20`) suit `vaultspec-standard-executor`
with a `vaultspec-code-reviewer` pass on the D1 skip-inversion and the D4 custody
Steps.

## Verification

The plan is complete when every Step is closed with a matching execution record
and the following checks hold:

- The D1 regression pin passes: authority-boundary validation performs exactly one
  corpus-cache write, a direct `RegistryValidator` call performs zero, a
  verdict-cache hit provably skips `validate_registry` (including on `modelo list`),
  and a fingerprint mismatch provably re-validates and rewrites the verdict.
- No end-user code path runs pypdfium2 PDF text extraction: the shipped
  content-keyed manual text is read at runtime, and a content-key mismatch refuses
  or recomputes rather than serving stale text (D2 negative test green).
- The compiled-registry cache loads only on a fingerprint match, is strict-validated
  on deserialisation, and a mutated on-disk cache is refused and rebuilt from TOML
  (D3 never-a-second-authority test green).
- CLI-versus-MCP envelope parity holds byte-for-byte across the subprocess and
  in-process transports (installed parity oracle green); the loop-responsiveness
  regression covers the warm path; and the warm runtime relocks under idle-lock
  custody and restarts cleanly after a crash with no torn persisted state.
- The serving-path benchmark meets the projected end-state thresholds: warm
  calculate at or under three seconds in subprocess mode and at or under one and a
  half seconds in server mode, with all reads and simple writes sub-second in
  server mode; the installed tax and MCP oracles re-run green and the rebuilt
  release cohort re-runs its installed-behavior evidence.
- Every new test exercises real behavior (real filesystem, real registry, real
  storage/crypto) with no mocks, stubs, skips, xfail, or tautological assertions.

For tier-specific verification cadence, see the authorizing documents linked in the
`related:` frontmatter.
