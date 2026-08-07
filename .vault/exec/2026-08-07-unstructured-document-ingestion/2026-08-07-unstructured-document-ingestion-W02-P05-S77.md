---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e32b983e97eaac988bd85a1446177222ba363b276bd860c0326ca3e5c77a5e0c'
step_id: 'S77'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Declare the field-form contract once and compile it into both the extraction prompt and the grounding validators (a rate as a bare number, amounts preserving the printed decimal separator, dates exactly as printed), resolving the printed-percent mismatch, gated by a contract-parity test proving prompt guidance and validator vocabulary derive from one declaration

## Scope

- `src/cadrumo/llm`

## Description

- Confirm the single field-form declaration is live and both derivations bind to
  it: one tuple of typed contract rows, each carrying the form the value must
  arrive in, the concept it means and the micro-guidance line the prompt renders.
- Extend the declaration with the two withholding fields, exercising the
  single-declaration property rather than asserting it: adding the rows alone
  reddened the parity gate, the fully-populated grounder round and both anchor
  fixtures until the response schema, the anchor mirror and the grounding
  dispatch had gained them too.
- Ground the withholding rate through the existing percentage form and the
  withheld amount through the monetary form, so the printed-percent resolution
  covers them with no new grounding branch.
- Populate the end-to-end Spanish fixture with a real withheld invoice, correcting
  its arithmetic to base plus cuota less retencion.

## Outcome

The form vocabulary is declared once and consumed twice, and the parity gate
proves it in both directions: the declaration covers the response schema exactly,
every declared form has exactly one grounding validator, and the grounder grounds
exactly the declared fields. The printed-percent mismatch stays resolved for the
new fields for free, because a rate is a form rather than a field: a document
printing a withholding as `-15%` yields the value `15` while its anchor keeps
`-15%` verbatim, so the distinction anti-fabrication depends on survives.

That the addition of two fields could not be made without the gate firing four
times is the evidence the declaration is load-bearing rather than decorative.

## Verification

    pytest src/cadrumo/llm/tests/test_invoice_field_contract.py src/cadrumo/llm/tests/test_invoice_prompt_cache_binding.py src/cadrumo/llm/tests/test_invoice_field_anchors.py -n0 -p no:randomly -q
    90 passed in 29.94s

Run sequentially on a cold interpreter against an isolated export of the tree,
because a concurrent lane's in-flight consent work leaves the working copy of the
llm package unimportable. Model-free and network-free throughout: no transport is
constructed anywhere in these gates.

Before the response schema and grounding dispatch were extended, the same
selection reported the parity gate biting on the incompleteness:

    5 failed, 85 passed in 38.69s

## Notes

The wider suites show 31 failures both before and after the change, an identical
set with zero delta, measured as a set difference against a baseline captured
from a pristine export of the same commit. Those failures belong to a separate
lane rewriting tests that assert a deterministic text path a ruling removed.

## The contract widened from form to meaning

A second defect, routed in after the first close, showed the declaration was
pinned on the wrong axis. Form was single-sourced; MEANING was not, and the
uncovered axis cost more than the covered one.

The structured reader wrote the printed-total identity's cuota term as cuota PLUS
recargo de equivalencia, because the source format states a combined output-tax
figure under a name the draft uses for the cuota alone. The closure check then
read that term as the cuota and added the recargo a second time from its own
slot. A bundled document whose printed arithmetic closes exactly -- 100,00 base
plus 21,00 cuota plus 5,20 recargo equals 126,20 -- was reported inconsistent by
exactly the surcharge, so a blocking finding fired at the confirm boundary for
every recargo de equivalencia filer. A real and common Spanish regime, refused on
a correct invoice.

Neither hop was wrong alone. That is the point: a contract pinning the FORMAT of
a number whose REFERENT is ambiguous has not removed the drift, it has hidden it,
because both sides now agree on the shape of the value they disagree about.

- Establish which meaning is canonical rather than choosing one: the identity is
  already declared and machine-enforced in the invoice domain, whose components
  model validates that the total equals base plus cuota plus recargo plus
  suplido, and that cash equals total less retencion. The cuota term excludes the
  surcharge. Neither end had derived from it.
- Fix the PRODUCER, which is where the drift entered. The reader now takes the
  cuota from the per-band tax amount, whose sibling element carries the
  surcharge, rather than from the combined total. A term read from a source that
  cannot contain the surcharge cannot acquire one, which is stronger than
  correcting a combined figure afterwards and remembering to keep doing so.
- Leave the consumer alone. Relaxing it was the obvious fix and it is wrong: it
  implements the canonical identity correctly, and dropping the surcharge from
  its sum would have silenced real closure failures alongside this false one.
- Sum the surcharge across bands instead of keeping the last node, so a
  two-rate invoice does not under-report it into the same identity.
- Invert the discovering lane's characterization class, which pinned the defect
  as the contract and instructed in its own assertion message that a pass meant
  the fix had landed.
- Correct an instance of the same defect class introduced here earlier: the
  withheld-invoice fixture had been given a total net of retencion, but the
  canonical identity places retencion between total and cash, so the total is the
  contraprestacion and the withholding is deducted from it.

## Widened outcome

Both ends now bind to the one declaration rather than to each other. The producer
is proven to emit the canonical cuota term; the consumer is proven to implement
the canonical identity, driven by feeding the same figures to the validator-
enforced components model and to the closure check and asserting they agree.

Assertions key on the numbers and the term semantics, never on which finding kind
fired. Two different faults reach the same closure finding -- a document that
omits the surcharge and one that double-counts it -- so a gate keyed on the kind
alone would have passed while the double-count survived, and reading either as
evidence about the other is how a false all-clear gets issued here.

The bundled document is the fixture. A fixture authored to match the fix would
prove only that it matches.

## Widened verification

    pytest src/cadrumo/application/ledger/tests/test_invoice_tax_term_semantics.py src/cadrumo/application/ledger/tests/test_evidence_corpus_parsing.py src/cadrumo/application/ledger/tests/test_closure_findings.py src/cadrumo/llm/tests/test_invoice_field_anchors.py src/cadrumo/llm/tests/test_invoice_field_contract.py -n0 -p no:randomly -q
    130 passed in 29.11s

Measured before and after at the producer, against the bundled document:

    BEFORE cuota 26.20 | recargo 5.20 | closes False
    AFTER  cuota 21.00 | recargo 5.20 | closes True

The three shapes through the real closure path, before the fix:

    defect      (cuota+recargo, surcharge stated)  -> arithmetic_closure
    correct     (cuota alone,   surcharge stated)  -> CLEAN
    omitting    (cuota alone,   no surcharge)      -> arithmetic_closure

The middle row is why the consumer was left untouched: given correct input it was
already correct.

Proven by mutation in both directions. Reverting the producer to assign the
combined figure:

    5 failed, 28 passed in 3.73s

Applying the tempting wrong fix instead -- dropping the surcharge from the
consumer's sum:

    7 failed, 18 passed in 2.28s

Five of those are assertions added here, so the gate cannot be satisfied by
loosening the consumer. Both positive controls stayed green under the first
mutation, which is correct: neither depends on the producer.

## Widened notes

The wider suites carry 31 failures before and after, an identical set with zero
delta, measured as a set difference against a baseline captured from a pristine
export of the same commit. An intermediate run showed 33; the two extra were the
discovering lane's characterization tests asserting the defect as the contract,
and inverting them returned the set to parity rather than suppressing them.

The other structured formats read by the same module state no recargo at all, so
their surcharge term stays absent and no double-count is reachable there. Left
unchanged rather than swept.
