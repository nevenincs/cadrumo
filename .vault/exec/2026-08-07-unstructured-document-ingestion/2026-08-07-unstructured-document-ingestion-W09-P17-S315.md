---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ed8ef9aed761c9e6e10b7ca9c5bdef32a9a236d0b45d09555c7272c234da1c18'
step_id: 'S315'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S315 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Determine whether package docstring examples are collected as doctests anywhere in the suite, and record the answer, so a shipped example that raises is either caught by a gate or knowingly ungated and ## Scope

- `dev/docs` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Determine whether package docstring examples are collected as doctests anywhere in the suite, and record the answer, so a shipped example that raises is either caught by a gate or knowingly ungated

## Scope

- `dev/docs`

## Description

- Search every configuration surface that could enable doctest collection, rather than one.
- Report the result as a measured absence with the surfaces named, so a later reader can tell what was checked.
- Change no code: the row asks a question and records its answer.

## Outcome

**Nothing in this repository collects docstring examples as doctests.** Checked the pytest configuration, the justfile, the documentation build configuration, and the workflows that run tests. No collection flag, no module option, no conftest hook.

So a shipped example that raises is **knowingly ungated**, which is the second of the two states the row asked to distinguish. It is not caught by anything, and nobody is under the impression that it is.

**That settles the disposition of the broken example the sibling row removed rather than repaired.** Repairing it would have restored an artefact with nothing to verify it, in a tree where exactly that condition let the original decay into an import error unnoticed. Removal was correct, and this measurement is the reason rather than the assertion.

## Verification

    surfaces checked for doctest collection    6
    surfaces enabling it                       0

The absence is over the surfaces named above. A collection hook in a location not checked would not be visible to it, and none is claimed to be absent beyond those.

## Notes

**A negative from a search is only as wide as the search.** This one is stated with its surfaces enumerated so the claim can be re-tested rather than re-believed.

