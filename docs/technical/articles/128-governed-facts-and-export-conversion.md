# Governed facts and export conversion

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-128` · **Topic:** [Tax calculation domain](../topics/tax-calculation-domain.md)

<!-- preserved:article -->
## Scope and method

This chunk contains 16 registry-domain modules, 4,243 physical lines, 171,734 bytes, and 38,053 measured `o200k_base` proxy tokens. I read all seven bounded pages, including the complete fact schema and both directions of export conversion. Static inspection only; no application code or tests were run and no sources were changed.

## Governed-fact model and resolution

The facts package defines seven closed payload families: scalar, bracket, mapping, entity set, override, event and multi-output. Atoms retain typed values, with explicit tagged JSON representations for decimals, dates, integers and booleans; deserialization only hydrates the tags when the reader opts into the tagged form, and tagged decimals/dates must be canonical. Mapping keys are unique by typed identity; brackets and multi-output bands are ordered, non-overlapping intervals; event output names are unique. These constraints make registry data an explicit typed authority instead of loosely interpreted TOML strings. Typed atom JSON codec (`src/cadrumo/domain/calculations/registry/facts/atoms.py`) Closed payload families (`src/cadrumo/domain/calculations/registry/facts/payloads.py`)

A `GovernedFact` is a stable semantic identity whose variants share one payload family. Variants have unique revision IDs and exact selector/date/period tracks, legal or source evidence, source citations restricted to declared sources, and ownership semantics. Generated variants must retain source revision IDs; authored variants cannot claim them. Within a track, overlapping windows require an explicit precedence path, the precedence graph must be acyclic, and predecessor contracts validate temporal continuity. A first omitted lower bound propagates to the registry support floor; explicit bounds remain real gaps rather than being silently bridged. Variant evidence and ownership (`src/cadrumo/domain/calculations/registry/facts/variants.py`) Fact track and predecessor validation (`src/cadrumo/domain/calculations/registry/facts/schema.py`)

Resolution checks fact identity, family, unique query selector names and the support envelope, then matches exact date axis, typed selector identity and period selection. A uniquely winning variant is chosen through the precedence graph; no candidate yields `GovernedFactNotApplicableError`, while ambiguous winners and malformed query/fact combinations remain registry validation failures. The resolved object retains the authority digest, review state, legal/source references and citations, matched selectors, variant and source IDs, provider, temporal window and projection direction. That provenance gives downstream projections a stable audit trail and distinguishes law-authorized absence from corruption or an unsupported query. Validated query and winner resolution (`src/cadrumo/domain/calculations/registry/facts/resolution.py`) Winner precedence (`src/cadrumo/domain/calculations/registry/facts/resolution.py`)

Reusable fact readers keep projection policy explicit. `StringMappingFact` requires a supplied governed authority or active validation scope, checks string-to-string entries, applies declared whitespace treatment, and returns an immutable mapping. The token helper only accepts a value once its projected token belongs to the selected fact's declared set. String-mapping contract (`src/cadrumo/domain/calculations/registry/facts/string_mapping.py`) Declared token guard (`src/cadrumo/domain/calculations/registry/facts/declared_token.py`)

## Export parsing, rendering and value semantics

Export literals backed by governed facts are materialized during registry validation, and only when the selected mapping key has the same nonblank value across every supported filing year. This prevents a supposedly static record constant from being frozen from an arbitrary year. The export semantic vocabulary also separates the single payload axis permitted for each field kind from the closed computed-key and draft-attribute vocabularies. Static export literal resolution (`src/cadrumo/domain/calculations/registry/export_literal_fact.py`) Semantic producer vocabulary (`src/cadrumo/domain/calculations/registry/export_semantics.py`)

`ExportValuePolicy` provides explicit, closed transforms for checkbox flags, years, dates, integer and decimal amounts, digit identifiers, split integer/fractional fields, and a documented design-mistyped prose field. Projectors reject booleans masquerading as years or amounts, floats where exact decimals are required, noncanonical decimal strings, invalid dates, out-of-range calendar parts, malformed ASCII digit runs, and control characters in prose. Policies whose source cannot be reconstructed from a leaf wire value retain a `ParsedExportPolicyWireValue` rather than inventing a semantic amount. An absent checkbox is explicitly `0`; other policies leave absence to the field's declared blank fill. Closed export value policies (`src/cadrumo/domain/calculations/registry/export_value_policy.py`) Projection and wire validation (`src/cadrumo/domain/calculations/registry/export_value_policy.py`)

The fixed-width codec validates coherent padding, justification and sign declarations; renders fields at declared width; leaves optional required values refused rather than zero-filled; and applies the design's signed convention, including a leading `N` that displaces one magnitude digit or an explicitly reserved sign byte. Record rendering encodes into the declared single-byte encodings, checks exact byte width, and refuses overlapping slots. Parsing mirrors the same rules, recognizes canonical absent fills as absent, verifies literals and filler, checks exact field and record widths/line endings, and rejects noncanonical unpolicyed wire text. Round-trip handling for non-invertible policies deliberately retains raw tokens. Field/record rendering (`src/cadrumo/domain/calculations/registry/fixed_width_codec.py`) Record assembly and overlap checks (`src/cadrumo/domain/calculations/registry/fixed_width_codec.py`) Canonical fixed-width parse (`src/cadrumo/domain/calculations/registry/fixed_width_parser.py`)

The payload parser handles fixed-width records and XML dictionary layouts. It validates auxiliary/filing envelope extents and relative closing tags, reads repeated binding rows until a next-record marker, and permits only line-ending bytes after the declared content. XML is parsed with `defusedxml`; dictionary bytes decode as UTF-8 or CP1252, dictionary path corrections must match real dictionary field IDs, and XML values follow declared numeric/boolean types. Dictionary casilla IDs preserve official spelling, accepting only numeric IDs or source-authorized single uppercase letters; placeholders remain non-casilla rows. A local quality follow-up is that malformed non-comment dictionary lines that do not match the row regex are skipped, and the parser refuses only if no rows at all parse. If a dictionary can contain malformed data rows alongside valid ones, silently omitting them may conceal a partial projection; tests or stricter diagnostics should establish whether that is intended. Export payload parsing (`src/cadrumo/domain/calculations/registry/export_parse.py`) Published XML dictionary rows (`src/cadrumo/domain/calculations/registry/export_parse.py`)

## Calculation seeds and obligation taxonomy

`formula_initial_values` builds numeric seeds only for numeric, noncomputed, non-projection casillas. Text values enter through the text channel or remain absent; materialized observations require both legal and source provenance and reject numeric observations for text-family casillas. Numeric inputs must name declared manual/input casillas; computed, projection-only and text casillas are refused. Observation-backed bound casillas must obtain their value through binding values, and any parallel input projection must equal that source value. Equivalent bindings prevent one missing alternative from being defaulted when another supplies a value. Prior-filing and relation-prefill sources receive zero only when the selected target period has no required anchor; otherwise a missing source is a refusal. Observation materialization (`src/cadrumo/domain/calculations/registry/formula_initial_values.py`) Initial-value validation (`src/cadrumo/domain/calculations/registry/formula_initial_values.py`)

The dated foreign-asset obligation catalogue projects the declared groups and legal references, validates asset-class keys against the closed core enum, and requires every declared group to be mapped by at least one class. It supports both group choice validation and the projection from an asset class or selected legal references to its obligation group. Obligation catalogue (`src/cadrumo/domain/calculations/registry/foreign_asset_obligation_catalogue.py`)

## Security, quality and limits

The main trust boundaries here are governed-fact authority, published dictionary bytes, and filing payloads. The code refuses missing or mismatched fact authority, preserves evidence metadata, uses a hardened XML parser, applies exact typed projections, and validates fixed-width geometry rather than tolerating malformed rows. Static policy tokens do not run embedded data as instructions. Remaining validation depends on upstream authority publication, review of legal/source evidence, application-layer payload assembly, and tests of deployed layouts. I did not execute tests, so findings describe the inspected contracts and follow-up candidates, not runtime-verified behavior.

## Coverage appendix

All 16 assigned files were fully read across seven bounded pages. Line counts are physical lines.

- registry/export_literal_fact.py (`src/cadrumo/domain/calculations/registry/export_literal_fact.py`) — 1–84
- registry/export_parse.py (`src/cadrumo/domain/calculations/registry/export_parse.py`) — 1–590
- registry/export_semantics.py (`src/cadrumo/domain/calculations/registry/export_semantics.py`) — 1–67
- registry/export_value_policy.py (`src/cadrumo/domain/calculations/registry/export_value_policy.py`) — 1–485
- registry/facts/__init__.py (`src/cadrumo/domain/calculations/registry/facts/__init__.py`) — 1
- registry/facts/atoms.py (`src/cadrumo/domain/calculations/registry/facts/atoms.py`) — 1–97
- registry/facts/declared_token.py (`src/cadrumo/domain/calculations/registry/facts/declared_token.py`) — 1–41
- registry/facts/payloads.py (`src/cadrumo/domain/calculations/registry/facts/payloads.py`) — 1–249
- registry/facts/resolution.py (`src/cadrumo/domain/calculations/registry/facts/resolution.py`) — 1–539
- registry/facts/schema.py (`src/cadrumo/domain/calculations/registry/facts/schema.py`) — 1–256
- registry/facts/string_mapping.py (`src/cadrumo/domain/calculations/registry/facts/string_mapping.py`) — 1–200
- registry/facts/variants.py (`src/cadrumo/domain/calculations/registry/facts/variants.py`) — 1–129
- registry/fixed_width_codec.py (`src/cadrumo/domain/calculations/registry/fixed_width_codec.py`) — 1–693
- registry/fixed_width_parser.py (`src/cadrumo/domain/calculations/registry/fixed_width_parser.py`) — 1–191
- registry/foreign_asset_obligation_catalogue.py (`src/cadrumo/domain/calculations/registry/foreign_asset_obligation_catalogue.py`) — 1–161
- registry/formula_initial_values.py (`src/cadrumo/domain/calculations/registry/formula_initial_values.py`) — 1–460
<!-- /preserved:article -->
