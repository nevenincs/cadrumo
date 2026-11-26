# Authority and fixture staleness

Two derived inputs sit between source and most tests: the published registry authority and the generated fixture projections. Neither is committed (with one exception below), both are keyed by content digests, and a test that reads a stale one proves nothing about your change. This reference says how each goes stale, how to see it, and what to run.

## Published registry authority

**What it is.** The runtime never reads registry TOML. It reads a published, digest-checked SQLite generation. In a checkout that is `.authority/` (gitignored), or wherever `CADRUMO_AUTHORITY_ROOT` points; the justfile and the root `conftest.py` both export that variable, so recipes and pytest read the same place. The folder holds the descriptor `authority.current.json` and one `authority-<sha256>.sqlite3`. When the root is set it is the only source: a missing descriptor is a refusal, with no fall back to a packaged copy ([location](../../../../src/cadrumo/domain/calculations/registry/authority_location.py#L14), [descriptor](../../../../src/cadrumo/domain/calculations/registry/authority_store.py#L52), [pytest export](../../../../conftest.py#L171)).

**Two identities.** `logical_generation` is the content identity of the legal sources; `database_sha256` is the hash of the SQLite bytes, which also depend on the code that built them. Two publishes of one tree can differ in `database_sha256`. Compare `logical_generation` when asking "is this the same authority" ([identities](../../../../dev/registry/compiler/authority_database.py#L49)).

**How staleness is decided.** `just registry-publish-authority-if-authority-stale` compares the descriptor's `logical_generation` with a digest of the registry files, the source-evidence inputs and the profile schema. It does not compile. Only `current` skips the publish; `stale`, `unreadable` and `unsupported_format` publish ([currency](../../../../dev/registry/pipeline/authority_publication.py#L396)).

**The trap: compiler edits.** The staleness check looks at registry data, not at compiler code. After changing anything under `dev/registry/compiler` or the publication pipeline, the conditional recipe reports `current` and publishes nothing. Run `just registry-publish-authority` to force it.

| You changed | Run | Why |
|---|---|---|
| Registry TOML or source evidence under `src/cadrumo/_data/registry` | `just registry-publish-authority-if-authority-stale` | Product code and product tests read the published authority, not the TOML |
| Registry compiler or publication code | `just registry-publish-authority` | The conditional check cannot see code changes |
| Nothing registry related | nothing | `just setup`, `just init`, `just dev`, `just test-registry` and `just test-frontend` already publish when stale |
| A wheel or sdist is about to be built | publish first | The build hook takes the existing publication as a selected input and does not check that it is current; a missing one is an error naming `just registry-publish-authority` ([hook](../../../../packaging/authority/hatch_build.py#L151)) |

**Who compiles and who reads.** Tests under `dev/registry` compile the bundled registry from source in a session fixture, once per worker, and do not need a publish to see a TOML edit. Product tests and the product read the published descriptor and do need it ([registry fixtures](../../../../dev/registry/conftest.py#L30), [tree fixtures](../../../../dev/registry/tests/conftest.py#L32)).

**Compiled copy on disk.** To spare each test worker a full compile, the compiled bundled registry is kept as a validated copy in the development cache (`CADRUMO_REGISTRY_DISK_CACHE_DIR`, else the repository's development cache folder). Its key covers the registry root and identity digest, the source receipt, the compiler source-tree digest, the validation key and the loader code fingerprint, so both data and compiler edits miss it. It exists only for the immutable bundled root; a copy that fails any check is deleted and the registry is compiled. A separate record keeps clean validation verdicts only, never failures. Neither needs manual clearing ([copy](../../../../dev/registry/compiler/validated_authority_copy.py#L98), [cache folder](../../../../dev/registry/compiler/loader_cache.py#L507), [verdicts](../../../../dev/registry/compiler/validation_verdict_cache.py#L1)).

**Proving registry work.**

- `just check-registry-gate` runs three conformance passes in order: `valid`, `runtime-load` (the published artefact loads exactly) and `integrity`, which first refuses a published authority that does not record the current registry and source identity. It is the quick proof after a registry edit ([recipe](../../../../justfile#L394)).
- `just check-registry` runs every lifecycle lane and writes one health report: authority currency, oracle bindings, validity, runtime loadability, target coverage, export placement, delta minimality and edition delta assessment ([lanes](../../../../dev/registry/analysis/registry_status.py#L849)).
- `just check-bindings` runs the binding analysis in strict mode.
- `just test-registry` publishes when stale, then runs collect, source load, calculations and conformance. Conformance is slow: it walks every bundled revision.

## Generated fixture projections

**What they are.** A family is one producer's projection, declared once in `dev/fixture_projections/registry.py`. Most families write JSON the desktop frontend imports (profile, household, ledger recordings, served words, year authority, Modelo envelopes) into `build/<preset>/fixtures/window`, which is never committed. One family is committed in place: `modelo-wire-types`, TypeScript under `native/desktop/frontend/src`. One, `docs-sequence-seeds`, has no producer and is only checked ([families](../../../../dev/fixture_projections/registry.py#L203), [window folder](../../../../dev/fixture_projections/location.py#L1)).

**Personas.** The synthetic taxpayers behind the fixtures are authored as data under `dev/fixtures/personas/`: `identities.toml`, and per persona a `persona.toml`, `ledger.csv`, `documents.toml` and `expectations.toml`. Years are tokens relative to the registry horizon, never literals. Every persona is validated before any producer is trusted ([personas](../../../../dev/fixtures/personas/README.md)).

**Freshness is a digest stamp.** Each produced family has a stamp recording its declaration, the digests of its input groups, the published authority identity and the hash of each output. Inputs are the producer and tooling files, the personas, `uv.lock`, and the product source the producer was observed to read (the whole product source when a run was not fully observed). Modelo families add host Rust sources and the frontend lockfile ([stamps](../../../../dev/fixture_projections/stamps.py#L1)).

| State | Meaning |
|---|---|
| `fresh` | Declaration, inputs, authority identity and outputs all match the stamp |
| `stale` | One of them changed; the changed items are listed |
| `unstamped` | Outputs exist but no usable stamp |
| `missing` | No outputs on disk |
| `check-only` | The family has no producer |

**What makes a family stale.** An edit to its declaration, its producer or tooling, a persona, `uv.lock`, a product file it reads, an output edited by hand, or a new published authority identity. A registry TOML edit reaches fixtures only through the authority: until you republish, fixtures stay "fresh" against the old authority.

**Commands.**

| Goal | Command |
|---|---|
| See what is stale and why (read-only) | `just fixtures-status [FAMILY]` |
| Produce what is not fresh | `just fixtures-seed [FAMILY]` |
| Produce everything regardless of stamps | `just fixtures-seed-force [FAMILY]` |
| Validate personas and run each family's check, writing nothing | `just fixtures-check [FAMILY]` |
| Also build each family twice and compare bytes | `just fixtures-check-determinism [FAMILY]` |
| Bare checkout: seed what a check needs, then check | `just fixtures-gate` |
| Remove generated projections (refuses the committed family) | `just fixtures-clean [FAMILY]` |

`fixtures-seed` needs a published authority and says so when none resolves. It adopts an unstamped family without rebuilding only when that family's check proves its outputs. `just setup`, `just init` and `just dev` publish the authority when stale, install the frontend packages and seed, in that order; `just check-frontend`, `just test-frontend` and `just test-native` seed what they need ([seed](../../../../dev/fixture_projections/cli.py#L466)).

**Tests never seed.** A test process reads projections and never writes them; lanes that need projections seed in a prerequisite step before pytest starts. If a test fails on a missing or stale projection, seed and rerun; do not make the test produce it.

## Order after a change

Registry data changed: publish the authority, then `just fixtures-seed`, then test. Persona or producer changed: `just fixtures-seed`, then `just fixtures-check`. Compiler changed: forced publish, then seed. When `modelo-wire-types` regenerates, review and commit the TypeScript diff with the change that caused it.
