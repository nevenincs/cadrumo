---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:f159e722de82bb8f82f2578f6ec97efd32a04ac45431c49b4d94cdf8b5e25e00'
step_id: 'S144'
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
     The S144 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Drive the anchor-not-equal-to-value gate from the contract declaration rather than a hardcoded name tuple, since the postal fixtures honour the property by author convention and collapsing an anchor to equal its value reds nothing, following the sibling gates in the same file that already derive their subjects. Rename the free-text grounder which now serves four fields while naming one of them and ## Scope

- `src/cadrumo/llm` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Drive the anchor-not-equal-to-value gate from the contract declaration rather than a hardcoded name tuple, since the postal fixtures honour the property by author convention and collapsing an anchor to equal its value reds nothing, following the sibling gates in the same file that already derive their subjects. Rename the free-text grounder which now serves four fields while naming one of them

## Scope

- `src/cadrumo/llm`

## Description

- Derive the anchor-not-equal-to-value gate's subjects from
  `INVOICE_FIELD_CONTRACTS`, replacing the hardcoded four-name monetary tuple,
  and rename it for the widened scope.
- Rename `_grounded_invoice_number` to `_grounded_free_text` at its definition
  and its dispatch-table entry, and document why the validator is named for the
  form rather than for a field.

## Outcome

The gate now covers every declared field. The retired tuple named the four
monetary fields, so the identifier, postal, country and legend anchors honoured
the non-equality property by author convention alone — a real gap, because the
anchor evaluator downstream treats an anchor equal to its value as a vacuous
parse and reports it as such. The gate and the evaluator now agree about which
pairs are worthless.

Every declared field is in scope rather than only the parsing forms, because the
property is about the FIXTURE and not about the form: whatever a field's declared
form, an anchor authored equal to its value tests nothing.

The free-text validator was named for the invoice number when that was the only
free-text field declared. It now serves six — both postal codes, both printed
countries, the invoice number and the regime legend — so a name pointing at one
of the six read as a rule about invoice numbers the other five were borrowing.
The dispatch tables key on the declared form, so the form is what the name says.

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

Both lanes were run sequentially over the owning suite.

    uv run --no-sync pytest -n0 -q -p no:randomly src/cadrumo/llm/tests
      -m "unit and not external_tool and not os_keychain and not resident_service"
    371 passed, 3 deselected in 95.72s (0:01:35)

    uv run --no-sync pytest -n0 -q -p no:randomly src/cadrumo/llm/tests
      -m "integration and not external_tool and not os_keychain and not resident_service"
    2 passed, 372 deselected in 3.30s

The gate was mutation-proved in three arms from outside the repository, each
printing a landed-marker, patching after collection because the fixture dict and
the subject binding are module-level names read at call time.

The control arm, plugin loaded and no mutation selected, passed. Authoring the
supplier country anchor equal to its grounded value failed the gate. The third
arm applied that same collapse AND rebound the subject set to the four monetary
names the retired tuple listed, and PASSED — which is the measurement that the
old shape was blind to the defect the new one catches, rather than an assertion
that it was.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The originating row describes the free-text grounder as serving four fields. It
serves six as of this change; the two printed-country fields landed after the row
was written.

No fixture needed altering to satisfy the widened gate: every declared field's
authored anchor already differed from its value, so the change records an
existing convention as a gate rather than forcing new fixture content.
