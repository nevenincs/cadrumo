---
tags:
  - '#research'
  - '#m349-legal-grounding-debt'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-m349-payable-invoice-authoring-research]]"
---

# `m349-legal-grounding-debt` research: `M349 collectible_invoice substantive Ley 37/1992 grounding gap (17/17 procedurally-only)`

Subagent audit pass surfaced by the M349 R21-closure research. The
M349 binding set is fully grounded **procedurally** (the
form-publication orden + the general information-supply duty), but
ZERO of the 17 bindings carry **substantive** Ley 37/1992
references for the intracomunitario operations they describe.

Per the `registry-calculation-legal-grounding` rule, a regulatory
value MUST cite the binding provision that establishes it. The
procedural refs name the publication channel; the substantive refs
name the law. This is a latent grounding gap independent of the
R21 collectible-vs-payable mirror work; it should land regardless
of when the payable-side mirror bindings author.

## Audit scope

- File: `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0007-bindings.toml`
- Bindings audited: 17 (all collectible_invoice)
- Current `legal_refs` (uniform across all 17):
  `["orden-eha-769-2010:art-1", "ley-58-2003:art-93"]`
  — orden form publication + general information-supply duty.
  Zero substantive Ley 37/1992 grounding.

## Required substantive additions (uniform across all 17)

Every binding's `claves` list enumerates
`["E", "M", "H", "A", "T", "S", "I", "R", "D", "C"]`, so each
binding spans all four operation families:

- **E** entregas intracomunitarias exentas → Ley 37/1992 Art. 25
- **A** adquisiciones intracomunitarias → Art. 15 (definición)
  + Art. 26 (exenciones)
- **T / M / H** triangulación (sujeto pasivo intermediario) →
  Art. 141
- **S / I / R / D / C** prestaciones / adquisiciones de servicios
  intracomunitarios → Art. 69-70 (localización; sibling refs,
  noted for completeness, outside the immediate four-article scope)

Uniform `refs_to_add` tuple per binding:

```
[
  "ley-37-1992:art-15",
  "ley-37-1992:art-25",
  "ley-37-1992:art-26",
  "ley-37-1992:art-141",
]
```

## Catalogue + corpus debt (precondition)

None of the four target articles is authored in
`src/aeat/_data/registry/aeat/legal/iva.toml`. The catalogue holds
25+ other LIVA articles (94, 95, 99, 102, 104, 107-110, 115, 116,
122-124, 163-x SII series) with valid `corpus_ref` pointers but
the four intracomunitario articles are absent.

A corpus-HTML glob for the four article files
(`ley-37-1992-art-{15,25,26,141}*.html`) returns zero matches —
the BOE normative texts have not been ingested.

The debt is three-layer:

1. **Corpus HTML** for each of the four articles must be added
   under `corpus/normatives/html/` (the path is not yet created
   in this worktree for these articles).
2. **Catalogue entries**
   (`[legal."ley-37-1992:art-15"]` etc.) in `iva.toml` with
   `document_id`, `corpus_ref`, and a `required_text` clause
   excerpt that the evidence gate can verify.
3. **Binding refs** appended to the 17 `legal_refs` lists.

## Landing-order recommendation

**Two commits, catalogue+corpus first, bindings second.**
Rationale:

- The `registry-calculation-legal-grounding` rule states that a
  `legal_refs` entry pointing at an undefined catalogue id is
  invalid; the evidence gate cross-checks the catalogue entry
  against corpus text. Landing the binding additions before the
  catalogue / corpus would red the gate immediately for any agent
  that pulls between the two commits.
- The 17 bindings are mechanical sweeps once the catalogue ids
  exist; bundling them with corpus authoring (which requires
  fetching BOE HTML, sanitising, and stamping `required_text`)
  mixes two different review surfaces.
- Suggested sequence:
  - **Commit 1 — catalogue + corpus**: Add
    `corpus/normatives/html/ley-37-1992-art-{15,25,26,141}.html`
    + four `[legal."ley-37-1992:art-N"]` blocks in `iva.toml`
    with `required_text` clauses. Gate stays green (no consumer
    yet).
  - **Commit 2 — binding sweep**: Append the four refs to each
    of the 17 bindings in `0007-bindings.toml`. Gate now
    validates new refs against the catalogue landed in commit 1.

A single atomic commit is acceptable only if the author can
guarantee corpus + catalogue + bindings all green in one push;
given corpus authoring tends to surface BOE-text mismatches
mid-review, the two-commit split is the safer default.

## Per-binding inventory (all share refs_to_add)

Declarante totals (4):
- `iva-349-declarante-numero-operadores`
- `iva-349-declarante-importe-operaciones`
- `iva-349-declarante-numero-rectificaciones`
- `iva-349-declarante-importe-rectificaciones`

Operador rows (5):
- `iva-349-operador-row-codigo-pais`
- `iva-349-operador-row-nif`
- `iva-349-operador-row-apellidos`
- `iva-349-operador-row-clave`
- `iva-349-operador-row-base`

Rectificación rows (8):
- `iva-349-rectificacion-row-codigo-pais`
- `iva-349-rectificacion-row-nif`
- `iva-349-rectificacion-row-apellidos`
- `iva-349-rectificacion-row-clave`
- `iva-349-rectificacion-row-ejercicio`
- `iva-349-rectificacion-row-periodo`
- `iva-349-rectificacion-row-base-rectificada`
- `iva-349-rectificacion-row-base-anterior`

## Source

Subagent audit pass 2026-06-03 surfaced by the R21 partial-closure
research (`2026-06-03-m349-payable-invoice-authoring-research`).
Cited file:line evidence:

- `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/bindings/0007-bindings.toml`
  (17 bindings, all with identical legal_refs)
- `src/aeat/_data/registry/aeat/legal/iva.toml` (target for new
  catalogue entries; lacks the four target article entries)
- `corpus/normatives/html/` (target directory for new BOE HTML;
  the four article files do not exist)
