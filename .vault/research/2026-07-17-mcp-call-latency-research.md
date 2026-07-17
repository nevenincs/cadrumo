---
tags:
  - '#research'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-17-mcp-service-robustness-research]]'
---



# `mcp-call-latency` research: `Serving-path latency architecture`

Empirical forensics of why local CLI/MCP calls breach the operator's
interactive-grade bar (sub-second reads and simple writes, low single-digit
seconds for the heaviest calculation). Every MCP tool call spawns a fresh
`aeat` subprocess (robustness research F2), so per-process costs are per-call
costs; the first-touch `modelo work create` on a fresh state root breached
Claude Desktop's 60-second request timeout. This document records the measured
decomposition against the installed v0.2.1 cohort, the two fixes already
landed and re-verified (R2 batched corpus-cache flush, R4 C-accelerated locale
loading), and the four remaining remedies as options with trade-offs for the
Architecture Decision Record (ADR) to rule on. All measurement scripts,
`cProfile` dumps, `importtime` logs, and state roots are retained under
`var/perf-forensics/` in the factory worktree.

## Findings

### Measured baseline (installed v0.2.1 cohort, per-subprocess, isolated state)

Cohort executable: `var/packaging-smoke/core-20260717T094351Z/venv/Scripts/aeat.exe`;
driver `var/perf-forensics/repro_first_touch.py`.

| call | pre-fix | notes |
| --- | --- | --- |
| `aeat --version` | 1.09 s (1.96 s cold FS) | interpreter + CLI import only |
| `config profile create` | 4.41 s | no registry touch |
| `modelo work create`, first touch on fresh state root | 49.64 s | the Desktop-timeout breach |
| `modelo work create`, warm | 10.79 s | |
| `modelo work calculate`, warm | 11.59 s | |
| `modelo list`, warm | 5.4 s | validates all 73 modelos to list names |

### The first-touch cliff, named

`cProfile` of the first `work create`
(`var/perf-forensics/workcreate-first-prof1.prof`, 55.8 s instrumented):
`_load_authority` 48.98 s cumulative, of which `validate_registry` 41.21 s —
the authority loader (`src/cadrumo/domain/calculations/registry/_authority.py`)
validates the full registry unconditionally inside its in-process
`lru_cache`d constructor. Inside validation, `validate_source_citations` ran
2,027 times (36.29 s) and decomposed into:

- `_extract_pdf_text_impl` 16.5 s: `pypdfium2` text-extracts 11 bundled AEAT
  manual PDFs (10,933 `get_textpage` calls) on the end-user machine, deriving
  searchable text that is identical for every install of a given release.
- `_write_disk_cache` 15.2 s: the per-miss whole-file JSON rewrite loop
  (56 rewrites of a file growing to 31,093,390 bytes) — fixed by R2.
- Cold-filesystem TOML parse of the 17,276-file registry tree: 5.4–8.8 s
  (drops to ~0.4 s with a warm OS file cache).

Why first-touch only: the derived corpus text persists to
`<storage_root>/cache/corpus-text/cadrumo_corpus_text_cache.json`, keyed per
storage root — so every new user, fresh profile root, and isolated CI or
smoke environment repays the full extraction.

### Post-fix verified state (R2 + R4, working tree)

Verified with runtime-wrapped counters, no production edits
(`var/perf-forensics/verify_r2.py`, `verify_r2_warm.py`,
`verify_r2_authority.py`; state roots `state-r2-verify`, `state-r2-authority`):

- Cold `validate_registry`, fresh cache dir: 37.79 s → 27.45 s
  (through the authority boundary after the flush relocation: exactly one
  `_write_disk_cache` call, 11 extractions, 56-key cache round-trips).
  Residual cold cost: 18.2 s PDF extraction + ~9.3 s validation proper.
- Warm-process registry cost: unchanged 3.7 s (two follow-on processes: zero
  writes, zero extractions, byte-identical cache file).
- R4 (`yaml.CSafeLoader` in `src/cadrumo/core/i18n/_render.py`): CLI package
  import module-body self time 413 ms → 52–82 ms; cumulative import 920 ms →
  ~660–750 ms median idle (`var/perf-forensics/importtime-checkout-cli-post-r4.txt`).
- Flush-relocation caveat: after the reviewability-driven move of
  `flush_corpus_text_cache()` to the authority boundary, a direct
  `RegistryValidator.validate_registry` caller accumulates dirty state
  without flushing. The authority is the only production entry today; a
  regression pin ("authority validation performs exactly one corpus-cache
  write; direct validator performs zero") would lock the contract.

### Warm `work calculate` budget (observed 11.6 s, sums to observation)

Profile `var/perf-forensics/calc-warm.prof`; uninstrumented cross-checks in
`var/perf-forensics/time_registry.py` output.

| component | seconds |
| --- | --- |
| exe + interpreter + CLI package import (pre-R4 incl. ~0.5 s locale YAML) | 1.1 |
| lazy `cli._modelo` → `application.modelo` import at dispatch (pydantic class construction, 923 models) | 3.4 |
| registry tree + source-evidence fingerprints (31k `nt.stat`, 12k `_getfinalpathname`) | 1.0 |
| `load_registry_tree` (warm FS; 5.4–8.8 s cold) | 0.4 |
| `validate_registry` warm (regex normalisation 0.9 s, semantic-role typo scan ~0.9 s, revision sections 1.2 s, cross-revision divergence ~0.5 s, corpus-cache load 0.2 s) | 3.7 |
| storage and crypto (keyring probe 0.18 s, Argon2id ×2 at 25 ms, engine 0.03 s, envelope decrypts sub-ms) | 0.3 |
| calculation engine + revision persistence + envelope emit | ~1.5 |

Storage/crypto is explicitly not a bottleneck: Argon2id (19 MiB, t=2, p=1)
costs 25 ms per derivation, AES-256-GCM ~2 µs per 4-KiB envelope, SQL engine
plus `create_all` under 30 ms. Key derivation is re-paid per process but the
whole stack is ~0.3 s.

### Redundancy fact for the ADR

The in-process authority cache (`lru_cache` on `_load_authority`) is keyed by
(root, source root, complete registry-tree fingerprint tuple, source-evidence
fingerprint tuple) — stat-based `(path, size, mtime_ns)` over 17,276 + 1,397
files, recomputed each process at ~0.9 s. Validation runs unconditionally on
every registry-touching process, including `modelo list`. A snapshot build
after validation costs 76–217 ms first, 0.0 ms cached. The bundled registry is
immutable per release and continuous integration already proves it validates
green — the runtime re-validation proves nothing new unless the tree changed,
which the fingerprints already detect.

## Options

The four remaining remedies. These are options with trade-offs, not
decisions; the ADR rules on them.

### Option R1 — persistent validation-verdict cache keyed by the fingerprint tuples

Persist a small verdict record (fingerprint-tuple hash, package version,
outcome) after a green `validate_registry`; on match, construct the authority
with validation marked done. Two variants:

- Per-storage-root verdict file (like the corpus-text cache): first process
  per root still pays validation once; every later process skips ~3.7 s warm
  or ~27 s cold.
- Ship-the-verdict-in-the-wheel: the release build stamps the verdict for the
  bundled tree at package-build time; a fingerprint match at runtime skips
  validation on the very first touch. Strongest variant; kills the remaining
  first-touch cost when combined with R3.

Trade-offs: moves a gate off the serving path — the honest framing is that
continuous integration and the build remain the gate and runtime asserts
fingerprint identity. The direct-validator flush caveat above must be covered
by the same regression pin. Cheap to invalidate correctly because the loader
already computes the exact key. Effort M; saves 3.7 s warm / up to 41 s cold
on every registry-touching call.

### Option R3 — ship precomputed corpus text

Extract the 11 manual PDFs at package-build time and bundle the normalised
text (content-keyed, e.g. hash of the source bytes rather than
size/mtime, so the key survives installation). Removes the 18.2 s
first-touch extraction from end-user machines entirely and shrinks install
variance. Independent of R1 but subsumed by R1's ship-the-verdict variant for
the validation path; still worthwhile because the corpus-text cache serves
any future consumer and keeps `validate_modelo` partial-validation paths
fast. Effort S/M.

### Option R5 — compiled-registry cache

Persist the compiled `ModeloDefinition` tuple (pickle or pydantic JSON) keyed
by the same tree fingerprint, so warm processes skip the 17,276-file TOML
parse (0.4 s warm FS, 5.4–8.8 s cold FS) and the fingerprint stat walk can
collapse into one `os.scandir` pass. Trade-offs: a derived artefact of
nontrivial shape — deserialisation must be strict-validated or the cache
becomes a second authority; pickle of pydantic models is version-fragile
across releases (acceptable: the cache is keyed and rebuildable, never
migrated). Effort M; saves 0.5–5 s per process plus part of the 1.0 s
fingerprint cost.

### Option R6 — persistent server / warm worker (the only route to sub-second)

Stop spawning a fresh `aeat` subprocess per MCP tool call: keep one warm
worker (or serve in-process in the MCP server) so interpreter start, the
~1.2–1.5 s pydantic-import floor, fingerprinting, and registry state are paid
once per session. In-process, a repeat snapshot is 0.0 ms and a warm
calculate is engine + persistence only (~0.3–1.5 s). Fold in the robustness
research findings: the F3 concurrency cap (no semaphore on subprocess spawn;
a warm-worker design needs an explicit request queue or cap) and the F4
launch cost (the MCPB manifest's `uv run` resolution on every session start;
a pre-provisioned environment with a direct interpreter launch removes it).
Trade-offs: process-lifetime state must respect the bucket-session
idle-lock/custody model (a long-lived worker holds decrypted key material
under the session idle rules); cache invalidation across a worktree edit is
already fingerprint-keyed; crash/restart supervision becomes part of the MCP
surface. Effort M/L. Without R6 the subprocess floor keeps reads at
~1.2–1.5 s; with it every read and simple write fits the sub-second bar.

## Constraints

- Registry cache invalidation MUST key on the complete tree fingerprint
  (registry authority-flow rule; directory-mode manifests and recursive
  revision fragments included). R1/R5 satisfy this by construction — they
  reuse the loader's existing fingerprint tuples. No path-only or
  version-only keys.
- No-legacy-compatibility: every cache here is derived and rebuildable —
  on any mismatch, delete and recompute; never migrate, version-bridge, or
  read-tolerate an old cache shape.
- CI-remains-the-gate framing for R1: runtime skipping of validation is
  sound only while the build/CI pipeline is the enforcement point for
  registry validity and the runtime check is fingerprint identity. The ADR
  should state this inversion explicitly.
- Secure-storage rules do not bind the registry caches (bundled public
  regulatory data, no taxpayer data), but R6's warm worker holds bucket
  session state and must honour the existing idle-lock custody model.
- The corpus-text and verdict caches live under the storage-root cache
  directory (settings-derived), never a shared OS temp dir.

## Projected end-state

With R1+R3+R5 (+ landed R2/R4) in subprocess mode, and R6 for server mode:

| call | today | post-fix subprocess | post-fix persistent server |
| --- | --- | --- | --- |
| `aeat --version` | 1.96 s | ~0.5 s | n/a |
| `config profile create` | 4.3 s | ~1.5 s | <0.5 s |
| `work create`, first touch fresh state | 49.6 s | ~2 s | <0.5 s |
| `work create`, warm | 10.8 s | ~1.7 s | <0.3 s |
| `work calculate`, warm | 11.6 s | ~3 s | ~1.5 s |
| `modelo list`, warm | 5.4 s | ~1.5 s | <0.3 s |

Subprocess mode cannot reach sub-second for anything but `--version`; the
floor is interpreter start plus the pydantic class construction in the
application-layer import. Meeting the operator's bar on reads and simple
writes requires R6; with it, the heaviest calculation sits at ~1.5 s.
