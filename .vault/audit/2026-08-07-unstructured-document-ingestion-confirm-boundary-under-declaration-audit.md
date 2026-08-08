---
tags:
  - '#audit'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:56c84e2527fdfb8b9863c89502c2fb5ae5ba64675235c25c09f863821724234e'
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

### invoice-and-bank-paths-classify-differently | critical | Not fixed: two feeds of one binding source disagree, and the zero-cuota half is dropped

Handed over by the invoice-IVA-category work and verified here at HEAD rather
than taken on report. The finding is real, and the fix it appears to call for is
not the fix.

The invoice-to-Modelo-303 loop skips every line whose cuota is not positive, so
an exempt, zero-rated or export line never becomes an observation. Axis-A
declares all six of those categories base REQUIRED, cuota ZERO_BY_LAW,
applicability ARISES, and the casilla 59 and 60 bindings exist and are live. So
there is a real consumer waiting for a base that never arrives.

What the report implies -- remove the guard -- delivers nothing. The loop builds
observations through a helper that classifies from the RATE SLOT, not from the
invoice's category, and that helper's own docstring says intra-community lines
must be constructed directly instead. Measured: the exempt slot yields category
domestic_exempt and rate kind exempt, while casilla 59 selects category
intra_community_supply with rate kind zero, and casilla 60 the two export
categories with rate kind zero. An exempt supply line misses on BOTH axes.
Removing the guard turns a dropped line into an observation that matches neither
binding: the casillas stay empty and the change looks like a fix while moving no
money. It is at least not harmful -- no Modelo 303 binding selects
domestic_exempt or domestic_zero, so the stray observations mis-route into
nothing rather than into a wrong casilla.

The root cause is an asymmetry between two feeds of ONE binding source. The
bank-transaction path reads the declared category first and falls back to the
rate-derived domestic category only when none is declared, and it gates an
intracom or export claim on the counterparty. The invoice path does none of
that: rate slot only, and zero-cuota lines dropped before classification. Two
surfaces populating the same source with divergent logic is the shape the
pull-equals-calculate discipline exists to prevent, and it is why one of them can
route an intra-community supply to casilla 59 and the other cannot.

The fix is therefore to make the invoice path read the invoice's own category the
way the bank path reads the transaction's, including the counterparty gate, not
to relax the cuota guard. That input is more available than it was: the confirm
boundary now populates the category from a structured document's own code, and
the codes for an intra-community supply and an export map to exactly the
categories these selectors want.

Left unfixed here for sequencing, not for doubt: the owning campaign holds the
decision record for this axis, the change touches a gate with its own legal
preconditions, and the correction above is what that campaign needed before
acting.

The prorrata consequence in the handover has since been traced and REFUTED, by
its own author and independently confirmed. Both prorrata casillas take manual
input, and the only bindings touching them read casilla ids rather than writing
them, so the declared percentage never came from observations at all. The dropped
lines could not have moved it. Recorded as refuted rather than quietly dropped:
it was carried as an unproven hypothesis in two documents at once, which is
exactly the shape that starts to read as corroboration, and the correction is
worth more than the removal.

What the skip actually broke is better evidenced and worse in one respect. It
blinded the divergence DETECTOR precisely where an under-declaring operator would
have been caught -- a false negative in the expensive direction.

### feed-axis-had-no-parity-gate | high | Closed: casilla 59 was guarded from one side only, and that is why the divergence survived

The reason the invoice-versus-bank divergence lasted is not that casilla 59 was
untested. It was tested, it passed, and it was guarded -- from ONE side. A
transaction-shaped intra-community supply reached it and the assertion held. An
invoice-shaped one never arrived, and no test existed that could have noticed,
because no test drove the invoice feed to a casilla at all.

That is a structural blind spot rather than a missing case. A feed silently
declaring less than its sibling is invisible to a per-feed test by construction,
since each feed's tests only ever assert what that feed itself produces. Both
feeds stay internally consistent and green while one of them under-declares.

The transport axis already had its gate: the pull path and the calculate path are
held to the same casilla values. That axis asks whether two ways of REACHING one
resolver agree. The feed axis -- two SOURCES populating one binding -- had no
equivalent, and the two are genuinely different questions: every transport of
each feed can agree perfectly while the feeds disagree with each other.

Closed with a gate that takes one operation, expresses it as both an invoice line
and a bank transaction, and holds the two to the same casilla and the same
classification. Written as a comparison rather than an expectation, so it cannot
be satisfied by updating a constant to match a regression, and the agreed figure
is then checked against the operation itself so two feeds agreeing on a wrong
number fails too. Proven against the original defect: reverting the invoice feed
to rate-slot classification reds all three assertions.

### received-reverse-charge-invoice-loses-its-category | critical | Not fixed: the declared category is overwritten and no self-assessed cuota is produced

The third consequence of the root cause the routing fix closed, in a case that
fix deliberately did not cover. A received domestic reverse charge (LIVA art.
84.Uno.2) obliges the RECIPIENT to self-assess the output cuota, and Axis-A says
so: on the received side the pair is base required, cuota REQUIRED, not
zero-by-law. The supplier charges nothing, so the invoice line carries an exempt
slot and no cuota.

Measured on both feeds for one operation, a 2.000,00 construction supply the
recipient must self-assess:

    bank feed:    category=domestic_reverse_charge  rate_kind=general
                  flow=inversion_sujeto_pasivo      base=2000.00  cuota=420.00
    invoice feed: category=domestic_exempt          rate_kind=exempt
                  flow=soportado                    base=2000.00  cuota=0.00

Every field except the base disagrees. The invoice DECLARED
domestic_reverse_charge and the projection threw it away in favour of a
rate-derived domestic_exempt, so the self-assessed devengada entry is never
produced. Net-zero for a taxpayer deducting in full, a real underpayment under
prorrata, and wrong on its face in either case.

SPLIT BY SIDE, after a re-measurement that corrected a near-miss of this
audit's own. The supplier side is now CLOSED: a peer extended the projection with
a declared-category flow map, and an issued reverse-charge invoice routes its
base to casilla 122 at 2.000,00, verified against the live code. The recipient
side is still open and produces no binding at all.

Two errors of this audit's own are recorded in this finding rather than quietly
corrected, because both are the same shape: a claim generalised past the evidence
that was already in hand. The binding overgeneralisation above is one. The other
follows.

The near-miss is worth recording because it nearly became a finding. Measuring
the recipient side and observing casilla 122 stay at zero, this audit almost
reported that casilla as unreachable from either feed. It is not. Casilla 122
declares the SUPPLIER's base, and the flow member that reaches it exists
precisely to keep the two sides apart; the zero was the correct answer to a
question asked from the wrong side. The same discipline this sweep recommends --
ask which side a gate is green from -- applies to a finding as much as to a gate.

What remains is the recipient half, and it is contained differently than first
written. Preserving the declared category rather than overwriting it is a small
change on the projection this sweep owns.
Producing the self-assessed cuota is not, and the binding-level reason differs by
family. CORRECTED after a peer enumerated it and this audit had overgeneralised
past its own data: an earlier reading here said there is no recipient-side base
binding at all. That holds for the DOMESTIC family only.

Enumerating every binding on the self-assessment flow: the domestic recipient
side has two, both cuota. The intra-community recipient side has four, and one of
them IS a base binding. All six admit only the general, reduced and
super-reduced tiers, so a cuota-less line reaches none of them either way -- the
conclusion survives, but for a different reason per family.

The remedy, however, is the SAME for both, and the one option that looked
family-specific should be taken off the table. Widening the intra-community base
binding to admit the zero and exempt tiers was the obvious asymmetric fix, since
that family has a base binding and the domestic one does not. It is the wrong
fix. The component table declares cuota REQUIRED on the received side of all
three reverse-charge categories: a domestic reverse charge, an intra-community
acquisition and an intra-community service acquisition. None of them is ever
legitimately cuota-less.

So a cuota-less line in any of them is an INCOMPLETE RECORD, not a zero-rated
operation, and the two cases are not alike. Widening the binding would declare a
base with no matching cuota for an operation the law says always bears one --
making the return internally inconsistent and hiding the incomplete record behind
a partially-populated one. That is a worse failure than the current silence,
because a half-populated return looks answered.

The correct remedy for both families is therefore to complete the record rather
than loosen the binding: state the rate the supply bore, keeping the cuota at
zero if it was never charged. That is exactly what the advisory this sweep added
asks the operator to do, which makes the advisory the fix rather than a
placeholder for one.

The structural reason the SUPPLIER half was closable is the same axis read the
other way: the casilla 122 base binding admits the zero and exempt tiers, which
is exactly why routing a base into it works for a document carrying no cuota.
The difference between the halves lives in the registry, not in the projection.

Whether the domestic recipient side SHOULD have a base binding is deliberately
not ruled on here. Casilla 122 is the supplier's base, and where the recipient's
base belongs on the form is a registry and AEAT question; inventing a box would
be worse than the gap.

The rate remains the blocker on both: it is not on the record, and deriving it
would mean asserting which rate the supply bore.
The bank row in the measurement above carried its own rate and cuota because the
operator stated them; the invoice did not. Whether an invoice line may carry a
real rate slot with a zero cuota, which would make the cuota derivable rather
than invented, is the decision that half waits on.

### m349-and-m303-draw-intra-community-volume-from-different-sources | high | Not fixed: a bank-recorded supply is declared on one modelo and not the other

Found by asking which other destination has more than one feed. Modelo 349's
bindings are entirely invoice-sourced -- thirty-four of them, split between the
collectible and payable invoice families, with no ledger source at all -- while
Modelo 303 casilla 59 is fed by the ledger aggregation, which draws from the bank
transactions AND, since the routing fix, from invoices.

So the two modelos declare the same intra-community operations from different
places. A supply recorded only as a bank transaction reaches casilla 59 and never
reaches Modelo 349, which is the return AEAT reconciles the 303 against. The
reverse case, an invoice-only supply, was the one the routing fix closed.

There is a detector and it is honest about being one: a non-blocking WARNING
compares the 303 intra-community total against the 349 resumen beyond a
de-minimis. It surfaces the divergence rather than preventing it, which satisfies
the minimum but leaves the operator to reconcile two returns by hand.

Not fixed because the remedy is a modelling decision rather than a defect
repair: either Modelo 349 gains a ledger feed, or intra-community operations are
declared to require an invoice, and choosing between those is not this sweep's
call. Recorded with the measurement so whoever takes it does not have to
rediscover that the source sets are disjoint.

### rate-kind-cuota-correspondence-is-real-but-not-an-invariant | medium | A gate was built for it, failed honestly, and was withdrawn

The correspondence a peer identified is real and it explains the difference this
sweep had only observed: a binding admits the cuota-less tiers exactly where the
component table declares that side's cuota zero by law, which is why the casilla
122 base binding admits zero and exempt while every recipient-side binding
refuses them. Read across Modelo 303, 390 and 322 it holds for seventy-seven of
seventy-nine selector pairs.

It is not an invariant, and the attempt to gate it is what established that. The
first run failed on six Modelo 390 bindings. Every one of them is correct: the
rate-BOX layer declares a per-rate line the official form actually has, so a
tipo-0 binding must admit the zero tier to populate a box that exists, and each
carries its own legal refs and form citation. Excluding that layer by its
structural marker rather than by name left two more, and those are correct too --
a deliberate rate-blind base capture, equally grounded.

The gate was withdrawn rather than narrowed. Two carve-outs discovered by running
it, each found because the assertion failed and then justified after the fact, is
the shape where the judgement quietly moves into the allowlist: a third exception
would have been added the same way. A property that needs exceptions found by
failure is a description of the current tree, not a rule the tree must obey, and
gating it would have frozen today's shape while reading as a law.

The correspondence keeps its explanatory value and loses its claim to be a
constraint. Recorded so a later reader does not re-derive it, believe it
universal because it holds everywhere they happen to look, and gate it -- and so
the two exception classes are already named when someone asks whether it could be
gated with them declared as roles rather than discovered as failures.

### positional-return-drift-introduced-by-this-sweep | medium | Closed: and the defect was this sweep's own, not a pre-existing one

Recorded with the attribution corrected, because the correction runs against this
audit's interest and the generous version was offered rather than claimed.

The invoice screen and its caller returned widening positional tuples of
same-typed channels. This sweep added a fifth channel to one and a third to the
other, broke three unpack sites in a sibling test, repaired them, and noted that
the shape wanted a named record -- recording the follow-up rather than smuggling
the refactor into a behavioural change. A peer took the refactor and both
boundaries now return frozen dataclasses with defaulted fields, which also
removes the early-return paths' obligation to emit the right NUMBER of empty
tuples in the right ORDER.

The peer found that one boundary's annotation declared two slots while its body
returned three, and offered it as a pre-existing drift that nothing had caught.
It was not pre-existing. Checked against the commit before this sweep's change:
annotation two, returns two, consistent. After: returns three, annotation
untouched. This sweep introduced the drift and did not notice, in the same change
whose message argued that positional returns of same-typed channels are fragile.

That is the finding. Not that the shape is dangerous in the abstract -- it was
demonstrated on the author who had just written the argument, one commit later,
against the exact hazard being described. Nothing caught it because every slot
has the same type, so neither the checker nor a passing suite can see the count
disagree. Writing the argument is not the same as being protected by it, and an
author who has just reasoned about a failure mode is not thereby immune to it.

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

Ask which SIDE a gate is green from. The most expensive finding in this sweep
survived behind a passing test: the casilla it guarded was reached correctly from
one feed and never from the other, and the gate could not have failed. Where two
sources populate one destination, a per-source test proves each source consistent
with itself and nothing about the pair. The gate has to be a comparison between
them.

A test that passes the day it is written proves nothing until it has been made to
fail. Every gate this sweep added was mutation-checked against the exact
historical regression it claims to prevent, and the diagnostics were read rather
than assumed. That is cheap and it is the difference between a gate and a comment.
