---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:837f4221e4f39db196fb8aca13f7700bb16fba0f5bb1fdb6d43679a4fd77d33a'
step_id: 'S327'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Surface the operation phase, deadlines, diagnostic reference and terminal receipt references in the operation modal, which today renders none of them although the public projection already carries every one: the modal's view model carries only the projection, spinner visibility, three control-enablement flags, close policy, interaction affordance and terminal copy key, and the modal itself renders status copy, a review dump, log rows and button enablement -- while `phase_code`, `execution_deadline_at`, `cleanup_deadline_at`, `diagnostic_ref`, `result_ref` and `refusal_ref` all exist on the public projection contract. So four of the eight facts the modal is supposed to present are not merely unproven, they are unrendered. Extend the view model with derived fields for each, validated against the projection in the same shape as the existing derivation validator so a derived field cannot disagree with its source, and render them. This is production work and is a prerequisite for proving that rendered state follows supervisor revisions -- that proof cannot discharge its own row while half the facts it names never reach a widget

## Scope

- `the operation modal view-model projection`
- `the modal render path`
- `and derivation validation for each new field`

## Changes

- `M` `src/cadrumo/entrypoints/tui/operations/projection.py`
- `M` `src/cadrumo/entrypoints/tui/operations/modal.py`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/operations/tests -m integration -n0 -k "not detach_closes"` -> `pass`

## Notes

The view model gains six derived fields: phase, both deadlines, the
diagnostic reference, and a settled receipt collapsed into one reference plus
a kind discriminator. The collapse is the only real derivation among them.
The projection refuses to carry a result and a refusal together, so a settled
operation has at most one receipt; representing that as one reference and a
kind makes the mutual exclusion the contract already guarantees impossible to
render wrongly, where two nullable fields would leave a renderer free to show
both.

Each field is checked in the existing derivation validator against its source.
The receipt check deliberately does NOT call the helper the builder uses. It
reads the settled reference straight off the projection, because a validator
sharing the builder's helper agrees with it by construction and a defect
inside that helper passes unseen. That was found by mutation, not by
inspection: corrupting the shared helper left every lifecycle test green
until the two readings were separated.

Six locale keys were added with real values in all four catalogues through the
locale CLI. Every key is spelled as a literal argument to the translation
call, after a first attempt assembled two of them from variables and the
catalogue scanner reported them as extras it could not see; a key it cannot
see drifts out of the catalogues at the next scaffold. The catalogue drift
check now reports no extras. The sixteen keys still missing from the Catalan
and Hungarian catalogues predate this change and belong to other surfaces.

Discovery for this Step ran against the local fallback index rather than the
live semantic-search service, which was down.
