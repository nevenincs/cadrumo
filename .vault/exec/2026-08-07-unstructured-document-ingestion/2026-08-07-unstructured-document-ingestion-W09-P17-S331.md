---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:7126602ac8a638a389c7f4373a23b02c971f6d80d9bf475eeb78201a580d79a8'
step_id: 'S331'
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
     The S331 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Wire the printed-statutory-citation supply-nature derivation into the confirm path, which is fully built and has NO production caller. MEASURED 2026-08-12: derive_supply_nature_from_citation and match_statutory_citations are exported on the domain facade and covered by their own suite, and nothing in the application layer calls either - so the axis is built and switched off, the dormant-resolver shape the aggregation rule names. The cost is not theoretical: the assembly's own gap message TELLS the operator the axis is settled by a printed statutory citation or an explicit assertion, and the declared-facts builder's comment calls the citation one of the two sanctioned sources - yet a document printing an art. 25 mention still asks the operator, because nothing reads it. The legend the reader already recovers is the input, and the derivation returns a typed three-state outcome whose DERIVED case carries the nature and its citations. Feed it into declared.supply_nature under DOCUMENT_EVIDENCE provenance, with the operator's own assertion continuing to take precedence, and surface CONTRADICTED as a review item rather than resolving it - the model refuses to carry a nature there precisely so a caller cannot use one side of a disagreement and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Wire the printed-statutory-citation supply-nature derivation into the confirm path, which is fully built and has NO production caller. MEASURED 2026-08-12: derive_supply_nature_from_citation and match_statutory_citations are exported on the domain facade and covered by their own suite, and nothing in the application layer calls either - so the axis is built and switched off, the dormant-resolver shape the aggregation rule names. The cost is not theoretical: the assembly's own gap message TELLS the operator the axis is settled by a printed statutory citation or an explicit assertion, and the declared-facts builder's comment calls the citation one of the two sanctioned sources - yet a document printing an art. 25 mention still asks the operator, because nothing reads it. The legend the reader already recovers is the input, and the derivation returns a typed three-state outcome whose DERIVED case carries the nature and its citations. Feed it into declared.supply_nature under DOCUMENT_EVIDENCE provenance, with the operator's own assertion continuing to take precedence, and surface CONTRADICTED as a review item rather than resolving it - the model refuses to carry a nature there precisely so a caller cannot use one side of a disagreement

## Scope

- `src/cadrumo/application/ledger`

## Description

- Trace where the supply nature actually comes from, before designing a way to
  suggest one.
- Wire the citation derivation into the declared-facts builder, behind the
  operator's own answer.
- Gate the route, its provenance, and the outcomes that must NOT produce a
  nature.

## Outcome

Delivered. A document that prints a statutory citation now settles its own
supply nature instead of asking the operator about it.

THE AXIS WAS BUILT AND SWITCHED OFF. `derive_supply_nature_from_citation` and
`match_statutory_citations` are exported on the domain facade and covered by
their own suite, and NOTHING in the application layer called either. So the
route existed end to end except for the one call that would make it run.

The cost was not theoretical, and it was written into the code twice. The
assembly's gap message tells the operator the axis is settled by "a printed
statutory citation, or an explicit operator assertion". The declared-facts
builder's own comment calls the citation one of the two sanctioned sources. A
document printing an art. 21 exemption asked the operator anyway, and the
instruction it gave them named a route that could not fire.

The legend the reader already recovers is the input, and BOTH lanes carry it --
the structured path reads it exactly from the record, the model path
transcribes it -- so one call site reaches every reader rather than the one it
was written for.

PROVENANCE IS THE CONTRACT HERE, and it is the reason this is not a one-line
change. A citation-derived nature is stamped DOCUMENT_EVIDENCE, not
OPERATOR_ASSERTION: an auditor asking why this record says goods must be sent
to the printed article rather than to a person. Reusing the operator stamp
would have passed every value check while telling the auditor to go and ask
somebody about a fact the page states.

The operator's own answer is checked FIRST and wins, provenance included. They
hold the document and can see a mention the reader mis-transcribed, so an
assertion is a correction rather than a duplicate.

Only the DERIVED outcome yields a value. CONTRADICTED deliberately carries no
nature -- the model refuses to hold one side of a disagreement -- and ABSENT is
the ordinary outcome for the domestic majority, which is obliged to cite no
article at all. Both are gated, alongside art. 84, which the table records as
establishing NOTHING because its sub-rules reach goods and services alike.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

FOUND BY REFUSING TO BUILD THE ROW THAT ASKED FOR A MODEL. The sibling row
proposes an LLM pre-suggestion for this axis. Tracing what already settles the
nature -- the discipline that turned three other rows around this session --
found a deterministic settler sitting unwired. A model guessing a fact the
document states, while the deterministic reader of that same statement had no
caller, would have been the sharpest instance of the pattern yet.

WORTH CARRYING: the "zero callers is not evidence of dead code, it is evidence
of no wired consumer" rule earned itself again here, and this is the second
dormant-or-blind surface found today after the ladder's rate walk. Both were
invisible for the same reason -- a well-tested unit whose test suite proves the
unit works and says nothing about whether anything calls it.

A CATEGORY-TO-NATURE DERIVATION IS A SEPARATE, LARGER CANDIDATE and is
deliberately NOT built here. Most categories that demand the nature fix it by
legal definition, verified against the bundled corpus: art. 25 exempts "las
entregas de bienes definidas en el articulo 8", art. 21 "las entregas de bienes
expedidos o transportados fuera de la Comunidad", art. 13 "las adquisiciones
intracomunitarias de bienes". But art. 22, assimilated exports, is the trap and
the corpus shows it plainly -- it covers "las entregas, construcciones,
transformaciones, reparaciones, mantenimiento, fletamento... y arrendamiento",
which are services as much as goods. A derivation that treated the export
family uniformly would silently assert GOODS on service exports. That row wants
its own grounding pass rather than a ride on this one.

The full-tree collect reports one error, and it is neither this nor a
regression: the registry loader refuses with "registry directory changed during
cache fingerprinting; retry after concurrent registry writes settle" -- a peer
writing registry files, the documented loader-cache race, named as such by the
refusal itself.
