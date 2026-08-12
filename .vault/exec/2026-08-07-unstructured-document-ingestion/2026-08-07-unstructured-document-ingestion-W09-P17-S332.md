---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b5349c6e538a509fcea0de0eba141e42e26616dbf1f610ac970d198ae97d97cf'
step_id: 'S332'
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
     The S332 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The CANDIDATE, needing its own grounding pass: derive the supply nature from the DECLARED IVA category, which fixes it by legal definition on most of the branches that demand it. Verified against the bundled corpus 2026-08-12 - art. 25 exempts las entregas de bienes definidas en el articulo 8, art. 21 las entregas de bienes expedidos o transportados fuera de la Comunidad, art. 13 las adquisiciones intracomunitarias de bienes, and two members name services in their own identifiers. So an operator asked goods-or-services on an intra-community supply is being asked a question the law already answers. THE TRAP IS ART. 22 AND THE CORPUS SHOWS IT PLAINLY: assimilated exports cover las entregas, construcciones, transformaciones, reparaciones, mantenimiento, fletamento and arrendamiento, which are services as much as goods, so a derivation treating the export family uniformly would silently assert GOODS on service exports. Domestic reverse charge is the other open one, art. 84 reaching both. DESIGN CONSTRAINT, not optional: the citation table ALREADY encodes this project's rulings on which article establishes which nature, each with a corpus_ref, so a second category-keyed table would be a rival authority on one question. Route category to its defining article to that existing table instead, which makes the new data a mapping rather than a second judgement and ## Scope

- `src/cadrumo/domain/iva` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# CANDIDATE, needing its own grounding pass: derive the supply nature from the DECLARED IVA category, which fixes it by legal definition on most of the branches that demand it. Verified against the bundled corpus 2026-08-12 - art. 25 exempts las entregas de bienes definidas en el articulo 8, art. 21 las entregas de bienes expedidos o transportados fuera de la Comunidad, art. 13 las adquisiciones intracomunitarias de bienes, and two members name services in their own identifiers. So an operator asked goods-or-services on an intra-community supply is being asked a question the law already answers. THE TRAP IS ART. 22 AND THE CORPUS SHOWS IT PLAINLY: assimilated exports cover las entregas, construcciones, transformaciones, reparaciones, mantenimiento, fletamento and arrendamiento, which are services as much as goods, so a derivation treating the export family uniformly would silently assert GOODS on service exports. Domestic reverse charge is the other open one, art. 84 reaching both. DESIGN CONSTRAINT, not optional: the citation table ALREADY encodes this project's rulings on which article establishes which nature, each with a corpus_ref, so a second category-keyed table would be a rival authority on one question. Route category to its defining article to that existing table instead, which makes the new data a mapping rather than a second judgement

## Scope

- `src/cadrumo/domain/iva`

## Description

- Check whether the category-to-article grounding already exists, before
  authoring any of it.
- Join the two shipped tables into a derivation that rules on nothing itself.
- Rank it below the printed citation and gate the precedence and the traps.

## Outcome

Delivered, and as a JOIN rather than a table. A document declaring a
cross-border category now settles its own supply nature with nothing printed on
the page.

NO NEW LEGAL JUDGEMENT WAS MADE, which is the whole design. Which articles
ground a category is already declared once, in the component table's
`legal_refs`. What an article establishes about the nature is already declared
once, in the statutory-citation table, each row carrying its `corpus_ref`. This
walks from one to the other. A category-keyed map of natures would have been a
second authority on a question two tables already answer, and it would have
drifted the first time either moved.

MEASURED over the shipped tables: exactly three categories derive, all GOODS --
intra-community supply via art. 25, intra-community acquisition via art. 15,
and export via art. 21. Those are high-volume cross-border families, and every
one of them was asking the operator a question the law had already answered.

THE DANGEROUS CASE EXCLUDES ITSELF, and that is the reason for the shape rather
than a happy accident. LIVA art. 22, assimilated exports, reads "las entregas,
construcciones, transformaciones, reparaciones, mantenimiento, fletamento... y
arrendamiento" -- services as much as goods. A hand-written map over the export
family would have asserted GOODS on service exports and nothing downstream
could have told. Art. 22 has no row in the citation table because nothing ever
ruled what it establishes, so the join finds nothing and the category stays
open. The same holds for the domestic reverse charge, whose art. 84 row
establishes nothing on purpose. Both are gated, and one case asserts the
exclusion comes from the TABLES rather than from a special case here -- so
adding an art. 22 row later fails loudly instead of silently starting to assert
a nature on service exports.

Ranked BELOW the printed citation, because the page is more specific than the
family: a document citing an article states something about itself, while a
category states what its family rests on. The operator still outranks both,
provenance included. All three routes and their full precedence are gated.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

KNOWN LIMITATION, recorded rather than worked around: the two SERVICE members
derive nothing. Their grounding articles are the general place-of-supply rules
69 and 70, which the citation table deliberately omits -- its own note explains
why, and the reason is a property of that table's file-based check rather than
of what the articles mean. So the two categories whose nature is most obvious
from their own identifiers are exactly the two this cannot settle. Closing that
belongs to the citation table, which would need to separate "what the article
establishes" from "can the check read it from the bundled file", and it is not
a special case to add here.

The category derivation deliberately does NOT consult
`supply_nature_is_required`. It answers for any category and lets the assembly
decide when to ask -- one authority on the laziness rule, not two.

Two suite failures alongside are not this surface. A registry cycle case fails
under parallel pytest and passes alone, which is the loader-cache race the local
execution rule names; a peer is writing registry files concurrently, and the
loader refused a full collect with "registry directory changed during cache
fingerprinting" in the same window. The rest are the locale-rendering set and a
peer mid-sweep on a new IVA category member.
