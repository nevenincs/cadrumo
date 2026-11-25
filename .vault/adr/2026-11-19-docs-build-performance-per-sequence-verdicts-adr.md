---
tags:
  - '#adr'
  - '#docs-build-performance'
date: '2026-11-19'
modified: '2026-11-19'
body_schema: 'body-v2'
body_hash: 'sha256:f7a06841b7c8184f009d95d84aaa3b02e0ccbee6a0f737c16c85c1fafbbcca40'
related:
  - "[[2026-09-24-docs-build-performance-adr]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
  - "[[2026-09-29-docs-build-workflow-adr]]"
  - '[[2026-09-24-docs-build-performance-research]]'
  - '[[2026-09-29-docs-build-workflow-audit]]'
---

# `docs-build-performance` adr: `Per-sequence cli-sequence verdicts keyed on the authority's logical generation` | (**status:** `proposed`)

## Problem Statement

The native `user_docs_verify` target re-executes every documented CLI sequence on each `verify-release` (about an hour), because it has no stamp and never consults the verdict cache. The cache itself held one whole-gate verdict, so any input change re-ran every sequence. It also keyed the authority on the descriptor's physical digest, and each fresh publication of the same source has a different digest. The operator asked that only sequences whose inputs diverged re-execute.

## Considerations

- D3 of `2026-09-24-docs-build-performance-adr` allows reuse of a proven identical verdict and requires that a hit print its origin and never turn a failure green.
- The `2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr` amendment says a verdict cache over rendered output keys on the descriptor's physical digest. The logical generation is the registry source identity (`dev/registry/compiler/authority_database.py:113`), and same-source publications differ in database bytes.
- Sequences run in-process through `CliRunner` with the runtime host on a thread. Profile workers run `dev/docs/sequences/runtime_fixture.py` as a script (`dev/docs/sequences/runner.py:600`, `dev/docs/sequences/runtime_fixture.py:257`).
- An audit-hook recorder of imported and read checkout files already exists for cached CMake producers (`dev/packaging/native/discovered_inputs.py:26`).

## Considered options

- Keep one whole-gate verdict and add only a CMake stamp. Rejected: any edit still re-runs the whole corpus.
- Per-sequence verdicts with the whole product source as a shared input. Sound and simple, but any product edit re-runs everything.
- Per-sequence verdicts with each sequence's observed product dependencies, falling back to the whole product source when the observation is incomplete. Chosen.
- Key the authority on the physical digest. Rejected: every native build publishes its own copy, so every build would miss.

## Constraints

- This amends the `2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr` ruling on physical digests, for the cli-sequence verdict only. The verdict keys on the logical generation together with the whole registry tooling tree that compiles it. Every other consumer of exact compiled content keeps the physical digest.
- One mechanism: `dev/docs/sequences/verdict_cache.py`, consulted by `check_sequences` and used by the native target, the Sphinx build gate and the CI goldens gate. There is no second cache and no new build target.
- Only a clean sequence is recorded, right after it passes. If any key input changed while it ran (size, modification time, or a file added or removed), the record is refused. A divergence, an engine error or an interruption records nothing for that sequence.
- If observation is incomplete or missing for a sequence, its key falls back to the whole product source. It never keys on less.

## Implementation

We will key each sequence on two parts. The shared corpus inputs are the interpreter and platform, the authority's logical generation, the `dev/registry` tree, the engine and its `dev` import closure, `uv.lock`, and the shared seeds and fixtures. The sequence's own inputs are its parsed sequence, its private contract bytes, its golden bytes, and the product files and directory listings its execution was observed to read.

`check --stamp` writes a stamp and a Makefile-syntax depfile from the same input enumeration. `user_docs_verify` becomes an `OUTPUT` stamp with a `DEPFILE`, so CMake skips an unchanged corpus.

Hypothesis that may change within the constraints: how observation is collected per process (in-process audit hook, worker journals).

## Rationale

A per-sequence key re-executes only what diverged, and observed dependencies stop a leaf command edit from re-running unrelated pages. The logical generation plus the compiler tree determines the bytes every sequence reads, so the key stays exact without depending on publication noise. The whole-source fallback keeps a stale pass impossible when observation is incomplete.

## Consequences

- An unchanged tree costs seconds. A golden or contract edit re-runs one sequence.
- A registry tooling edit re-runs every sequence even when the compiled content is unchanged. This is an accepted cost.
- Edits to modules that every sequence loads (configuration, CLI root, authority reader) still re-run the corpus.
- Records accumulate in the development cache, one file per verdict of a few hundred kilobytes (the observed file and listing digests), and are removed with that cache.
- Observation records the following, each at its first-seen digest:
  - file opens (including `r+` and `a+`), SQLite connections, directory listings, and every imported module;
  - existence and metadata probes, through wrapped `os.stat` and `os.path` predicates;
  - the parent listing of each observed file.
- Docs workers and Python `-m` checkout children run through journaling bootstraps, and the parent expects each journal. A worker that cannot journal refuses to run rather than run unobserved.
- Any other child process, a missing journal, conflicting digests between processes, an entry outside the repository, or an observation lacking the product package makes the record fall back to the whole product source.
- The corpus key also carries the configuring environment and the product modules that the authority compiler imports.
- The authority currency check's re-read of the registry sources is not observed. It only refuses a stale generation, and the generation keys every record.
- If the authority compiler stops being deterministic for a given source and toolchain, this ruling must be reconsidered.
