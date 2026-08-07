---
name: casilla-grounding-corrects-actividades-default-by-section
trigger: always_on
---

# Casilla legal_refs: correct the actividades generic default by section, never by id

## Rule

A casilla whose `legal_refs` carry the actividades-económicas chapter
(`ley-35-2006:art-{27,28,30,31,32}`) as a *generic default* — that is, the box is
NOT an actividad-económica income or affectation box — MUST be re-grounded to
ITS concept's binding article, keyed by the **renumbering-immune section tag**
(the leaf of `section = [...]`), never by casilla id across filing years.

A framework article that *applies* a regime is a valid foundation home even when
the regime is *established* elsewhere: autonomic deductions ground to `art-77`
(cuota líquida autonómica), régimen de atribución to `art-86`, base reductions
and integración to `art-48/49/50`, individualización to `art-11`, RIC to
`ley-19-1994:art-27`.

For a casilla that is a member of a calculation **construct or binding**, sweep
the casilla, its construct, AND its `previous_filing` / per-source bindings in
ONE coherent change — the registry validator requires a construct's `legal_refs`
to cover both its member casillas' and its bindings' refs.

Where the box genuinely IS actividades (estimación directa or objetiva, módulos
agrícolas, "inmueble afecto a actividades económicas"), the actividades chapter
is the CORRECT grounding and MUST be preserved.

## Why

Modelo 100 revisions used the actividades chapter as a generic-default
`legal_refs` filler across thousands of non-actividades casillas. Three hazards
make naive correction wrong:

- **Casilla ids RENUMBER across years** — the same id is a ganancia box in one
  year and a deducción-maternidad box in another — so id-keyed maps inject the
  wrong articles. The section tag is concept-specific and stable.
- **The "different corpus" assumption is often false.** Autonomic deductions
  have a correct LIRPF framework home in `art-77`; check before concluding a
  concept needs a separate corpus.
- **Calculation-chain casillas are construct- and binding-entangled**, so the
  validator's three-layer coverage check breaks registry load if a casilla is
  grounded without sweeping its construct and bindings.

## How

- **Good:** ground every autonomic-deducción box to `art-77` by matching the
  comunidad name in the section path, pinned with a substring gate; the
  base-liquidable-negativa carry-forward grounds its casillas, its construct and
  its `previous_filing` binding to `[art-48, art-50]` in one commit, so the
  binding-coverage check passes.
- **Good:** an actividad-económica box keeps the actividades chapter.
- **Bad:** mapping one year's id to another's to copy grounding — the
  renumbering injects an unrelated article.
- **Bad:** grounding a construct-member casilla without also grounding its
  construct and bindings; the registry then fails to load.

## Source

Audit `2026-06-14-legal-grounding-centralization-audit`. Companions:
`registry-calculation-legal-grounding`,
`legal-grounding-verifies-bundled-authoritative-corpus`.
