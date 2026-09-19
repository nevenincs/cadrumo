---
tags:
  - '#research'
  - '#decimal-notation-under-declaration'
date: '2026-08-04'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:cb2aa77c3782f416a78236318311660406f8895e3d78e130e09b47efa48e948e'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-adr]]"
  - "[[2026-08-04-minimo-descendientes-eligibility-audit]]"
---

# `decimal-notation-under-declaration` research: Spanish thousands separator silently misread as a decimal point

## Context

A live, silent under-declaration measured on 2026-08-04 on the documented operator entry
surface. Recorded before any remedy is designed, because the defect currently exists only
in session messages and an acknowledged defect that lives only in a dispatch does not
exist.

Found while chasing an unrelated and much smaller question — whether the guided flow
accepts a cents figure. The path to it is worth recording: the guided flow was measured to
refuse cents loudly, which was the good outcome; the executor then observed that the
comma-decimal form is refused on *both* surfaces and flagged that as a Spanish-locale gap
worth stating independently of the cents question. Probing one form further along that same
axis found the defect. Neither the cents question nor the comma observation was itself the
problem.

## The measurement

The operator-facing descendiente flag parses a rentas figure through the shared canonical
decimal parser. Measured behaviour across the four forms a Spanish taxpayer might type:

- `8000` — accepted, eight thousand. Correct.
- `8000.50` — accepted, eight thousand and fifty cents. Correct under dot-decimal reading.
- `8000,50` — refused. Loud, no misread.
- `8.000,50` — refused. Loud, no misread.
- **`8.000` — ACCEPTED, and parsed as eight euros.**

The last is the defect. In Spanish notation the dot is a thousands separator, so a taxpayer
entering eight thousand euros records eight — a factor-of-one-thousand misread with no
refusal, no advisory, and nothing in the stored value that looks wrong.

## The tax outcome

Driven through the production injector rather than reasoned. A descendant earning 12.500
euros is above the Art. 58.1 ceiling and must be excluded from the mínimo:

- typed `12.500` in Spanish notation — stored as 12,50 — mínimo **2.400 granted**
- typed `12500` — stored as 12.500 — mínimo **0**, correct

The misread lands on the claiming side of a strict `>` comparison, so it grants a mínimo
that reduces the base. That is an under-declaration of the tax, silent, on the notation a
taxpayer reads off their own document, in an application whose entire domain is Spanish.

Note the boundary case that masks it in casual testing: at exactly `8.000` versus `8000`
both readings produce the same mínimo, because the ceiling excludes only figures strictly
above it and 8.000 is not above 8.000. A probe using the threshold figure itself shows no
divergence. The defect only becomes visible with a figure that should exclude.

## What is not yet known

The blast radius is being measured and is the open question. The ambiguity lives in the
shared canonical decimal parser rather than in the descendiente flag, so every
operator-facing money input that reaches it is in scope — ledger amounts, guardería spend,
cotizaciones, invoice figures, any `--amount`. A silent thousand-fold misread on a ledger
amount would be materially worse than on a rentas figure, because it feeds aggregation
rather than a single threshold test.

A coordination hazard applies: a peer campaign is mid-refactor consolidating decimal
parsing onto the canonical helpers, which is exactly the code that owns this. The remedy
may belong inside that work rather than beside it.

### Measured since: the blast radius resolves, and the second site is not where it looked

**The leaf parser is closed and the gate now sees its layer.** The descendiente flag routes
through the canonical grammar and refuses the Spanish thousands shape, the ambiguous forms,
and exponent notation. The regression asserts an outcome divergence rather than describing
one, using a figure away from both ceilings — the two threshold figures are in the
parametrised refusal set with the reason recorded, since a probe at either boundary cannot
distinguish the two readings.

The enforcing gate previously declared its scope by layer, which encoded an assumption that
operator input never reaches the domain package. It does. Scope now follows the input
instead. Widening surfaced eight further domain sites, every one exempted with a stated
reason rather than tightened: AEAT export XML, registry-authored TOML, oracle replay text
and workbook parity figures are machine-produced, and one is an inverted non-finiteness
predicate where routing it through the strict grammar would make the guard *more*
permissive.

### The second site is a JSON re-parse promoter, and tightening it would break reloads

The brief named the profile fact carrier as the write door. It is not. Its own docstring
states it promotes strings back to typed values when a persisted record is re-read — the
serialiser emits Decimal and date as strings, and this validator restores them before the
union resolves. It serves **app-written persisted values**; operator text merely passes
through the same path.

Measured consequence of applying the strict grammar there: a legitimately persisted
three-decimal value, such as a business-use ratio, round-trips today and would begin
**refusing on reload**. So the fix as briefed converts a silent misread into a load failure
on existing records. That is worse than the sequencing risk anticipated — it is not that the
change needs a roundtrip test, it is that the location is wrong.

### Why neither existing authority can close it, which is the structural finding

Two mechanisms exist that ought to cover this, and both are structurally unable to.

**The widened gate cannot see it.** The parse there is guarded by a regex fullmatch rather
than being a bare constructor call, so it never appears in the scan. Extending the gate's
layer scope does not reach it, and no claim is made that it does.

**The declared numeric authority runs too late.** There is a single declared authority for
whether a value is legal for a given numeric field, and it executes *after* coercion. By the
time it is consulted the ambiguous string has already become a Decimal three orders of
magnitude below what the operator typed, and that value sits legally within range. **The
string is destroyed before the only authority that could judge it is reached.**

That is the canonicalization defect in its sharpest form, and it is not the one this record
originally described. An authority exists, is correctly declared as the single home for the
question, and cannot answer it — because it receives the wrong type. Adding a second
authority earlier in the path is the fragmenting move; the correct fix is to place the
existing one where the information still exists.

### The decision this now needs

Enforcement has to happen where the string is still a string **and** is known to be
operator-typed. That requires the profile write boundary to distinguish an operator write
from an application reload, which it currently does not. That is a boundary design decision
rather than a parser change, and it should be recorded before it is built.

## The decision this needs

The remedy is a product decision as much as a technical one, and it should be made
explicitly rather than settled by whoever writes the patch first.

Refusing every ambiguous form is the safe direction, but a rule such as "refuse a dot
followed by exactly three digits" also refuses a legitimate `8.000` meaning eight euros
exactly. Accepting Spanish notation properly is friendlier to the taxpayer and carries its
own ambiguity in the other direction. A third option is to require an unambiguous form and
say so at the boundary.

The constraint that is not negotiable: **no input may be silently misread by three orders
of magnitude.** A loud refusal naming both accepted forms is an acceptable outcome. A
silent misread is not, and is barred by the no-silent-under-declaration discipline.

Worth grounding before deciding: whether this project has already made a canonical
Spanish-notation decision somewhere. It is a Spanish-stem codebase and the question is
older than this defect.

## Companion findings from the same surface, both bounded

Recorded here because they were measured in the same pass and would otherwise be
re-derived.

The guided flow's rentas page is integer-only and refuses a cents figure loudly, honouring
the rejection rather than advancing. The operator is blocked and told. The residual concern
is that the only workaround — rounding to whole euros — crosses the same strict `>` in the
under-declaring direction, and the refusal message names the wrong constraint: it reports
an invalid integer rather than saying the field takes whole euros. The sibling gastos page
is integer-only too, so this is a consistent design rather than an oversight, and that one
feeds a proportional deduction rather than a threshold test, so rounding there loses cents
without flipping an outcome.

## Closed, and the residuals the call-site gate exposed

The canonicalization landed in two commits: the detector composed into the parsers so
ambiguity refuses by construction, the bypassing sites routed, three contracts named in an
amendment to the governing ADR, and the gate re-keyed from layer membership to call-site
ownership.

**The inversion earned itself immediately.** Keying on the call site rather than the layer
surfaced seven sites no allowlist had covered. Five are machine-text adapters — bank import,
PDF label extraction, two authority scrapes, a rates feed — exempted with reasons. **Two are
operator input in `core/`**, a layer no allowlist would plausibly have named, which is the
argument for the inversion made concrete rather than argued.

### Residual one: two operator-input parseability predicates in `core/`

Both parse the operator's value, discard the result, and store the answer as text — so they
admit the ambiguous form at the wizard and defer the refusal downstream, where it now arrives
as a message about *type* rather than about *notation*. Measured: the ambiguous forms are
admitted and stored verbatim.

One carries the INCN figure, threshold-bearing for the micro-empresa rate, so it was flagged
as the more serious. **Measurement narrows it, and the narrowing is recorded so nobody
re-escalates on the label alone.** A figure above that threshold cannot be written in Spanish
notation with a single dot group — it needs two, and the bare constructor already refuses
those. So within the single-group forms that *are* admitted, both readings sit on the same
side of the threshold and the rate does not flip. The stored value is still wrong by three
orders of magnitude, which is a data-integrity defect on a filing-grade field; what it is
not, on this threshold, is a rate change. Whether that figure feeds anything with a different
boundary is unchecked.

### Residual two: a fragment capture, not an ambiguity

At the rate-extraction site a three-decimal rate backtracks and captures a two-digit
fragment, yielding a **zero** rate. That is a regex defect rather than a contract one — the
pattern admits a partial match where it should reject the whole token — and it feeds a
non-blocking advisory. Recorded rather than folded in, because fixing it inside a
canonicalization would have buried a distinct bug in an unrelated change.

### The third contract has no consumer, deliberately

It was named for the rate site, and measurement then showed the ambiguous shape cannot reach
that parse: the capture pattern admits at most two fraction digits while the ambiguous shape
needs exactly three. The bound is enforced by the pattern, not by a resolve step. The
contract stays recorded with `impossible` as its discriminator and is explicitly marked as
having no consumer today, so the next bounded field inherits the reasoning without anyone
believing it is live.

### The counter-example worth keeping

Retiring a local guard as "subsumed by the canonical grammar" turned a Spanish postcode into
a number three orders of magnitude wrong, by discarding the leading zero that carries its
meaning. The comment asserting the grammar decided it "the same way for the same reason" was
unmeasured. The guard is restored and documented as non-redundant, at the site, so the next
reader with the same correct-sounding intuition meets the argument rather than the
temptation.

That is the boundary of the whole exercise. Canonicalization establishes one home per
**concept**, not a merge of every site that looks alike — and the discriminator is whether
the specific case carries meaning the general authority discards. A postcode is not a
decimal.
