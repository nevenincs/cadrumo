---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7b4780273ee02ce57086b60532429cfd45cca5f90abad6cb9791c4931504b01d'
step_id: 'S287'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Thread the field selection the compiler gained through to the production text reader

## Scope

- `src/cadrumo/llm/_evidence_draft_text.py`

## Description

- Capture the full-prompt bytes before any edit, so comparability is proved
  against a recorded artefact rather than reasoned about afterwards.
- Accept a field selection on the text prompt builder and pass it to the shared
  compiler.
- Accept one on the reader, hold it for the reader's lifetime, and pass it in
  both the request builder and the provenance stamp.
- Gate the THREADING rather than the parameter, and prove each assertion capable
  of failing under a selection that is accepted and then dropped.

## Outcome

**Delivered.** Commit `02e624a584`, 29 added lines in the reader and a 178-line
gate. The fewer-fields call shape is now reachable through the shipped entry
point, which is what `W04.P10.S82` was blocked on.

The capability existed one layer above everything that could use it: the compiler
took a selection and **no production caller passed one**. Four call sites in the
reader module, all omitting it, so every read emitted the whole declaration.

### What changed

`build_text_field_extraction_prompt` takes `fields` and passes it to the shared
compiler unchanged — validation stays in the one place that knows the vocabulary,
so an unrecognised name refuses there rather than being dropped en route.

`TextInvoiceFieldExtractor` takes `fields` and holds it for the reader's
lifetime rather than per read. That is deliberate: the selection describes the
SHAPE of the call this reader makes, and a shape that varied between two reads of
one corpus would make those reads incomparable. A measurement comparing call
shapes builds one reader per shape.

**The provenance stamp carries the selection too.** The stamp answers "under
which instruction was this read performed", so one naming the full prompt while
three fields were asked for is a confident wrong answer to the only question it
exists to answer.

### The full path is byte-identical, proved against a recorded capture

Captured before the first edit, at the settled contract set: the compiled prompt
at 8736 characters, fingerprint `19d0ad82e263`, and the assembled text prompt at
8772 characters. After the change, both compare **byte-identical** to those
files, and the fingerprint is unchanged.

**The fingerprint is not the one the sequencing note quotes.** That note cites
`94acbce47cf0` at 8598 characters; the declaration has since been changed by a
peer, which legitimately moved the prompt. So the useful statement is not "the
prompt is what it always was" but "**this change moved nothing**" — and anything
compared across that peer edit needs its own contract-set check.

### Where the selection is validated, and why not here

The reader does not re-validate. A selection naming an undeclared field refuses
inside the compiler, against the declaration, which is the only surface that
knows the vocabulary. A second check here would drift from it the first time the
declaration grew.

## Verification

The gate, sequentially:

    uv run --no-sync pytest src/cadrumo/llm/tests/test_text_reader_field_subset_threading.py -m integration -n 0
    8 passed in 9.46s

Surrounding suites, both lanes:

    uv run --no-sync pytest src/cadrumo/llm/tests -m integration -n 0
    11 passed, 449 deselected in 28.70s

    uv run --no-sync pytest src/cadrumo/llm/tests src/cadrumo/application/ledger/tests -m "not integration" -n 0
    3 failed, 1711 passed, 40 deselected in 371.18s

**Every one of those three failures was triaged and none is this change:**

- `test_live_anthropic_round_trip` — refuses with *"selected live test requires
  CADRUMO_LIVE_TESTS_ENABLED=1"*. The live-test safety gate working as designed.
- `test_vision_model_override_selects_the_named_model` — passes in isolation both
  at HEAD and with this change; the suite-run failure was a local-runtime flake.
- `test_a_structured_document_whose_arithmetic_does_not_close_is_caught` —
  **reproduces identically with the HEAD version of this file in place**, so it
  is pre-existing. It is not this lane's, and it is reported rather than touched.

The HEAD comparison was made by copying the working file aside, writing the HEAD
bytes in its place, running, and restoring — no git verb that could disturb a
peer's work.

**The mutation proof. The gate had to bite on a selection ACCEPTED and then
IGNORED**, because that is the defect, and it passes every signature check and
every compiler test. Applied at runtime from outside the repository, so nothing
tracked was edited:

    BASELINE -- unmutated, every gate must pass:                    all pass
    MUTATION 1 -- reader accepts fields and DROPS them
      selection dropped in _build_request (size 3)   RED (gate bites)
      selection dropped in _build_request (size 1)   RED (gate bites)
    MUTATION 2 -- prompt builder accepts fields and drops them
      selection swallowed in the prompt builder      RED (gate bites)
      bad selection no longer refuses                RED via Failed
    MUTATION 3 -- stamp describes the FULL prompt while a subset was sent
      stamp ignores the reader's selection           RED (gate bites)
    MUTATION 4 -- default is no longer the unselected prompt
      default silently drops one contract            RED (gate bites)
    RESTORED -- baseline must pass again:            clean restore: True

The contract declaration this was built against, recorded so a later comparison
can prove it saw the same one:

    git show HEAD:src/cadrumo/llm/_invoice_field_contract.py | git hash-object --stdin
    bbdb55d8378db5bf1f92de7cfdbcee5c1f02d571

## Notes

- **The mutation harness had its own defect, found by running it.** Six mutations
  were reported and the run then died: pytest's failure signal subclasses
  `BaseException`, not `Exception`, so a caught-`Exception` reporter silently
  truncated at the first refusal-style mutation. The report would have shown four
  RED results and no indication that two more were never evaluated. Fixed, re-run
  in full.
- The reader's public method is `extract(*, transcription=...)`, not `read`. The
  gate was written against the wrong name and failed loudly rather than passing
  vacuously, which is the right failure to have.
- This Step deliberately does not touch the field declaration. What a selection
  is validated against is that declaration; what this changes is only whether a
  selection reaches the validator at all.
