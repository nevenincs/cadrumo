---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:4fa8cdb5cc75e4adcf02a0012c2436bc49c15b328a4eb86a1f8bfb2ef7a181f6'
step_id: 'S13'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
  - '[[2026-08-04-minimo-descendientes-eligibility-deferred-descendant-axes-adr]]'
---

# Add the DescendantRelacion closed set, the two named entry-event dates replacing adoption_date, and their flag, wizard and locale entry surface

## Scope

- `src/cadrumo/core/_descendant_relacion.py`

## Description

- Add `DescendantRelacion` to `src/cadrumo/core/_descendant_relacion.py` as the closed
  five-member set, with `ART_58_2_ENTITLING_RELACIONES` declaring the narrower entitling
  subset once so no call site re-lists it.
- Replace `adoption_date` on `DescendantInfo` with `inscripcion_registro_civil_date` and
  `acogimiento_resolucion_date`, and add the `relacion` field defaulting to the ordinary
  descendant.
- Add `art_58_2_entry_date` returning the FIRST entitling event, and re-anchor
  `is_eligible_minimo_incremento_menor_tres` on it.
- Keep `_entry_date` and `entry_year` reading the inscription alone, so the autonomic
  nacimiento/adopcion window is unmoved by an acogimiento.
- Add the coherence validators: refuse an entry date under a relacion the statute
  excludes, read an unstated relacion carrying an inscription as an adoption.
- Rename the fact paths and the `--descendiente` keys, adding `RELACION`, `INSCRIPCION`
  and `ACOGIMIENTO`.
- Add the three wizard pages with the two date pages gated per-instance on the relacion
  answer, and replace the adoption cross-field validator with an entry-event one.
- Add the missing-anchor advisory and wire it into the calculate-path coordinator.
- Land twelve new locale keys and both flag-help strings across all four catalogues
  through the locales CLI, and remove the three orphaned adoption-date leaves.
- Regenerate the API stub for the new core module.

## Outcome

The statutory boundary is expressible for the first time. Art. 58.1 assimilates tutela
and acogimiento for the tranche amounts while Art. 58.2 grants the under-three increase
only for adopcion and acogimiento tanto preadoptivo como permanente, so a temporal
acogimiento carer is assimilated and excluded at once. That carer now has a truthful
value to record; with a single collapsed acogimiento member they would have selected the
entitling one and taken an increase the statute withholds.

The cap is measured rather than asserted: a child fostered in 2019 and adopted in 2022 is
granted 2019, 2020 and 2021 and nothing after. Anchoring on the later event would have
granted six periods where the law allows three.

Two named dates were required rather than one because three consumers read two different
anchors for the same child. The autonomic nacimiento/adopcion deduccion keys on the
adoption specifically, Art. 58.2 keys on the first entitling event, and the maternidad
clause is date-granular rather than period-granular. A single field would have applied
one statute's window to another's deduccion.

Coherence fails toward under-grant deliberately. An entitling relacion with no date is
valid and merely withholds, because an operator may know a child is adopted before they
hold the inscription date and a refusal to record is worse than a grant deferred. A date
under an excluded relacion refuses, because tolerating it would leave an entitling anchor
on a record the statute excludes.

The persisted-shape change carries a save-load-strict-equality roundtrip over one record
per relacion with every defaultable field set to a non-default value, plus an
anti-tautology proof that deleting the stored token changes the reloaded record and
changes it toward under-grant rather than toward entitlement. Coverage is structural
rather than numeric, so nothing re-derives a registry formula against itself. 2696 tests
pass across the contribuyente, wizard, modelo and CLI surfaces, tree-wide collection is
clean, and ruff and the project type gate pass on everything touched.

## Notes

A mutation probe found a guard that could not fire. Deleting the relacion check from
`art_58_2_entry_date` left all 28 tests in the new module green, because the coherence
validator makes that branch unreachable through the model - the check was real defence in
depth with nothing proving it. A second-layer test constructing the forbidden record
directly was added, and the probe now fails on exactly that test. Two further mutations,
a no-op coherence validator and an anchor switched to the latest event, each turn the
suite red. Any later change to these guards should re-run the probe rather than reason
about coverage.

The relacion enum is strict, so a bare string is refused at construction and every door
hydrates the member at its boundary. "Unstated" is a third input distinct from the
ordinary default, since an unstated relacion carrying an inscription is read as an
adoption while an explicitly-ordinary one carrying the same date is a contradiction. It
is expressed by OMITTING the keyword through one shared helper rather than by a sentinel,
so the type checker sees a plain enum at each call site.

DISCLOSED, not requested: rewriting the two flag-help strings meant re-supplying their
trailing sentence, so the Spanish and Catalan tails now read "introducirlos de forma
guiada" and "per introduir-los de manera guiada" rather than the slightly ungrammatical
originals. That is a copy change nobody asked for and it is trivially revertible.

DISCLOSED, attributed and NOT mine: the docs build gate fails on
`test_rendered_site_identity_and_static_marks_are_canonical`. The Sphinx handler
`_generate_legal_reference` resolves the legal catalogue relative to the docs source, and
that test builds from a copytree into a temporary directory carrying no `src/`.
Attribution is evidential rather than asserted: the copytree's ignore patterns exclude
the `api` directory, which is the only docs directory this Step touched, and the handler
landed the same day in another campaign's commits. Left alone as an active peer surface.

The whole Step is one commit rather than several because retiring a field is a
relocation: the canonical site, every consumer, every fixture and every test share one
index and one commit, so splitting the axis from its entry surface would have left the
tree uncollectable in between. The API stub follows as a separate commit, which was a
miss - the scaffolding discipline asks for it in the same commit as the source change.

### Correction, appended after the fact

The verification claim above is true and was misleading, and a peer caught what it hid.

One fact-path consumer was NOT swept: the Rioja adoption manual-oracle module still read
`renta_family.descendiente.0.adoption_date` after the rename. A peer landed the re-key
immediately after this Step, in the commit subject `re-key the Rioja adoption oracle to
the current fact shape`.

The mechanism is the part worth recording. That module is marked `integration`, and every
suite run cited above used the default marker selection, which is `unit` and deselects
it - so all 18 of its tests were deselected, not passed. The count of 2696 was real and
covered none of them. Worse, the miss would not have announced itself as an error: an
unrecognised fact path is silently ignored by the reconstruction regex, so the oracle's
"adopted child" would have been rebuilt with no entry date at all rather than raising.

The sweep itself found the file. A `rg` over the retired names listed it, and it was then
dropped when the mechanical rename was scoped to three test directories that did not
include the modelo one. Locating a consumer and then losing it between the search and the
edit is the failure, not the search.

Re-run afterwards with `-m integration` across the contribuyente, modelo and wizard
surfaces: 96 pass, including the re-keyed oracle module, so no further consumer is
outstanding. The CLI integration surface carries ten unrelated failures - ECB
euro-reference-rate network timeouts and M036 period-token assertions - and none of the
ten files contains any of the retired or new tokens, checked by grep rather than assumed.

The durable lesson: a marker-selected suite is not a verification of a rename. A
tree-wide rename must be verified with the marker selection that actually reaches the
renamed symbol, and `--collect-only` reporting thousands of deselected tests is the signal
that the default selection is not the whole tree.
