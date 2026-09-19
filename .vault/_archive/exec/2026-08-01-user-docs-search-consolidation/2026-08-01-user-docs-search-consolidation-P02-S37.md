---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:74cac99b3f81affb9edf5332bc229b5c4cc76eb9238745545d3b6d1aa67067cc'
step_id: 'S37'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Resolve the shipped query/alias authority

## Scope

- `src/cadrumo/_data/terminology/query-aliases/query-alias-authority.json`
- `dev/docs/terminology/_query_aliases.py`
- `dev/docs/terminology/tests/test_query_aliases.py`

## Description

- Re-read the finding against HEAD before acting on it, as the standing mandate requires.
- Establish that two of its three premises are falsified: the authority carries two independently ratified entries, and it is consumed by the live sweep and the sweep command, not by nothing.
- Establish that the third premise, that it ships inside the wheel, is not a defect: its siblings under the same packaged data root are the committed concept fragments, the ratification queue and the laundered relevance mapping, all of which the boundary ruling explicitly places on the committed side.
- Re-home the artefact out of the path segment naming the retired tier, so its directory states what it contains like every sibling does.
- Retire the tier name from the schema token, the loader constant, the two schema literals, the error messages and the module docstring, atomically with the committed JSON and the tests.

## Outcome

The finding recorded a zero-entry artefact with no consumers reaching a reader disk. That is not what is at HEAD: the authority is live, ratified and consumed. The remedy the ruling therefore calls for is narrower than the removal the finding proposed, and this row executes that narrower remedy.

The artefact was never a Rung-2 artefact in substance. It admits additional reviewed aliases into the closed query vocabulary the sweep runs, which produces the committed relevance mapping that boosts lexical results. That is rung-1 work, and rung 1 ships. What retirement required was only that its name stop advertising a tier that no longer exists.

The rename is atomic across the data file, the loader and the tests, so no reader ever resolves the retired name. Under the zero-legacy posture no alias, bridge or read-tolerance for the old token was added: the old path and the old schema string simply cease to exist.

## Verification

The alias-authority gate passes twelve tests, including the two that pin the repository-relative path and the provenance identity, so the loader, the committed bytes and the recorded provenance agree on the new name. A tree-wide search for the retired tier token across the package and the shipped data root returns nothing.

## Notes

The module docstring previously argued that the schema id should be kept because renaming it would invalidate the file it names. That reasoning held while the tier was live and something external might pin the token. Nothing external pins it: the file is committed in-repo, the loader pins it through a literal, and the browser validator that once checked it was deleted. The docstring is corrected rather than left asserting a superseded rationale.
