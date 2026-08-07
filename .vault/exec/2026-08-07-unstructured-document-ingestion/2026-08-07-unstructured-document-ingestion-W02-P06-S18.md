---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ea547f36944cfc2c3eeb40c7953f1446e7e7760778a0a07bfdaccb7fe1db26e2'
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

### The anchor search was substring-soft, and that was an anti-fabrication bypass

Found by the injection-gate lane while building `W04.P09.S32`, and fixed here
before close-out so this record describes the check as it behaves rather than as
it was first written.

`evaluate_anchor` did a plain substring search, so **an injected `0,00` anchored
inside a printed `100,00` and grounded.** Reproducing it locally showed it is
broader than the one figure that exposed it: `1,00` grounds inside `21,00`, and
bare `00` grounds inside almost any amount.

That is not a fixture quirk. Most real invoices carry some amount ending in
`,00`, so an injected zero total grounded against a large share of the corpus
with no cleverness at all -- which made D4's structural check certify little more
than "these digits appear somewhere". For short numeric forms that is close to
vacuous, and it is the load-bearing mechanism of the whole design.

The fix is a boundary-aware search: the anchor must occur as a COMPLETE printed
token. The rule keys on characters that continue a *number* (`0-9`, `.`, `,`),
applied per edge and only where that edge is numeric -- so a currency prefix, a
trailing percent, a non-numeric anchor and the text edges all still match, while
a fragment of a longer figure does not. Every occurrence is examined and one
clean occurrence suffices, because a document may print the same figure as a
fragment in one place and standing alone in another.

Collateral damage was checked for explicitly: a genuine `0,00` retención
standing alone still grounds. Trading one false-negative class for another would
not have been a fix.

### The conjunction is the guarantee, not the anchor alone

Also recorded so this check is not trusted for more than it does. The anchor
check establishes that a printed form is PRESENT. It does not establish that the
form plays the ROLE claimed for it -- an injected sentence printing its own
plausible figure passes it honestly, because the figure really is on the page.

What catches that is the second leg: `closure_findings`, where the obeyed total
reds with an `ARITHMETIC_CLOSURE` finding because the document's other figures do
not reach it. The boundary's real strength is the conjunction. This is asserted
in the suite (`test_the_anchor_check_alone_is_not_the_anti_fabrication_guarantee`)
rather than left to prose, so the tests cannot be read as crediting the anchor
check with a guarantee it does not provide.

### Two decisions worth preserving against silent reversal

**`CONTRADICTED` rather than merely ungrounded** when an anchor is present but
parses to a different value, with the anchor kept in the envelope. A reader that
located a real printed figure and typed a different value has a different and
faster-to-act-on defect than one that invented a figure, and the operator needs
to see the form that was misread.

**Tolerance as one cent per STATED term rather than a percentage** (recorded in
S20, restated here because the two checks are read together). A percentage grows
with the invoice, so the largest invoices -- where a misread component costs the
most -- would get the widest licence to be wrong.

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

`test_grounding_anchor.py` -- 37 tests, all passing, run with `-p no:randomly`
and counts read from a log on disk. Full `application/ledger` lane plus the CLI
provenance parity suite: 658 passed, exit 0.

Mutation-proved from a pytest plugin on `PYTHONPATH` OUTSIDE the repository;
nothing under `src` was edited, so nothing needed restoring.

- `evaluate_anchor` forced to always return `ANCHORED`: **13 failed, 3 passed**,
  including `test_an_off_document_value_never_grounds` -- the required proof.
- Self-reported anchors made to read as independently verified (validator
  dropped, constructor stamping `ANCHORED`): **2 failed, 17 passed** --
  `test_a_self_reported_anchor_never_reads_as_verified` and
  `test_a_self_reported_anchor_cannot_be_laundered_into_an_anchored_outcome`.
- Anchor search reverted to plain substring matching: **6 failed, 31 passed** --
  including `test_an_injected_zero_total_does_not_anchor_inside_a_printed_amount`
  and every row of the fragment parametrisation.
- Anchor search made to refuse every occurrence: **24 failed, 13 passed** --
  including `test_a_genuine_zero_standing_alone_still_anchors` and
  `test_a_whole_printed_token_still_anchors`. Proved in BOTH directions, so the
  boundary rule is not satisfiable by a check that grounds nothing.

Positive controls carried throughout, so none of these is satisfiable by a
checker that always refuses: a genuinely parsed anchor is asserted NOT vacuous,
and a text-lane anchor is asserted NOT self-reported.

## Inherited requirement: this machinery has no production caller

Stated as an obligation the next lane inherits, not as an observation, because
"shipped, tested, unreachable" is a shape this codebase keeps producing and an
orphan is only found by someone looking for it.

`application/ledger/_evidence_draft.py` -- the router every `evidence extract`
call goes through -- contains **zero references** to `transcribe_text_layer`,
`evaluate_anchor`, `resolve_counterparty_identity` or `closure_findings`. Every
stage W02.P06 delivered is correct, gated and mutation-proven, and reached by
nothing. The anchor check cannot bypass a fabrication that never passes through
it.

Who inherits what:

- **The router wiring** -- transcribe, extract semantically, then ground. Note
  the plan has a genuine GAP here: `W02.P06.S22` deletes the regex family
  "after the semantic reader is wired", but no Step wires it. That is a missing
  row, not a row someone skipped.
- **`W02.P06.S21`** -- route per-field degradation advisories through the typed
  `Notice` channel, so "read successfully with few fields" is distinguishable
  from "could not read this layout".
- **`W02.P06.S22`** -- delete the Spanish-label regex family, and only after the
  two above are green. Deleting the sole working reader before its replacement
  is reached would be the worst available ordering.

`FieldProvenance` anchors must also be populated by the readers for the anchor
check to have anything to verify on a live draft; that population is another
lane's Step.

## Notes

The field-form contract declared by the reader lane
(`llm/_invoice_field_contract.py`) was deliberately NOT consumed. It governs the
form a model emits values in; this check asks whether an anchor parses to its
value, which is form-agnostic by construction. Importing it would have added a
new production `application -> llm` edge for something unused, and those pins
exist to make exactly that loud. No second vocabulary was declared.
