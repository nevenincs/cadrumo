---
tags:
  - '#adr'
  - '#registry-toml-parser'
date: '2026-07-07'
modified: '2026-07-08'
related: []
---

# `registry-toml-parser` adr: `adopt rtoml for the registry TOML parse boundary` | (**status:** `accepted`)

## Problem Statement

A cold registry compile costs ~14.45s, of which ~8.6s is pure-Python `tomllib`
parsing the 16,310 fragmented registry TOML files under
`src/aeat/_data/registry/` (`read_toml` in `core/_toml.py`, ~7.1s inside
`tomllib.loads`/`tomllib.load` itself). This is the "backed library
regression" flagged during the ledger-perf-optimization / root-suite-slowness
campaign: a pure-Python parser sitting on a hot compile path that every fresh
clone, CI cache miss, or registry-content invalidation pays in full, and that
every pytest worker that misses the disk cache (`registry-disk-cache-pytest`
ADR) also pays. The disk cache amortises the compiled RESULT across
processes; it does not make any single cold compile cheaper. This ADR
addresses the cold-compile cost itself.

## Considerations

- `core/_toml.py` is the SOLE TOML-parsing surface project-wide: `read_toml`
  (file-path entry) and `parse_toml_text` (in-memory-text entry), both thin
  wrappers around `tomllib.load`/`tomllib.loads`. Every registry, user-profile
  schema, and bucket-manifest TOML read funnels through these two functions.
  A prior security-hardening review (`secure-storage-production-hardening`
  W12.P26.S372/S288) confirmed this module is a plaintext-parse boundary with
  no storage, profile, or master-key entanglement — safe to modify in
  isolation.
- The registry-authority-flow decision (`registry-authority-flow` ADR/research)
  fixes the loader's role as a deterministic TOML compiler feeding strict
  frozen pydantic schema objects; this ADR only touches the PARSE step inside
  that compiler, not the compilation or validation semantics.
- A prior security-input-validation audit confirmed the property this ADR must
  preserve: TOML is a pure data format with no executable nodes, and the only
  parser in use was stdlib `tomllib` (a safe parser). Any replacement parser
  must retain this "safe, non-executable data parse" property.
- Registry money/rate values are stored as TOML STRINGS and coerced to
  `Decimal` downstream by pydantic field validators (`aeat-schema-central-config`
  convention) — the raw TOML parser never sees or produces a `Decimal`. This
  removes the most dangerous class of parser-swap risk (a replacement parser
  silently choosing a different numeric type for monetary values) from
  consideration entirely: both the incumbent and the candidate parser return
  `float` for any bare non-integer TOML numeric literal, identically.

## Considered options

- **Keep `tomllib` (status quo).** Zero risk, zero win. Rejected: leaves an
  8.6s cold-compile cost that a fresh clone, CI cache miss, or a registry edit
  invalidating the disk cache pays in full, on every such occasion.
- **`tomli` (PyPI backport, C-accelerated in some environments).** Measured
  3.56s median on the full 16,260-file registry tree (vs `tomllib`'s 5.13s on
  the same run) — a free, zero-correctness-risk win since `tomli` and
  `tomllib` share the same parser lineage (`tomllib` is `tomli` merged into
  stdlib). Rejected as the PRIMARY choice only because `rtoml` measured
  faster still; kept as the documented fallback if `rtoml`'s Rust-extension
  dependency becomes unacceptable later.
- **`rtoml` (Rust extension, PyO3-bound `toml-rs`).** Measured 2.13-2.15s
  median (path-based `rtoml.load(path)`) on the same corpus — ~2.4x faster
  than `tomllib`, ~1.7x faster than `tomli`. Correctness proven exhaustively
  (see Rationale). **Chosen** — operator-selected over the safer-but-slower
  `tomli` and over deferring, given the exhaustive correctness proof reached
  full-corpus parity, not a sample.
- **Parallelize fragment parsing (plan B, not pursued).** Would cut wall time
  via concurrency without touching per-file parse cost, but adds
  process/thread-pool complexity to a loader whose contract explicitly
  favours deterministic, side-effect-free compilation
  (`registry-authority-flow`). Kept on record as the fallback path if a
  faster serial parser had not cleared the correctness bar; not needed here.

## Constraints

- `rtoml` is a smaller side project (by pydantic's creator, Samuel Colvin)
  than his flagship libraries; it is less actively maintained than
  `pydantic-core`. Mitigated by keeping the swap narrowly scoped (two
  functions), constraining the dependency to a bounded range in
  `pyproject.toml` (`rtoml>=0.13.0,<1`) with the exact resolved version
  locked in `uv.lock` (`0.13.0`), and documenting `tomli` as a same-effort
  fallback if `rtoml` is ever abandoned upstream.
- `rtoml`'s PyPI classifiers list only Unix/Linux/macOS operating systems
  (the maintainer appears not to have updated them), but the actual wheel
  matrix DOES publish a prebuilt `win_amd64` wheel for the project's pinned
  Python version — confirmed by direct install and successful native-module
  import on this Windows 11 x64 development machine, with no build toolchain
  invoked. `uv sync` on CI/other platforms must be re-confirmed once the
  dependency lands (tracked as a verification step in Implementation, not a
  frontier risk — the wheel already exists and installs cleanly).
- `rtoml` raises its own `rtoml.TomlParsingError` (a `ValueError` subclass) on
  malformed TOML, distinct from `tomllib.TOMLDecodeError`. `core/_toml.py`'s
  `error_factory` wrapping already treats parse failures as an opaque class to
  re-wrap into the caller's domain-specific exception, so this is a
  swap-in replacement in the `except` clause, not a widening of the public
  contract.

## Implementation

Swap the two parse call sites inside `core/_toml.py`:
`read_toml` moves from opening the file in binary mode and calling
`tomllib.load(fh)` to calling `rtoml.load(path)` directly (`rtoml` accepts a
`Path` natively, so the manual file-open is removed); `parse_toml_text` moves
from `tomllib.loads(text)` to `rtoml.loads(text)`. Both functions' `except`
clauses catch `rtoml.TomlParsingError` in place of `tomllib.TOMLDecodeError`;
the `OSError` branch and the public `dict[str, object]` return contract are
unchanged, so every consumer (`domain.calculations.registry._loader`,
`domain.user_profile._loader`, `core.access_gate._authorization`, the bucket
manifest reader, and any other caller of `read_toml`/`parse_toml_text`)
requires zero call-site changes. `rtoml` is added to `pyproject.toml` pinned
to the exact version validated in this ADR's research, `uv.lock` is
refreshed, and `uv sync` plus a native Windows wheel install is re-verified
as part of landing. A durable, non-tautological parity test asserts that a
real registry TOML sample parses to independently-known-correct expected
values (not `rtoml_result == tomllib_result`, which would tautologically pass
even if both parsers agreed on a WRONG value) — the test must fail if `rtoml`
ever diverges from the values BOE/the registry authoring tree actually
declare. The cold registry compile is re-measured end to end before and after
the swap and the delta reported alongside this ADR's research numbers.

## Rationale

Full-corpus, non-sampled correctness proof: a deep structural (type AND
value) comparison of `rtoml.load()` against `tomllib.load()` output across
ALL 16,260 real registry TOML files under `src/aeat/_data/registry/` found
ZERO mismatches. This is stronger evidence than a representative sample —
every fragment the registry actually ships was independently re-parsed by
both parsers and found byte-for-byte structurally identical. Targeted
edge-case probes beyond the corpus (offset and local datetime, local date,
local time, `inf`/`-inf`/`nan`, large exponent floats, duplicate-key
rejection) all matched `tomllib` exactly in type and value; duplicate keys
are rejected by both parsers (with different message text, immaterial since
both surface through the same `error_factory` wrapper). Combined with the
Decimal-non-risk noted under Considerations, there is no discovered class of
input on which `rtoml` and `tomllib` disagree for this codebase's real data.

Timing: `tomllib` 5.13s median / `tomli` 3.56s median / `rtoml.load(path)`
2.13-2.15s median (most consistent of the three), measured as 3 warm runs
each over the full real fragment tree on the same machine. Proportionally
applied to the operator-measured 8.6s embedded `read_toml` cost inside the
full compile, this is expected to cut roughly 5s off the cold compile absolute
floor — a cost every fresh clone, CI cache miss, and registry-content
invalidation still pays even with the disk-cache ADR in place, and a cost
production cold start pays on every process launch regardless of any test
harness caching.

Dependency cleanliness: MIT license (compatible with the project), zero
transitive dependencies, `Development Status :: 5 - Production/Stable`
classifier, authored by the creator of `pydantic` (an ecosystem the project
already depends on heavily, though this specific package is a smaller,
less-frequently-released side project of his — named honestly under
Constraints, not hidden).

## Consequences

**Gains:** the cold registry compile drops by roughly a third of its current
wall time with no change to the compiler's contract, no change to any
consumer call site, and no widening of the parse boundary's exception
surface. Production cold start, CI cache misses, and fresh-clone developer
experience all benefit, not only the pytest suite this campaign started from.

**Difficulties:** a new native-extension dependency enters the tree; version
pinning and the `tomli` fallback plan are the mitigation, not elimination, of
the maintenance-risk caveat named under Constraints. The wheel-availability
claim is validated on one Windows development machine and must be
re-confirmed on the project's actual CI matrix during landing.

**Pitfalls avoided:** the correctness proof is exhaustive over the real
corpus specifically because a parser silently choosing a different numeric or
temporal type for even one registry value would corrupt a regulatory figure
undetected — a risk this ADR treats as the primary gate, satisfied before any
code changed, not asserted after the fact.
