# Registry, legal sources, and Python API

The Agencia Estatal de Administración Tributaria (AEAT) owns the official
modelo structure. API means application programming interface.

## Registry and legal-source lookup

Cadrumo's calculation registry preserves the AEAT structure it represents:
modelo identifiers, periods, sections, casillas, formulas, bindings,
classifications, and source references remain authority-named. A resolved
calculation revision records the registry revision it used so later review can
identify the exact rule set.

| Reference field | Meaning |
| --- | --- |
| Registry revision | Exact bundled rule revision used for the calculation |
| Formula or binding | Deterministic route from source values to a casilla |
| `legal_refs` | Legal provisions grounding a rule or finding |
| `source_refs` | Official manual or source material supporting the implementation |
| Evidence provenance | Local record, document, observation, or prior filed revision that supplied a value |

## Runtime authority publication

The runtime authority is the digest-checked publication of the validated AEAT
registry intended for installed calculations and filing exports. It is
generated output with two files: `authority.current.json` is a small canonical
descriptor, and its `database` member names the exact
`authority-<database_sha256>.sqlite3` payload beside it. The descriptor and
database are admitted together; the database is opened read-only and is not
hydrated into one process-wide model graph.

The pair is resolved from one directory, and where that directory is depends
on how Cadrumo was installed. An installed distribution carries it at
`cadrumo/_data/registry/authority/` and resolves it there with no
configuration. A checkout publishes its own into `.authority/` at the
repository root, which is excluded from version control, and names it with the
`CADRUMO_AUTHORITY_ROOT` environment variable. When that variable is set it is
the whole answer: resolution reads the named directory and does not fall back
to the packaged location, so a checkout cannot silently answer from packaged
bytes it believed it had replaced. A directory holding no descriptor is a
refusal naming the publication command, not an empty authority. See
[Publish a validated runtime authority](../how-to/publish-runtime-authority.md).

| Term | Meaning |
| --- | --- |
| Validated candidate | The registry and source-evidence inputs accepted by the development compiler. |
| Source receipt | Root-relative registry and source-evidence content, including manually maintained evidence sidecars. |
| Compiler receipt | The Cadrumo and compiler source files the canonical compiler process loaded, dependency manifests, Python major/minor, and Pydantic versions. |
| Component receipt | The source and compiler receipts bound to one fresh, complete-authority generation. |
| Identity digest | The content-addressed combination of those receipts, recorded so a stale artifact can be detected. |
| Authority descriptor | The atomically replaced selector containing the database basename, byte count, physical SHA-256, and logical generation. |
| Authority database | The content-addressed SQLite publication containing typed components, dependency rows, and the complete manifest. |

The descriptor format is `cadrumo-authority-descriptor-v1`; its exact members
are `format`, `database`, `database_size`, `database_sha256`, and
`logical_generation`. The database format is
`cadrumo-authority-sqlite-v3`. Its manifest binds the logical generation and
the complete component directory, and it records the compiler source closure
and environment the compiler receipt is computed from. A database in an older
format is refused rather than read. The physical database digest is both the
descriptor's admission check and the content-addressed filename, so a changed
or colliding payload is refused before runtime work begins.

The development publication command is
`python -m dev.registry.pipeline publish-authority`. It writes to the
configured authority root, and refuses rather than choosing a location when
none is configured; its `--destination` option selects an isolated authority
directory instead. Custom `--registry-root` or `--source-root` values must be
paired with an explicit `--profile-schema`.
The command-bearing product package has no command that compiles or repairs
this publication.

The source receipt folds each registry and source-evidence file's root-relative
path and content digest. Registry files fold CRLF to LF; source evidence is
byte-exact. The compiler receipt hashes the portable path and content of every
non-test `cadrumo` and `dev/registry` source file loaded to compile, validate
and project the authority, together with `pyproject.toml`, `uv.lock`, Python
major/minor, and the installed `pydantic` and `pydantic-core` versions. Every
publication, whether started from the command above or by the package build,
compiles in one fresh interpreter running the same module, so the recorded
files do not depend on the launching tool. The currency check re-hashes exactly
those recorded files without compiling: an edit to a recorded file, or its
removal, makes the publication stale, while an edit to a module the compiler
never loaded does not. A fresh clone in the same declared environment is
stable, without promising identity across incompatible build environments.

Each component payload is a compact canonical projection of one typed authority
value. Required fields are always written; a field is omitted only when its
typed value equals the default declared by its schema. Strict rehydration
restores those defaults. Discriminators and authored union spellings remain on
the wire, so compaction never guesses which typed variant to construct.
Decimals and dates are JSON strings where the schema types a field as a decimal
or a date. A governed-fact value can be text, an integer, a decimal, a boolean,
or a date, and JSON cannot tell those apart by value alone. Every non-text fact
value is therefore written as an object with one tag that names its type:

| Fact value | Written as |
| --- | --- |
| Decimal | `{"$decimal": "0.40"}` |
| Date | `{"$date": "2025-01-01"}` |
| Integer | `{"$int": 5}` |
| Boolean | `{"$bool": true}` |
| Text | The bare JSON string, for example `"0.40"` |

Runtime decodes the payload under the same strict schema the development
compiler uses. It refuses an unknown tag, a malformed or non-canonical tagged
value, and an untagged non-text fact value; it never infers a type from the
shape of a string.

The compiler, not the product runtime, expands authoring deltas into complete
canonical revisions. The database also carries typed runtime catalogues for IVA
regulations, place-of-supply rules, country aliases, Spanish postal territories,
territorial carve-outs, recargo bands, and apoderamiento scopes. These are
frozen schema records, not embedded TOML bytes or an untyped JSON bag. A
write or read refuses an authority when any required runtime catalogue is empty.

Modelo and tax-domain types validate stable identifier syntax without loading
the authored tree. The compiled authority owns membership and validates those
identifiers against its published vocabularies. The same authority projects the
shared temporal support envelope—`floor`, `horizon`, and optional
`hard_ceiling`—used to admit supported coordinates.

The `IndexedRegistryAuthority.operation()` path has no source compilation, raw
authored-tree loader, repair path, eager JSON runtime backend, or JSON fallback.
A missing descriptor or database raises an unavailable error. A malformed
descriptor, unexpected database member, incomplete manifest, or invalid
component raises a format error. A descriptor/database or component digest
mismatch raises an integrity error. These failures occur before
authority-dependent calculation or filing proceeds. Components are loaded only
when a pinned operation asks for them; successful values remain in a bounded
generation-scoped cache.

Development checkpoint C may compare the indexed reader with an explicit
`dev.registry.indexed_authority_benchmark` JSON baseline. The baseline is
written from the same validated in-memory `AuthorityArtifact` as the exact
candidate, retains its logical generation identity, and eagerly decodes the
same complete public authority semantics. The benchmark verifies the
descriptor's physical database bytes before measuring. The baseline is a
measurement fixture, not a product module or a shipped fallback. Numeric
latency and memory results are pending until checkpoint C is run against a
stable candidate; no measured gain is implied by this API description.

The runtime contract is for ordinary filesystem-installed wheels, where the
descriptor and SQLite database have stable physical paths. Direct zip-import
execution is not supported: SQLite cannot open an archive member as its
read-only database.

`python -m dev.registry.conformance integrity` refuses a descriptor/database
publication whose recorded identity digest differs from the identity of the
live registry and its compiler environment. See
[Publish a validated runtime authority](../how-to/publish-runtime-authority.md)
for the canonical command, publication guarantees, currentness checks, and
recovery path.

## Filing-input contract shapes

The validated registry snapshot is the read-model authority for one modelo,
filing year, and period. It defines the casillas, formulas, bindings, repeating
fields, grounding, and export layout required by that filing revision. Source
business records remain owned by their encrypted domain repositories.

| Shape | Registry contract | Runtime projection |
| --- | --- | --- |
| Scalar binding | Typed source kind, selector, and aggregation | One numeric, enumerated, text, or date value for a binding id |
| Repeating row binding | Typed source kind plus grouping, row field, and aggregation | Values keyed by binding id and one-based row index, with validated detail rows |
| Formula | Typed operands and operation grounded by registry references | A calculated casilla observation |

A binding is not an attachable data blob. It is the contract by which an
enrolled source resolver projects an owned source record into one of these
filing-input shapes. Modelo 720 foreign assets use an enrolled repeating-row
projection. The binding-source taxonomy currently has no inventory member. No
calculation resolver is enrolled for the encrypted `InventoryLedger`, so it
remains a standalone business register.

Use the generated [application command reference](../cli/app.rst) to look up
modelo calculation, description, verification-report, and audit surfaces. Use
the {doc}`glossary </_generated/glossary>` for taxpayer-facing definitions.

## Python public API lookup

The generated [Cadrumo package API](../api/cadrumo.rst) is the entry point for
Python lookup. Public consumers import from `cadrumo` and its documented public
facades. The generated package tree lists the supported adapters, application,
core, domain, entrypoint, and locale surfaces.

There is no `aeat` Python import compatibility package. Names containing
`aeat` inside the `cadrumo` package identify the external authority adapter or
authority-owned vocabulary, not a second product API.
