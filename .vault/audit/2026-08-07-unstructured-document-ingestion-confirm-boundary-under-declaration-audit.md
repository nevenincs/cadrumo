---
tags:
  - '#audit'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:df3326887cb340eb626a97063eb63862a680000fe25d02086649a764290bcca1'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` audit: `Confirm-boundary under-declaration sweep`

## Scope

A sweep for sites where a declarable value can be silently dropped, collapsed,
defaulted or rounded away between where a document is read and where the figure
reaches a declaration. Seeded by the multi-rate collapse found at the invoice
confirm boundary, and generalised from its shape: two correct halves with a
lossy boundary between them, each half carrying its own passing tests, neither
half's tests able to see the loss.

The sweep was led by semantic search over the code and the decision corpus, with
every candidate confirmed against the tree at HEAD before action. It covered the
structured-document readers and the confirm boundary, the bulk invoice import
path, the ledger aggregation predicates, and the cuota-devengada totals of the
IVA modelo family. Every fix was proven red before it was written, against
bundled corpus fixtures rather than hand-built objects, so parser and boundary
are exercised together and neither can be satisfied by a stub of the other.

## Findings

### structured-single-rate-cuota-collapse | critical | A one-rate structured invoice lost its entire cuota and confirmed as exempt

The structured readers populate the per-rate breakdown and never the draft's
flat rate field. The confirm boundary read the breakdown only when it held two
or more entries, so a one-rate document reached the writer with no rate at all,
resolved to the base-only exempt slot, and minted a zero-cuota invoice out of a
document that plainly charged one. This is the far commoner case than the
multi-rate collapse that was fixed first, and it was left open by that fix.

Measured on the bundled Facturae recargo fixture, which prints base 100,00,
cuota 21,00, recargo 5,20 and total 126,20. It confirmed as base 100,00 with a
zero cuota and no recargo, a recorded total of 100,00 against a document
totalling 126,20. Red before the fix: `assert Decimal('0') == Decimal('21.00')`,
alongside a printed-total discrepancy of 26,20. Not a rounding drift; the whole
tax was gone. Fixed by reading the breakdown at any length. A breakdown missing
either half of a subtotal falls through rather than being completed, because
deriving the missing cuota would substitute the boundary's arithmetic for the
document's own figure.

### recargo-equivalencia-dropped-at-confirm | critical | The recargo the document states never reached the record

The Facturae parser reads the equivalence-surcharge amount exactly, and the sole
sanctioned invoice writer already models the recargo as riding inside the
invoice total under LIVA art. 161, re-checking the base plus cuota plus recargo
identity on the way in. The boundary between them forwarded only the operator's
explicit override, so a document stating its own recargo lost it whenever the
operator did not retype the figure they were confirming. A recargo is a real
cuota the issuer owes and Modelo 303 sums it in its own devengado tiers, so the
loss removes the whole figure from every downstream aggregation while leaving an
invoice that looks complete. Fixed by layering the document-read value under the
operator override, exactly as every other field on this path is layered.

### confirm-idempotency-candidate-divergence | high | A retry of a multi-rate confirm raised instead of returning the existing record

The invoice identity hashes the grand total, and the guarded-retry lookup was
performed against a candidate invoice built separately from the one actually
written, without the per-rate lines or the recargo the real record carries. The
candidate hashed 150,00 where the record it had to find held 176,00, so the
lookup missed every time and the retry fell through to the writer's
duplicate-identity refusal. Proven red against the prior commit on the bundled
two-rate fixture: `InvoiceValidationError: an invoice with the same identity
already exists in the catalogue` on the second confirm. This arrived with the
multi-rate fix rather than predating it, and it breaks the idempotent-guarded
contract for an operator that is an autonomous agent and therefore retries.
Fixed by building the candidate from the same resolved lines and recargo as the
write.

### iva-category-dropped-at-confirm | critical | The document's own IVA treatment was dropped, silencing a reverse-charge self-assessment

The tax-category code is a fact only a structured reader can recover: it is in
the document's own record and no regex or vision reader can supply it. The
parser already mapped it onto the closed category enum for exactly that reason.
The boundary forwarded only the operator's override, so a document stating its
own treatment lost it whenever the operator did not restate the label.

Domestic reverse charge under LIVA art. 84.Uno.2 is the case where that costs a
declaration. Reverse charge, exempt and zero-rated supplies all print a taxable
base and no cuota, so once the code is gone the record cannot be told apart from
an ordinary zero-cuota supply, and the self-assessed output IVA the recipient
owes is never assessed. Nothing downstream recovers it: the aggregation layer
derives a domestic category from the stored rate and bank direction, which is
correct for an ordinary supply and wrong for this one. Red before the fix:
`assert None is <IvaCategory.DOMESTIC_REVERSE_CHARGE>`.

The source change for this finding was swept into commit `bdc24c48b6` by an
unrelated no-pathspec commit, so a reader arriving at that SHA finds the code
under another message with no explanation. The reasoning was landed separately
and in full as commit `9cd4e7f2e1`; that is where it is recoverable.

The proof needed a new bundled fixture, because no document in the corpus stated
a category other than the standard-rate code, so the drop could not be detected
against the corpus as it stood. The fixture carries a provenance sidecar
declaring it synthetic. The asserted value is the category the document states,
never a figure recomputed from the code under test.

### m322-m353-skeletal-devengada-totals | medium | Not fixed: the grupo-entidades modelos omit recargo, among much else

The cuota-devengada total of Modelo 322 sums four repercutido terms and no
recargo tiers, which reads as the omission the standing recargo rule names. It
is not that defect. Modelo 322 carries ten casillas in total and Modelo 353
thirteen, against Modelo 303's one hundred and twenty-six, and neither declares
a recargo casilla anywhere in its tree. These are skeletal registry models
covering only the regimen general spine; recargo is one of many absent axes.

Adding a recargo term alone would reference casillas that do not exist and would
break registry load. The gap is modelling completeness against the official
Modelo 322 form, needing legal grounding, not a formula edit. Left unfixed
deliberately.

The under-modelling is invisible to the gate that exists to catch it; that is a
separate defect and it is recorded as its own finding below.

One correction worth keeping. The first pass at this searched casilla ids for the
substring recargo, found none on Modelo 303 either, and briefly read a correct
model as broken: Modelo 303 does include its recargo tiers, referenced by box
NUMBER rather than by a semantic id. Searching one naming scheme when a model
carries two is how that happens, and it is the failure mode a symbol-name search
cannot protect against.

### completeness-manifest-cannot-see-under-modelling | high | The export gate is self-consistent with a skeletal modelo and structurally cannot fail on it

The export completeness gate asserts that every casilla the completeness manifest
requires carries a value before any filing artefact is written. On Modelo 322 and
Modelo 353 the manifest declares exactly the skeleton's own casillas, and its
number fields repeat the casilla ids rather than official AEAT box numbers. The
gate therefore compares the model against itself and passes.

That is a gate that cannot fail on the defect it exists to catch. It guards
RENDERING -- did the calculation populate what the model declares -- and nothing
in the chain guards MODELLING, so a modelo covering a fraction of its official
form produces a draft that is confident, thin, and green. The digest over those
bytes is a byte-integrity lock, not a completeness one.

Not a Modelo 322 problem specifically. Any modelo whose manifest was authored
from its own casilla set rather than from the official form inherits it, and the
repeated-id number fields are the readable signal that this one was. Belongs in
front of whoever owns those modelos, grounded against the official forms.

**Scope measured, by the coordinator, after this finding was widened.** The claim that any manifest authored from its own casilla set inherits the blindness is correct, and the readable signal is sharper than "repeated ids": it is whether the `number` field holds an official box number at all.

`id == number` is NOT the signal. For most modelos the casilla id legitimately IS the box number -- Modelo 303 carries `casilla_id = "59"` with `number = "59"`, and that is the manifest correctly naming box 59. Counting id/number equality flags those as suspect and is the wrong measurement; it was run first and discarded.

The discriminator is a `number` value that could not be a box: a dotted internal identifier such as `iva.autorepercutido.intracomunitaria` or `compensacion-disponible-fin-periodo`. Those name a casilla in the registry's own vocabulary, so the manifest is quoting itself where it should be quoting the form.

Counted across every modelo completeness manifest in the tree, as non-box `number` values over total rows:

| Modelo | Non-box | Rows |
| --- | --- | --- |
| 232 | 56 | 56 |
| 309 | 3 | 3 |
| 322 | 8 | 8 |
| 349 | 4 | 4 |
| 353 | 11 | 11 |
| 369 | 8 | 8 |
| 720 | 5 | 5 |
| 303 | 42 | 102 |
| 390 | 18 | 38 |
| 210 | 6 | 22 |
| 714 | 1 | 13 |

Thirteen modelos are clean throughout: 111, 115, 117, 123, 126, 128, 136, 187, 188, 194, 202, 216, 296.

Two readings this supports, and one it does not.

**Seven modelos are wholly self-quoting** (232, 309, 322, 349, 353, 369, 720). For those the finding applies exactly as written: the manifest and the modelo were authored from the same source, so the gate compares a skeleton against itself.

**Four are MIXED**, and that is the more interesting result. Modelo 303 is the campaign's best-modelled IVA form at 126 casillas, and 42 of its 102 manifest rows still carry an internal name where a box number belongs. So this is not a property of skeletal modelos -- a well-modelled one carries it too, on the part of its manifest that was written from the registry rather than from the form. A reader who took "skeletal modelo" as the boundary would not look at 303 at all.

**What this does NOT establish** is that any of these rows is wrong in its declaration. A non-box `number` proves the manifest was authored from the casilla set; it does not prove the casilla set is incomplete against the official form. Those are separate claims and only the first is measured here. Modelo 303's 42 rows may correspond to real boxes whose numbers simply were not transcribed. Establishing under-modelling requires reading each form, which is the legal-grounding work this finding defers rather than performs.

### bulk-import-has-no-recargo-column | low | Not a silent loss: unknown columns are refused

The bulk invoice import accepts five required and four optional columns, none of
them recargo, retencion or IVA category, and it refuses an unrecognised header
rather than ignoring it. An operator cannot express a recargo through this path,
but nothing is dropped quietly. Its candidate and its write are also built
identically, so it does not carry the idempotency divergence found at the
confirm boundary. A capability gap, not an under-declaration.

### idempotency-projection-had-no-coverage-gate | high | The retry comparison's field set was hand-maintained with nothing pinning it

The manual ledger add's guarded retry returns the stored row when the content
matches, and the match is built from two hand-maintained parallel mappings folded
into positional tuples. A persisted field missing from the comparison makes a
retry that changes only that field look identical: the guard returns the old row,
the new value is discarded, and the operator is told the write succeeded.

This guard had already lost a field once, dropping the recargo and the source
jurisdiction on retry, and the fix extended the mapping by hand without adding
anything to stop it recurring. The mapping's own docstring offers a single
greppable site as the safeguard, which is a property of a reader who thinks to
grep; the field that went missing sat in a mapping just as greppable.

The positional fold carries a second failure mode nobody had named: a key present
in one mapping and absent from the other does not fail at that key, it shifts
every later field by one and compares unrelated values. Two gates now pin both,
deriving their expected set from the models rather than from a copied list.
Mutation-proven by dropping the recargo from the command projection, the exact
historical regression, which reds both with `At index 14 diff:
'source_jurisdiction' != 'recargo_amount'` and the named missing field.

### standard-rated-document-grounds-as-undeclared | critical | Not fixed: needs a legal decision. A plain rated invoice is refused by the renta income path

This is the same drop as the category finding above, seen from the far end, and it
is still open. The category code for a standard-rated supply carries no special
treatment, so the parser maps it to the empty string and the record is minted with
no category at all. A record with no declared IVA treatment fails the invoice
decomposition contract with an undeclared-treatment defect, and the renta
sales-evidence path refuses an ungrounded decomposition.

The refusal is not an exclusion, which is what makes it quiet. The row still
contributes, but it contributes its bank cash instead of the ingresos integros the
casilla asks for: the invoice's base, its cuota and its retencion are all dropped.
An advisory does fire, so this is visible to an operator who reads it, but the
figure that reaches the declaration is wrong.

Measured directly rather than inferred. Building the same invoice with no category
yields `grounded=False defects=['iva_treatment_undeclared']`; building it with the
general-rate domestic category yields `grounded=True defects=[]`.

Deliberately not fixed. The obvious repair is to resolve the standard-rate code to
its domestic tier from the rate the document states, and that is a legal mapping
this sweep has no authority to invent. The rate-to-category direction is not a
mechanical inversion of the category-to-rate mapping that already ships: that
mapping's own documentation records that a tier once carried exactly one rate for
all time and that RD-ley 4/2024 ended it. A percentage therefore identifies a tier
only in combination with a date, and a wrong inversion would mis-declare rather
than under-declare, which is not an improvement. A multi-rate document compounds
it, since one invoice carries a single category field and a two-tier document has
two answers. Needs legal adjudication and a modelling decision on the multi-rate
case.

### peer-registry-enum-not-hydrated-at-the-loader | medium | Not mine: an in-flight export-exemption enum reds every M130 registry load

Encountered while running gates, recorded because it was twice mistaken for a
transient. A new export-exemption reason enum is being introduced: the enum module
and the registry TOML value are both present, but the loader does not hydrate the
stored token into the enum at the boundary, so strict validation refuses the whole
M130 revision and any test that loads it fails with a validation error pointing at
an unrelated invoice model.

Left entirely alone: all three files are actively held. Noted only so the next
reader does not attribute the failure to the confirm boundary, which is where its
symptom surfaces.

### rate-derived-domestic-category | critical | Closed: the plain rated document now grounds, resolved rather than guessed

The open half of the standard-rated finding above is closed, and closing it
required inventing nothing. Two authorities already ship. One answers which tier
a declared rate WAS on a given date, against the registered rate records, and
returns a tuple precisely because that question can have more than one answer, so
a caller detects ambiguity instead of picking. The other is the single authority
for which domestic category a tier denotes, promoted after three independent
copies of that mapping were found. Composing them resolves the ordinary case
without asserting any legal mapping this sweep authored.

The earlier refusal to invert the category-to-rate direction was still correct.
The hazard recorded there was real but mis-scoped: RD-ley 4/2024 broke
tier-to-rate, not rate-to-tier. Measured against the shipped table, no percentage
maps to two tiers, and the 2 percent and 4 percent super-reducido rates both
resolve to the same tier.

Three cases decline rather than approximate, each with its own proof. A
multi-rate document, because one category field cannot hold a two-tier answer and
that remains a modelling decision. A recargo-bearing document, because such a
supply may belong to the ordinary domestic tier or to the recargo category and
the decomposition contract accepts BOTH, so a wrong pick would be caught nowhere
downstream. And a rate not registered on the issue date, which the lookup reports
as a real refusal rather than a lookup failure. Declining is visible; a guess
would not be.

Red observed before green by neutralising the resolution: `AssertionError: the
21% tier was not resolved from the document: None`. The refusal branch is
exercised against the real lookup rather than assumed, using a 2023 issue date
the registered records do not cover, paired with the same draft on a date they do
so the refusal is attributable to the date rather than to an unusable draft.

One convention is worth stating because it cost two probes to find: the lookup
takes the rate as a FRACTION, matching how a transaction stores it, not as the
percentage a document prints. Passing a percentage returns empty, and empty is
documented as a real refusal, so a caller unaware of the convention reads "not a
registered rate" for an ordinary 21 percent.

### zero-rate-record-dropped-for-2025-onward | high | Not mine: a rate re-grounding refuses legitimate zero-rated records

Encountered while running the regression after the change above. The Spanish rate
table was re-grounded to admit the 2024 temporary food rates, which is a correct
and welcome grounding. In the same pass the standing zero-rate records were
reduced to a single window covering July to September 2024, so the zero tier is
now in force only inside that window.

That conflates two different zero rates. The temporary measure is one thing; the
zero-rate SLOT is what an exempt or intra-community supply carries, and such a
supply in 2026 is entirely legitimate. Building one now raises `line rate RATE_0
was not in force on 2026-01-15`, and 26 tests in the invoices suite fail on it.

The direction is fail-closed, so it refuses records rather than under-declaring
them, which is the safe direction of the two. It is still wrong: a taxpayer with
an intra-community supply cannot record it. Left entirely alone, as re-grounding
a rate table is a legal exercise owned by whoever performed it, and the fix is a
decision about whether the zero SLOT and the temporary zero RATE are one record
or two.

## Recommendations

Treat a parser field that no consumer reads as a defect class in its own right,
not a latent capability. Every loss in this sweep had the same signature: a value
the reader recovered correctly, a writer that already modelled it, and a boundary
that forwarded only the operator's override. A test on either side passes while
the value never arrives. The cheap standing check is to enumerate the draft's
fields against the fields the confirm resolves, and to justify each difference
rather than each match.

Prefer the printed total as a detector, but never as a control. The
printed-versus-recorded cross-check correctly flagged 26,20 of missing tax on the
recargo fixture, and its own documentation already named all three losses it
would catch. It fired for years without any of them being fixed, because an
advisory that the totals disagree is not a declaration of the missing figure. A
detector that nothing acts on is indistinguishable from an absent one.

Two architecturally significant questions are left open for follow-on decision
records, and neither can be closed by a test.

The first: whether a skeletal registry modelo should be reachable by calculate and
export at all. Modelo 322 and Modelo 353 will produce a draft that the
completeness gate passes, because the manifest describes the skeleton rather than
the official form. The decision that record must make is whether a modelo
declares its own modelling completeness explicitly, so a partial model refuses a
filing artefact instead of producing a confident and thin one.

The second: how a standard-rated structured document resolves to a domestic IVA
tier. A document stating the standard-rate code carries no special treatment, so
the record is minted with no category, and a record with no declared treatment is
refused by the invoice decomposition contract. The decision that record must make
is whether a rate percentage may be resolved to a tier at all, given that the
one-tier-one-rate assumption ended with RD-ley 4/2024 and a percentage now
identifies a tier only together with a date; and what a multi-rate document
resolves to, when the record carries a single category field and a two-tier
document has two answers. Until that is settled, a plain rated invoice confirmed
from evidence contributes its bank cash rather than the ingresos integros the
casilla asks for. That is a live under-declaration, not a latent one.

A guard whose completeness is maintained by hand should carry a gate that derives
its expected set from the model. Two of the findings here are the same mistake at
different sites: a field is added to a record and a comparison, a projection or a
forwarding list is not extended with it, and nothing notices because every test on
both sides still passes. Greppability and a careful docstring are not controls.
Where a list must mirror a model, assert the mirror against the model.

A test that passes the day it is written proves nothing until it has been made to
fail. Every gate this sweep added was mutation-checked against the exact
historical regression it claims to prevent, and the diagnostics were read rather
than assumed. That is cheap and it is the difference between a gate and a comment.
