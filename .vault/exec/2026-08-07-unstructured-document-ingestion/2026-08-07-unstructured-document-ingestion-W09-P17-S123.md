---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:7c0feb23ca7a7095da7792c9c5beb2db41e06a27932e58a0576335263a514c5c'
step_id: 'S123'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Add Ley 37/1992 art. 3 to the bundled consolidated corpus, since the territorial exclusion the Spanish territory table rests on cites art. 3.Dos by identifier while only arts. 1 and 102 are bundled, so the evidence gate cannot validate the citation and the grounding resolves by name alone. Take the LAST version in the consolidated payload rather than the first, since it carries every historical version oldest first and the first block is repealed law, assert the amending norm identifier, never pass the legal text through a shell, and read the file back before trusting it. Same class as the arts. 68 to 70 gap and worth fetching in the same pass

## Scope

- `src/cadrumo/_data/corpus`

## Description

- Probe the bundled corpus for Ley 37/1992 art. 3 before fetching anything.
- Establish that art. 3 is already bundled, at anchor `a3` of the whole-law
  consolidated file, and that arts. 68, 69 and 70 are bundled and already
  carry legal catalogue entries.
- Cross-check the bundled art. 3 unit against the live BOE consolidated text.
- Derive the amending norm and its entry-into-force date from the amending
  norm's own disposicion final rather than from a sibling entry's date.
- Add the `ley-37-1992:art-3.dos` entry to the framework legal catalogue,
  pointing `corpus_ref` at the bundled whole-law file rather than authoring a
  duplicate excerpt.
- Correct the territory table's grounding prose, which asserted that art. 3 was
  absent from the corpus and attributed apartado Uno's content to apartado Dos.
- Add a grounding gate binding the territory table to the statute.

## Outcome

The Step's premise did not hold: no fetch was required, and no corpus file was
added. Art. 3 was already bundled inside the whole-law consolidated payload, so
the citation's problem was never a missing text. It was a missing catalogue
entry — nothing defined the cited identifier, so no `corpus_ref` and no
`required_text` existed for the evidence machinery to check, and the territory
table is read by the IVA domain directly rather than through the modelo registry
authority, so its citations were validated by nothing at all.

The gap is closed at both ends. The catalogue now defines the provision against
the bundled text, and a new gate binds the table's rows to the statute: every
cited provision must resolve to a catalogue entry, the cited article must carry
both exclusion limbs, and the Balears must stay inside the territory by
non-exclusion.

The bundled art. 3 unit is character-identical to the live BOE consolidated text
at 2311 characters, checked on the day of the change. The figure originally
recorded here was 2733, which no artefact carries; a later review measured the
unit and a re-measurement confirmed 2311. The convention is stated so the number
stays re-derivable rather than merely corrected: it is the length of the anchored
unit's own text as the json sidecar stores it, excluding the article heading.
Rendering the same unit with its title gives 2340, which is what the registry's
legal evidence gate reads.

Three findings, none silently reconciled. The table's prose claimed art. 3 was
not bundled, which was false. It attributed the definition of the ambito
espacial to apartado Dos, which is apartado Uno. And it described that ambito as
"the peninsula and the Balearic Islands", while the statute names neither — the
Balears are inside by adjacency plus non-exclusion. The mapping data itself
contradicts nothing in the statute and was left untouched.

## Verification

The new gate and the existing territory suite:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_spanish_territory_grounding.py src/cadrumo/domain/iva/tests/test_spanish_territory.py -m unit -n0 -q
    29 passed in 1.93s

The registry evidence and catalogue gates, which validate the new entry's
`corpus_ref` and `required_text` against the bundled corpus:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_normatives.py src/cadrumo/domain/calculations/registry/tests/test_authority.py -n0 -q
    84 passed in 53.12s

The whole IVA domain plus the catalogue gates, after the change:

    uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_normatives.py -n0 -q
    517 passed in 50.64s

Lint, format and type gates on the new module: `ruff check` and
`ruff format --check` both clean, `ty check` reports "All checks passed!".

Both gates were proved to bite, from outside the repository, with no tracked
file mutated.

The evidence gate, exercised against the real entry with three controls. The
positive control validates. An absent phrase is rejected. A phrase that is
genuinely in the law but belongs to a different article is rejected at this
anchor, and the article's own text is rejected at a different anchor — the two
that prove the check is scoped to the article rather than satisfied by the file:

    POSITIVE: real entry validates against the bundled corpus -> PASS
    NEGATIVE A: absent phrase rejected -> RegistryValidationError
    NEGATIVE B: phrase from art. 68 rejected at anchor a3 -> RegistryValidationError
    NEGATIVE C: art. 3 text not found at anchor a68 -> RegistryValidationError

The new grounding gate, exercised against a temporary tree holding real corpus
text and a deliberately corrupted table, with a green baseline first so the
results are not noise:

    BASELINE on temp root: all cases PASS
    MUTATION 1 (citation names an undefined provision): CAUGHT by 1 case(s)
    MUTATION 2 (Balears excluded from the TAI): CAUGHT by 1 case(s)
    MUTATION 3 (statute loses the Ceuta/Melilla limb): CAUGHT by 1 case(s)

## Notes

The date was the one place a plausible wrong answer was available for free. The
sibling entry created by the same amending article carries 2020-03-01, and
copying it would have been invisible. The amending norm's own entry-into-force
disposition names only apartados dos through nueve of that article for that
date; the apartado amending art. 3 is apartado uno, and the article sits in
libro tercero, so neither the later date nor the twenty-day rule reaches it. The
correct date is the general one, the day after publication.

Every phrase considered for `required_text` was counted across the whole law
before being chosen. One candidate, the article's own rubric, occurs twice and
was rejected for that reason; the four that shipped occur exactly once each.

Two hazards the Step named did not arise, because no fetch was needed: the
oldest-first historical-version trap and the truncating-shell trap. No legal
text passed through a shell at any point regardless — every fetch, comparison
and extraction ran in Python and was read back from disk.

Incident, reported not reconciled. A peer's catch-all commit swept this work's
in-progress edits into itself while the work was still under verification. The
substance is intact and complete in the tree and was re-verified there
afterwards, so nothing was lost, but the change did not land as one authored
atomic commit as intended.

Left uncommitted: a type-narrowing refactor of the new gate, replacing two
unchecked TOML reads with a helper that verifies the shape. It is written,
formatted, linted, type-clean and covered by the runs above. The repository
index was held by another process across repeated attempts, and the lock was
left in place rather than removed.
