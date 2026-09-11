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

## Runtime authority artifact

The runtime authority artifact is the versioned, digest-checked publication of
the validated AEAT registry intended for installed calculations and filing
exports. It is generated output, not a signed document: it carries no
signature, key, or certificate. `bundled_authority()` reads the packaged
`registry/authority/authority.json` and checks its schema version and content
digest before reconstructing typed authority data.

| Term | Meaning |
| --- | --- |
| Validated candidate | The registry and source-evidence inputs accepted by the development compiler. |
| Validation receipt | The digests captured for those inputs; a change before publication refuses the candidate. |
| Identity digest | The content-addressed identity of the candidate, recorded in the artifact so a stale artifact can be detected. |
| Authority artifact | The atomically written JSON publication containing the resolved authority. |
| Schema version | The artifact format identifier. Runtime refuses an unsupported version. |

The artifact is one canonical JSON object with exactly three members:
`schema_version`, `payload`, and `payload_sha256`. `payload_sha256` is the
SHA-256 digest of the canonical JSON of `schema_version` and `payload`
together. The digest detects a truncated, corrupted, or hand-edited file. It
doesn't authenticate the publisher.

The identity digest folds, for every registry file and every source-evidence
file, its path relative to its root and the SHA-256 of its content. Registry
files are digested with CRLF line endings read as LF. Source evidence is
digested byte for byte. Absolute paths, sizes, and timestamps never contribute,
so an identical checkout anywhere derives the same identity.

The current format is `cadrumo-authority-artifact-v3`. Its payload records
every schema field of the authority. Decimals and dates are JSON strings where
the schema types a field as a decimal or a date. A governed-fact value can be
text, an integer, a decimal, a boolean, or a date, and JSON cannot tell those
apart by value alone. Every non-text fact value is therefore written as an
object with one tag that names its type:

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
shape of a string. It refuses a `cadrumo-authority-artifact-v1` or
`cadrumo-authority-artifact-v2` artifact and names the format to republish in.

The `bundled_authority()` artifact-loading path has no source-compilation,
validation, repair, or cache fallback. A missing artifact raises an unavailable
error. A malformed frame, an unexpected frame member, or an invalid payload
raises a format error. A digest mismatch raises an integrity error. These
failures occur before authority-dependent calculation or filing proceeds.

Development tooling publishes with
`uv run --no-sync python -m dev.registry.pipeline publish-authority`, or
programmatically through the development-only
`dev.registry.pipeline.cli.publish_authority_candidate_workflow` API:

```python
publish_authority_candidate_workflow(
    registry_root=registry_root,
    source_root=source_root,
    artifact_path=artifact_path,
)
```

`python -m dev.registry.conformance integrity` refuses an artifact whose
recorded identity digest differs from the identity of the live registry and
source evidence. See [Publish a validated runtime authority](../how-to/publish-runtime-authority.md)
for the workflow and recovery path.

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
