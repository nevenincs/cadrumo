---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:fd0c15a62402ffedc2888551b5d7164c35abe12a6fb899883d12cb58ed891cab'
step_id: 'S292'
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
     The S292 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Route category and iva_category through the existing classifier rather than the transcription prompt, since LocalTextLLMClassifier already exists and is consumed by _llm_classification while the invoice reading path produces neither field - and both are judgements rather than transcriptions (issued-versus-received needs the filer identity which the page does not carry, and the IVA regime needs tax knowledge) so asking a transcription prompt for them mixes misread and misclassified into one output with no way to tell them apart - category alone is 221 corpus slots and the whole S4 subject and ## Scope

- `src/cadrumo/application/ledger/_llm_classification.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Route category and iva_category through the existing classifier rather than the transcription prompt, since LocalTextLLMClassifier already exists and is consumed by _llm_classification while the invoice reading path produces neither field - and both are judgements rather than transcriptions (issued-versus-received needs the filer identity which the page does not carry, and the IVA regime needs tax knowledge) so asking a transcription prompt for them mixes misread and misclassified into one output with no way to tell them apart - category alone is 221 corpus slots and the whole S4 subject

## Scope

- `src/cadrumo/application/ledger/_llm_classification.py`

## Description

- Check each of the two fields against what actually produces it, before
  designing a route for either.
- Check whether a shipped gate governs the second.

## Outcome

REFUTED ON BOTH FIELDS, and the row must NOT be built. Executing it as written
would replace two deterministic authorities with probabilistic ones, and the
second is refused out loud by a gate.

The row's premise is that the invoice reading path produces neither field. That
is true of the READING stage and false of the pipeline, and the difference is
the whole row: both are produced one stage later, by code, on purpose.

DIRECTION is derived deterministically from the document. A dedicated module
matches the filer's own tax identity against the printed party blocks and asks
which ROLE the filer occupies, resolving identity through the same-bearer
predicate so a punctuated print still matches a stored compact form, and
attributing by CONTAINMENT within the heading partition rather than by
proximity. It even handles the case a naive comparison gets wrong: a document
placing the filer on BOTH sides yields no derivation rather than answering on
slot order, so it asserts nothing about autoconsumo instead of asserting
something false.

IVA CATEGORY is governed by a SINGULARITY GATE. Exactly one module on the
ingestion path may decide it, and the gate records why: two rival deriving
surfaces once sat live ahead of the sanctioned authority and reached it never,
while the criteria assembly that feeds the rule table had no production caller
at all. Routing the field through the LLM classifier would add a third rival to
a surface that was deliberately reduced to one, and the gate would red.

So the residual the row was written from is real -- both fields read as absent
at the extractor stage -- but the diagnosis inverts the cause. The fields are
not missing from the pipeline; the CAPTURE was taken before they exist, which
is the sibling row's subject.

No change made.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

THIS IS THE THIRD ROW TODAY WRONG IN A WAY ITS EXECUTOR COULD FULLY SATISFY,
after the branch-table sweep and the postal role-evidence widening. The shape
repeats: an accurate measurement, a plausible cause, and a remedy that damages
working code. Nothing about "route these two fields through the existing
classifier" announces difficulty, and the classifier genuinely exists.

What makes this one the sharpest of the three is that the harm was already
written down before I got here. The sibling capture row records, in its own
words, that an identical residual across every pilot document motivated a
proposal to route both fields through the LLM classifier and would have
replaced two deterministic authorities with probabilistic ones. That row is
this row's cause, and reading it first is what turned a build into a refutation.

The standing lesson, now earned three times in one session: check for the
authority and the gate BEFORE designing the remedy. Twice today I checked
afterwards and had to revert.
