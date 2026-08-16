---
generated: true
tags:
  - '#index'
  - '#mcp-call-latency'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:1663e3b90c513204d0c5baa68a61ca3740595206722f3585079a8f29a3922eda'
related:
  - '[[2026-07-17-mcp-call-latency-P01-S01]]'
  - '[[2026-07-17-mcp-call-latency-P01-S02]]'
  - '[[2026-07-17-mcp-call-latency-P01-S03]]'
  - '[[2026-07-17-mcp-call-latency-P01-S04]]'
  - '[[2026-07-17-mcp-call-latency-P02-S05]]'
  - '[[2026-07-17-mcp-call-latency-P02-S06]]'
  - '[[2026-07-17-mcp-call-latency-P02-S07]]'
  - '[[2026-07-17-mcp-call-latency-P03-S08]]'
  - '[[2026-07-17-mcp-call-latency-P03-S09]]'
  - '[[2026-07-17-mcp-call-latency-P03-S10]]'
  - '[[2026-07-17-mcp-call-latency-P04-S11]]'
  - '[[2026-07-17-mcp-call-latency-P04-S12]]'
  - '[[2026-07-17-mcp-call-latency-P04-S13]]'
  - '[[2026-07-17-mcp-call-latency-P04-S14]]'
  - '[[2026-07-17-mcp-call-latency-P04-S15]]'
  - '[[2026-07-17-mcp-call-latency-P04-S16]]'
  - '[[2026-07-17-mcp-call-latency-P04-S17]]'
  - '[[2026-07-17-mcp-call-latency-P05-S18]]'
  - '[[2026-07-17-mcp-call-latency-P05-S19]]'
  - '[[2026-07-17-mcp-call-latency-P05-S20]]'
  - '[[2026-07-17-mcp-call-latency-adr]]'
  - '[[2026-07-17-mcp-call-latency-plan]]'
  - '[[2026-07-17-mcp-call-latency-research]]'
---

# `mcp-call-latency` feature index

Auto-generated index of all documents tagged with `#mcp-call-latency`.

## Documents

### adr

- `2026-07-17-mcp-call-latency-adr` - `mcp-call-latency` adr: `Serving-path latency architecture` | (**status:** `accepted`)

### exec

- `2026-07-17-mcp-call-latency-P01-S01` - Add a validation-verdict record keyed by the complete registry-tree, convenio, and source-evidence fingerprint tuples plus package version and outcome, with load, store, and delete-on-mismatch helpers using real filesystem behavior
- `2026-07-17-mcp-call-latency-P01-S02` - Read the verdict at authority load so a fingerprint match constructs with validation marked done and skips validate_registry, persist a fresh verdict after a green validate_registry, and delete the verdict then re-validate on any mismatch
- `2026-07-17-mcp-call-latency-P01-S03` - Stamp the bundled-tree verdict into the release build so the first end-user touch skips runtime validation, keyed by the same fingerprint tuples
- `2026-07-17-mcp-call-latency-P01-S04` - Pin the regression contract with real-behavior tests proving authority-boundary validation performs exactly one corpus-cache write, a direct RegistryValidator call performs zero, a verdict-cache hit skips validation including modelo list, and a fingerprint mismatch re-validates
- `2026-07-17-mcp-call-latency-P02-S05` - Extract the eleven bundled AEAT manual PDFs to normalised text once at build time and commit content-keyed sidecars hashed on source bytes, extending the existing extraction-sidecar pipeline
- `2026-07-17-mcp-call-latency-P02-S06` - Read the shipped content-keyed manual text at runtime and remove the end-user pypdfium2 extraction so no install runs PDF text extraction
- `2026-07-17-mcp-call-latency-P02-S07` - Prove with a real-behavior negative test that a content-key mismatch between shipped text and source bytes refuses or recomputes rather than serving stale text
- `2026-07-17-mcp-call-latency-P03-S08` - Add a compiled ModeloDefinition-set cache keyed by the registry-tree fingerprint, strict-validated on deserialisation and deleted on any mismatch or deserialisation failure, exercised against the real bundled tree
- `2026-07-17-mcp-call-latency-P03-S09` - Load the compiled cache when the tree fingerprint matches so warm processes skip the TOML parse, and write the cache after a fresh compile, wired through the loader
- `2026-07-17-mcp-call-latency-P03-S10` - Prove with a real-behavior test that mutating the compiled cache on disk makes strict load refuse and rebuild from TOML, so the cache is never a second authority
- `2026-07-17-mcp-call-latency-P04-S11` - Add an in-process verb dispatch path that runs the already-importable per-verb command functions and envelope builders in one warm runtime instead of spawning a fresh aeat subprocess
- `2026-07-17-mcp-call-latency-P04-S12` - Route both the direct per-verb call and the meta-execute call through the warm in-process runtime while keeping the shared off-loop progress wrapper and the per-tier timeout ceilings
- `2026-07-17-mcp-call-latency-P04-S13` - Replace the unbounded anyio thread-pool spawn with an explicit concurrency cap or request queue bounding concurrent in-process calls
- `2026-07-17-mcp-call-latency-P04-S14` - Hold the warm runtime's decrypted bucket-session state under the existing idle-lock custody rules and restart a crashed runtime cleanly with no torn persisted state
- `2026-07-17-mcp-call-latency-P04-S15` - Pre-provision the MCPB environment once and launch the interpreter directly thereafter, removing the per-session uv run resolution from the manifest launch
- `2026-07-17-mcp-call-latency-P04-S16` - Prove CLI-versus-MCP envelope parity with a real-behavior oracle asserting byte-identical envelopes across the subprocess and in-process transports so D4 does not fork result shapes
- `2026-07-17-mcp-call-latency-P04-S17` - Extend the loop-responsiveness regression to cover the warm path plus a custody test proving idle-lock relock and clean crash restart
- `2026-07-17-mcp-call-latency-P05-S18` - Add a durable serving-path benchmark driver that measures the research call table against isolated encrypted state and asserts the projected end-state thresholds as acceptance gates, warm calculate at or under three seconds subprocess and one point five seconds server with reads and simple writes sub-second in server mode
- `2026-07-17-mcp-call-latency-P05-S19` - Re-run the installed tax and MCP oracles after D1 through D4 land and capture the corrected warm serving behavior as installed evidence
- `2026-07-17-mcp-call-latency-P05-S20` - Rebuild the release cohort so the v0.2.1 train re-runs installed-behavior evidence against the new caches and warm serving

### plan

- `2026-07-17-mcp-call-latency-plan` - `mcp-call-latency` plan

### research

- `2026-07-17-mcp-call-latency-research` - `mcp-call-latency` research: `Serving-path latency architecture`
