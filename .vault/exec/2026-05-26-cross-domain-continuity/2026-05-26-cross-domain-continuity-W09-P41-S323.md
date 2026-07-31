---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:2ea867037fa1a3c77d0948434bb44eb7a144817a6c5b18523713d35963fc751d'
step_id: 'S323'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-MANUEL-A SC profile schema lacks socio enumeration

## Scope

- `entity_type=attribution_entity stored as generic legal entity with no fields for nombre de socios percentages NIFs forma juridica`
- `extend UserProfileSchema with attribution_entity-specific section (socios: tuple[SocioEntry`
- `...] with nif name share_pct fields)`
- `required precondition for M184 calculation to work end-to-end`
- `src/aeat/domain/user_profile/_schema.py`

## Description

- Run required RAG grounding query: `attribution entity socios user profile schema M184 SocioEntry share_pct`.
- Inspect W09.P41 S307/S323/S324 plan rows and the existing user-profile schema, loader, validator tests, and M184 attribution-member row bindings.
- Add numeric `minimum` and `maximum` metadata to strict user-profile schema fields, restricted to numeric field types.
- Extend the committed user-profile schema with `attribution_entity.legal_form` and repeatable `attribution_entity_socios` fields for `nif`, `name`, `share_pct`, and `role`.
- Add focused domain tests proving schema load, percentage bounds, role enum coverage, legal grounding, and preservation of the `taxpayer_type.entity_type=attribution_entity` branch.

## Outcome

- User-profile schema version advanced to 3 for the additive attribution-entity facts.
- `share_pct` is declared as a decimal percentage in the closed interval 0..100.
- `role` covers `socio`, `comunero`, and `participe`; `legal_form` covers sociedad civil and comunidad de bienes.
- LIRPF attribution legal refs already present in the corpus are attached to the new fields.
- Focused user-profile tests pass: `uv run --no-sync pytest src/aeat/domain/user_profile/tests -q`.
- Python lint passes on touched Python files: `uv run --no-sync ruff check src/aeat/domain/user_profile/_schema.py src/aeat/domain/user_profile/tests/test_schema.py src/aeat/domain/user_profile/tests/test_attribution_entity_schema_fields.py`.
- Code review recorded no findings in `2026-07-01-cross-domain-continuity-audit`.

## Notes

- This step intentionally does not implement the `atribucion_member` source resolver or CLI profile editing for socios; W09.P41.S307 and W09.P41.S324 remain separate follow-up rows.
- The existing shared worktree contains extensive unrelated dirty files. This step only edits the user-profile schema surface, focused tests, this exec record, the review audit, the cross-domain feature index, and the plan row closed by the vault CLI.
