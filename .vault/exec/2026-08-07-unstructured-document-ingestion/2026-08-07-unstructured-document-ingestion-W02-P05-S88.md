---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:39ebd59543ebb5ce3f43382511813e767da07dc88570d89d73e26105b546cf27'
step_id: 'S88'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Build the deterministic model-free classifier downstream of grounding that derives IvaCategory from the transcribed legend plus the per-rate breakdown plus counterparty establishment plus direction, recording its input set in the provenance envelope under a new DERIVED origin member, deriving only where signals are decisive and treating an unstated counterparty country as unknown rather than domestic, gated by model-free classification tests

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add `domain/iva/_legend_derivation.py`: the legend axis of the deterministic
  classifier. Matches a transcribed phrase against the closed statutory
  vocabulary, checks the matched mention's declared expectation against the
  printed tax evidence, and returns one of three outcomes.
- Add `FieldOrigin.DERIVED` in `core/`, for a value concluded from other values
  rather than copied off the document.
- Add the `derived_from` field and its validator to `FieldProvenance`: a derived
  value must record the inputs it followed from and may never claim `ANCHORED`.
- Promote the four new symbols onto the `domain.iva` facade in the same change
  that introduces them.
- Extend the `FieldOrigin` member-set gate and add envelope cases for the new
  origin.
- Complete the `GROUNDABLE_ORIGINS` rationale, which enumerates why each origin
  is excluded and would otherwise have gone silent on the new member.

## Outcome

The axis reports only what the issuer stated in writing. RD 1619/2012 art. 6.1
obliges an issuer to print a fixed mention whenever certain regimes apply, so for
those cases the paper states the regime in words the regulation sets: copying the
phrase is a reading step, concluding what it declares is a deterministic step,
and neither guesses.

It is deliberately not a second classifier. The existing rule table remains the
single authority for the categories that turn on who the counterparty is, and
those need a counterparty tax status, which is a profile fact rather than a
document fact. The legend axis takes two inputs and nothing else, so it cannot
enter that table's domain and the two cannot silently disagree. A test asserts
the two-parameter signature, so a later change that tries to bridge the two
authorities through this module reddens rather than succeeding quietly.

Three outcomes and no fourth, with no numeric confidence anywhere: a threshold
between "the issuer declared this" and "the issuer did not" would be invented.
The contradicted outcome deliberately carries no category even though a mention
named one, because a caller holding the value would use it and skip the
contradiction; resolving that disagreement into an operator-facing finding
belongs to the review path and is not done here.

The absent outcome is the common one and the design protects that. The statutory
table carries seven mandated mentions and exactly one declares a category, so
most invoices legitimately derive nothing. Treating that silence as ordinary
domestic supply would hand a category to every invoice whose issuer stated none,
which is the restrictive-provision-as-default failure: a wrong category is worse
than an absent one, because an absent one asks the operator.

The wiring into the draft assembly is deliberately not part of this change. The
classifier's criteria record is constructed nowhere in production today, so a
single wire here would have created a second, partial entry point into that
problem; all wiring is tracked separately.

### The row is wider than this record

Recorded by the coordinator after two later lanes mapped the row and handed back
on budget. This record covers the legend-derivation delivery only, and the Step
it belongs to also carries the convergence itself: demoting the two live minting
sites in `_evidence_draft.py` to comparators and routing supplied facts into the
criteria assembly. That work is not delivered here, and the exclusion paragraph
above should be read as scoping this change rather than the row.

The mapping passes established one fact that reshapes the remaining work.
`IvaInvoiceClassificationCriteria` has no category field and cannot have one,
because the criteria produce a category. So the structured tax-category code
cannot be re-routed as a supplied fact into the criteria, as the row's text
proposes: it is structurally incapable of being an input. It becomes a
corroboration check against the minted result instead. The supplied-fact channel
is real, but it carries the criteria's genuine inputs — supply nature, customer
tax status, territorial scopes — and its contribution is recording who
established each one, which the flat asserted parameters cannot express.

## Verification

The three files this change touches, measured together:

    uv run --no-sync python -m pytest src/cadrumo/domain/iva/tests/test_legend_derivation.py src/cadrumo/core/tests/test_field_origin.py src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py -n0 -p no:cacheprovider -q -m unit
    52 passed in 2.84s

The same three files re-run against the staged tree object, extracted with `git
archive` rather than read from the working copy, which held other lanes' work:

    52 passed in 3.08s

The full `domain/iva` directory, run once before the machine's disk became
critical:

    uv run --no-sync python -m pytest src/cadrumo/domain/iva/ -n0 -p no:cacheprovider -q -m unit
    392 passed in 29.66s

The anti-default gate, mutation-proven by making the axis acquire the exact
default this Step forbids -- silence read as a declared regime -- with the
behaviour change asserted before the run so a mutation that failed to land could
not be read as a passing gate:

    mutated behaviour on a blank invoice: derived
    mutation lands: True
    1. UNMUTATED  22 passed
    2. MUTATED     5 failed, 17 passed
    FAILED ...::test_the_ordinary_invoice_derives_nothing_rather_than_defaulting[none]
    FAILED ...::test_the_ordinary_invoice_derives_nothing_rather_than_defaulting[empty]
    FAILED ...::test_the_ordinary_invoice_derives_nothing_rather_than_defaulting[blank]
    FAILED ...::test_the_ordinary_invoice_derives_nothing_rather_than_defaulting[unrelated-text]
    FAILED ...::test_the_ordinary_invoice_derives_nothing_rather_than_defaulting[exempt-reference]

Every red lands in that gate. The six mandated mentions that declare no category
stay green under the same mutation, because those inputs match a real legend so
the default never fires -- an unplanned control confirming the mutation reaches
only the path it should. The mutation ran from outside the repository and no
tracked file was modified.

**Scope of what was NOT measured, stated rather than implied.** The
`application/ledger` directory was not run against this change, and the
`domain/iva` figure above predates the last commit in this Step. The machine's
system volume reached 235 MB free with 156 pytest temporary directories
outstanding, and further suite runs were stopped: at that level an I/O failure
reads as a code fault and a green is not trustworthy. The row is left unchecked
for this reason and no directory-level claim is made.

## Notes

The facade change came within one commit of breaking every consumer of
`domain.iva`. The working copy of the package `__init__` carried this Step's four
exports beside another lane's nine, for a module that was still untracked, so an
ordinary explicit-pathspec commit would have put an import of a non-existent
module into the committed tree. It was caught only because the dirty check was
run unfiltered; the change was rebuilt from the committed bytes with this Step's
exports alone, asserted free of the other lane's markers, staged as an index-only
update, and validated by extracting the staged tree and running the suites there
before committing. An `__all__` diff after the fact confirmed four names added and
none removed.

Separately, this Step's core enum member and provenance validator reached the
committed tree through another lane's sweeping commit before this lane could
commit them, and their fixture updates did not travel with them -- leaving the
member-set gate red in the committed tree until this Step's commit closed it. The
same pattern had occurred once already on an earlier Step in this lane.

## The declared-facts channel

A later slice of the same row, landed after the legend axis above. The
convergence needs facts supplied INTO the criteria, and the assembly could take
values but not attribution.

- Replace the three flat `asserted_*` parameters with one `declared:
  DeclaredFacts` channel, each fact carrying who established it.
- Reuse the shipped classifier-input source vocabulary rather than declaring a
  second one for the same question.
- Extend that vocabulary with an operator-assertion member, and make the audit
  envelope's backing validator exhaustive over the three members instead of two.
- Migrate the assembly's existing suite through one named adapter, and write the
  channel's own contract against the real signature.

## Why the channel is a model rather than more parameters

The parameters could carry a VALUE but not its ATTRIBUTION, so once a criteria
field existed nothing recorded whether a human had claimed it or the page had
stated it. An auditor asking why a record says the customer is a consumer got
the value back and nothing else.

Making it a model is what stops the next stage inventing a parallel supply route:
a later contributor adds an ATTRIBUTE, and the assembly, the envelope and the
stamp carry it with no new plumbing. A second route would fork the attribution
exactly the way the flat parameters forked it, and a fork is invisible until
someone asks who said what. That property is gated by recomputing the assembly's
real signature and asserting exactly one supplied-fact parameter exists.

**The source vocabulary was NOT duplicated, and that was the live decision.** The
specified design carried a private two-member source enum. A shipped enum already
answers the same question for the audit envelope, so a private one would have
been a second authority on "who says so" — introduced, as these always are, by
someone who found a small local enum tidier. It was missing only an
operator-assertion member, which is an addition rather than a retirement and
therefore safe: the three consumer sites were checked and only one branches on a
member.

Extending it forced the envelope's validator to become exhaustive. With two
branches an operator assertion fell to the document arm and was allowed to carry
an anchor — which would state that the page printed the very fact the operator
had to supply BECAUSE the page did not, leaving an auditor pointed at a citation
that does not exist.

## Verification

    pytest src/cadrumo/application/ledger/tests/test_declared_facts_channel.py src/cadrumo/application/ledger/tests/test_classification_assembly.py -n0 -p no:randomly -q
    27 passed in 3.55s

    pytest src/cadrumo/application/ledger/tests/test_declared_facts_channel.py -n0 -p no:randomly -q
    14 passed in 0.46s

Whole-tree, sequential, cold interpreter, cache provider disabled, on an isolated
export of the commit:

    16 failed, 1737 passed, 21 deselected in 276.69s

None of the sixteen are in files this slice touched: they belong to the consent
lane and the wired-reading lane. The assembly and channel suites are green.

Proven by mutation, each applied to an isolated export so no tracked file
changed.

Reintroducing a second supply route beside the channel:

    1 failed, 9 passed

Allowing an operator assertion to carry a document anchor:

    1 failed, 13 passed

## Notes

**The second mutation ran fully green the first time, and that was the finding.**
The validator branch had shipped with no assertion behind it, so nothing in the
tree objected to the laundering it refuses. The gate was written in response and
the mutation re-run against it. A fully-green mutation is the tell that a guard
is unwitnessed, not that it is sound.

Two mechanical corrections are recorded rather than smoothed over. A first
migration of the assembly suite blanked whole LINES to remove a keyword, which
deleted the assignment target on every call written on one line; a second used a
pattern rewrite and regressed a different case. The third was restored from a
scratch copy taken before the first attempt and used a single named adapter,
which is what landed. Both failed attempts were caught by the suite rather than
by review.

**A sweep committed an in-flight version of the channel gate**, carrying an
import of the invoice-direction enum from a package that does not export it, and
collection failed for the entire ledger test tree rather than for that module
alone. Repaired in its own commit against the facade its sibling suite already
reads from. The convergence of the two minting sites in the draft module is NOT
part of this slice: that file carried another lane's uncommitted work throughout.
