---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6602f119616bcacbb42a46d7cea53533a521ef3373ccf08c029c8194c34e7fc5'
step_id: 'S78'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Build the prompt compiler in the application layer: template plus registry-resolved IVA and retencion rates for the filing year and period plus IvaCategory members, handed to the extension as data, with no numeric rate literal in any template, gated by the model-free anti-drift gate proven by mutation in both directions

## Scope

- `src/cadrumo/application/ledger`

## Description

- Replace the compiled prompt's no-tax vocabulary authority. It enumerated the
  M303 cuota-less categories, which answer whether a category produces a cuota on
  the return; the prompt's question is whether the paper carries a tax line.
- Declare the answer to the paper's question as its own derived set in the domain,
  beside the two sets already there, built from the closed category enum rather
  than hand-listed, and promote it onto the owning package facade.
- Ask for the withholding the prompt was already spending context enumerating:
  the rates were listed while the response had no slot for them, so every reading
  of a withheld invoice dropped it, and the destination draft already carried the
  fields.
- Gate the anti-drift property by mutation in both directions, each mutation
  applied at runtime from outside the production modules.

## Outcome

The reverse-charge family is the whole difference between the two authorities,
and it differs in the direction that costs. The received side is deliberately
excluded from the cuota-less set because it bears a real self-assessed cuota,
while the supplier's invoice repercutes nothing and is required to say so. The
prompt was therefore telling a reading model that the commonest no-IVA invoice a
Spanish autonomo receives cannot exist -- pressure toward supplying the rate it
expected to find, on a design target chosen for being weak.

The withholding loss ran in the direction nothing downstream watches: a retencion
already withheld and never recovered is tax paid twice, and no gate in the tree
looks for over-payment.

Two parts of the Step are NOT delivered and are named rather than absorbed.

First, permitted categories are compiled in only as the no-printed-tax
vocabulary, not as a selectable set the model classifies against. Emitting a
category is a classification act, not a transcription: the enum's values are
internal stored tokens that appear on no invoice, and a category is derived from
facts (the parties' establishment, the printed regime legend, the presence of a
rate) rather than read off the page. Asking for one would put inference inside
the stage whose guarantee is that values are copied and never computed. The
resolution that would satisfy both is a transcribed regime legend -- the verbatim
printed phrase, anchorable like any other field -- feeding a deterministic
classifier downstream. That is a decision to route, not one to take here.

Second, the compiler runs in the llm package, not the application layer. The
governing decision places it in the application layer for a stated reason, so
this is a divergence rather than a preference. The relocation is atomic by rule
and its two consumers both carry another lane's uncommitted work right now, so
moving it would have meant editing live peer WIP.

## Verification

    pytest src/cadrumo/llm/tests/test_invoice_field_contract.py src/cadrumo/llm/tests/test_invoice_prompt_cache_binding.py src/cadrumo/llm/tests/test_invoice_field_anchors.py -n0 -p no:randomly -q
    90 passed in 29.94s

Both directions of the anti-drift gate proven by mutation, each applied to an
isolated export so no tracked file changed and no concurrent sweep could commit
it.

Direction one, the compiler stops reading the rate authority and returns a frozen
tuple:

    3 failed, 5 passed, 36 deselected in 6.62s

The registry-follows assertion reddened, together with two pre-existing
enumeration assertions.

Direction two, the literal scan reverts to reading an import-time snapshot rather
than the registered template:

    1 failed, 5 passed, 38 deselected in 6.06s

The planted-literal assertion reddened while the pre-existing scanner control
stayed green -- which is the finding, not an aside: that control proves the regex
matches a rate, never that the gate is pointed at the artefact that ships.

Third mutation, the prompt reverts to the cuota-less authority:

    4 failed, 40 deselected in 5.66s

After restoring each mutation the selection returned green, so nothing leaked
into module state through the cached prompt registry:

    44 passed in 10.76s

## Notes

The wider suites carry 31 failures before and after, an identical set with zero
delta, measured as a set difference against a baseline captured from a pristine
export of the same commit rather than compared by count. The tree-wide import
hygiene and docstring gates carry 5 failures on both sides, also an identical
set. Both belong to concurrent lanes.

No inference was run. No model was loaded and no cloud request was issued, so no
claim here rests on a measured extraction result.

## Follow-up: the deferred relocation is closed

The divergence named above -- the compiler running in the llm package rather
than the application layer -- is now closed, and the deferral's stated blocker
(both consumers carrying another lane's uncommitted work) was worked around with
the HEAD-anchored own-only staging drive rather than by editing peer WIP.

Resolution moved, rendering stayed. `application/ledger/_invoice_extraction_authority.py`
resolves the IVA percentages overlapping a period, the RIRPF art. 95 retencion
percentages, the no-printed-tax `IvaCategory` members and the mandated regime
phrases into one frozen `InvoiceExtractionAuthorityValues`. The llm module keeps
the template and the rendering and holds no runtime reach into any of those
authorities: `render_invoice_extraction_prompt` substitutes what it is handed and
can print no figure the application layer did not resolve.

The rate table is read at CALL time inside the resolver, not bound at import. A
module-level `from ... import load_iva_rate_table` captured the function once and
silently broke the pre-existing registry-follows gate -- an unplanned but real
mutation proof that the gate bites.

The compiler now has a production consumer. `_read_transcription_semantically`
resolves the values once per document and passes them to both reader branches, so
the on-host and consented off-host reads of one document use identical values.
The reader's `period` parameter is replaced by `authority_values`, which is what
makes "handed as data" structural rather than conventional.

Files: `src/cadrumo/application/ledger/_invoice_extraction_authority.py` (new),
`src/cadrumo/application/ledger/__init__.py`,
`src/cadrumo/application/ledger/_evidence_draft.py`,
`src/cadrumo/llm/_invoice_extraction_prompt.py`,
`src/cadrumo/llm/_evidence_draft_text.py`, `src/cadrumo/llm/__init__.py`,
`src/cadrumo/application/ledger/tests/test_invoice_extraction_authority.py` (new),
`src/cadrumo/llm/tests/test_invoice_prompt_cache_binding.py`.

### Mutation proof of the new gate

The new property -- the renderer cannot reach around its argument -- was proven by
rebinding `_join_pcts` from a pytest plugin living OUTSIDE the repository, so no
tracked file changed and a concurrent sweep could not commit the mutation. Three
rungs: a banner proved the plugin loaded, a counter proved the rebound function
was reached seven times, and an assertion inside the plugin proved the rebinding
changed observable output before any test ran.

    2 failed, 7 passed in 1.50s

The two behavioural assertions reddened. The other seven stayed green
legitimately and the distinction is the finding: the artefact-stamp test asserts
the model's `iva_rate_pcts` field rather than the rendered text, so it survives a
renderer that prints something else entirely. The text assertion is the
load-bearing one.
