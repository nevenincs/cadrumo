---
name: casilla-grounding-corrects-actividades-default-by-section
trigger: always_on
---

# Casilla legal_refs: correct the actividades generic-default by section, never by id

## Rule

A casilla whose `legal_refs` carry the actividades-económicas chapter
(`ley-35-2006:art-{27,28,30,31,32}`) as a *generic default* — i.e. the box is NOT
an actividad-económica income/affectation box — MUST be re-grounded to ITS concept's
binding article, keyed by the **renumbering-immune section tag** (the leaf of
`section = [...]`), never by casilla id across filing years. A framework article
that *applies* a regime is a valid foundation home even when the regime is
*established* elsewhere (autonomic deductions → `art-77` cuota líquida autonómica;
régimen de atribución → `art-86`; base reductions/integración → `art-48/49/50`;
individualización → `art-11`; RIC → `ley-19-1994:art-27`). For a casilla that is a
member of a calculation **construct/binding**, sweep the casilla, its construct, AND
its previous_filing/per-source bindings in ONE coherent change — the registry validator
requires a construct's `legal_refs` to cover both its member casillas' and its bindings'
refs. Where the box genuinely IS actividades (estimación directa/objetiva, módulos
agrícolas, "inmueble afecto a actividades económicas"), the actividades chapter is the
CORRECT grounding and MUST be preserved.

## Why

The 2021-2024 Modelo-100 revisions used the actividades chapter as a generic-default
`legal_refs` filler across ~6000 non-actividades casillas (income, cuota, base,
autonomic deductions, ganancias, reductions, inmueble, contribuyente identification) —
documented in the `2026-06-14-legal-grounding-centralization-audit` (V12-V22). Three
hazards made naive correction wrong: (1) casilla ids RENUMBER across years (id `1911`
is a ganancia box in 2024 but a deducción-maternidad box in 2022), so id-keyed maps
inject wrong articles — the section tag is concept-specific and stable; (2) the
"different corpus" assumption for autonomic deductions was false — `art-77` (which
applies them to the cuota) is the correct LIRPF framework home, collapsing a
~2000-casilla "separate campaign" into a section grounding; (3) calculation-chain
casillas are CONSTRUCT- and BINDING-entangled — the validator's three-layer coverage
check (casilla → construct ⊇ casilla refs AND construct ⊇ binding refs) means a casilla
grounded without sweeping its construct+binding breaks registry load. This rule is the
correction-method companion to `registry-calculation-legal-grounding` (which governs the
binding provision a compiled VALUE must cite) and `legal-grounding-verifies-bundled-
authoritative-corpus` (verify the figure against bundled corpus).

## How

- **Good:** ground every `c_valenciana_res`/`canarias_res`/… autonomic-deduction box to
  `art-77` by matching the comunidad name in the section path; pin with a substring gate.
- **Good:** the base-liquidable-negativa carry-forward grounds the 13 casillas + the
  anexo-c construct + the previous_filing binding all to `[art-48, art-50]` in one commit,
  so the validator's binding-coverage check passes.
- **Good:** a heterogeneous section (the `gravamenes_res` cuota computation) is grounded
  PER-BOX by deaccented label (escala→`art-63/74`, cuota líquida→`art-67/77`, each
  deducción→its own article), leaving the RIC/regularización boxes that bind elsewhere.
- **Good:** an actividad-económica box (`actividad_est_directa`, "inmueble afecto a
  actividades económicas") KEEPS the actividades chapter — it is correct there.
- **Bad:** mapping `2024`-id → `2025`-id to copy grounding — the renumbering injects a
  maternidad-deduction article onto a ganancia box.
- **Bad:** grounding a construct-member casilla without also grounding its construct and
  bindings — `construct '…' does not include legal refs […] required by binding '…'`,
  registry fails to load.
- **Bad:** assuming a regime needs a "different corpus" before checking whether a LIRPF
  framework article (cuota líquida autonómica, régimen de atribución, base liquidable)
  already applies it.

## Source

Campaign `legal-grounding-centralization`, audit
`2026-06-14-legal-grounding-centralization-audit` (findings V12 section-tag discriminator,
V19/V20 construct+binding-aware sweep, V21 framework-foundation for autonomic). ~6345
M100 casillas re-grounded across ~40 sections; 14 LIRPF legal entries authored. Promoted
per the `vaultspec-codify` discipline after the method held across the full form.
