---
tags:
  - '#adr'
  - '#registry-header-requirements'
date: '2026-10-12'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:8e0618aa857dd9b1252d59bfc07327322a76e39669d0fea47e31d29dd904312e'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - '[[2026-10-12-registry-header-requirements-reference]]'
---

# `registry-header-requirements` adr: `Reviewed source-cited header requirements in the semantic map` | (**status:** `accepted`)

Accepted on the owner's ruling of 2026-10-12, given verbatim: "i followw your recommedation". The recommendation it accepts is the one recorded here: add a reviewed, source-cited header-field requirement to the registry's semantic map and regenerate the Modelo 111 export target, keeping one canonical mechanism and adding no application-level side check.

## Problem Statement

The generated export layout marks a field `required` only from the record design's Validación column (`_is_required` in `dev/registry/pipeline/export_field_schema.py`), and only a `required` field makes export refuse a blank (`src/cadrumo/application/filing/record_field_renderer.py`, header branch). Modelo 111's page sheet `dr M11101` prints no Validación at all, so since the generated tree replaced the hand-written one the declarant NIF, apellidos o razón social, nombre, ejercicio and periodo were all optional, and a profile with no name exported a return with no declarant. The requirement is stated, but by the official instructions rather than the design, and the semantic map had no place to carry it: its only requirement field, `required_with`, applies to casillas.

## Considerations

- Code grounding for how a generated field gets its requirement today, and the provenance and republish precedents: `2026-10-12-registry-header-requirements-reference`.
- Grounding: source `aeat-modelo-111-instructions` (`src/cadrumo/_data/corpus/aeat_official/instructions/modelo_111/files/modelo-111-instrucciones.html`, catalogued in `src/cadrumo/_data/registry/aeat/legal/irpf.toml`). Apartado "IDENTIFICACIÓN": "Introduzca el NIF del declarante y los apellidos y nombre o bien la razón social de la persona o entidad." Apartado "DEVENGO" states the ejercicio and the período.
- The identification sentence makes nombre required only for a natural person: an entity gives a razón social and has no nombre.
- The generator authority ADR `2026-08-10-aeat-export-fragment-generator-authority-adr` makes the semantic map the reviewed, source-epoch meaning authority and forbids defaults, inference and neighbouring-tree oracles.
- `required_for = "natural_person"` already exists on the layout field and is evaluated per filing against the taxpayer's legal form.
- Rule 14 requires filing-affecting claims to be grounded in a specific official provision for the exact revision; rule 09 requires export to distinguish missing from permitted blank and never let padding supply a required fact.

## Considered options

- **Hand-edit `required = true` into the generated tree. Rejected.** Generated trees are CLI-owned; the next regeneration silently reverts it.
- **An application-level check before export. Rejected.** A second requirement mechanism beside the layout's, invisible to the registry, and refused by the owner's ruling.
- **Infer requirements from the field's role (any taxpayer identifier is required). Rejected.** An inferred requirement has no source, and the generator ADR forbids inference.
- **A reviewed, source-cited requirement on the semantic-map entry, combined with the design's own requirement by the generator. Chosen.** One canonical path into the layout's existing `required`/`required_for`, with the grounding carried in the reviewed input.

## Constraints

- **Declaration shape.** A semantic-map entry may carry one `requirement` table: `applies_to` (`all_taxpayers` or `natural_person`), `source_ref`, `source_sha256` and `statement`. It is optional and absent by default; every existing map is unchanged.
- **Citation.** `source_ref` must be catalogued for the target revision, must not be a `record_design` source, and must also be listed in the entry's own `source_refs`, so the generated field cites it. `source_sha256` must equal the catalogue's current digest: a recaptured source is a new review, not a silent carry-over. `statement` is the source's own words; validation reads the cited file at its verified bytes (markup removed, entities decoded, whitespace collapsed) and refuses a statement it does not contain. A source whose text cannot be read this way (today, anything other than HTML) refuses rather than passing unchecked.
- **Scope.** A requirement may sit only on a `header` or `draft` entry. Casillas keep their design requirement and `required_with`; literals, fillers and reserves get theirs from the source.
- **Combination with the design.** The design's Validación remains the first authority. A reviewed requirement fills only a silent design cell: if the design already states a requirement, unconditional or qualified, a reviewed one on the same field is refused as a second spelling of the same fact. `all_taxpayers` yields `required = true`; `natural_person` yields `required = false` with `required_for = "natural_person"`.
- **Conditional cases.** `natural_person` is admitted only on a header field, matching the layout's existing `required_for` contract. Evaluation stays in the export, against the filing's own taxpayer identity.
- **Provenance.** The requirement is digested into the semantic-map provenance only when declared, so maps without one keep their digest.
- **Modelo 111 scope.** NIF, apellidos o razón social, ejercicio and periodo are `all_taxpayers`; nombre is `natural_person`. `tipo-declaracion` stays unrequired: no source grounds a requirement for it. Modelos 115, 117, 216 and 360 are untouched.
- **Refusal wording.** The export names the missing profile fact (for example `identity.surnames or identity.legal_name`), not the producer key, because the profile fact is what the operator declares.

## Implementation

We will extend the semantic-map schema (`dev/registry/pipeline/semantic_map.py`), its validation (`dev/registry/pipeline/semantic_map_validation.py`, catalogue and digest checks inside the join, plus a quotation check run wherever the join runs with a source root) and the generator's requirement derivation (`dev/registry/pipeline/export_field_schema.py`), carry the requirement through the provenance projection, declare the five Modelo 111 requirements, and regenerate the 111 target through the pipeline's republish route. The application export translates a missing-producer refusal into the profile fact it is read from. Hypothesis that may change within these constraints: quotation checking for PDF sources could later read the corpus text sidecars instead of refusing.

## Rationale

The semantic map is already the reviewed place where registry meaning attaches to exact design anchors, and the layout already has the fields that make export refuse a blank; adding a cited input to that one path closes the gap without a second mechanism. Holding the quotation to the cited bytes is what keeps the requirement grounded rather than asserted: a requirement nobody can point at, or one whose source moved, refuses before generation.

## Consequences

- Modelo 111 export refuses a missing declarant NIF, apellidos o razón social, ejercicio or periodo, and a missing nombre for a natural person, with a refusal naming the profile fact.
- Any other modelo whose design is silent can gain grounded requirements by the same declaration; each one is a reviewed, digest-pinned claim that fails loudly when its source is recaptured.
- Generated layouts now cite the instructions source for the affected fields.
- Reconsider if a design starts printing a Validación for these fields (the reviewed requirement then refuses and must be removed), or if a non-HTML source needs to ground a requirement.
