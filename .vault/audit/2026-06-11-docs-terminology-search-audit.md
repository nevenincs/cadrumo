---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-06-11'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace docs-terminology-search with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `docs-terminology-search` audit: `umbrella gap-concept curation pass`

## Scope

A richness curation pass acting on the redeclaration-gate lever surfaced by
the S27 review: the documentation referenced 16 high-frequency tax-vocabulary
terms that had no approved Terminology Handbook concept, so the glossary, the
redeclaration gate, and the compiled search could not anchor them. This pass
hand-authored the missing umbrella concepts with real, grounded definitions to
widen all three surfaces at once. Implements ADR D1 (the committed Handbook
authoring tree) in service of D7 (the redeclaration gate's coverage). No
fabricated definitions: every concept is sourced from the BOE-cited vault
glossary references and the pre-cutover glossary content.

## Findings

The 16-term gap split into two groups. PRIORITY 1 - clear tax-domain umbrella
terms grounded in the BOE-cited Spanish glossary reference: `iva` (Ley
37/1992, BOE-A-1992-28740), `irpf` (Ley 35/2006, BOE-A-2006-20764), `renta`
(the IRPF income base), `modelo` (the generic numbered AEAT form), `nif` (the
tax identifier, with CIF/NIE as admitted forms), `vies` (the EU VAT-number
validation system). PRIORITY 2 - app vocabulary grounded in the pre-cutover
glossary: `fichero-boe`, `ledger`, `binding`, `work-unit`, `preflight`,
`revision`, `verificado-completo`.

All 13 were authored as `concepto`-domain concepts and reached `approved`
(each carries an es definition with a `source` citation plus es/en/ca/hu
short descriptions - the approved-completeness gate). The Spanish-stem tax
terms keep Spanish stems per the naming rule; the English app vocabulary
(`ledger`, `binding`, `work-unit`, `preflight`) is English-named as generic
product vocabulary, which the naming rule permits.

Legal grounding: the umbrella tax concepts cite their establishing law in
prose `source` (LIVA / LIRPF / RGAT / EU Regulation 904/2010), but carry NO
`legal_refs` - the establishing articles (LIVA art. 1, LIRPF art. 1) do not
resolve in the legal catalogue, which holds only the specific calculation
articles. This is the S13 pattern: drop the unresolvable ref, keep the prose
source. So zero `legal_refs` were added; all grounding is prose-sourced.

Two term collisions were caught and resolved (the recargo lesson): the new
`renta` concept initially claimed `declaracion de la renta`, already owned by
`modelo-100` (the form legitimately owns that surface) - removed from `renta`.
The `verificado-completo` concept referenced a non-existent `presentado`
relation target - retargeted to the real `borrador-vs-presentado` concept.
After the fixes the glossary renders 33 approved concepts with ZERO
deduplication.

## Recommendations

- A follow-up doc pass can now convert the remaining plain prose mentions of
  these 13 terms to `{term}` references; this pass already converted the 3
  `modelo (...)` parenthetical glosses the gate auto-flagged the moment
  `modelo` became approved (the gate widened correctly, the conversions
  followed).
- The audit backlog (75 draft concepts, 75 empty short descriptions) is the
  next curation target; the standing curation ratchet tracks it.
- Each newly-approved term is now enforceable by the redeclaration gate, so
  future inline redefinitions of `iva`, `irpf`, `modelo`, etc. red the build.

## Codification candidates

None. This is a content-curation pass (authoring concepts), not a
constraint-shaped lesson: the existing rules already govern the discipline
(`aeat-spanish-stem-naming`, `registry-calculation-legal-grounding`,
`terminology-scaffold-preserve-contract`). No new cross-session rule is
warranted.

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
(the directory the CLI's `vaultspec-core spec rules add` writes to today; the
planned `--scope project` flag will move authored rules under
`.vaultspec/rules/rules/project/`).

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

<!-- Example:

- **Source:** finding S04 (destructive verbs lack preview).
  **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
