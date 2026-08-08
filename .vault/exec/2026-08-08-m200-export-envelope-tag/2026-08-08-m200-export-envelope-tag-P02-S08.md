---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:f5eece8c67c50d7389a5e96974865c74336be9f1bc71b75dc32e1299f57f0f5f'
step_id: 'S08'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---




# prove the byte-level test is load bearing by reverting the open-tag composite and the envelope-footer record, confirming the test reds, then restoring the fix

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`

## Description

- Lock the close tag with a proof that removing the footer record removes the tag:
  rebuild the layout through the registry's own model without its
  `envelope_footer` record, render through the real export entrypoint, and assert
  the closing bytes are gone while the open tag — declared on a different record —
  is unaffected.
- Lock the open tag against re-collapse with a real-site refusal proof in the
  registry validator's own suite: read the committed Modelo 200 year field by
  property, restore the 17-character width the defect shipped with, and drive the
  real validator over the real loaded revision.
- Prove that refusal is caused by the width ruling this feature installed, by
  restoring the abstention in memory from a pytest plugin loaded from outside the
  repository, so nothing under the source tree changes and no peer sweep can
  commit the mutation.

## Outcome

Both ends of the envelope are now load-bearing rather than merely asserted. The
footer-removal proof matters because a close-tag assertion could otherwise pass
for the wrong reason, if some other record happened to end the fichero with those
bytes; dropping the record shows the bytes leave with it.

The refusal proof reds with the abstention restored:

    PLUGIN: filing_year width ruling set back to None
    Failed: DID NOT RAISE RegistryValidationError

That also establishes something the grounding reference did not: the collapsed
17-character declaration does not trip the byte-range overlap check either, so the
width ruling is the only detector for this defect shape. Which is precisely why an
abstaining ruling let it ship.

Both proofs ship as permanent tests rather than as transient edits to tracked
files, so there is no window in which a peer could sweep a mutation into the tree.

## Verification


Both locks green:

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -k "modelo_200" -n0 -q
    4 passed, 42 deselected in 18.08s

The refusal proof reds when the abstention is restored from outside the repository:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part1.py::test_validator_rejects_the_modelo_200_envelope_open_tag_collapsed_onto_one_draft_field -n0 -q -s -p abstain_plugin
    1 failed in 5.40s

## Notes

