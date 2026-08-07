---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1575a6b2e1ab83fbb54ec7a490691f3e903d219112629e7c639b6f5bfa7a3ac2'
step_id: 'S22'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Delete the Spanish-label regex extractor family and its tests after the semantic reader is wired, gated by clean collection, zero remaining label-regex references WITHIN _evidence_draft.py only (the justificante and declaracion inbound parsers carry their own LABEL_RE symbols and are NOT in scope), and the bundled fixtures passing through the new path against the loopback stub

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

- Delete the eight Spanish-label patterns and their six consumer helpers from
  `src/cadrumo/application/ledger/_evidence_draft.py`, together with the
  `extract_invoice_fields` primitive they served and the now-unused `re`,
  `parse_date`, `validate_spanish_tax_id`, `IdentityError`,
  `coerce_finite_european_decimal` and `extract_evidence_text` imports.
- Drop the primitive from the ledger facade in the same commit: the eager
  `TYPE_CHECKING` import, the lazy-export map entry and the `__all__` member.
- Promote `transcribe_text_layer` to the facade in exchange, so the exported
  `EvidenceInput` still has an exported consumer and the surrounding prose that
  already cited it as a facade symbol becomes true.
- Sweep every docstring naming the deleted primitive: the router's own module
  and function prose, the ledger facade overview, the on-host vision reader, the
  semantic text reader and the evidence-extract CLI regression.
- Remove the eight regex-primitive cases from the draft suite, retarget the
  no-text-layer refusal case at `transcribe_text_layer`, and retarget the
  facade-export gate's signature assertion at the same function.
- Add `test_no_label_regex_reader.py`: an AST-walking, file-scoped deletion gate
  carrying its own positive control.
- Retire the wiring suite's source-text slice assertion, whose subject no longer
  exists and which therefore could no longer fail.

## Outcome

The label-regex reader is gone rather than merely unreached, and re-introducing
it reddens. The gate binds to the router module alone and proves that scope is a
decision: it runs its own checker against the justificante extractor and the
declaracion parser, which legitimately compile 22 and 9 patterns respectively
for fixed AEAT-published layouts, and asserts the checker sees them. Without
that control a checker that silently detected nothing would pass forever.

The gate walks the parsed AST rather than slicing source text, because the gate
module's own prose names the deleted symbols repeatedly and a text scan would
match itself, and because a windowed slice stops detecting once the region it
measures outgrows the window.

Three files in the change carried other lanes' uncommitted work. Their content
was rebuilt from the committed bytes and staged as index-only updates, so the
commit carries none of it and the working copies were left untouched.

## Verification

The deletion gate, the facade-export gate and the wiring suite:

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/test_no_label_regex_reader.py src/cadrumo/application/ledger/tests/test_evidence_input_facade_export.py src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py -n0 -p no:cacheprovider -q
    22 passed in 2.23s

The same three files run against the committed tree, extracted with `git
archive` from the staged tree object rather than read from the working copy,
which still holds other lanes' work:

    22 passed in 16.58s

The affected suites in the unit lane, stated with its deselection:

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/ src/cadrumo/llm/tests/ src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_extract_cli.py -n0 -p no:cacheprovider -q -m unit
    6 failed, 999 passed, 28 deselected in 168.13s (0:02:48)

The six failures are triaged to other lanes and none names a deleted symbol: two
refuse a ledger import diagnostic whose message key has no authoritative Spanish
translation, and four are blocked by a confirmation gate that lives in an
untracked module absent from the committed tree.

The mutation proof, run with the gate's own assertion functions against a
mutated copy in the scratchpad with the module's router constant repointed, so
no tracked file entered a mutation window:

    observable change: patterns before=() after=('_TOTAL_LABEL_RE',)
    [RED (expected)] router compiles no patterns
        from: test_no_label_regex_reader.py:111 in test_the_router_compiles_no_patterns
    [RED (expected)] router does not import re
        from: test_no_label_regex_reader.py:124 in test_the_router_does_not_import_re

Both reds originate inside the gate's own assertions rather than in fixture
setup or a production guard. The facade assertion reddens under a separate
runtime mutation that puts the deleted name back, at line 134 of the same
module. Under the router mutation the two AEAT parser controls stay green, which
is what distinguishes a scoped gate from a broken one.

## Notes

The handed-over scope measurement was incomplete: it named the router, the
facade, two reader docstrings and one CLI test docstring, and missed three test
modules that bind to the deleted primitive. One of them asserts the exported
argument type and would have failed outright; the other two call it directly.
Re-deriving the consumer set rather than trusting the count was what surfaced
them.

The router module was reported as clean and was not. An early diff of it was
filtered in a way that hid another lane's in-flight confirmation-gate work
lower in the file, and that work was only noticed when four of its tests failed.
Nothing was lost -- the peer content stayed in the working copy and out of the
commit -- but the file was edited under a false premise, and the abort-on-dirty
check only holds if the diff that answers it is unfiltered.
