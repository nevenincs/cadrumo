---
tags:
  - '#research'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:f55fbf4366ca86db74b186ca95a74edaa5a6a3e9661849cb5f9f5457e1f16641'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-08-m200-export-envelope-tag-adr]]"
---
# `aeat-export-fragment-generator-authority` research: `s61 dp30300 envelope authority`

Modelo 303 cannot enter semantic-map authoring while its `DP30300` variable envelope remains outside both the semantic authority and the generator. The five hash-pinned record designs contain the same thirteen-field prefix plus a Variable body, a relative closer, and a Variable total, but the current semantic map covers only fixed sheets and the generator refuses every retained variable envelope. The evidence also disproves an existing cross-model shortcut: AEAT's developer-company NIF is neither the taxpayer NIF nor the presenter NIF.

## Findings

### The missing denominator is one typed variable-envelope channel, not thirteen more fixed fields

The parser already represents a variable envelope separately as `RecordDesignIntermediateVariableEnvelope`, and the joined design preserves it unchanged (`dev/registry/_record_design_ir.py:141`, `dev/registry/_semantic_map_join.py:81`). `SemanticMap` has only fixed `records` and `entries` (`dev/registry/_semantic_map.py:128-139`), while `render_complete_export_tree` refuses whenever `joined.variable_envelopes` is non-empty (`dev/registry/_export_tree.py:149-152`). This matches the accepted generator ADR: a variable wrapper must not be truncated or treated as a fixed record, and generation remains blocked until a separate composition contract has byte-level proof (`.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:49`, `:64`, `:86`).

Across the five reviewed Modelo 303 sources in `src/cadrumo/_data/registry/aeat/legal/iva.toml:567-631`, the parser yields 2,032 fixed fields plus 65 envelope-prefix fields: 406, 406, 426, 429, and 430 total parser fields by epoch. Each epoch has one `DP30300` envelope with thirteen contiguous prefix fields ending at byte 328, a Variable body beginning at byte 329, one relative closer, and a Variable total. The prefix geometry and source descriptions are identical across the five epochs, but semantic authority must still remain source-hash and exact-anchor bound rather than copied by resemblance.

### Eleven prefix slots have direct wire authority; two require explicit product authority

The official design directly supplies the `<T`, `303`, discriminant `0`, `0000>`, `<AUX>`, three reserved blank spans, and `</AUX>` values; filing year and period are existing draft coordinates. These eleven positions need no new filing producer identity. The body is an ordered composition of generated page records, and the closing tag is a computed function of the same modelo, discriminant, year, and period coordinates; the relative closer and Variable total are codec/composition facts, not business producers.

The remaining four-character “Versión del programa” and nine-character “NIF Empresa Desarrollo” slots are not literals. AEAT introduces both with “A cumplimentar por las entidades desarrolladoras (EEDD)”, states that the former identifies the version of the software developed by the development entity, and states that the latter is that entity's NIF (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_303/files/03-303-ejercicio-2023-actualizado-14-12-23-376-kb-xlsx.xlsx.extracted.md:24-27`). The extracted Markdown is only a review locator; the hash-pinned workbook remains the wire authority. The source does not by itself decide whether Cadrumo, a locally authored tool, or another filing product is an EEDD or when non-EEDD producers leave these slots blank.

### Program version has a dormant candidate but no accepted four-byte derivation

The package exposes version `0.2.2`, but AEAT's field is four characters and existing application code explicitly says the AEAT program identifier is distinct from package `__version__`. A dormant `_PROGRAM_VERSION_CODE = "A001"` exists only in `src/cadrumo/application/modelo/_export.py:163-169`; exact production search finds no consumer. Conversely, `program_version` is deliberately rejected from `FilingProducerKey` in `src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py:50-66`. Therefore neither the package version nor `A001` is currently an authorized generated value. The ADR must decide one product-owned, validated four-character program-code authority or require fail-closed configuration; it must not silently reinterpret a release version.

### Developer NIF is a separate product identity and current presenter reuse is wrong

`FilingProducerSnapshot` keeps `taxpayer_tax_id` and `presenter` as distinct facts (`src/cadrumo/application/filing/_producer_snapshot.py:279-290`), and `FilingProducerKey` now has separate `presenter.tax_id` and `taxpayer.tax_id` identities (`src/cadrumo/core/_filing_producer_key.py:18-20`). Neither denotes the software-development entity. Exact production census finds no developer-company NIF authority or configuration.

The accepted M200 envelope ADR currently describes “NIF empresa desarrollo” as `presenter_nif`-equivalent and instructs a `presenter_nif` header at offset 101 (`.vault/adr/2026-08-08-m200-export-envelope-tag-adr.md:88-94`, `:193-201`). That conflicts with the official definition above. S61 must not propagate this mapping. The ADR corpus must amend or supersede that statement and any implementation depending on it; M303 generation must refuse when an explicit developer-company NIF is required but unavailable.

### The evidence favors a dedicated envelope semantic and composition authority

Three options remain for the ADR:

1. Extend fixed `SemanticMapEntry` and treat `DP30300` as another record. This conflicts with the accepted parser/generator boundary and loses body/closer/total composition, so the evidence rejects it.
2. Keep envelope semantics outside reviewed maps and hardcode the thirteen positions in the generator. This creates a second, ungrounded authority and cannot bind five source hashes or explain the two product-owned values, so the evidence rejects it.
3. Add a separately typed, exact-anchor envelope map joined beside fixed records, plus one composition renderer and an explicit product-software-identity applicability/result boundary. This preserves the parser distinction, allows exhaustive 65-field census, binds all wire slots to reviewed sources, and can distinguish an attested EEDD identity from an adjudicated non-EEDD blank outcome. The evidence favors this option.

Under the favored option, source constants, reserved blanks, filing year, period, body membership, closer template, and total rule remain semantic/composition entries tied to the exact source SHA and anchor. When EEDD metadata applies, program code and developer-company NIF are explicit product metadata with closed validation and no fallback to package version, taxpayer, or presenter. A non-EEDD blank result is admitted only if product/legal adjudication explicitly establishes its applicability. One canonical renderer consumes the joined envelope contract and generated fixed records; the old blanket refusal is deleted only after exact five-source structural and byte proofs pass.

The ADR must also settle record occurrence and order inside the Variable body rather than infer it from parser sheet order: which of `DP30301` through `DP30305` and `DP303DID` are always emitted, which are applicability-selected, and how repeated `DP30302` rows are ordered. It must bind the composition and product-identity authority to provenance, and it must specify whether embedding a developer NIF in a public distribution is owner-approved.

### Spanish IVA naming is clean internally; the remaining `IVA/IVA` occurrence is external vocabulary

The current Spanish-stem conformance gate passes and exact production identifier census finds no authored `VAT` stem. The only production `IVA/IVA` text is the official AEAT locator path mirrored in the legal catalogue and external-constants authority; it must remain byte-exact as external wire vocabulary. S61 introduces only Spanish internal `iva` names and must not create `vat`, `iva_iva`, or mixed aliases.

## Sources

- `dev/registry/_record_design_ir.py:141-169`
- `dev/registry/_semantic_map.py:128-139`
- `dev/registry/_semantic_map_join.py:81-135`
- `dev/registry/_export_tree.py:149-154`
- `src/cadrumo/_data/registry/aeat/legal/iva.toml:567-631`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_303/files/03-303-ejercicio-2023-actualizado-14-12-23-376-kb-xlsx.xlsx.extracted.md:18-27`
- `src/cadrumo/application/modelo/_export.py:163-169`
- `src/cadrumo/application/filing/_producer_snapshot.py:279-290`
- `src/cadrumo/core/_filing_producer_key.py:18-20`
- `src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py:50-66`
- `.vault/adr/2026-08-10-aeat-export-fragment-generator-authority-adr.md:21-88`
- `.vault/adr/2026-08-08-m200-export-envelope-tag-adr.md:88-94`
- `.vault/adr/2026-08-08-m200-export-envelope-tag-adr.md:193-201`
- `src/cadrumo/tests/test_spanish_iva_stem_conformance.py`
