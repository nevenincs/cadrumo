---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:28be1b01a0723389bb59219758e0672ebe49eabb703b3b13e01ddf6ec605ab51'
step_id: 'S92'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# add a tree-wide gate asserting every casilla label resolves in the mandatory Spanish source for every modelo and every revision, measured through resolve_modelo_localization and the production resolver chain and never by reading catalogue YAML, and prove the gate bites

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_casilla_label_spanish_source_coverage.py`

## Description

- Sweep every modelo, every revision and every casilla the bundled authority compiles, resolving each label through the production `get_label` surface, which is `resolve_modelo_localization` with the mandatory Spanish source.
- Treat both a resolver refusal and a whitespace-only answer as a gap, so a blank does not pass as a translation.
- Add a companion non-vacuity assertion proving the sweep reaches real modelos, real revisions and real casillas, and that every casilla carries localization keys the resolver chain can walk.
- Prove the gate bites from outside the repository.

## Outcome

The gate lands green: 2 passed. The tree-wide sweep finds zero mandatory-Spanish casilla-label gaps across all 73 modelos. `ruff format --check` and `ruff check` pass on the target.

The bite was proven by a runtime patch loaded from outside the repository as a pytest plugin, blanking the Spanish answer for one casilla identity. The coverage assertion reds and the non-vacuity assertion stays green, which is the correct split - the injected fault is a coverage fault, not a sweep fault. Nothing under `src` was mutated for the proof.

## Notes

The measuring instrument is the point of this gate, not the number it returns today. The locale scaffold emits an occurrence key for every casilla in every revision, null until translated, and the resolver walks an ORDERED chain whose first entry is only the revision-specific tier - continuity and shared tiers sit below it and carry the label for every revision that inherits it. A direct catalogue read sees the null at index zero and stops, so it reports a gap the resolver does not have: on the Modelo 303 split revisions a YAML read reported 201 missing labels per revision where the resolver's true figure was 84. A gate written against the catalogue file would therefore have failed loudly on a corpus that renders correctly, and would have trained every reader to distrust it.

The gate deliberately does not enumerate a count. It asserts the property - every casilla resolves - so a modelo, revision or casilla added tomorrow is covered without a constant to update.

Spanish is the mandatory source and the last backstop: every other catalogue falls through to it, so a Spanish miss is the one miss that reaches an operator as a refusal rather than as a foreign-language string. The three non-Spanish catalogues are deliberately not swept, because their scaffolded nulls are exempt by the resolver's own contract and asserting on them would contradict the untranslated-string honesty ratchet.

This Step's commit could not land in-session: `.git/index.lock` has been held since 19:31:00 with a frozen mtime and no HEAD movement, a dead holder blocking every staging operation in this worktree. Removing anything under `.git/` is absolutely forbidden. No data loss and no destructive Git operation occurred.
