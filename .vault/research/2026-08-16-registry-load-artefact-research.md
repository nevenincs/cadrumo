---
tags:
  - '#research'
  - '#registry-load-artefact'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:118b460881928df017d8e390c545ecbecece34721f2f076fb2915cdf75165b2b'
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
available lever there is folding the two walks into one. The audit's measured
0.26s dedup ceiling does not apply to it: that ceiling bounds redundant
`_read_entries` calls WITHIN one compile, a different pair of walks.

That fold was unmeasured when this section was written. It is measured below
under "O5 measured", at roughly seventeen times the ceiling it must not be
scored against — and then retired under "O5 retired", because the second walk
turns out to be the freshness policy doing its job rather than waste. Read all
three in order; this paragraph's "only available lever" framing is where the
reasoning started, not where it ended.

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

### O5 measured: the authoring tree fingerprints itself two to three times, ~4.4s each

O5 was the one lever carrying no number. It has one now, and it is much larger
than the shape of the ADR's earlier note suggested.

Measured against an immovable `git archive` snapshot of the real tree, kept
MUTABLE — not redirected to look bundled, because an authoring tree is exactly
the case where every registry TOML takes the content-digest path. Redirecting
would have measured the cheap stat-only path an install uses and answered the
wrong question:

| | median of 3 |
|---|---|
| fingerprint walk, uncached, with content digests (18,829 entries) | **4.360s** |
| `discover_modelo_sources`, structural | 1.540s |
| `_validate_legal_directory` | 0.004s |

**A mutable tree's fingerprints are never memoised, by design.** Two consecutive
`collect_registry_tree_fingerprints` calls cost 4.360s and 4.719s, and inspecting
the cache after the first shows **zero entries** — not an expired one. That is
deliberate and documented at `_loader_cache.py:437`: a mutable tree's rows carry
content digests that only re-reading the files can validate, so it is
fingerprinted afresh every call. Worth stating explicitly because the timings
alone read like a TTL that never hits, and "fix the TTL" would be the wrong
conclusion drawn from the right numbers.

The consequence is the finding. Instrumenting one authority load on that tree:

    authority identity fingerprints : 4.430s   (1 walk)
    loader collector calls          : 2, costing 9.959s

So an authoring-tree load walks the tree **three** times, ~14.4s in total. The
loader's second call is the post-`RegistryLoadError` refresh path, which this red
tree reaches; a green tree pays two walks, ~9.4s. Either way the authority
collects tree fingerprints and then `load_registry_tree` independently collects
them again, at full price, microseconds later.

**The fold is therefore worth ~4.4s per authority load on an authoring tree**,
and it is the cheap kind: the authority already holds the tree fingerprints, so
passing them down removes a walk without changing what is keyed on. It is
strictly fresher than a second independent walk, not less fresh — the two walks
observe the tree at different instants today, and the later one is the one
currently used.

For contrast, the audit's dedup ceiling for the OTHER pair is 0.26s. This is
roughly seventeen times that. Citing the audit's figure here — the thing the ADR
explicitly forbade — would have under-valued the lever by more than an order of
magnitude and probably retired it.

One scope caveat: this is the AUTHORING case only. A stamped install skips all of
it under D1, so O5 buys nothing there. It is precisely the lever for the tree
developers work in every day, which is the half D1 cannot reach.

### O5 implemented, and reverted: the naive fold breaks cross-process cache agreement

The fold was built and then removed. Recording it because the measurement above
makes it look obviously worth taking, and the next reader will otherwise
re-derive the same attractive design and hit the same wall.

**What was built.** The authority captured the tree fingerprints it walked during
identity resolution — lazily, so a stamped install still walked nothing and D1's
saving was untouched — and offered them to `load_registry_tree`. The offer was
passed AROUND the authority's `lru_cache` via a digest-keyed holder rather than
through it, because a ~19,000-entry tuple in the cache key would have
reintroduced the per-lookup hashing cost `_FingerprintKey` exists to avoid: the
fix for one walk would have been repaid on every cache probe.

It worked on its own terms. Loader walks per authority load went **2 to 0**.

**What it broke.** `test_bundled_root_disk_cache_is_shared_across_processes`
failed: the child process wrote a SECOND compiled pickle, meaning parent and
child derived different compiled-cache keys for one tree. That is the property
the audit measured as collapsing twenty-four xdist workers' independent compiles
into one shared read, and it is worth more than several seconds on an authoring
tree.

**How it was attributed, which is the part worth copying.** Two of the three
failures in that run were non-deterministic — one flipped to passing on re-run,
with eleven registry files dirty from peer churn — which made "it is churn" the
comfortable reading. It was tested instead: the offer was disabled with a
one-line edit and nothing else. Enabled, the test failed twice; disabled, it
passed twice. A plausible explanation and a controlled one are not the same
thing, and the churn nearby was exactly the kind of noise that makes the
plausible explanation feel sufficient.

**Why the shape is wrong, not just the code.** The two collectors are literally
the same function and return identical tuples when called on the same tree, so
the divergence is not a scope mismatch — it is that the offer makes ONE process's
key depend on when ITS authority walked, while a sibling process still derives
its key from its own walk. Any design where different processes can key on
different observation instants of a mutable tree will fragment the shared cache.

The next attempt should invert the direction: have the authority consume the
loader's collector result, so a single canonical walk feeds both and every
process derives its key by the same route it does today. That is untried and
unmeasured. **The saving is real; the mechanism above is not the one to ship.**

### O2's gating question is still open, and two constraints on it are now known

The ADR gates O2 on whether rebuilding pydantic models from rows beats
unpickling. That is still **unmeasured**, and the attempt to measure it produced
two facts worth keeping plus one method error worth not repeating.

**Hydration is dominated by a handful of modelos.** Unpickling the five heaviest,
individually:

| modelo | pickled size | `pickle.loads` |
|---|---|---|
| 100 | 10.12 MB | **424.8 ms** |
| 200 | 2.79 MB | 75.2 ms |
| 390 | 2.40 MB | 61.5 ms |
| 303 | 2.15 MB | 72.7 ms |
| 369 | 1.03 MB | 19.1 ms |

653 ms across those five, against 0.73-0.95s for decoding the whole artefact —
so five of seventy-odd modelos are most of the cost, and modelo 100 alone is
roughly half of it. That is the strongest quantitative argument yet FOR random
access: a caller wanting 303 pays 73 ms if it can address one modelo, and the
better part of a second if it cannot. It is an argument about read amplification,
not about per-object reconstruction cost, and does not settle the gate.

**`model_dump` / `model_validate` is not a round-trip for these models.**
`localization_key` is declared `Field(min_length=1, exclude=True)` on two schema
classes (`_schema.py:359` and `:1102`), so a dump omits it and validation of that
dump fails "Field required" on every construct. Any row format for O2 must carry
excluded fields explicitly rather than assuming the model's own dump is
sufficient. Cheap to discover now, expensive to discover after a format is
committed.

**The method error.** A second arm timed `model_construct(**modelo.__dict__)` and
reported 0.0001x of pickle — which is not a reconstruction at all.
`model_construct` assigns already-materialised nested objects; the revisions,
casillas and formulas in `__dict__` are live Python objects that were never taken
apart. It measured dictionary assignment and would have made O2 look free. A
genuine answer needs the object graph actually serialised to rows and rebuilt
from them, which is the prototype the ADR asks for rather than a micro-benchmark
around it. Recorded because the number is seductive and reproducible, and someone
will otherwise cite it.

### O5 retired: the redundant walk IS the safety property, not waste

The failed implementation forced a re-reading of why the second walk exists, and
the answer retires the option rather than pointing at a better mechanism.

`is_bundled_registry_root`'s docstring states the policy in as many words: a
mutable tree "is fingerprinted afresh on every call rather than served from a
window whose freshness check cannot speak for its file content", because its
rows carry content digests that only re-reading the files can validate.

O5 is exactly that forbidden thing. Handing the loader the tuples the authority
walked seconds earlier IS serving it from a window, and no amount of plumbing
changes what the window is. The ~4.4s is therefore the deliberate PRICE of
refusing to trust a stale observation of a tree that can change under the
process, not redundancy anyone failed to notice.

Two facts complete the picture:

- **On a bundled tree the fold already happened.** The 10-second TTL memo serves
  the second caller for free — measured at 1.291s then 0.000s in the phase
  decomposition above. There is nothing left to fold where folding is safe.
- **On a mutable tree the fold is unsafe by the same policy** that makes the
  memo bundled-only. The two are one decision, not two.

So O5 has no safe remainder. It can only be revisited by revisiting the
freshness policy itself — whether a registry authority may act on a
several-second-old view of an authoring tree — which is an owner-level decision
about registry semantics, not a performance change, and would touch the
complete-tree-fingerprint invariant `aeat-registry-authority-flow` mandates.

Recorded at length because the 4.4s figure is real, large, and reads as an
obvious win in isolation. The measurement was worth taking and the conclusion it
supports is "do not take this", which a figure alone would never have said.

### O2's gate answered: row construction costs 1.68x unpickling, so O2 only pays for PARTIAL reads

The gate finally has a number, obtained by measuring validation from plain dicts
rather than around it.

Subject: the 208 `CasillaDefinition` objects of modelo 303's heaviest revision —
the dominant leaf type by count. The excluded field was re-injected before
validating, and the round-trip was PROVEN (`C.model_validate(d) == original`)
before any timing, so this measures reconstruction of equal objects rather than
of a degraded shape:

| | median of 5 |
|---|---|
| `pickle.loads` of the list | 0.98 ms |
| `model_validate` from plain dicts | **1.65 ms** |
| ratio | **1.68x** |

**So the risk the ADR named is real.** Building pydantic models from rows is
more expensive per object than unpickling them, because unpickling restores
state while validation re-checks every field.

That does not kill O2; it fixes its shape. O2 wins only when random access avoids
enough objects to outrun a 1.68x per-object penalty, and hydration is
concentrated enough that this is easy for partial reads and impossible for full
ones. A listing surface reading ~70 modelo headers, or a calculation path reading
one revision, avoids nearly everything and wins outright. A caller that still
hydrates the whole authority would pay roughly 68% MORE than today.

**The consequence for the decision: O2 must ship WITH partial-read call sites,
not before them.** Replacing the pickle with a randomly-indexed artefact and
leaving every consumer doing a full hydration is a straight regression, and the
measurement says so numerically rather than as a worry.

Two dead ends recorded so they are not re-run. `model_validate(instance)` and
`ModeloDefinition(**__dict__)` both measure ~0.00-0.02 ms and prove nothing:
`revalidate_instances` is unset, so pydantic's default of `never` short-circuits
whenever the nested values are already model instances. Only plain dicts exercise
the path O2 would actually take.

Still open: whether `model_construct` from rows — legitimate if the artefact is
digest-verified, since validation would then be re-proving what the digest
already covers — beats pickle. It does not recurse into nested models, so it is
only viable for leaf types or with an explicit bottom-up rebuild, and that was
not measured.

### The excluded-field problem is systematic, not incidental

Three schema classes so far declare a REQUIRED field with `exclude=True`:
`ConstructDefinition.localization_key`, `ModeloRevision.localization_key`, and
`CasillaDefinition.localization_keys`. Their dumps omit the field and validation
of that dump fails "Field required".

This is a standing constraint on any row format, not a detail: the artefact must
carry excluded fields out of band, or the schema must stop excluding them — and
that second option is not local, because `exclude=True` is presumably serving the
JSON envelope and export surfaces that should not carry localization keys. The
first option is the one that does not disturb other consumers.

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
