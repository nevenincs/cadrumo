---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7bd93e3dea399c65c84f7a3891deb81bd3d17510f6062bf4d3e11f5fe6fb6263'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` reference: `modelo 136 2026 filing boundary`

Modelo 136 revision 2026 is a current AEAT quarterly electronic-form obligation, but it is not fileable by Cadrumo. The official sources establish form completion and transmission, while the current AEAT record-design catalogue has no Modelo 136 entry. With no official positional or schema contract, authoring a fixed-width layout would invent filing semantics. Retain the revision only at its declared applicability grade and preserve the explicit filing refusal.

## Summary

### Official law and current procedure establish a form route, not a fichero route

BOE-A-2013-952 approves Modelo 136, states its quarterly presentation window, and requires electronic presentation through the conditions in articles 10 and 11. Its paper alternative is generated exclusively by the AEAT service after the electronic form has been completed. The electronic procedure specifically requires the declarant to complete and transmit the approved form's data. It does not publish record types, byte positions, a field-length table, an XML schema, or a third-party fichero upload contract for Modelo 136.

AEAT's current GH09 procedure, retrieved on 2026-08-24, remains an electronic procedure: its only form surface is `Tramitación electrónica`, and it names the 2013 and 2018 orders as governing authority. That confirms that the obligation remains active; it does not convert the form into an export-layout authority.

### The current AEAT record-design catalogue has no Modelo 136 source

AEAT's complete current `Modelos 100 al 199` record-design index lists published design artifacts for nearby models, including 130 and 131, then continues from 131 to 141. It contains no 136 entry. This catalogue-level negative result agrees with the shipped corpus: there is no `modelo_136` record-design directory and none of the Modelo 136 legal source references is `kind = "record_design"`.

The cited BOE annex is useful proof of official form labels and derived calculations, but it is not a field-position contract. A screenshot, form PDF, or reconstructed browser request must not be promoted into fixed-width offsets.

### Supported boundary and future owner

`136/2026` is supported as a registered, law-selected quarterly revision at its declared `applicability` grade. Its official form provenance, deadline windows, completeness-manifest casillas, and formula graph remain valid evidence for that limited boundary. It is not calculation-grade or filing-grade, and Cadrumo must not claim a filing artifact for it.

The filing-capability worklist deliberately refuses this revision with `BLOCKED on corpus: no record design is bundled for this modelo`. The focused Modelo 136 grounding suite passes; that combination proves a genuine form-grounded registry entry while preventing an unsupported export capability.

This is a terminal refusal rather than a presently authorable export task. The current owner is the refusal disposition itself. If the condition below occurs, `W02.P04.S28` must enroll the single implementation remedy in the existing `aeat-export-fragment-generator-authority` plan; it must not start a parallel Modelo 136 export path.

Reconsider fileability only if all of these are true:

- AEAT publishes an official machine-readable declaration contract for Modelo 136, with a hash-pinned source and exact filing-year/period scope. A visual form or portal observation is insufficient.
- The source identifies an export representation that the established generator can validate and faithfully render; the exact schema or positional definitions must be preserved rather than inferred.
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
