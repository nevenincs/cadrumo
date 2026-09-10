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

The runtime authority artifact is the signed, versioned publication of the
validated AEAT registry intended for installed calculations and filing exports.
Its identity digest identifies the validated development generation. When
published and packaged, `bundled_authority()` reads
`registry/authority/authority.json`. It verifies the schema version, content
digest, and Ed25519 signature against its compiled public trust anchor before
reconstructing typed authority data.

| Term | Meaning |
| --- | --- |
| Validated candidate | The registry and source-evidence inputs accepted by the development compiler. |
| Validation receipt | The digests captured for those inputs; a change before publication refuses the candidate. |
| Authority artifact | The atomically written signed JSON publication containing the resolved authority. |
| Trusted publisher | The release holder of the private key corresponding to the package's compiled public key. |
| Schema version | The artifact format identifier. Runtime refuses an unsupported version. |

The current format is `cadrumo-authority-artifact-v2`. Its payload records
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
shape of a string. It refuses a `cadrumo-authority-artifact-v1` artifact and
names the format to republish in.

The `bundled_authority()` artifact-loading path has no source-compilation,
validation, repair, or cache fallback. A missing artifact raises an unavailable
error. A malformed artifact or invalid signature encoding raises a format
error. A digest or signature failure raises an integrity error. These failures
occur before authority-dependent calculation or filing proceeds.

Release tooling uses the development-only
`dev.registry.pipeline.cli.publish_authority_candidate_workflow` API:

```python
publish_authority_candidate_workflow(
    registry_root=registry_root,
    source_root=source_root,
    artifact_path=artifact_path,
    signing_private_key_hex=signing_private_key_hex,
)
```

The caller owns all four values. In particular, the caller must obtain
`signing_private_key_hex` through its approved external release-secret system.
The project provides no private key, release-secret provider, or runtime
override for the trusted public key. See [Publish a validated runtime authority](../how-to/publish-runtime-authority.md)
for the release workflow and recovery path.

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
