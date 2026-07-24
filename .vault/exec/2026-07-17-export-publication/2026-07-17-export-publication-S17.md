---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S17'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Make the subject-access completeness claim true by deriving the excluded personal-data categories from the bundle coverage manifest, carrying them beside the included categories through the operation journal and the operator payload, and rewriting the catalogue notice to state both what the archive holds and what it omits, gated on a test asserting the excluded set matches the manifest and ## Scope

- `src/cadrumo/application/user_profile/_bundle_export_contracts.py`
- `src/cadrumo/application/user_profile/_bundle_export_operation.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make the subject-access completeness claim true by deriving the excluded personal-data categories from the bundle coverage manifest, carrying them beside the included categories through the operation journal and the operator payload, and rewriting the catalogue notice to state both what the archive holds and what it omits, gated on a test asserting the excluded set matches the manifest

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_contracts.py`
- `src/cadrumo/application/user_profile/_bundle_export_operation.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`

## Description

- Confirm the gap: the archive ships under the structured custody profile, so whole
  namespaces stay in encrypted storage while the response listed only what it carried.
- Derive the omitted categories from the same coverage manifest the serializer already
  computes, as the counterpart of the carried derivation.
- Carry the omitted set on the durable operation record and the published result so it
  reaches the operator surface by the same route as the carried set.
- Report it on the subject-access payload, never omitted.
- Rewrite the catalogue notice to state what the archive holds and what it does not,
  replacing the completeness assertion.
- Correct the contracts module docstring, which claimed the exhaustiveness refusal made
  the response complete.
- Author the rewritten notice in all four catalogues through the locales CLI.
- Add a test asserting the reported omissions equal the manifest's, that carried and
  omitted are disjoint, and that the omitted set is not empty.
- Add a pure-derivation test pinning the direction of the two helpers.

## Outcome

The claim is now true rather than softened. The wording no longer asserts completeness;
it names the omissions and points at the encrypted recovery archive for them, and the
machine-readable context carries both sets so an automated reader sees the same thing
the prose says.

The non-vacuity assertion earns its place: the structured archive really does leave
namespaces behind, so this was a live disclosure gap and not a formality. Carried and
omitted are asserted disjoint, so no category can be claimed as both.

Both sets derive from one coverage manifest, which is the property that keeps them
honest over time. A future custody-profile change moves both together, and neither can
drift from what the bundle actually did.

Non-tautology is observed: dropping the omitted set from the payload reddens both
subject-access proofs, one on the empty list and one on the manifest comparison.

## Notes

Switching the right-of-access archive from structured to full custody was considered
and deliberately not done here. It changes what leaves the encrypted boundary in a
legally-loaded artefact, which is a decision for an accepted record rather than a code
change, and it is being carried to the operator separately. This step makes today's
claim accurate under today's custody profile.
