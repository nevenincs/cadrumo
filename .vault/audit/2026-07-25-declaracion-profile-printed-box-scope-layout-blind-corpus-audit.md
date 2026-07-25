---
tags:
  - '#audit'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
  - "[[2026-07-25-declaracion-profile-printed-box-scope-adr]]"
---

# `declaracion-profile-printed-box-scope` audit: `the corpus that survived a layout change`

## Scope

The governing decision mandates that any synthetic Modelo 303 expectation staying
green through the printed-box re-scope be reported as a finding rather than
quietly left alone, on the reasoning that an expectation surviving a layout change
it should have caught is evidence the corpus is not measuring layout.

This record answers that mandate for the implementation lane. It enumerates what
stayed green and why, and adds the findings that surfaced while implementing and
verifying the change. Every number here was re-measured against the working tree
at implementation time, not inherited from the companion coverage-evidence audit;
where the two disagree the disagreement is recorded as its own finding.

One instrument caveat governs the whole pass. The semantic code index was
truncated throughout — roughly 1027 chunks against roughly 4546 files — while
reporting itself healthy with an empty degraded-reasons list. A semantic miss was
therefore worthless as evidence, and every site claim below was established by
literal-string walk, by targeted search, or by loading the registry through the
authority and inspecting the compiled schema.

## Findings

### layout-blind-value-corpus | critical | Every one of the 76 expected-value entries survives the layout change untouched

This is the finding the decision record mandated reporting, and it is confirmed by
independent re-measurement rather than inherited. The current-template expectations
module carries 48 `Decimal`-keyed expectation entries and the historical support
module carries a further 28, for 76 in total. A literal-string test of all six
dropped casilla ids against both modules returns zero occurrences in either.

Not one of the 76 entries changed, and not one needed to. Every entry asserts
either a retained printed total or an engine closure value, so the entire
value-level corpus is blind to the layout being removed. The absence is itself the
evidence: a corpus that measured the printed layout would have had at least one
entry to move.

The consequence is that the layout guarantee this change removes was never really
held by the value-level suite. Only two mechanisms pinned the primitive layout at
all: two hand-maintained frozensets consumed by set-equality assertions, which
auto-track the shrink because they reference the symbol rather than restating the
ids, and the verification-chain engine-summation cases, whose coverage is
re-established on the calculate path by this change. Re-establishing a genuine
layout guarantee needs a real AEAT render, which the repository does not contain
for the justificante parser path.

### synthetic-corpus-cannot-validate-the-coverage-floor | critical | All 15 synthetic fixtures score exactly 1.0, at any floor

Measured by running the production extraction path over every fixture in the
synthetic corpus against the live post-change profiles: all 15 score a coverage
ratio of exactly 1.0, with zero missing targets. None falls below 1.0 at any
value the floor could take.

This is the trap the decision record names, now measured rather than predicted.
Because the generator drops its primitive lines in lockstep with the profile
dropping its targets, coverage stays pinned at 1.0 on both sides of the change. A
floor left at its original `"1"` would therefore have kept the entire synthetic
suite green while preserving the exact real-render refusal the change exists to
remove. The floor is unfalsifiable from inside the generated corpus and can only
be validated against the bundled AEAT published-facsimile annex quarters.

### coverage-floor-sits-at-exactly-zero-headroom | medium | The restated floor is satisfied by the worst quarter with nothing to spare

Running the production extraction path over the four bundled annex quarters
against the 12 retained targets gives 12/12, 11/12, 11/12 and 10/12 — coverage
1.0000, 0.9167, 0.9167 and 0.8333. All four are accepted at the restated floor,
which is the change's central objective: the profile parses a real AEAT render for
the first time, where previously all four were refused at 0.667, 0.611, 0.611 and
0.556 against 18 targets.

The measured headroom at the worst quarter is exactly zero. This is correct by
construction — the mandate was to restate the floor at the level the form
genuinely yields across all four quarters, and that is the highest value all four
satisfy — but it should be recorded that the margin is nil. Any future real render
carrying one further legitimately blank optional box falls below the floor and is
refused. The two boxes already responsible for the degradation are optional by
nature, so a filer legitimately blanking a third is not exotic. A future reader
weighing a refusal should check whether the missing box is optional before
treating the refusal as a parser defect.

### parse-path-no-longer-exercises-the-engine | high | A genuine test pathway is lost and re-established elsewhere, not preserved in place

The verification-chain assertion on the parse path previously compared engine
output against extracted values. It cannot survive the change: the engine obtains
the devengada and deducible totals by summing per-rate primitives, the printed
form does not carry those primitives, and the printed totals cannot be substituted
because the engine refuses computed casillas as inputs — a guard that exists so the
pull and calculate paths cannot diverge.

The assertion is now a property of the document rather than of the engine: printed
box 46 must equal printed box 27 minus printed box 45, grounded in Orden
EHA/3786/2008 art. 1. This is a real check, not a weaker one — the three amounts
are printed independently by AEAT, so a render whose own totals disagree is caught
— and its falsifiability is proven by perturbing each of the three in turn and
confirming refusal.

It should nonetheless be recorded plainly that engine coverage on the parse path is
lost, not preserved. It is re-established on the calculate path, where the
primitives arrive from ledger aggregation. The replaced assertion also had a second
half that compared the engine's resultado against the engine's own box 27 minus box
45; since that subtraction is precisely the registry formula for resultado, that
half held by construction and would have passed even at zero. Replacing a
tautological comparison with a falsifiable one is a strengthening that the
loss-of-pathway framing should not obscure.

### misnamed-real-declaration-copy-constant | high | A constant named for a real redacted declaration resolved to a generated fixture

A parser-boundary constant named for a real redacted Modelo 303 declaration copy
resolved to the synthetic 2024-1T fixture, whose sidecar declares
`provenance = "synthetic_generated"`. The name asserted an external grounding the
file does not carry, which is the same class of error as a profile claiming to read
boxes the form does not print — and it is why the original defect was invisible from
inside the suite. The constant and its consuming test are renamed to say what they
are, with the reason recorded at the definition site.

Checked as a class rather than as a one-off: the analogous Modelo 190 constant is
correctly named, its sidecar declaring `provenance = "real_corpus"`. The misnaming
was isolated to Modelo 303, so this is a repair rather than a systemic rename.

### annex-sidecar-prose-mismatch-is-five-files-not-one | medium | The companion audit scoped this defect too narrowly

The companion coverage-evidence audit records the annex sidecar prose defect as
affecting the 2024-1T sidecar alone. Re-measured, the mismatched clause appears in
all five sidecars in the annex directory: the four per-quarter files and the
unsplit source sidecar.

The clause described the specimen as the annex to the manual chapter on the annual
summary Modelo 390, while the document's own extracted page-one header reads
`ANEXO / Modelo 303 de autoliquidación del Impuesto sobre el Valor Añadido`. The
repair points the prose at the document's own printed title and the published asset
filename, both directly verifiable, and drops the chapter-title claim rather than
substituting a different one, because which chapter number carries which title is
not establishable from bundled evidence. Every structured field in all five
sidecars was already correct; only the prose drifted.

### m130-real-copy-constant-carries-no-sidecar | low | Out of scope, recorded so it is not lost

The analogous Modelo 130 constant, also named for a real declaration copy and
consumed by a test whose name asserts the same, points at a fixture that carries no
provenance sidecar at all. Its provenance is therefore neither declared nor
checkable by the fixture-provenance gate, so the name can be neither confirmed nor
refuted.

This is outside the printed-box feature and was not touched. It is recorded here
because it is the same question this feature just answered for Modelo 303, and
because an undeclared provenance on a fixture whose name makes a provenance claim
is exactly the shape that hid the original defect.

## Recommendations

Treat the 76 surviving expectations as a corpus-quality result rather than as an
absence of work, and do not read the green suite as evidence that the layout change
is safe. It is evidence that the value-level corpus never measured layout. The two
frozenset set-equality assertions are the only value-side mechanism that moved.

Do not raise the coverage floor without re-measuring against the annex quarters,
and do not lower it on the strength of a synthetic run. The synthetic corpus scores
1.0 at any floor and is structurally incapable of validating the number; only the
published-facsimile renders can move it.

Record the zero headroom at the worst quarter as a known property rather than a
defect. If a future real render is refused, establish whether the missing target is
a legitimately blank optional box before treating the refusal as a parser fault.

Acquire a real Modelo 303 render for the justificante parser path if one can be
obtained without taxpayer identity. It is the only thing that would restore a
genuine layout guarantee, and its absence — not any single wrong string — is the
condition that let a profile drift into asking for text no AEAT document prints.

Resolve the Modelo 130 fixture's undeclared provenance under whichever feature owns
that corpus, so that the constant's name can be confirmed or corrected on evidence.
