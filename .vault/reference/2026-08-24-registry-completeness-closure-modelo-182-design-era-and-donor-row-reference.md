---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8a142efd29440da205997b8d834c1e3fcf0b107811ae90de3b366125a6016bf2'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` reference: `Modelo 182 design-era and donor-row filing boundary`

## Summary

Modelo 182 revision `2007-y-siguientes` is supported only for its declared
applicability reach. It is not fileable by Cadrumo for any filing year. The
current corpus supplies exact AEAT record-design evidence only for exercises
2024 and 2025; it supplies no selected, hash-pinned design for 2007--2023 or
2026 onward. Even in the two evidenced exercises, the application has neither
the complete declarant/type-2 value lifecycle nor a filing layout. Promoting
the revision or filling an export layout from its five present donor bindings
would produce a structurally false declaration.

## Official filing subject and design-era evidence

BOE-A-2007-18192 approves the Modelo 182 record design and requires
computer-readable supports to conform to its physical and logical designs
(article 2). Article 3 identifies the declarants as recipient entities that
issue the donation certificate, plus the named political-party cases. A donor
claiming a deduction is not, merely by being the donor, the Modelo 182 filer.
Accordingly a filing feature would need an explicit product scope for an
eligible recipient entity; donor-deduction data alone cannot justify a filing
claim.

The shipped source catalogue has two authentic, hash-pinned AEAT PDFs:
`aeat-dr-182-2024`, 413,403 bytes, SHA-256
`6ed486256193f31e81d19b3f464ee15fbdeaa9251ec825349b3263ced5ff381f`,
and `aeat-dr-182-2025`, 276,709 bytes, SHA-256
`90eac5615609f6bec7bf5c9fa9386253e80bd0e26997747fbb1160c3da180831`.
They identify themselves as exercises 2024 and 2025 respectively. The
registry's earlier `enrolled-modelo-182-layout` citation is only the 1,155-byte
BOE procedure excerpt and its own catalogue note correctly says it has no
annex or record-layout content.

The 2025 source is not evidence of an unchanged era. BOE-A-2025-25389 changes
the type-2 `RECURRENCIA DONATIVOS` field at position 132 and makes that change
applicable first to exercise 2025. Therefore the 2024 and 2025 designs need
their own exact scopes; neither can demonstrate the unbounded
`2007-y-siguientes` revision. The missing 2007--2023 and 2026-onward evidence
is a shipped-corpus and temporal-selection gap, not a licence to infer that
the original design or later design remains identical.

## Donor-row filing prerequisites are not met

The two AEAT designs require a type-1 declarant record as well as a complete
type-2 declared-person record. The type-2 record carries more than donor NIF,
name, amount, deduction percentage, and recurrence: it contains, as
applicable, representative identity, province, operation key, in-kind marker,
autonomous-deduction fields, declared-person nature, revocation and its year,
asset identification, and protected-estate fields. The type-1 record also
requires the declarant's identity and declaration-level control, count, total,
and nature fields. No current Cadrumo producer owns or validates that complete
set.

The current `DonativoDonorObservation` and its five row bindings are useful
input scaffolding, not an export contract. `donativo_donor` remains in
`DEFERRED_SOURCE_KINDS`, so it yields an unhandled-source advisory rather than
being supplied by an enrolled live resolver. Its observation model also has
`country_code` while the row-field literal does not; the existing
detail-row-field gate names that as tolerated latent residue only because
Modelo 182 has no export layout. An eventual exporter must adjudicate this
against the actual type-2 province requirement rather than silently projecting
or discarding it.

The present row fold is also incompatible with the official record cardinality.
It groups by country and donor NIF, sums amounts, retains one deduction rate,
and collapses recurrence to a boolean encoded as `1` or `0`. Both AEAT designs
require separate declared-person records when the same donor has different
deduction percentages or mixes cash and in-kind donations. The 2025 design
requires the applicable recurrence state to be `1` or `2`, not this boolean
model's false value. These are value-lifecycle gaps, not renderer details, so
an export layout cannot be authored first.

## Adjudication, owner, and reconsideration

**Disposition: no Modelo 182 filing capability is shipped.** Keep
`authority_grade = "applicability"`, no export layout, and the visible deferred
source diagnostic. This is a mixed refusal:

- 2007--2023 and 2026 onward lack a selected exact record-design source in the
  shipped corpus.
- 2024 and 2025 have official source material but lack an approved recipient-
  entity filing scope, complete source lifecycle, a complete schema/producer
  projection, and the governed export proof.

The existing source owner is `2026-08-22-source-casilla-integration-plan`,
Phase `W05.P17`: `S100` adjudicates recipient/donor-row ownership, `S101`
enrolls the resolver, `S102` proves persistence, diagnostics, provenance,
replay, review, and export, and `S103` closes the census disposition. It is the
only legitimate home for live donor-row evidence and must not be bypassed by
manual bindings or an export-only writer. `W02.P04.S26` of the closure plan
must route the exact era split and source scopes to
`2026-08-14-registry-temporal-coverage-plan`; `W02.P04.S28` must route any
eventual layout, semantic map, generated-tree, and emitted-byte work to
`2026-08-10-aeat-export-fragment-generator-authority-plan`.

Reconsider fileability only after all of the following are independently
landed and reviewed:

1. The revision is split or otherwise bounded to exact, hash-pinned designs for
   every claimed exercise, including the 2025 recurrence amendment.
2. An accepted product decision names eligible recipient entities as the filing
   population and assigns typed owners for every type-1 and type-2 value.
3. `W05.P17` supplies the durable donor-row source, resolver, provenance,
   diagnostics, and record-cardinality preservation; in particular it cannot
   merge different rate or in-kind records.
4. The export authority provides a full reviewed semantic map and render
   profile, validates generated fragments through the canonical publisher, and
   proves the production fixed-width bytes at official offsets.
5. The selected revision is promoted only after its complete evidence and
   filing artifact meet the authority-grade gates. No remote AEAT submission is
   authorized by this adjudication.

## Sources

- BOE-A-2007-18192, Orden EHA/3021/2007, articles 2 and 3, retrieved
  2026-08-24: https://www.boe.es/buscar/doc.php?id=BOE-A-2007-18192
- BOE-A-2025-25389, Orden HAC/1430/2025, article 2 and final provision,
  retrieved 2026-08-24: https://www.boe.es/buscar/doc.php?id=BOE-A-2025-25389
- AEAT Modelo 182 procedure, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI02.shtml
- AEAT Modelo 182 design, exercise 2025, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_182_2025.pdf
- `src/cadrumo/_data/registry/aeat/legal/modelo-182.toml`
- `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2007-y-siguientes/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_182/`
- `src/cadrumo/domain/calculations/registry/_donativo_bindings.py`
- `src/cadrumo/application/calculations/_row_set_assembly.py`
- `src/cadrumo/application/aggregation/_source_mesh.py`
- `src/cadrumo/domain/calculations/registry/tests/test_detail_row_field_declaration_coverage.py`
- `2026-08-22-source-casilla-integration-plan`
- `2026-08-14-registry-temporal-coverage-plan`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`
