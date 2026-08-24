---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:68c922f5d2acd0f05999408372775b494840884745f9039132c9da84f88bb374'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` reference: `modelo 136 2026 filing boundary`

Modelo 136 revision 2026 remains an active AEAT quarterly electronic-form obligation, but it is not fileable by Cadrumo. The official sources establish form completion and transmission, while AEAT's current record-design catalogue has no Modelo 136 entry. Without an official positional or schema contract, authoring a fixed-width layout would invent filing semantics. This finding records the filing boundary only; the separately governed non-filing authority grade is outside S14.

## Summary

### Official law and current procedure establish a form route, not a fichero route

BOE-A-2013-952 approves Modelo 136, sets its quarterly window, and requires electronic presentation under articles 10 and 11. Its paper alternative is generated exclusively by the AEAT service after completion of the electronic form. The electronic procedure requires the declarant to complete and transmit the approved form's data. It does not publish record types, byte positions, a field-length table, an XML schema, or a third-party fichero upload contract for Modelo 136.

AEAT's current GH09 procedure, retrieved on 2026-08-24, remains an electronic procedure: its only form surface is `Tramitación electrónica`, and it names the 2013 and 2018 orders as governing authority. The obligation is current; this does not convert the form into export-layout authority.

### The current AEAT record-design catalogue has no Modelo 136 source

AEAT's complete current `Modelos 100 al 199` record-design index lists published design artifacts for nearby models, including 130 and 131, then continues from 131 to 141. It contains no 136 entry. This agrees with the shipped corpus: there is no `modelo_136` record-design directory and none of the Modelo 136 legal source references is `kind = "record_design"`.

The BOE annex proves official form labels and calculations, not field positions. A visual form, screenshot, or reconstructed browser request cannot be promoted into fixed-width offsets.

### Supported filing boundary and future owner

`136/2026` remains a registered law-selected quarterly revision. Its separately governed non-filing grade, form provenance, deadline windows, completeness-manifest casillas, and formula graph remain valid registry evidence. This S14 adjudication does not authorize filing grade, a filing artifact, a fixed-width layout, a semantic map, or emitted bytes.

The filing-capability worklist refuses the revision with `BLOCKED on corpus: no record design is bundled for this modelo`. The focused Modelo 136 grounding suite passes; together those results show a valid form-grounded revision whose filing export is visibly refused.

This is a terminal refusal rather than a currently authorable export task. The present owner is that refusal disposition. If AEAT publishes qualifying evidence, `W02.P04.S28` must enroll the one remedy in the existing `aeat-export-fragment-generator-authority` plan; it must not start a parallel Modelo 136 export path.

Reconsider fileability only if all of these are true:

- AEAT publishes an official machine-readable Modelo 136 contract with a hash-pinned source and exact filing-year/period scope; a visual form or portal observation is insufficient.
- The source identifies a representation the established generator can validate and faithfully render, preserving exact schema or positional definitions rather than inferring them.
- The owning export plan supplies the reviewed semantic map, render profile, generated-tree proof, and production emitted-byte evidence required of every filing-grade revision.

## Sources

- AEAT record-design index, retrieved 2026-08-24: https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- AEAT Modelo 136 procedure GH09, retrieved 2026-08-24: https://sede.agenciatributaria.gob.es/Sede/procedimientos/GH09.shtml
- BOE-A-2013-952, Orden HAP/70/2013, arts. 5 and 7-11: https://www.boe.es/buscar/doc.php?id=BOE-A-2013-952
- `src/cadrumo/_data/registry/aeat/legal/modelo-136.toml`
- `src/cadrumo/_data/registry/aeat/modelos/136/revisions/2026/revision.toml`
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_136/files/modelo-136-procedure-record.html`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_136_grounding.py`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`
