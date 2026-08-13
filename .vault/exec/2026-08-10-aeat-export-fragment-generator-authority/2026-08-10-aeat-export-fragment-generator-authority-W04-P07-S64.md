---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:44552fac8a51737b63a8c2ca68febf2afe76487a16443abba20ea9ea5a4bfdff'
step_id: 'S64'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Require every persisted semantic map and fragment set to carry one exact source_ref and source_sha256 identity, validate that identity against the parser intermediate and selected revision source membership, bind it into provenance, and hard-refuse design-epoch-only maps, implicit source selection, alternate anchor catalogues, coordinate-bearing projection declarations, legacy-layout reads, and heuristic mapping compatibility before S19 authoring begins

## Scope

- `dev/registry/_semantic_map.py`
- `dev/registry/_semantic_map_loader.py`
- `dev/registry/_semantic_map_validation.py`
- `dev/registry/_semantic_map_join.py`
- `dev/registry/_provenance_manifest.py`
- `dev/registry/tests/`

## Description

- Amend the two existing governing ADRs in place after Sol medium architecture review.
- Insert S64 through the plan CLI without colliding with the active S63 declaration-deficit row.
- Require exact source identity on semantic maps and every persisted fragment.
- Enforce fragment agreement, parser identity, selected-revision membership, envelope agreement, provenance digest inclusion, and generation attestation.
- Delete acceptance of design-epoch-only maps and refuse every implicit or alternate mapping route.
- Add non-tautological red tests for missing, changed, mixed, and revision-detached source identity.
- Obtain formal Luna review and resolve the verification boundary honestly.

## Outcome

S64 is complete. The semantic map is now the sole source-epoch coordinate authority and cannot exist or render without exact official source identity. Formal review approved with no Critical, High, or Medium findings. The focused lane passed 167 tests, the independent real-authority retry passed three tests, Ruff passed, BasedPyright reported zero errors, Ty passed, and the diff check passed.

## Notes

Five pre-existing M303 variable-envelope parametrizations remain red because their partial one-field maps cannot biject the complete S62 revision projection declarations. They are not S64 source-identity failures and were not weakened, skipped, or hidden. Their repair belongs with complete persisted M303 map/declaration authority.
