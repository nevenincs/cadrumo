---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:711f623c5d260891c1abad79d0020335a36770f239ca7c6f13c1faa69c3a7308'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` research: `M182 row source grounding`

Modelo 182 has two non-substitutable fact families: the Article-3 filer/header in record type 1 and the declared-person/detail record in type 2. The official 2025 record design makes both the header nature and an administrator's protected-estate-holder identity value-bearing controls. The current donor worksheet carrier is neither family in full and has no secure authoritative owner, so the evidence supports retaining the visible deferral pending a later, separately proven source slice.

## Findings

### Article 3 establishes the filer population, not the donor population

Article 3 of Orden EHA/3021/2007 names as obliged filers: recipient entities that issue the qualifying certificate, qualifying political parties, and protected-estate holders or, where they lack capacity, their administrators. Article 4 then separates the declarant's own identity from the donor, contributor, and beneficiary information to be reported. A person who makes a deductible donation is consequently a declared-person fact, not evidence that the person is the Article-3 filer. https://www.boe.es/buscar/doc.php?id=BOE-A-2007-18192

The 2025 AEAT design implements that distinction in separate records. Type 1 contains the declarant NIF and denomination, record count, aggregate amount, and `NATURALEZA DEL DECLARANTE` at position 160. Its values distinguish the Ley 49/2002 recipient, the specified foundation/association, protected-estate holder or administrator (`3`), and political-party group (`4`). Type 2 repeats the type-1 exercise and declarant NIF before identifying the declared person. A donor row therefore cannot supply, select, or infer the header's filer identity, nature, control totals, or declaration controls. `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_182/files/01-182-ejercicio-2025.pdf.extracted.md:22` https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_182_2025.pdf

### Nature 3 and administrator-holder identity are independent type-1/type-2 axes

For type-1 nature `3`, the official design identifies the declarant as the protected-estate holder or its administrator. Where the declarant is the administrator, type 2 positions 133--141 require the protected-estate holder's NIF and positions 142--181 require the holder's name. These fields are neither the declarant's NIF nor the donor's NIF/name and cannot be reconstructed from either. The same design makes several type-2 axes conditional on header nature and the row key: deduction percentage and recurrence are not generic donor attributes, and a nature-3 record leaves the deduction percentage blank. `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_182/files/01-182-ejercicio-2025.pdf.extracted.md:373` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_182/files/01-182-ejercicio-2025.pdf.extracted.md:576` https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_182_2025.pdf

### The current donor carrier is partial and has synthetic identity

`DonativoDonorObservation` carries only a worksheet `source_id`, donor NIF/name, country, a derived transaction date, amount, deduction percentage, and a boolean recurrence flag. Its bindings expose just five row fields. It does not retain the type-1 declarant/header family; type-2 representative, province, key, in-kind marker, regional-deduction, declared-person nature, revocation/year, asset identity, or administrator-holder facts; or the official recurrence coding and conditions. `src/cadrumo/domain/calculations/registry/_donativo_bindings.py:90` `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2025/bindings/0001-bindings.toml:3`

The carrier is also lossy at the required record grain. Its fold keys only by country and donor NIF, sums all amounts into the first observed deduction percentage, collapses recurrence to `1`/`0`, and cannot distinguish cash from in-kind donations. AEAT requires independent type-2 records for a single declared person with different deduction percentages and for a mix of cash and in-kind donations; recurrence is `1` or `2` in the circumstances the design names. `src/cadrumo/domain/calculations/registry/_donativo_bindings.py:209` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_182/files/01-182-ejercicio-2025.pdf.extracted.md:443` https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_182_2025.pdf

The worksheet assembler assigns `detalle:per_donativo_donor:row-{row_index}` and defaults the date to 31 December of the filing year. The scoped persistence search finds no Modelo-182/donativo secure repository or secure-object namespace. The census therefore correctly identifies an assembler, not an authority, and the mesh keeps `DONATIVO_DONOR` deferred. The active Censo read is only the authenticated taxpayer's own identity, refuses representation, does not persist the read itself, and deliberately does not project a parsed identity name; it cannot be treated as an owner of a recipient entity, political-party filing class, protected-estate administrator, or protected-estate holder. `src/cadrumo/application/calculations/_row_set_assembly.py:1035` `src/cadrumo/application/aggregation/_source_mesh.py:302` `src/cadrumo/_data/source_connectivity/census.toml:270` `src/cadrumo/application/live/__init__.py:494` `src/cadrumo/application/user_profile/_censo_sync.py:224`

### The current temporal and export boundaries reinforce a bounded deferral

The temporal S44 record selects only the exact 2025 design and preserves refusal for 2007--2024 and 2026 onward. The revision remains `authority_grade = "applicability"` and has no export layout. Its current five bindings are explicit deferred-source scaffolding, not a declaration that the design, owner, persistence path, or fixed-width output is complete. `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2025/revision.toml:2` `src/cadrumo/domain/calculations/registry/_export.py:100` `.vault/exec/2026-08-14-registry-temporal-coverage/2026-08-14-registry-temporal-coverage-W02-P05-S44.md`

The evidence favours retaining the existing donor ingress-blocked disposition and treating the unowned header and administrator-holder axes as explicit prerequisites, not donor-row defaults. A future decision must select one secure owner per official fact family, preserve the type-1/type-2 relationship and official row cardinality, define immutable source identities and fingerprints, and establish the conditional field matrix before S101 can propose resolver enrollment. This research neither chooses such owners nor authorizes a resolver, binding, registry, export, or census-disposition mutation.

## Sources

- https://www.boe.es/buscar/doc.php?id=BOE-A-2007-18192
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_182_2025.pdf
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_182/files/01-182-ejercicio-2025.pdf.extracted.md:22`
- `src/cadrumo/_data/manual_corpus_text/aeat_official/disenos_registro/modelo_182/files/01-182-ejercicio-2025.pdf.corpus_text.json:1`
- `src/cadrumo/domain/calculations/registry/_donativo_bindings.py:90`
- `src/cadrumo/application/calculations/_row_set_assembly.py:1035`
- `src/cadrumo/application/aggregation/_source_mesh.py:302`
- `src/cadrumo/_data/source_connectivity/census.toml:270`
- `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2025/revision.toml:2`
- `src/cadrumo/_data/registry/aeat/legal/modelo-182.toml:75`
- `.vault/exec/2026-08-14-registry-temporal-coverage/2026-08-14-registry-temporal-coverage-W02-P05-S44.md`
