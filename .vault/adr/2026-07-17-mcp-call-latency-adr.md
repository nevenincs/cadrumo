---
tags:
  - '#adr'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-mcp-call-latency-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `mcp-call-latency` adr: `Serving-path latency architecture` | (**status:** `accepted`)

## Problem Statement

Local CLI and MCP operations breach the interactive-grade bar the operator set:
sub-second reads and simple writes, low single-digit seconds for the heaviest
calculation. Measured against the installed v0.2.1 cohort, a warm `modelo work
calculate` cost 11.6 seconds, a warm `modelo list` 5.4 seconds, and the first
`modelo work create` on a fresh state root 49.6 seconds — the call that
breached Claude Desktop's 60-second request timeout in the real client
acceptance run. Every MCP tool call spawns a fresh `aeat` subprocess, so every
per-process cost is a per-call cost. The forensics research decomposed every
second; two fixes (the batched corpus-text cache flush and the C-accelerated
locale loader) already landed. This decision rules on the four remaining
remedies.

## Considerations

The grounding research measured: full-registry validation runs unconditionally
in every registry-touching process (3.7 seconds warm, up to 41 seconds cold)
although the bundled registry is immutable per release and continuous
integration already proves it green; text extraction of the 11 bundled AEAT
manual PDFs happens on the end-user machine (18.2 seconds, first touch per
storage root); the 17,276-file TOML parse and stat-based fingerprint walk cost
0.4-8.8 seconds per process; the application-layer import floor (pydantic
class construction) is 1.2-1.5 seconds per process; storage and cryptography
are not bottlenecks (~0.3 seconds). Subprocess dispatch therefore has a hard
floor above one second regardless of caching.

## Considered options

Per the research: R1 persistent validation-verdict cache (per-storage-root
variant and ship-the-verdict-in-the-wheel variant); R3 build-time corpus-text
extraction shipped with the release; R5 compiled-registry cache; R6 warm
in-process MCP serving replacing the per-call subprocess. The alternative of
weakening or trimming validation content was not considered an option: the
validation corpus is the legal-grounding gate and its coverage is
non-negotiable — only WHERE it runs is decided here.

## Decision

- **D1 (R1, both variants):** a green `validate_registry` persists a verdict
  record — the fingerprint-tuple hash the loader already computes (complete
  registry tree, directory-mode manifests, revision fragments, source-evidence
  set), the package version, and the outcome. On fingerprint match the
  authority constructs with validation marked done. The release build stamps
  the verdict for the bundled tree into the wheel so the very first touch on
  an end-user machine skips runtime validation; per-storage-root verdicts
  cover development trees. This is an explicit inversion: the build and
  continuous integration are the validation gate; runtime asserts fingerprint
  identity. A mismatch deletes the verdict and re-validates in full.
- **D2 (R3):** the release build extracts and normalises the manual-PDF corpus
  text once and ships it content-keyed (hash of source bytes, not size/mtime)
  with the release artifacts. End-user machines never run PDF text extraction.
- **D3 (R5):** the compiled `ModeloDefinition` set persists as a
  fingerprint-keyed cache so warm processes skip the TOML parse. The cache is
  derived and rebuildable, strict-validated on load, and deleted on any
  mismatch or deserialisation failure — it is a shortcut to the same compiled
  authority, never a second authority and never migrated across shapes.
- **D4 (R6):** the MCP server stops spawning a fresh `aeat` subprocess per
  tool call and serves verbs through one warm in-process runtime that
  preserves the JSON envelope contract byte-for-byte, with an explicit
  concurrency cap replacing the unbounded thread-pool spawn, honouring the
  bucket-session idle-lock custody model for held key material, and retaining
  the per-call timeout tiers. The MCPB bundle pre-provisions its environment
  once and launches the interpreter directly thereafter, removing the per-
  session `uv run` resolution. The human CLI keeps its one-shot process model.

## Constraints

- Cache invalidation keys on the complete tree fingerprint per the registry
  authority-flow rule; no path-only or version-only keys.
- Every cache introduced here is derived and rebuildable: on mismatch, delete
  and recompute — no migration, no version bridge, no read-tolerance of old
  cache shapes (no-legacy-compatibility governs).
- The regression pin from the research is mandatory: authority-boundary
  validation performs exactly one corpus-cache write, a direct
  `RegistryValidator` call performs zero, and a verdict-cache hit provably
  skips validation while a fingerprint mismatch provably re-validates.
- CLI-versus-MCP envelope parity remains gated by the existing installed
  oracles; D4 may not fork result shapes between transports.
- The warm worker holds decrypted bucket session state and must follow the
  existing idle-lock custody rules; a crashed worker restarts cleanly with no
  torn persisted state (single-writer contracts unchanged).

## Implementation

Layered: D2 and D1's build stamp land in the release-cohort build (the
packaging surface already assembles the data wheels and manifest); the runtime
verdict/compiled caches land in the registry loader/authority behind the
existing fingerprint computation; D4 restructures only the MCP server's
dispatch layer — the per-verb command functions, gates, telemetry, and
envelope builders are already importable in-process. The distribution
campaign's installed oracles re-measure the projected end-state table (reads
and simple writes sub-second in server mode, heaviest calculation ~1.5
seconds) as acceptance evidence.

## Rationale

The research shows the serving path re-proves, per call, facts that are
immutable per release and already proven at build time — the definition of
removable waste. Each cache reuses the exact invalidation key the loader
already computes, so correctness reduces to fingerprint identity, which the
authority-flow rule already mandates. Subprocess dispatch cannot meet the bar
(interpreter plus import floor), so the MCP surface — the latency-critical,
agent-facing transport — moves to warm serving while the CLI, whose contract
is one deterministic process per human command, stays unchanged.

## Consequences

The performance work invalidates any previously built cohort: R2/R4 landed
already and D1-D4 land as product changes, so the v0.2.1 release train must
rebuild its cohort and re-run installed-behavior evidence after this feature
lands (the readiness gate enforces that automatically). The Claude
Desktop/Cowork client rows should re-run only after D4 so their evidence
captures the corrected serving behavior. Runtime no longer re-validates an
unchanged bundled registry; a corrupted install that also preserves the
stamped fingerprint would go undetected at runtime, which is accepted because
package-manager digest verification and the distribution evidence chain
already own byte integrity. Projected end-state per the research: warm
calculate ~1.5 s in server mode, all reads and simple writes sub-second.
