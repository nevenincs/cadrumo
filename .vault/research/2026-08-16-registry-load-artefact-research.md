---
tags:
  - '#research'
  - '#registry-load-artefact'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:8d20683bb7faecd38dfff454a89ee20ee14c6e98df29062fbaf33bae4723f6f6'
related:
  - "[[2026-08-14-test-harness-sanity-harness-performance-audit]]"
  - "[[2026-07-17-mcp-call-latency-adr]]"
---

# `registry-load-artefact` research: `where a warm authority load actually spends its time`

`2026-08-14-test-harness-sanity-harness-performance-audit` established the
end-to-end numbers and one decisive ratio inside the compiled-registry cache:
reading the 23 MB artefact costs 0.007s while a warm `_construct_authority`
costs 2.9s. It read that ratio as "99.8% of a warm load is rebuilding objects,
not I/O", and concluded the remedy is a randomly-accessible shipped artefact.

That ratio is real, and it does not describe the warm load. It compares two
phases of one component while the warm load has three components, and the
artefact is not the largest. This document decomposes the warm load phase by
phase so the artefact question can be scored against the alternatives rather
than assumed to be the whole problem. No end-to-end figure is re-measured here;
the audit's remain canonical.

## Findings

### A warm authority load has three cost centres, and the artefact is the smallest

Measured by timing each phase of `_construct_authority` directly through its
real entry points, on the bundled tree, with the compiled artefact present and
in-process caches primed. Two consecutive rounds in one process:

| phase | round 1 | round 2 |
|---|---|---|
| `collect_registry_tree_fingerprints` (the cache key) | 1.291s | 0.000s (TTL) |
| `load_registry_tree` (walk + artefact) | 2.059s | 2.429s |
| — read the 23.2 MB artefact | 0.012s | 0.010s |
| — decode, verify digest, hydrate | 0.950s | 0.729s |
| — remainder: the pre-key walk | ~1.10s | ~1.69s |
| `load_convenio_authority` | 0.003s | 0.002s |
| `compile_supplementary_ordenes` | **1.962s** | **1.775s** |
| `load_authorization_manifest` | 0.005s | 0.004s |
| **`_construct_authority` total** | **4.277s** | **4.013s** |

The totals run above the audit's 2.9s because this box was carrying peer suites;
the ratios between phases are the durable result and are what the decision turns
on. Grouped:

- **tree identity walks** — the fingerprint collection plus the pre-key
  discovery walk inside `load_registry_tree`, which runs on a cache HIT — are
  the largest bucket, and the audit already records the second of them at ~1.05s
  standalone.
- **annual-Orden re-extraction** is second at 1.78-1.96s, and is not covered by
  the compiled cache at all.
- **artefact hydration** is third at 0.73-0.95s. Reading its bytes is 0.010s.

So shipping and randomly-indexing the artefact addresses roughly a fifth of a
warm load. It is a real lever and it is not the main one.

### Every process re-parses the annual Orden BOE HTML

The single largest phase is `compile_supplementary_ordenes`, and it spends the
time on a full BeautifulSoup parse of every pinned Orden's BOE HTML, which the
module's own docstrings state at `_m303_orden_manifest.py:48` and `:106`.
`_m303_orden_manifest.py` regenerates the annual-Orden manifest from that parse
and compares it against the committed one, refusing at `:190` on mismatch.

The staleness refusal is the most VISIBLE thing the parse produces and it is not
the only thing, which matters for the remedy and is developed below under "the
annual-Orden cost is 100% HTML parsing": the extraction also yields the census
the compiled projections are built from. Read the refusal as the purpose and the
obvious fix — assert a digest instead — leaves the authority with no data.

Nothing about that check varies per process. It is the same inversion
`2026-07-17-mcp-call-latency-adr` already made for registry validation in its
D1: the build and continuous integration are the gate, and the runtime asserts
identity. Validation took that inversion; this extraction did not, and it now
costs more per warm load than the artefact hydration the audit targeted.

The audit measured this same code at 8.0% self time of a COLD compile
(`bs4/_lxml.feed`) and declined it on reward — correctly, against a 10s cold
compile. Against a warm load it is ~45% of `_construct_authority`, because
everything around it got faster and it did not. The earlier declination was a
rewrite of the extractor onto `lxml`; moving the whole extraction to build time
is a different remedy and does not require touching the extractor.

### The identity walk runs twice, and one of the two cannot be stamped away

`ValidatedRegistryAuthority.load` collects the tree fingerprints, then
`load_registry_tree` independently resolves the root, validates the legal
directory, and runs `discover_modelo_sources` over every modelo and revision
directory before it can compute the disk-cache key. Both enumerate the same
tree; neither reuses the other's enumeration. The audit records the second at
~1.05s on a cache hit and names it "the walk BEFORE the cache lookup".

For an immutable installed tree both can be replaced by reading one stamped
digest. For an authoring tree neither can — files genuinely change — so the only
available lever there is folding the two walks into one. That fold is
**unmeasured**. The audit's measured 0.26s dedup ceiling does not apply to it:
that ceiling bounds redundant `_read_entries` calls WITHIN one compile, a
different pair of walks. Anyone implementing the fold must measure it first.

### The install-versus-authoring discriminator already exists, and it is not the obvious one

`is_bundled_registry_root` is the wrong predicate for "this tree cannot change":
under an editable install it returns True for the live in-tree source directory,
which is edited constantly. Its own docstring at `_loader_cache.py:437` and the
TTL comment above it record exactly this.

The sound discriminator is already in use for verdicts: the release build stamps
a file BESIDE the registry root, and `bundled_verdict_path` returns `None` when
no such stamp is present. An editable checkout has no stamp because nothing
stamps into `src/`. Presence of the stamp IS the immutability claim, and it is
made by the build rather than inferred at runtime. The same shape extends to a
compiled-artefact identity stamp with no new predicate semantics.

`shipped_verdict_location` also records the placement rule the new stamp must
follow: a sibling of the root, never inside it, so the stamp is not walked by
the fingerprint it certifies.

### D1 measured after implementation: 3.1s removed per process, 24s added per release

The identity split was projected at 2.2-3.0s from the decomposition above. Now
that it is built, it was measured directly rather than left as a projection.

Against a `git archive` snapshot of the real registry tree in scratch — 17,548
files, 18,788 fingerprint entries — with the bundled root redirected at the
snapshot so its files take the same read-only fingerprint path production uses:

| | seconds |
|---|---|
| walked resolution, three cold runs | 3.065, 3.862, 3.124 |
| stamped resolution, three cold runs | 0.002, 0.002, 0.002 |
| stamping the tree (build-time, once per release) | 24.179 |

The snapshot is immovable, which is why these three runs agree where a live-tree
measurement would not. A collector that RAISES was injected on the stamped runs,
so the 0.002s is a walk that provably did not happen rather than one that merely
got faster.

So D1 removes ~3.1s from every registry-touching process, at the top of the
projected range. Two caveats belong with the number. It is the identity walk
alone: the loader's structural discovery pass is skipped on the same condition
and is not included here, so the per-process saving is larger than 3.1s and has
not been separated. And the stamped figure is what an INSTALL gets; an authoring
tree has no stamp and keeps the full 3.1s, which is the honest half.

The 24.2s stamping cost is roughly eight times the walk it replaces, because it
reads all 17,548 files rather than stat-ing them. That is affordable exactly once
per release and would be indefensible per process — which is the asymmetry the
whole design rests on, now quantified rather than asserted. An earlier draft of
the implementing docstring guessed "on the order of a second" for this; that was
wrong by more than an order of magnitude and has been corrected to the measured
figure.

### The annual-Orden cost is 100% HTML parsing, and the manifest is not the payload

Two things needed establishing before D2 could be built, and the second corrects
the ADR's own description of it.

**Where the time goes.** Timing each stage over the five pinned ejercicios
(2022-2026, ~480 KB of BOE HTML each):

| stage | total |
|---|---|
| reading the source bytes | 0.001s |
| SHA-256 over those bytes | 0.001s |
| `extract_orden_anual_iva_authority` (BeautifulSoup) | **1.593s** |
| full `extract_m303_annual_orden_source` | 1.592s |

The parse is the whole cost — read and digest together are 0.2%. So shipping the
extraction result genuinely REMOVES the work rather than moving it, which was the
open question: had the cost been the file read or the pydantic construction,
shipping it would have bought nothing.

**What must be shipped is the CENSUS, not a digest.** The ADR's D2 says the
runtime "asserts the committed manifest's digest against the value the build
recorded". Reading the code, that is not sufficient, and the reason is
structural. `M303AnnualOrdenGeneratedManifest` carries only INVARIANTS per source
— counts, a module distribution, a few scalars, and `source_content_digest`. The
full `M303AnnualOrdenSourceCensus` (every activity and module, agricultural
indexes, ingresos a cuenta, seasonal indexes) is never committed. The runtime
re-extracts it because `_compile_generated_annual_orden_source` and
`_annual_orden_projections_for_source` build the compiled projections FROM the
census. The staleness comparison is a by-product of an extraction that happens
for its data.

So a digest assertion would leave the authority with nothing to compile. D2's
real shape is a build-time generated census artefact beside the existing
manifest, with the runtime validating the shipped census against metadata the
registry already holds — `source_content_digest` against the pinned source's
`sha256`, and `extractor_version` against the current extractor — neither of
which requires opening the BOE HTML at all.

One implementation constraint found alongside: `_check_manifest_with_censuses`
refuses ANY unexpected entry in the generated directory, so adding a second
generated file there is not additive — that guard has to admit it explicitly, or
the load refuses.

### Not investigated

The cost of a random-access read against a SQLite artefact was not measured;
no such artefact exists to measure. The projection is arithmetic from the
0.010s/0.73s split — reading a bounded row set must cost less than hydrating
the whole graph — and it is a projection, not a measurement. A prototype
measurement belongs in the first implementing step, before the format is
committed to.

Whether pydantic model reconstruction from SQLite rows can beat unpickling the
same objects was likewise not tested. Unpickling a pydantic v2 model restores
state without re-validating; building one from rows may re-validate and cost
MORE per object. That is the single largest technical risk in the artefact
option and it is unquantified.

## Sources

- `src/cadrumo/domain/calculations/registry/_authority.py:433` —
  `_construct_authority`, the phase sequence timed above.
- `src/cadrumo/domain/calculations/registry/_authority.py:99` —
  `ValidatedRegistryAuthority.load`, the first of the two tree walks.
- `src/cadrumo/domain/calculations/registry/_loader.py:1223` —
  `_load_registry_tree_cached`, where the artefact is consulted after the walk.
- `src/cadrumo/domain/calculations/registry/_compiled_cache.py:405` —
  `load_compiled_registry_cache`, the read/verify/hydrate path.
- `src/cadrumo/domain/calculations/registry/_m303_orden_manifest.py:48`,
  `:106`, `:190` — the per-process BeautifulSoup extraction and its refusal.
- `src/cadrumo/domain/calculations/registry/_loader_cache.py:437` —
  `is_bundled_registry_root` and why it does not mean immutable.
- `src/cadrumo/domain/calculations/registry/_verdict_cache.py:187`, `:200` —
  `shipped_verdict_location` and `bundled_verdict_path`, the stamp-presence
  discriminator and the sibling placement rule.
- `dev/packaging/python_cohort.py:271` —
  `_stamp_bundled_verdict_into_build_tree`, the existing build-time stamping
  hook a compiled artefact would ride.
