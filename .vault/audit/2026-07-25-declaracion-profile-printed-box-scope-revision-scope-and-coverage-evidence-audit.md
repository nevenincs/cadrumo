---
tags:
  - '#audit'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - '[[2026-07-25-declaracion-profile-printed-box-scope-adr]]'
  - '[[2026-07-25-declaracion-profile-printed-box-scope-research]]'
  - '[[2026-06-02-m303-parser-engine-totals-impedance-adr]]'
  - '[[2026-06-03-m303-synthetic-generator-primitive-spec-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
  - '[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]'
---

# `declaracion-profile-printed-box-scope` audit: `revision scope and coverage evidence`

## Scope

The governing ADR is `proposed` and one decision in it is unresolved: it states the
Modelo 303 extraction profile drops six engine-primitive casilla ids in the singular,
while two M303 revisions carry those ids. This audit produces every fact that decision
needs, and every fact implementation needs once the decision is made, without
implementing any part of the ADR.

Four questions were dispatched to a worker cluster and every returned claim was then
re-verified against HEAD by the coordinator. Numbers below carry the method that
produced them. Where the repository cannot answer a question, that is recorded as the
answer rather than substituted with a proxy.

Verification baseline: HEAD `11c5fe4af3`. No production code, registry data, fixture,
or test was modified by this audit.

## Findings

### adr-overstates-2009-profile | high | The 2009 profile names five of the six ids, not six, and the sixth casilla does not exist in that revision

The ADR's own re-measured section states "Both ... name the six ids". That is wrong for
the older revision. Parsing both profiles with `tomllib` (not grep) gives: the
`2023-y-siguientes` profile carries 18 targets including all six primitive ids; the
`2009-y-siguientes` profile carries 9 targets including five — it omits
`iva.autoconsumo.promotor.base`. Dropping the six therefore leaves 12 targets in the
2023 profile and 4 in the 2009 profile.

The omission is not an oversight in the profile. Loading the 2009 revision through
`bundled_authority().validate_modelo("303")` shows `iva.autoconsumo.promotor.base` is
absent from its casilla set entirely, and the revision declares zero `autoconsumo`
casillas (2009 casilla count 118; 2023 casilla count 126). The profile's inline comment
asserting exactly this is accurate. The ADR's re-measured note should be corrected to
"five" before a plan is written against it, and any worklist stating the 2009 profile
has 10 targets is also wrong.

### 2009-revision-is-live-for-historical-years | medium | The older revision is a complete authority for filing years 2009-2022 quarterly, not a stub

The 2009 revision is not vestigial. Compiled through the authority it carries 118
casillas, 67 formula lines, 94 binding lines, export layouts, a completeness manifest,
constructs, relations, verification expectations, filing schedules, and dependency
classifications. Its `period_selector` binds `year_from = 2009, year_to = 2022`,
quarterly periods only.

It is genuinely exercised, not merely named. Two test modules parse real fixture bytes
against its extraction profile and assert its revision id:
`test_parser_boundary_m303_historical.py` (7 parametrised corpus PDFs, asserting the
extracted casilla set equals a hardcoded frozenset) and
`test_verification_chain_m303_historical.py` (same 7 fixtures, recomputing engine
resultado). Its fixture coverage is the 2021-2022 tail only, `2021-2T` through
`2022-4T`; there are no fixtures for filing years 2009-2020.

It has no `deadline_windows` directory, so the present-day calendar surface emits windows
from the 2023 revision and current-year filings route there. The correct
characterisation is "live authority for a wholly past binding window", not "dead code".
Dropping its five primitive targets would break a currently-green assertion, so the 2009
half is real work, not a no-op.

### 2023-revision-selector-is-fragmented-not-absent | low | The 2023 manifest has no inline period_selector because the selector is a fragmented subdirectory

Reading `revision.toml` alone suggests the 2023 revision declares no `period_selector`.
It does: the selector lives in its own `period_selector` subdirectory, because the
fragment manifest is scalar-only by loader contract. Compiled, it is
`year_from = 2023, year_to = None` (unbounded forward) with quarterly and monthly
periods. `validate_revision_windows` returns empty, so there is no overlap and no year
gap between the two revisions.

One derived coverage hole surfaced incidentally and is out of this feature's scope but
worth recording: monthly M303 filers (REDEME or large company, periods `01` through
`12`) for filing years 2009-2022 resolve to no revision at all, because the 2009
selector carries only the four quarterly codes. The window validator only checks
overlap, so it does not catch this. This is a pre-existing gap unrelated to the
printed-box decision.

### repository-has-no-printed-m303-form | high | The question "does the printed form differ between revisions" is unanswerable from bundled evidence

The bundled M303 corpus under `corpus/aeat_official/disenos_registro/modelo_303/files/`
is, by its own extracted header, a diseño de registro: the electronic
submission-record layout. Per-ejercicio workbooks exist for 2014, 2015-2016, 2017, 2018,
2019-2020, 2021 (split at periodo 07), 2022, 2023, 2024 (split), 2025, and 2026; nothing
for 2009-2013. A search for M303 files named for an impreso, formulario, or printed form
under the corpus tree returns nothing. Only the `disenos_registro` and `instructions`
trees exist.

Substituting the diseño for the printed form is precisely the error the ADR exists to
correct, so the honest finding is that the repository cannot establish whether printed
box numbers mean the same thing in a 2009-2022-era printed form as in 2023 onward. What
the diseño evidence does show is that the electronic record layout was re-issued per
ejercicio and split mid-2024 — layout churn, but on the wrong surface to answer the
question. The operator's decision on the 2009 revision cannot be grounded in bundled
printed-form evidence, because there is none; it must rest on the reachability and
defect-symmetry facts instead.

### annex-specimens-are-a-third-provenance-class | medium | The grounding specimens declare aeat_published_facsimile, neither of the two classes the provenance rule names

The four annex quarters are `tests/fixtures/manual_annexes/303/2024-1T.pdf` through
`2024-4T.pdf` with JSON sidecars, derived from a bundled source master. All four declare
`provenance = "aeat_published_facsimile"` and `role = "casilla_value_oracle"`, neither
`real_corpus` nor `synthetic_generated`, the two classes the fixture-provenance rule
names. The class is stronger than synthetic and weaker than a taxpayer render: the
official AEAT form filled with AEAT's own worked-example figures, rendered by AEAT's
publication toolchain, carrying no taxpayer identity. It is a legitimate external AEAT
authority and therefore a valid grounding source for the coverage claims, which is
exactly why it can ground this ADR where the project's own synthetic corpus cannot.

Note that `parse_declaracion` end-to-end cannot consume these specimens: they carry no
NIF and the parser rejects them at the identity step by design. Measurement therefore
runs the same text-extraction primitive the parser calls, then the parser's own
`_classify_target`, rather than a reimplemented extractor.

One incidental data-quality defect: the `2024-1T.json` notes prose is copy-pasted from
the Modelo 390 annex, though every structured field correctly identifies the M303 annex.
Harmless, but it is drift in a provenance sidecar and should be corrected.

### coverage-degradation-is-blank-boxes-not-pattern-drift | medium | The ADR's 12/11/11/10 figure is confirmed, and every miss is a legitimately blank optional box

Applying the 18 profile label patterns to the extracted text of each annex quarter, then
classifying with the parser's own `_classify_target`, reproduces the ADR's figure
exactly: value-bearing targets are 12, 11, 11, and 10 of 18 for 1T, 2T, 3T, and 4T. Zero
malformed, zero ambiguous.

A separate coordinator check distinguishes two things the single figure conflates: all 12
retained labels are textually present in all four quarters. The degradation is not label
absence and not regex drift; it is blank-value detection. The misses are
`iva.compensacion-aplicada-periodo` (printed box 78) in 2T, 3T, and 4T, and casilla `37`
in 4T only. In each case the label matches and the captured token is the box's own
printed number, which the parser correctly reads as a blank box.

This matters for the plan: there are no pattern defects among the 12 retained targets, so
no regex re-grounding work is implied for them. The ADR's framing that a floor must
tolerate absent optional boxes rather than assume the 1T shape is correct, and the missing
boxes are genuinely optional.

### six-ids-absent-from-every-real-render | critical | The ADR's central premise is confirmed with zero counter-evidence

The six ids' labels are the project generator's own invention. Across all four annex
quarters the string `Primitivo` occurs zero times, and not one of the six label patterns
matches anywhere. The words the profile relies on as label anchors do not appear as
printed labels. The real form carries the devengado section positionally, as base
imponible, tipo, and cuota rows.

A single hit would have refuted the decision; there are none, in any quarter. The
consequence is that no `named_label` strategy can ever reach these values, which is the
concrete reason the rejected option B is inexpressible on the closed `match_strategy`
Literal rather than merely unattractive. The box-29 collision the ADR cites is also
visible: casilla `29` (retained, matches) and `iva.soportado.interiores` (dropped, no
match) name the same printed box.

### min-coverage-ceiling-is-10-of-12 | critical | The restated coverage floor has a hard ceiling of 0.8333 the ADR does not state

`min_coverage` is a fraction, not a count. The schema declares
`min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))` in
`_schema_extraction.py`, and the consumer in `_parser.py` computes coverage as the count
of extracted values divided by the count of profile targets, failing when coverage is
below `min_coverage`. Both profiles set `min_coverage = "1"` with
`failure_semantics = "fail_hard"`, so today every target must yield a value.

That is why the current profile refuses every real render: at 18 targets the four annex
quarters score 0.667, 0.611, 0.611, and 0.556, all below 1.0. This corroborates the ADR's
claim of universal real-render refusal with a measured number.

After the drop, against the 12 retained targets the quarters score 12/12 = 1.0000,
11/12 = 0.9167, 11/12 = 0.9167, and 10/12 = 0.8333. The highest single value satisfiable
by all four quarters simultaneously is therefore 10/12, approximately 0.8333, floored by
4T. The ADR mandates restating the floor at the level the form genuinely yields across
all four annex quarters but states no number; any value above 10/12 re-arms the fail-hard
refusal on 4T, and any value above 11/12 also re-arms it on 2T and 3T. This is the single
most consequential number the implementation lane needs and it is currently absent from
the decision record.

A second-order caution: because the synthetic corpus prints every retained target, its
coverage stays 1.0 at any floor. Leaving `min_coverage` at `"1"` therefore keeps the whole
synthetic suite green while silently preserving the exact real-render defect the decision
removes. The floor cannot be validated by the synthetic corpus at all.

### synthetic-corpus-does-not-measure-layout | critical | Zero of 76 expected-value entries reference any of the six ids

This is the finding the ADR itself mandates reporting. Every M303 synthetic expectation
was enumerated and classified as would-break or would-stay-green.

Would stay green, and this is the finding. All 48 expected-value entries in the
current-template expectations module and all 28 in the historical support module, 76 of
76, survive the layout change untouched, because every entry asserts a retained printed
total or an engine closure value and not one references any of the six dropped ids. On
the value axis the corpus measures none of the layout being removed. Also green: both CLI
reconcile-verb tests, which seed only 9 retained casillas; both application-layer
multi-modelo reconcile tests, which build an in-memory declaración of three retained
casillas and never touch the fixture PDF, so they never measured layout at all; the three
verification-source snapshot-resolution tests, which assert flag presence rather than
target sets; and the corpus round-trip gate module, which exercises Modelo 130 and checks
a boolean, never inspecting which casillas are targeted.

Would break, and this is the honest coverage genuinely lost. Only two mechanisms pin the
primitive layout. First, two hand-maintained frozensets in the parser-boundary support
module, hardcoding the six and the five ids, consumed by three set-equality assertions.
Because those assertions reference the symbol rather than restating the ids, they
auto-track a shrink of the frozensets, so the ADR's three parser-boundary modules collapse
to one shared support edit. Second, the verification-chain engine-summation tests in three
modules, roughly 23 parametrised cases, which exercise the primitives indirectly by
feeding parsed values to the engine.

That indirect coverage is itself weak. The fixture generator's expected closure value is
produced by replicating the same box-27-minus-box-45 registry arithmetic the engine
performs — the generator's own docstring concedes this — so "engine equals printed" is the
same computation on both sides. Genuine external-oracle coverage of these numbers already
lives off the extraction path in the AEAT Manual Práctico worked-example test, which does
not parse a PDF and is unaffected by the change.

Confirmed sizing, with one correction. Fifteen synthetic corpus fixtures: confirmed by
directory walk (15 PDFs, 15 sidecars; 7 legacy, 8 current). Three parser-boundary modules:
confirmed. Forty-eight expected-value entries across 8 fixture blocks: confirmed for the
current-template module, but scope-limited — a further 28 historical entries across 7
blocks exist in the support module, so the true total is 76. The ADR's 24-module and
40-TOML census is confirmed; four additional markdown hits exist in bundled agent-skill
files for other modelos and are unaffected.

### real-render-test-does-not-exist | high | The one test named for a real declaration copy points at a synthetic fixture

A parser-boundary test consumes a constant named for a real redacted M303 declaration
copy. That constant resolves to the synthetic `2024-1T` fixture, whose sidecar declares
`provenance = "synthetic_generated"`. There is consequently no real-render M303 test in
the suite at all, which is why the defect was invisible from inside the suite and why the
census rather than a red test surfaced it. The misleading name is itself the tautology the
ADR describes and should be corrected regardless of how the open decision is ruled.

### anti-tautology-proof-breaks-at-its-precondition | high | The primitive-summation proof reads its input from the parse and must be re-sourced, not deleted

The ADR flags this and it is confirmed. The proof parses the `2023-1T` corpus fixture,
retrieves `iva.repercutido.general` from the extracted values, and asserts it is a Decimal
as a precondition before mutating it and proving the engine's total moves. Once the profile
stops targeting that id the parse omits it, the retrieval yields nothing, and the
precondition fails first, so the module breaks at its setup rather than at its assertion.

The property it defends is real and the ADR forbids deleting it. The remedy is to construct
the engine inputs directly, on the calculate path, rather than sourcing the primitive from
a parse; the mutation-delta assertion itself survives that substitution unchanged.

### parser-versus-engine-arbitration-is-the-real-blocker | critical | The mechanical target removal cannot be committed green until an undecided arbitration is settled

The engine is fed extracted inputs, and printed boxes 27 and 45 are classified as
engine-computed, so their parsed values are deliberately excluded from the input set. The
engine obtains box 27 and box 45 only by summing the parsed primitives. Remove the
primitives from extraction and the engine computes box 27 and box 45 as zero, so the
recomputed resultado is zero against a positive printed value, and the verification-chain
tests fail.

The existing internal-consistency assertion has two parts. The first compares engine
resultado to the extracted printed value; this is the parser-versus-engine comparison, and
it is what breaks. The second compares engine resultado to engine box 27 minus engine box
45; since the registry formula for resultado is exactly that subtraction, this part is
effectively tautological and would pass trivially at zero. The ADR proposes this comparison
as the natural shape for arbitration, but in its current wiring it is not that check:
feeding the printed boxes 27 and 45 and comparing against the engine resultado is the
strengthening required.

The ADR deliberately defers this arbitration to the implementation lane. The consequence
for planning is concrete: the profile edit cannot land green without co-resolving the
arbitration in the same commit. The critical path is the arbitration, not the target
removal.

### coverage-ratio-cannot-flip-any-existing-gate | low | No currently-green test changes state purely from the target-count drop

Checked as a distinct class. Because `min_coverage` is a ratio over the profile's own
target count, dropping 18 to 12 and 9 to 4 while the generator drops its printed lines in
lockstep keeps coverage at 1.0. Even if the profile shrank while the generator was left
alone, the parser would match only the remaining targets and still score 1.0. The only
newly-failing assertions are the three hardcoded set-equality lines, which is a
set-equality break rather than a coverage-ratio effect.

### shared-support-files-straddle-both-revisions | high | Three files hold both revisions' logic, so a two-commit split has an ordering hazard

The parser-boundary support module (both frozensets), the fixture generator (both
templates' draw logic), and the verification-chain support module are each touched by both
revisions' work. If the 2023 change lands first and deletes the generator's primitive draw
block outright, the legacy fixtures stop printing primitives the 2009 profile still
targets, so the 2009 tests break between the two commits.

Two resolutions exist. If both revisions are re-scoped, land them in one commit and the
straddle disappears. If only the 2023 revision is re-scoped, the generator edit must take a
different shape: gate the five unconditional primitive draws so they fire only for the
legacy template, and delete only the autoconsumo block, which is 2023-only. The generator
diff therefore differs in shape depending on the ruling. This is the single place where the
operator's decision changes the mechanics rather than merely the scope.

### no-registry-validator-fires-on-target-removal | low | The 38 non-profile registry TOMLs are correctly unaffected and no build gate refuses the edit

All 38 non-profile registry TOMLs carrying the six ids are unaffected, and a plan that
edited any of them would be wrong. The ADR explicitly preserves the engine's
compute-from-primitives design, so the ids remain engine casillas, formula operands,
bindings, locale labels, and manifest entries. The breakdown: 7 files across the two M303
revisions' casillas, formulas, constructs, and completeness manifests; 6 locale catalogues;
1 verification-predicates file whose numbered-box-equals-semantic-source assertions hold
through engine bindings independently of extraction; 21 files belonging to Modelos 309,
322, and 353, which carry the same id strings in their own namespaces and are outside this
feature's scope; and 1 profile-schema prose description whose referenced casilla survives.

No registry-build validator refuses a target removal. The specimen and round-trip gates key
on fixture-directory presence and the `corpus_round_trip_verified` and
`verification_source` flags, never on the target set. The artefact-kind validator and the
bbox-anchor validator do not apply. There is no casilla-must-be-targeted gate and no
legal-reference-versus-target coverage requirement. The profile edit introduces no new
legal-catalogue reference, so the atomicity requirement that a referencing registry file
ship with its legal entries does not bind here.

One honesty caveat: `corpus_round_trip_verified = true` is enforced only as a
co-occurrence check with a non-null `verification_source`. It does not re-verify a round
trip when the profile changes. Leaving it true after the edit is therefore not
self-checking; its truth rests entirely on the reworked round-trip and verification-chain
tests, which is an argument for resolving the arbitration properly rather than for
flipping the flag.

## Recommendations

Correct the ADR's re-measured section to state that the 2009 profile names five ids, not
six, and that `iva.autoconsumo.promotor.base` does not exist as a casilla in that revision.
Correct its target counts to 18 and 9, yielding 12 and 4 after the drop. This is a factual
repair to the record, not a change of decision.

Add the measured coverage ceiling to the decision record before a plan is written: 10/12,
approximately 0.8333, floored by 4T against the 12 retained targets. Record with it that
the synthetic corpus cannot validate the floor, because it scores 1.0 at any value, so a
floor left at `"1"` keeps the suite green while preserving the defect. The ADR mandates
restating the floor but names no number; the number is now measured and should live in the
record rather than being rediscovered by the executor.

Record that the printed-form comparison between revisions is unanswerable from bundled
evidence, and that the repository holds only electronic diseño-de-registro layouts for
M303. The operator's decision on the 2009 revision must rest on reachability and defect
symmetry, not on printed-form evidence that does not exist.

Plan the arbitration first and the target removal second. The mechanical edit is small and
the arbitration is the critical path; a plan sequenced the other way produces a commit that
cannot be green. The arbitration's shape is available: feed the printed boxes 27 and 45 and
compare the engine resultado against their difference, replacing a comparison that is
currently tautological at zero.

Re-source the primitive-summation anti-tautology proof onto the calculate path rather than
the parse path, in the same commit as the 2023 profile edit. Do not delete it.

Rename or annotate the constant that calls a synthetic fixture a real redacted declaration
copy, and correct the Modelo 390 prose in the M303 annex sidecar's notes field. Both are
small honesty repairs that stand regardless of the open decision.

Treat the 76 would-stay-green expectations as a corpus-quality finding in their own right
rather than as an absence of work. They are not wrong, but they establish that the M303
synthetic corpus measures totals and closures and not layout, so the layout guarantee the
ADR removes was never really held by the value-level suite, and re-establishing it needs a
real render, which the repository does not currently contain.

If both revisions are re-scoped, land them in one commit to avoid the shared-support-file
straddle. If only the current revision is re-scoped, the fixture generator's edit takes a
different shape, gating the legacy primitive draws instead of deleting them, and that
difference must be stated explicitly in the plan.

The open decision itself is not recorded here. It is a single choice for the operator:
re-scope both M303 revisions in one change, or re-scope only the current revision and
accept, with a stated reason in the ADR, that the older revision continues to assert
printed boxes the form does not print.
