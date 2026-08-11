---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:3c1feef44a9535c7603c395c5b6329b9abf92c44a6598f4a3715f0745f941ca5'
step_id: 'S227'
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
     The S227 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Harden the honesty-gate extractor against a helper handed a criteria ATTRIBUTE rather than the criteria itself, a latent fragility recorded rather than changed because no shipped helper triggers it. The extractor recurses into such a helper and attributes reads to that helper's first parameter, which is the attribute VALUE and not the criteria, so a helper reading a field off the value it was handed would contribute that field name as though it were a criteria attribute and the unknown-attribute refusal would fire on a CORRECT predicate. That is the loud direction rather than the silent one, which is why it was recorded and not urgent, but it will present as a false refusal against an author who did nothing wrong and ## Scope

- `src/cadrumo/domain/iva` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden the honesty-gate extractor against a helper handed a criteria ATTRIBUTE rather than the criteria itself, a latent fragility recorded rather than changed because no shipped helper triggers it. The extractor recurses into such a helper and attributes reads to that helper's first parameter, which is the attribute VALUE and not the criteria, so a helper reading a field off the value it was handed would contribute that field name as though it were a criteria attribute and the unknown-attribute refusal would fire on a CORRECT predicate. That is the loud direction rather than the silent one, which is why it was recorded and not urgent, but it will present as a false refusal against an author who did nothing wrong

## Scope

- `src/cadrumo/domain/iva`

## Description

- Read the extractor branch the row names and confirm the attribution it makes.
- Narrow the follow to a helper handed the criteria itself.
- Pin the shape in both directions against a synthetic helper.

## Outcome

PREMISE CONFIRMED and fixed. The extractor attributes every read to the
callee FIRST PARAMETER. For a helper handed a criteria ATTRIBUTE that
parameter is the attribute VALUE, so following it recorded a field of the
value type as though a criteria attribute of that name had been read -- and
the exhaustive-mapping check would then refuse an unknown attribute on a
CORRECT predicate.

Only a helper handed the criteria ITSELF is followed now. Nothing is lost by
declining: the handed attribute is already recorded by the plain attribute
walk, and the attribute IS the fact. That is asserted rather than assumed,
because a fix that also stopped seeing the delegated read would be a
regression wearing a fix.

The row was right to record this as latent rather than urgent -- it is the
loud direction, and no shipped helper has the shape. It was still worth
fixing: a gate that reds a correct predicate is one an author works around
rather than trusts, and "no helper triggers it today" is a fact about today.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

THE FIRST DRAFT OF THE PINNING CASE PROVED NOTHING, and that is the finding
worth carrying. Its synthetic helper read the handed value through getattr.
The extractor walks attribute ACCESS, so the branch was never exercised and
the case passed identically with the fix and without it -- a green assertion
over a shape it never reached, which is the vacuous gate this campaign keeps
removing, authored here by accident while removing another one.

It was caught by running the pre-hardening branch condition and the shipped
one side by side over the same predicate and finding they agreed. They should
not have. The helper reads the attribute directly now, and the two conditions
demonstrably differ: the old one extracts the stray field, the new one does
not.
