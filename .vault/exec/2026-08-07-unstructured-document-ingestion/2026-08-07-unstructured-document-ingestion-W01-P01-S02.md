---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3f2bc6cfd9bdf1b614335ceafa772cffad58baa4ae8a21fc1a58a1f1b172c969'
step_id: 'S02'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Add the closed FieldRole StrEnum for tabular column mapping including UNMAPPED, with facade export, gated by a test asserting every importer-consumed role is a member

## Scope

- `src/cadrumo/core`

## Description

- Add `FieldRole` as a closed StrEnum of 22 members in `src/cadrumo/core/_field_role.py`, member values byte-identical to the column tokens the tabular importers already accept.
- Export it eagerly from the core facade and its `__all__`, matching the sibling provenance enum's pattern rather than the lazy attribute map.
- Add the closedness gate in `src/cadrumo/core/tests/test_field_role.py`: member set, token pinning, hydration, refusal of an unrecognised token, and the representability of `UNMAPPED`.
- Add the derivation gate in `src/cadrumo/application/tests/test_field_role_importer_coverage.py`, reading both importer column sets from their owning facades and asserting each resolves to a member.
- Scaffold the generated API stub for the new module.

## Outcome

The vocabulary is deliberately wider than the two importers it is gated against, and that was the load-bearing judgement in this Step. The Step text says "every importer-consumed role is a member", which a literal reading satisfies with exactly the union of the two importers' column sets. The governing decision record's tabular ruling says something stronger: retención is a role, not a column name, and the measured libro registro must map fully. Four members were therefore shipped that no importer column backs today — the retención, recargo and suplido terms plus the printed total the arithmetic closure is checked against.

That call has since been settled by evidence rather than argument. Four consumer modules landed afterwards, one semantic mapper and three tabular providers, and between them they use eleven members including two of the four added beyond the importer-derived set. The narrowest reading of the Step would have left the tabular lane with no role for retención — precisely the gap the decision record named. Reading the decision beat reading the Step text literally.

Member values are byte-identical to the importer column tokens, so a role resolves against an existing column with no second translation table in between. A translation table would be a place for the two vocabularies to drift silently.

The two gates are split by layer. The closedness gate imports nothing outside core, so the core test layer stays inward-only; the derivation gate spans two application packages plus core and lives at the application test boundary accordingly.

`UNMAPPED` is a member rather than an absence. A mapping that could only express recognised columns would force an unrecognised one to be guessed or dropped silently, and a sentinel colliding with a real importer column would let deterministic copying write the sentinel's cells into a genuine field. Both are asserted.

The semantic sweep that preceded the work found no existing column-role vocabulary. The nearest neighbour is a presentation-role enum in the spreadsheet export translator, which is a styling axis and not a candidate home.

## Verification

    uv run --no-sync pytest src/cadrumo/core/tests/test_field_role.py src/cadrumo/core/tests/test_field_origin.py src/cadrumo/application/tests/test_field_role_importer_coverage.py -p no:randomly
    80 passed in 25.64s

Re-run at HEAD after a large peer sweep of the core facade, to confirm the gates survived it:

    uv run --no-sync pytest src/cadrumo/core/tests/test_field_role.py src/cadrumo/core/tests/test_field_origin.py src/cadrumo/application/tests/test_field_role_importer_coverage.py -p no:randomly -p no:cacheprovider
    80 passed in 6.38s

Both logs were written in full to disk and read back; grepping them for deselection and error markers returned nothing, so all 80 collected tests ran.

    uv run --no-sync ruff check <touched files>
    All checks passed!

    uv run --no-sync ruff format --check <touched files>
    3 files already formatted

Three mutation proofs, each driven from a throwaway plugin on the interpreter path outside the repository, so nothing under the source tree was edited and a crashed run could leave no residue.

Removing a member that a real importer column backs reds five tests, including the coverage assertion and its parametrised case for that column.

Adding a column to an importer's set that no member covers reds two, both coverage assertions. This is the drift direction the gate exists for: two sets declared in different packages that move independently.

Emptying one importer's column set reds the populated-denominator assertion. This is the proof most often skipped, and without it the coverage assertion would pass vacuously over an empty set while claiming to have checked every column.

## Notes

The commit did not land on the first attempt. The repository index was locked with a lock file whose modification time stayed frozen across eight minutes, indicating a dead holder. The lock was not removed, waited on, or worked around; the commit was skipped and the work left in the working tree, which a later sweep committed intact along with two unrelated core modules from peers.

A peer added an unrelated import to the core facade while the verification suite was running. Both edits coexisted cleanly and the facade was re-imported afterwards to confirm it still resolves.

The generated API stub scaffold is tree-wide. It also emitted stubs for four peer modules and removed two stale ones; only this Step's own stub was staged and the rest were left for their owners. The shared core table-of-contents entry was deliberately not committed, because its diff carried this module's line alongside two peer modules whose own stubs were still untracked, so landing it would have referenced files nothing tracked yet.

A repository-wide import-hygiene gate was red throughout at 83 reaches against 79 documented. None of the four excess sites belong to this Step, whose tests import only public facades; it was recorded rather than patched.
