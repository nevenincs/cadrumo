---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:7af202fe5af556369614f9bd103a6bd54444994cee8508bd79eacb6788735375'
step_id: 'S284'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Decide what the Workspace schema record's required label means for formula, binding, relation and parameter rows, for which no locale-key derivation exists alongside the modelo, revision, construct and casilla functions that do: rule whether these identities carry operator-facing display text at all, and either add the missing key convention with its four catalogue entries or give the label field a way to state that a row's identity is a technical name rather than a translated string, so a bare identifier is never presented as a localized label; amend the governing registry-api-gate decision record in the same change

## Scope

- `the amended 2026-08-24-tui-registry-api-gate-adr`
- `src/cadrumo/domain/calculations/registry/modelo_localization.py`
- `src/cadrumo/application/modelo/workspace_models.py label contract`
- `and focused non-casilla label tests`

## Changes

- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md`
- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_models.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_models.py -m "unit or integration" -q` -> `pass` (29 passed, 1 pre-existing unrelated failure)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace_models.py` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (69 passed, no regression)

## Notes

Ruled: formula, binding, relation, and parameter identities carry no
operator-facing display text, and the label field now says so honestly
rather than either inventing a translation or leaving the question
unanswered. Checked `modelo_localization.py` for a key-derivation function
(none exists for these four kinds, only modelo/revision/construct/casilla)
and checked existing consumers before ruling rather than assuming: both
`work_review.py`'s findings and the discovery CLI's missing-binding
diagnostics already display these identifiers as bare registry names in
every place they currently surface, never as translated prose. The absent
locale convention is the correct reflection of what these identities are,
not a gap to fill with four new catalogue key families -- which, per the
locales rule's no-untranslated-state guarantee, would have meant real
authored values in all four catalogues for every formula/binding/relation/
parameter in every revision, a large permanent translation burden for names
nobody reads.

`ModeloWorkspaceSchemaRecordV1.label` is now `ModeloWorkspaceRecordLabelV1`,
a discriminated union of the existing `ModeloWorkspaceLocalizedTextV1`
(`kind="localized"`, default -- every existing caller unaffected) and the
new `ModeloWorkspaceTechnicalLabelV1` (`kind="technical"`, carrying only its
own `identifier`, no locale summary attached because none was resolved).
Same shape of decision as S283's `None`-versus-`()`: the type previously had
no way to say "this row's name was never translated," so a bare identifier
could silently masquerade as a resolved localization. Proved both label
kinds construct, discriminate correctly, and round-trip through JSON.

Two pre-existing tests needed a one-line fix: they built the localized
label payload as a raw dict without the new required `"kind"` tag, which
the discriminator now requires to resolve the union. Fixed in the same
commit rather than leaving them red.

**Seventh field-shape gap this campaign, same underlying cause named at
S283**: `review_status`, `family_dispositions`, `legal_refs`/`constraints`,
and now `label` are all instances of the shared Workspace records assuming
something the STATIC_INSPECTION-side data or convention did not provide.
Unlike the first three, this one was not about `RegistryRevisionInspection`
missing a field -- it was the locale catalogue itself having no convention
for these identities at all, structurally correctly so. Worth distinguishing
the two failure shapes going forward: "the inspection doesn't carry this"
versus "no convention for this exists anywhere," since the fix differs
(enroll a field vs. teach a type to express absence).
