---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e3236bc87e5cff7300163808d97446803412433216a70959f8d243dc470d428a'
step_id: 'S37'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Add explicit reviewed value-policy semantics for selected-1-unselected-0 numeric checkboxes and four-digit-year-final-two-digits fields to the export schema, filing writer, parser, verifier, and registry record renderer, with strict invalid-value refusal and real emitted-byte tests

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/adapters/outbound/aeat/export/`

## Description

- Add the closed public `ExportValuePolicy` axis and one exact semantic-to-wire projector.
- Validate policy-bearing export fields against their complete unsigned integer wire shape.
- Reuse the projector in the filing writer, verifier, and active registry record renderer.
- Validate checkbox and short-year tokens in the fixed-width parser before generic integer parsing.
- Key verifier policy lookup by record and field identity and prove repeated field identifiers across records.
- Include `value_policy` in loader-semantic normalization and advance that normalization contract.
- Reuse the two public runtime policy members from the reviewed render-profile authority.
- Add schema, projector, parser mutation, emitted-byte, verification, adapter, provenance-digest, and canonical-home guards.

## Outcome

The runtime value-policy axis is closed to `selected-1-unselected-0` and `four-digit-year-final-two-digits`. An absent policy is inert and performs no field-shape inference. Checkbox projection accepts only absent, empty, boolean, or exact numeric/string zero and one states. Short-year projection accepts only a non-boolean four-digit integer or canonical four-ASCII-digit string and emits the final two digits. The parser independently refuses any policy-bearing wire slot outside exact ASCII `0`/`1` or two-digit year form.

The filing writer and active registry renderer emit the same projected bytes, while verification projects the expected draft value through the same public function before comparison. Record-scoped lookup prevents two records carrying the same field identifier from selecting each other's policy. The S31 render-profile schema now hydrates its two runtime policies through the shared enum rather than redeclaring those tokens, and loader-semantic digest version 2 includes the optional field so policy drift changes provenance.

Focused production and development-tool verification passed with 121 tests. The broader schema, export-parser, and implicit-decimal slice passed with 68 tests. Scoped Ruff formatting and lint passed, strict BasedPyright reported zero diagnostics, and the import-structure gate passed. Independent formal review found no critical, high, or medium issues; its one low exception-boundary finding was remediated and regression-tested before closure.

## Notes

Fresh semantic searches before and after implementation found one canonical runtime owner after consolidation. The S31 development profile remains the reviewed authoring authority and consumes the shared enum only for the two runtime policies; S32 must map those same members during generator integration and must not redeclare them.

Adjacent pre-existing fixed-width drift remains outside this exact two-policy slice: the application and adapter disagree on generic integer, money, boolean, padding, and sign coercion. The newly ordered S38 plan prerequisite owns their consolidation before S32 and final byte proofs. S37 does not route its policy values through those lossy behaviors.

A broad test attempt first encountered active peer Modelo 303 revision-split validation failures and later a transient import race between peer relation-validation modules. Both were outside S37 ownership; the focused and broader owner slices passed after the peer import surface stabilized. The tree-wide relative-import gate remains red on the committed absolute import in `test_record_design.py`; S37's new tests use relative imports and the dedicated import-structure gate is green.
