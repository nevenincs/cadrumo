---
tags:
  - '#plan'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_hash: 'sha256:a7941826c79e48a37fb41cdc39afc9ca9fe4405bbd914a3120f5a615d02836e4'
tier: L2
related:
  - '[[2026-08-04-profile-derived-selectors-adr]]'
  - '[[2026-08-04-profile-derived-selectors-research]]'
  - '[[2026-08-04-minimo-descendientes-eligibility-adr]]'
---

# `profile-derived-selectors` plan

## Description

Executes `2026-08-04-profile-derived-selectors-adr` in full. Twenty profile schema fields
declare a value the engine computes, render as editable rows, and silently suppress the
law computation when written to. This plan declares those paths as data, refuses operator
writes to them, deletes the declarations, and hardens the injectors.

`P02` must not begin until `2026-08-04-minimo-descendientes-eligibility-plan` is complete.
That plan corrects the derivation, and the refusal authored here closes the only channel
by which a filer can currently correct it. Landing the refusal first would convert a
correctable tax under-declaration into an uncorrectable one.

## Steps

### Phase `P01` - Prove the hazard and declare the namespace

Demonstrate the override with a real failing test before designing around it, then land the derived-selector pattern namespace additively while the field declarations still stand, so no commit boundary leaves a binding selector unresolvable. Retire the dormant selector-level as-of channel in its own commit rather than leaving a second unread temporal axis beside the new placeholder.

- [x] `P01.S01` - Prove with a real failing test that an operator-stored value at a derived aggregate path suppresses the Art. 58 computation on the live calculate path, and record the red run before flipping it; `src/cadrumo/application/modelo/tests/`.
- [ ] `P01.S02` - Declare the derived-selector pattern namespace as ONE atomic commit over three interlocked files, the schema TOML array, the typed entry model and its field on the schema definition, and the loader payload that passes the key through, because the TOML alone is silently dropped and the loader alone raises at every schema load, compiling the filing-year placeholder as a four-digit terminal-anchored fragment so a shorter pattern cannot swallow a longer sibling; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/domain/user_profile/_schema.py, src/cadrumo/domain/user_profile/_loader.py`.
- [ ] `P01.S03` - Retire the dormant selector-level as-of field, its two populated registry declarations, and the presence-only assertion that blesses it; `src/cadrumo/domain/calculations/registry/_bindings.py, src/cadrumo/_data/registry/aeat/modelos/100/revisions/, src/cadrumo/application/modelo/tests/test_profile_binding_real_path.py`.

### Phase `P02` - Refuse operator writes to derived paths

Add the path-legitimacy judgment beside the existing unknown-path check rather than inside the value-refusal authority, filter derived rows out of the overview in the same commit to close the transitional window, and convert the duplicated test seeding to real source facts.

- [ ] `P02.S04` - Add a domain helper answering whether a path is derived, as the single written-once judgment over the declared patterns; `src/cadrumo/domain/user_profile/_schema.py`.
- [ ] `P02.S05` - Consume the helper as the FIRST statement of the per-fact validation, before the field-index lookup, not merely before the unknown-path arm, because during this phase the declarations still stand so the index lookup succeeds and the unknown-path arm never fires, and a check placed after it would leave the override channel fully open; `src/cadrumo/application/user_profile/_validation.py`.
- [ ] `P02.S13` - Retire the write-time emission of the guarderia aggregate from the descendant projection AND add its calculate-time injection in the same commit as the refusal, which also closes a latent gap because that aggregate is the only one of the four with no injector and is written only when non-zero, so a childless or zero-expense filer leaves its casilla unresolved today; `src/cadrumo/domain/contribuyente/_descendant_facts.py, src/cadrumo/application/wizard/_checkpoint_store.py, src/cadrumo/application/modelo/_profile_binding.py`.
- [ ] `P02.S06` - Add the refusal copy to all four locale catalogues through the locales CLI, never by hand-editing a catalogue; `src/cadrumo/locales/`.
- [ ] `P02.S07` - Filter derived paths out of the profile overview projection in the same commit as the refusal, closing the window where a row would render that the write door refuses; `src/cadrumo/application/user_profile/_overview.py`.
- [ ] `P02.S08` - Delete the derived-path seeds from the eight files carrying the duplicated block, converting only the three derived lines and leaving the raw operator field untouched, and exclude the two idempotency tests whose whole purpose is asserting the injector defers to an explicit fact; `src/cadrumo/application/modelo/tests/, src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P03` - Delete the declarations and harden the injectors

Delete the twenty declarations, their locale entries, and the one write-time materialisation in a single explicit-path commit, then make the injectors compute-always, gate future filing years on registry content rather than Python constants, and replace the silent parse swallow with a refusal.

- [ ] `P03.S09` - Delete the twenty derived field declarations, drop their locale entries through the locales CLI, and sweep both the registry-contract test asserting the year-suffixed selectors are declared field paths and the profile-surface test matching those selectors as literal strings, all in one explicit-path commit; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/locales/, src/cadrumo/domain/user_profile/tests/test_registry_contract.py, src/cadrumo/domain/calculations/registry/tests/test_modelo_100_2024_profile_surface.py`.
- [ ] `P03.S10` - Make the remaining injectors compute-always so a stray stored fact cannot win, and invert rather than delete the two tests that currently bless the defer-to-explicit-fact behaviour being removed; `src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/application/modelo/tests/test_minimo_descendientes_engine.py, src/cadrumo/application/modelo/tests/test_anualidades_eligibility_derivation.py`.
- [ ] `P03.S11` - Replace the year-gating frozensets and the hardcoded single-year gate with gating on registry content, so a new filing year needs no code edit; `src/cadrumo/application/modelo/_profile_binding.py`.
- [ ] `P03.S12` - Replace the silent parse swallow that under-counts a descendant with a raised refusal naming the index and value, and add the derived-scoped advisory for a selected derived binding that still resolves to nothing; `src/cadrumo/application/modelo/_profile_binding.py`.

## Parallelization

`P01` steps are sequential: the proof grounds the design, and the namespace must exist
before anything depends on it. The `valid_at` retirement is independent of the rest of
`P01` and may run in parallel with it. `P02` and `P03` are strictly sequential, and both
are gated on the sibling eligibility plan completing.

## Verification

The plan is complete when every Step is closed and all of the following hold: the
override hazard is demonstrated and then demonstrably closed, with the same probe
inverted; every declared pattern matches at least one live binding selector and the
anti-rot gate fails if one does not; the refusal fires from both the lifecycle write door
and the manager validator pre-check, and no derived row renders in the overview
row-count probe; the value-refusal authority and its two exhaustive consumers are
unchanged; a full registry load and per-modelo validation pass green after the deletion
commit, with collection clean across the tree; a stray stored fact at a derived path
provably does not alter the computed aggregates; and the shipped tests derive expected
figures from external oracles rather than from the formulas under test.
