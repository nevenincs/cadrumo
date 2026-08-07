---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bf30f7076f7c1a56ff200d36283eaa0d73cd7d37d10185454cb76238e36c3077'
step_id: 'S18'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Enforce the anchor check: a candidate grounds only when its anchor occurs in the transcription and the typed value equals the deterministic parse of that anchor, proven by mutation with an off-document value observing red

## Scope

- `src/cadrumo/application/ledger`

## Description

The structural half of the anti-fabrication contract, landed as
`application/ledger/_grounding_anchor.py`. A candidate grounds only when BOTH
halves hold: its anchor occurs in the transcription, AND the typed value equals
the deterministic parse of that anchor.

The deterministic parse is `core.decimal.coerce_finite_european_decimal` -- the
repository's one extraction-side decimal contract, reused rather than re-spelled,
because that concept already spans five sites. Its refusal to resolve an
ambiguous thousands reading is exactly the behaviour wanted: an anchor whose
reading cannot be settled does not ground.

Byte-identity between anchor and value is deliberately NOT required. Anchor `21`
with value `Decimal("21")` grounds; requiring identity would make the check
useless for every field needing a parse, which is every monetary field. Where
anchor and rendered value ARE the same string the parse half compares a value
against itself and establishes nothing, so `AnchorEvaluation.parse_was_vacuous`
records that rather than letting the outcome read stronger than it is.

An anchor present in the document but parsing to a different value resolves
`CONTRADICTED` rather than merely ungrounded: a reader that located a real
printed figure and typed a different value has a different, faster-to-act-on
defect than one that invented a figure.

### The two lanes give different strengths of evidence

Encoded after the reader-owning lane established that the vision path produces
no transcription at all -- it reads image to fields in one model call, so there
is no independently produced text for an anchor to be a substring of.

- **Text lane** -- the anchor is matched against a transcription a DIFFERENT
  reader produced. A genuine external check.
- **Vision lane** -- the anchor is the model's own claim about its own output.
  Matching it against the model's reply confirms self-consistency, which a
  fabricating model also has.

`FieldProvenance` therefore carries `anchor_self_reported`, and a model validator
makes `ANCHORED` structurally unreachable when it is set. The invariant lives on
the MODEL, not in the checker, so no reading path can launder a claim into a
verified-looking record even by constructing the envelope directly. The anchor is
still recorded -- an operator comparing `21%` against the page is doing exactly
the check the machine cannot, and withholding it would remove what makes that
quick. What is withheld is the verdict.

This is a floor, not a ceiling: when a vision transcription stage lands, that
path calls the same checker and earns `ANCHORED` through the real check with no
change to any logic here.

## Outcome

- `application/ledger/_grounding_anchor.py` -- `evaluate_anchor`,
  `ground_anchored_value`, `ground_self_reported_anchor`,
  `ground_ambiguous_candidates`, `normalise_for_anchor_search`,
  `AnchorEvaluation`. All promoted to the package facade in the same change.
- `FieldProvenance.anchor_self_reported` plus the validator forbidding
  `ANCHORED` on a self-reported anchor.
- The CLI provenance payload mirrors the new field, so the distinction reaches
  the operator rather than stopping at the application boundary.

Normalisation for the substring search is deliberately narrow: Unicode form and
whitespace only. Digits, separators and punctuation are untouched, because those
ARE the evidence -- `1.234,56` and `1234,56` must stay distinct or the check
stops discriminating between readings that differ thousandfold.

## Verification

`test_grounding_anchor.py` -- 19 tests, all passing, run with `-p no:randomly`
and counts read from a log on disk.

Mutation-proved from a pytest plugin on `PYTHONPATH` OUTSIDE the repository;
nothing under `src` was edited, so nothing needed restoring.

- `evaluate_anchor` forced to always return `ANCHORED`: **13 failed, 3 passed**,
  including `test_an_off_document_value_never_grounds` -- the required proof.
- Self-reported anchors made to read as independently verified (validator
  dropped, constructor stamping `ANCHORED`): **2 failed, 17 passed** --
  `test_a_self_reported_anchor_never_reads_as_verified` and
  `test_a_self_reported_anchor_cannot_be_laundered_into_an_anchored_outcome`.

Positive controls carried throughout, so none of these is satisfiable by a
checker that always refuses: a genuinely parsed anchor is asserted NOT vacuous,
and a text-lane anchor is asserted NOT self-reported.

## Notes

The field-form contract declared by the reader lane
(`llm/_invoice_field_contract.py`) was deliberately NOT consumed. It governs the
form a model emits values in; this check asks whether an anchor parses to its
value, which is form-agnostic by construction. Importing it would have added a
new production `application -> llm` edge for something unused, and those pins
exist to make exactly that loud. No second vocabulary was declared.
