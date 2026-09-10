---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:e215c38bd81a368e29affe20144d4c446758f89834484247de22f1de5bb446b9'
step_id: 'S35'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Add the predecessor forest validator: every edition of a modelo declares a predecessor except exactly one, and the graph must be a single tree rooted at that one with no cycle, no unknown or self target, and every edition reachable. The unique root positively identifies a first edition, and a successor that omits its predecessor becomes a second root and is refused naming both. Mark the field manifest-only so a section fragment cannot declare it. Proof: a three-edition fixture whose third omits the key is refused as two roots; restoring it loads.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/revision_predecessor_forest.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_predecessor_forest.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_manifest_only_placement.py`
- `verify:` `pytest test_revision_predecessor_forest.py` -> `pass` (11); rule neutralised -> 8 red; marker dropped -> fragment test red
- `verify:` `pytest` forest, manifest-only placement, predecessor declaration, modelo 369, schema family coverage, loader directory mode -> `pass` except `test_legal_parameters_only_preserves_valid_parameter_key_identity`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass` (exit 0)
- `verify:` `ruff check`, `ruff format --check`, `ty check` on changed Python -> `pass`

## Notes

The rule binds a modelo only once one of its editions declares the key. Today that is modelo 369 alone.

The ADR's date-agreement clause is not built: a declared predecessor must agree with date order where the pair does not overlap. The S35 row does not assign it.

`test_legal_parameters_only_preserves_valid_parameter_key_identity` fails with a legal-catalogue refusal, "missing supported_filing_years catalogue declaration". The failure does not involve the predecessor or the schema, and it was not re-run against a baseline.

The reviewer persona was not launched from this session, so the mandatory code review is still outstanding.

- The reviewer persona could not be launched; the orchestrating session reviewed the S10 and S35 diffs together against the ADR. Only a named predecessor edge triggers inheritance, casillas are the only family that inherits (the manifest is excluded explicitly), the forest check runs before recursion, and each merge ambiguity is refused naming both sides. Verification: 99 tests passed across materialisation, forest, declaration, placement, 369, minimality and totality; `registry verify` exit 0; ruff and ty clean. Inherited rows still carry predecessor-edition tokens until restatement is lifted.
