---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ab793c8d3711932677938816e49e351e79ec571baf23a9a00321163503c5b361'
step_id: 'S83'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S83 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add a declaration-time guard refusing any StorageLocation carrying both override_policy=FIXED and a non-null settings_field, with a positive control proving an OPERATOR_OVERRIDABLE member with a settings_field is not flagged, because S18's existing gate only asserts that today's fixed members happen to carry no settings_field rather than refusing the combination itself, so the guarantee behind R10's keystore-must-not-relocate-out-from-under-its-bucket invariant is currently held by the absence of a field on today's declarations, not by a guard, and would silently stop being true the moment anyone gives a FIXED member a settings_field, which the model permits and which the existing gate would still pass because it would then be asserting a fact that had quietly stopped holding for the thing it names and ## Scope

- `src/cadrumo/core/_storage_taxonomy.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a declaration-time guard refusing any StorageLocation carrying both override_policy=FIXED and a non-null settings_field, with a positive control proving an OPERATOR_OVERRIDABLE member with a settings_field is not flagged, because S18's existing gate only asserts that today's fixed members happen to carry no settings_field rather than refusing the combination itself, so the guarantee behind R10's keystore-must-not-relocate-out-from-under-its-bucket invariant is currently held by the absence of a field on today's declarations, not by a guard, and would silently stop being true the moment anyone gives a FIXED member a settings_field, which the model permits and which the existing gate would still pass because it would then be asserting a fact that had quietly stopped holding for the thing it names

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Add a second `model_validator(mode="after")` on `StorageLocation` refusing
  `override_policy=FIXED` combined with a non-null `settings_field`.
- Add a mutation-proof test exercising three cases: the violating declaration
  raises `ValidationError` at construction; the identical `settings_field` on
  an `OPERATOR_OVERRIDABLE` member (positive control) is unproblematic;
  removing only the `settings_field` from the `FIXED` declaration restores a
  legal construction.
- Confirm every one of the 57 real taxonomy declarations still constructs
  cleanly under the new guard.

## Outcome

The existing gate (`test_bucket_and_keystore_layout_is_fixed_not_operator_
overridable`) only asserted that today's `FIXED` members happen to carry no
`settings_field` — a fact about current declarations, not a constraint on a
future one. The new validator makes the contradictory combination
unconstructable at declaration time instead of merely absent so far.

Mutation-proven from the violating-declaration side (not by disabling the
guard): a `StorageLocation` built with `FIXED` and a `settings_field` raises
immediately; the guard does not misfire on a legitimate `OPERATOR_OVERRIDABLE`
member carrying the same field name.

## Notes

None. No skipped work, no scaffolds left in code.
