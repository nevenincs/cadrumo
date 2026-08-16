---
tags:
  - '#adr'
  - '#registry-load-artefact'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:81126836962a3fe4a09f5b43e4d0d35289f17fa87d58a2b435997486b5a3f8e1'
related:
  - "[[2026-08-14-test-harness-sanity-harness-performance-audit]]"
  - "[[2026-07-17-mcp-call-latency-adr]]"
  - "[[2026-07-07-registry-disk-cache-pytest-adr]]"
  - "[[2026-07-07-registry-toml-parser-adr]]"
  - '[[2026-08-16-registry-load-artefact-research]]'
---
# `registry-load-artefact` adr: `build-time registry artefact, cheap install identity, and drift-triggered rebuild` | (**status:** `proposed`)

## Problem Statement

A registry-touching process pays a multi-second authority load before it can
answer anything, and the operator-facing consequence is recorded in
`2026-08-14-test-harness-sanity-harness-performance-audit`: a listing command
costs tens of seconds cold and low tens warm, with the overwhelming majority of
a cold run attributed to one call.

The audit proposes the remedy — compile at release, ship a randomly-accessible
artefact, and give an immutable install a cheap identity instead of a walk — and
supplies the ratio that motivates it. `2026-08-16-registry-load-artefact-research`
then decomposes the warm load and finds that ratio describes one component of
three, and not the largest. A decision is needed now because the obvious reading
("build the database") would spend the most invasive change in the codebase's
most load-bearing surface on the third-largest lever, while two cheaper levers
that reuse mechanisms already in the tree go untaken.

This record rules on which levers are taken, in what order, and on the drift
detection that makes any of them safe.

## Considerations

- The three cost centres of a warm load, their measured sizes, and the finding
  that the artefact is the smallest of them:
  `2026-08-16-registry-load-artefact-research`.
- The per-process annual-Orden BeautifulSoup extraction is the largest single
  phase, and it yields both a staleness refusal and the census the compiled
  projections are built from — so the remedy must ship the census, not a digest:
  same research.
- The identity walk runs twice, and the fold of the two is measured for neither
  cost nor saving: same research, "not investigated".
- `2026-07-17-mcp-call-latency-adr` already established the governing inversion
  in its D1 — the build and continuous integration are the gate, the runtime
  asserts identity — and already accepted its risk: a corrupted install that
  preserves the stamped fingerprint goes undetected, because package-manager
  digest verification owns byte integrity. Its D3 already commits the compiled
  set to a fingerprint-keyed derived cache. This record extends both rather
  than reopening either.
- `aeat-registry-authority-flow` forbids parallel read paths over registry data
  and requires cache invalidation on the complete tree fingerprint. The audit's
  own resolution of that tension applies: random access over ONE artefact is
  the same authority consulted without full hydration, not a second read path.
- `no-legacy-compatibility` governs every artefact here. `COMPATIBILITY_REGIME`
  is `PRE_RELEASE`, so a format change deletes the old surface outright.
- The registry tree is currently red on validation, and no verdict can be
  certified while validation fails: same audit. That bounds what can be
  acceptance-measured, and it is a scheduling fact, not a design input.

## Considered options

Scored on measured warm-load saving, blast radius, and whether the mechanism
already exists. Sizes are per-process, warm, from the research decomposition.

| | option | saves | blast radius | mechanism exists |
|---|---|---|---|---|
| **O1** | ship the existing compiled pickle inside the wheel | first-run compile only; **0s warm** | small | yes |
| **O2** | replace the pickle with a randomly-indexed artefact built at release | up to ~0.7-0.95s warm, proportional to what is read | **large** — artefact format, release pipeline, loader | no |
| **O3** | stamped identity for an immutable install; keep the walk for authoring trees | **3.1s measured** on installs, 0s on authoring trees | medium | **yes** — the verdict stamp shape |
| **O4** | move the annual-Orden extraction to build time; runtime loads the shipped census | **1.59s measured** parse, warm, everywhere | medium | **yes** — same inversion as D1 |
| **O5** | fold the two identity walks into one | unmeasured | medium | no |
| **O6** | warm in-process serving | everything, for MCP only | large | already decided |
| **O7** | keep micro-optimising the walk and the loader | ceiling measured at ~0.26s | small | n/a |

**O1 — rejected as a destination, absorbed as a component.** It removes the
first-run compile and nothing else; every later run pays the same warm load. A
design that stops here fixes the first run and leaves the operator-facing number
where it is. The artefact is built at release under O2 regardless, so O1 is not
a separate deliverable.

**O2 — accepted, third.** It is the only option that attacks hydration, and the
audit is right that hydration cannot be removed by a bigger or better-placed
cache. It is also the most invasive change available and carries an unquantified
risk the research names: building pydantic models from rows may re-validate
where unpickling does not, which would make per-object reconstruction more
expensive rather than less. It is sequenced last and gated on a prototype
measurement before its format is committed.

**O3 — accepted, first.** Largest measured saving, and the discriminator and
placement rules already exist in the verdict-stamp machinery. It buys nothing on
an authoring tree, which is where development happens — an honest limitation,
not a hidden one. Now implemented and re-measured at the top of its projected
range, with the build-side cost quantified too; both figures are in
`2026-08-16-registry-load-artefact-research`.

**O4 — accepted, second.** A per-process re-derivation of a fact the build can
prove once, which is precisely the class D1 already ruled on. It needs no change
to the extractor, which is what makes it cheap where the audit's earlier `lxml`
rewrite proposal was not — the extractor simply runs at build time instead. The
saving is real rather than relocated: measurement puts 100% of the extraction in
the BeautifulSoup parse and 0.2% in reading and digesting the bytes, so shipping
the result removes the work rather than moving it. Had that split gone the other
way this option would have been worthless, which is why it was checked before
anything was built.

**O5 — deferred, not rejected.** It is the only lever available to an authoring
tree, and it is the one lever here with no number attached. The audit's 0.26s
dedup ceiling bounds a different pair of walks and must not be cited for this
one. Deferred pending its own measurement; re-entering this record when it has
one.

**O6 — out of scope.** Already decided as D4 of `2026-07-17-mcp-call-latency-adr`
and orthogonal: it amortises the per-process cost for MCP and leaves the
one-shot CLI paying it in full. Everything decided here still binds the CLI.

**O7 — rejected.** Ruled out with a measured ceiling by the audit, in several
independent forms. Not to be re-chased.

## Decision

- **D1 — stamped identity for immutable installs.** The release build stamps a
  registry-identity record beside the registry root, carrying the package
  version and a content digest of the tree. At load, a present and
  version-matching stamp IS the tree identity: no fingerprint walk, no source
  discovery walk. Stamp presence is the immutability claim and is made by the
  build; `is_bundled_registry_root` is explicitly NOT the discriminator, because
  it is true of a live editable checkout. Absent, unreadable, foreign, or
  version-mismatched stamp falls back to the full walk.
- **D2 — build-time annual-Orden extraction, amended.** The runtime stops
  parsing the pinned annual Orden BOE HTML. The build extracts once and emits the
  full `M303AnnualOrdenSourceCensus` set as a generated artefact beside the
  existing generated manifest; the staleness refusal moves to a build and
  continuous-integration gate that regenerates and compares. The runtime loads
  the shipped censuses and validates each against metadata the registry already
  holds — its `source_content_digest` against the pinned source's `sha256`, and
  its `extractor_version` against the current extractor — neither of which opens
  the HTML. Any mismatch, or an absent artefact, re-runs the extraction and its
  refusal in full.

  **Amended from "the runtime asserts the committed manifest's digest".** That
  was wrong about what the extraction is for, and the correction is load-bearing:
  the committed manifest carries only per-source invariants, while the census the
  compiled projections are built FROM is never committed. A digest assertion
  would leave the authority with nothing to compile. Measured decomposition and
  the structural reason are in `2026-08-16-registry-load-artefact-research`.
- **D3 — randomly-indexed compiled artefact, built at release.** The compiled
  registry becomes a plain-data, randomly-addressable file — SQLite is the
  intended fit — built by the release pipeline and shipped, replacing the
  pickle. A listing surface reads the rows it needs; a calculation path reads
  its revision; neither pays for the other. It remains derived and rebuildable:
  a key mismatch, digest failure, or shape refusal deletes and recompiles from
  TOML.
- **D4 — one authority, not a projection.** No separately-authored listing or
  metadata table. Every row in the artefact is emitted by the same compile that
  produces the authority today, and a parity gate proves the artefact answers
  identically to a full TOML compile. The artefact is a lazily-consulted view of
  the one authority; anything hand-maintained beside it is a second authority
  and is forbidden.
- **D5 — sequencing.** D1, then D2, then D3. Each lands behind its own gates and
  is independently revertible. D3's format is not committed until a prototype
  measures row-read reconstruction against the current unpickle.

## Drift detection

Two trees, two mechanisms, one fallback. This is the part that must not be
flattened into a single answer.

**Installed, non-editable tree.** Identity is `(package_version, tree_digest)`
read from a small stamped record placed as a sibling of the registry root —
never inside it, so the stamp is not walked by the fingerprint it certifies,
which is the placement rule the shipped verdict already follows. The runtime
reads one file and compares. It does not walk. Drift is undetectable by
construction, and that is the same accepted trade
`2026-07-17-mcp-call-latency-adr` already made for validation: the
package-manager digest chain owns install byte integrity. This record extends an
accepted risk from validation to compilation; it does not introduce a new class
of risk, and it must not be described as if it were free of one.

**Authoring or editable tree.** No stamp exists, so nothing changes: the full
fingerprint walk over every registry file, content digests included, keyed
exactly as today. Files genuinely change here and no cheap identity is
available. O5's walk-fold is the only lever and is deferred unmeasured.

**Mismatch.** Every mismatch path is identical and non-negotiable: delete, do
not migrate; recompute in full; never serve a partial or degraded answer. That
covers an absent stamp, a version mismatch, a digest mismatch, a schema-version
mismatch, an unreadable or foreign artefact, and any structural refusal. A
half-written artefact is never observable because writes are atomic and readers
verify an embedded digest before use, exactly as the current compiled cache
does.

## Constraints

- **Blocking:** the registry tree is red on validation, so no verdict can be
  certified and the end-to-end acceptance figures cannot be re-measured until
  the in-flight registry authority-grade campaign lands. Design, implementation
  and unit gates are not blocked; the headline number is. Any "validation runs
  every time" observation taken before then is a symptom of the red tree, not
  the steady state.
- **Unquantified, and D3 is gated on it:** whether reconstructing pydantic
  models from artefact rows beats unpickling them. Unpickling restores state
  without re-validating; row construction may not. Named in
  `2026-08-16-registry-load-artefact-research`. If the prototype shows row
  construction is not cheaper per object, D3's saving evaporates and the option
  must be re-scored rather than shipped on the strength of this record.
- **Unmeasured, and therefore deferred:** O5's walk fold. No number may be
  claimed for it from the audit's dedup ceiling, which bounds a different pair.
- **Parent stability:** this record depends on `2026-07-17-mcp-call-latency-adr`
  D1 and D3, both accepted and both shipped in the tree (the shipped verdict,
  its build-time stamping hook, and the fingerprint-keyed compiled cache all
  exist and work). It depends on no in-flight feature. The registry
  authority-grade campaign is a scheduling dependency for measurement only, not
  a design dependency.
- Windows and network-share behaviour is a real constraint on any new on-disk
  artefact: the existing cache already carries a bounded read retry for a
  transient sharing violation during an atomic replace, and a SQLite artefact
  must be opened read-only and must not rely on lock semantics the backing share
  may not honour.

## Implementation

Three layers, in the D5 order, each independently landable.

The **identity stamp** rides the packaging surface that already stamps the
validation verdict into the build tree, writing a second sibling record with the
package version and a tree content digest. The registry authority gains one
early branch: resolve the stamp; on a match, construct with the stamped identity
as the cache key and skip both walks; otherwise take today's path unchanged. The
verdict cache's existing stamp-presence discriminator is reused rather than
reimplemented, so an editable checkout is excluded by having no stamp rather
than by a runtime guess.

The **annual-Orden inversion** moves the regeneration and comparison out of the
authority construction path into a build and continuous-integration gate, and
leaves behind a digest assertion. The extractor itself is untouched. The
refusal semantics are preserved exactly: a stale committed manifest still
refuses, at the gate rather than on the operator's machine, and the runtime
still refuses if the digest it asserts is absent or wrong.

The **artefact** replaces the compiled-cache module's serialisation layer, not
its contract. Its key derivation, its integrity framing, its structural
refusal, its atomic write, its eviction, and its delete-on-mismatch behaviour
all carry over; what changes is that the payload becomes rows addressable by
modelo and revision instead of one opaque blob, and that the release build
produces it rather than the first operator to run the tool. Consumers reach it
only through the authority, which grows lazy per-modelo and per-revision
hydration behind its existing accessors. No consumer learns that the artefact
exists.

Migration is deletion, per `no-legacy-compatibility` under `PRE_RELEASE`: the
pickle encode and decode path is removed in the same change that lands the
artefact, not retained as a fallback; the runtime Orden extraction call is
removed, not made conditional. No dual-read, no format flag, no compatibility
branch. Old pickles are unreadable by key and are pruned by the eviction that
already exists.

## Gates

Every item below is a real-behaviour gate, proven to bite by breaking the
production code from outside the repository and confirming the red.

1. **Identity soundness.** A mutated file in an authoring tree re-keys and
   rebuilds; a stamped install with a mutated file is knowingly NOT detected and
   the gate asserts the documented boundary rather than pretending otherwise.
   Extends `test_mutable_tree_fingerprint_invalidation.py`.
2. **No stale serve.** An artefact built from one tree is never served for
   another; a stamp carrying a different package version is refused and the full
   walk runs. Extends `test_compiled_registry_cache.py` and
   `test_bundled_verdict_stamp.py`.
3. **Artefact equals TOML compile.** The randomly-indexed artefact answers
   identically to a full TOML compile of the same tree, per modelo and per
   revision, over the real bundled tree — the proof that it is not a second
   authority. New `test_compiled_artefact_authority_parity.py`.
4. **Anti-tautology.** Corrupt the artefact on disk — flip a digest byte, drop a
   row — reload, and assert refusal and rebuild rather than a silent partial
   answer. Extends `test_compiled_registry_cache.py`, which already carries the
   shape.
5. **Delete-not-bridge.** No reader for the pickle format survives, no
   conditional Orden extraction survives, and the compatibility regime is
   unchanged. Extends `test_compatibility_lifecycle_gate`.
6. **Concurrency.** N processes building and reading simultaneously neither
   corrupt the artefact nor observe a half-written one, exercised under xdist
   with a private `--basetemp`. Extends
   `test_registry_disk_cache_loader_fingerprint.py` and
   `test_loader_cache_isolation.py`.
7. **Cold install.** No artefact present and a read-only package directory: the
   load still succeeds by compiling, and writes nothing into the package
   directory. Extends `dev/packaging/tests/test_release_cohort_integration.py`.
8. **Orden staleness still refuses.** The build gate regenerates and refuses a
   deliberately stale committed manifest, and the runtime digest assertion
   refuses a mismatched digest. New gate under `dev/registry/tests/`.

Items 1-5 are reconstructed from the deliverable brief, whose enumeration
reached this record truncated between items 5 and 6; items 6 and 7 are its own
words. The reconstruction is stated so it can be corrected rather than silently
adopted.

## Rationale

The knockout is ordering, not selection. Every option here except O7 does
something real; the decision that matters is which one is spent first, and the
research inverts the intuitive answer. The artefact is the change the audit
names and the brief assumes, and it is measurably the third-largest lever and
the most invasive by a wide margin. Taking it first would spend the largest
blast radius available on roughly a fifth of a warm load, while a build-time
stamp and a build-time Orden proof — each reusing a mechanism that already ships
and works — together address the other four fifths.

D1 and D2 also win on a criterion the audit itself supplies: both are cases of
the runtime re-proving, per process, a fact that is immutable per release and
already proven at build time, which is the definition of removable waste. D1's
inversion is not new here; it is the one
`2026-07-17-mcp-call-latency-adr` already accepted for validation, applied to
the two adjacent facts it did not reach. Extending an accepted inversion is
cheaper to reason about and cheaper to review than inventing an artefact format.

D3 survives as a decision rather than being dropped because the audit's core
finding stands: hydration cannot be removed by a better cache, only by not
hydrating what was not asked for. But it is sequenced last and explicitly gated
on a prototype, because the one thing that would falsify it — row construction
re-validating where unpickling does not — is unmeasured.

D4 exists because the cheapest way to make a listing surface fast is also the
one `aeat-registry-authority-flow` forbids: author a small metadata table beside
the real registry. The audit's resolution is adopted verbatim as a decision so
that the forbidden shortcut cannot re-enter as an implementation detail.

## Consequences

The prize, if all three land: an installed operator's warm authority load loses
both identity walks and the Orden re-extraction outright, and pays hydration
proportional to what was asked rather than for the whole tree. The cold first
run loses its compile entirely. An authoring tree gains D2 only, which is the
honest and unglamorous half — development stays slow until O5 is measured, and
this record does not pretend otherwise.

The costs are real. Drift on an installed tree becomes undetectable at runtime
by design, which is an extension of an already-accepted trade but is now load
bearing for compilation as well as validation; if the package-manager digest
chain is ever not the integrity owner, both decisions have to be revisited
together. The release pipeline grows two more artefacts it must produce
correctly, and a build that stamps a wrong digest ships a wrong answer rather
than a slow one — so gates 2 and 8 are not optional polish, they are what makes
build-time authority safe.

None of this can be acceptance-measured end to end until the registry campaign
clears the standing red. Landing D1 and D2 against a red tree is possible and
worth doing; declaring the operator-facing improvement is not, and any claim to
that effect before a green tree is a claim about a program that is about to
change shape.

The pathway this opens is the one the audit identified and could not take
without violating a rule: registry surfaces that need part of the authority
stop paying for all of it, without a second read path ever being authored.
