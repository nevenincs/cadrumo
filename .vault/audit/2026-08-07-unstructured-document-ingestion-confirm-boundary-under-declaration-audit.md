---
tags:
  - '#audit'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0466fbb0ccadc5755b26352eb4d64904796674d1627338a23e0afd1e60a1c52c'
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

Two things about it are worth recording. The completeness manifest declares
exactly the skeleton's own casillas, and its number fields repeat the casilla
ids rather than official box numbers, so the export completeness gate is
self-consistent with the under-modelling and structurally cannot detect it: that
gate guards rendering, not modelling. And the first pass at this finding searched
casilla ids for the substring recargo and found none on Modelo 303 either, which
was a false negative. Modelo 303 does include its recargo tiers, referenced by
box number rather than by a semantic id. Searching one naming scheme when a
model carries two is how a correct model reads as broken.

### bulk-import-has-no-recargo-column | low | Not a silent loss: unknown columns are refused

The bulk invoice import accepts five required and four optional columns, none of
them recargo, retencion or IVA category, and it refuses an unrecognised header
rather than ignoring it. An operator cannot express a recargo through this path,
but nothing is dropped quietly. Its candidate and its write are also built
identically, so it does not carry the idempotency divergence found at the
confirm boundary. A capability gap, not an under-declaration.

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

An architecturally significant question is left open for a follow-on decision
record: whether a skeletal registry modelo should be reachable by calculate and
export at all. Modelo 322 and Modelo 353 will produce a draft that the
completeness gate passes, because the manifest describes the skeleton rather than
the official form. The decision that record must make is whether a modelo
declares its own modelling completeness explicitly, so a partial model refuses a
filing artefact instead of producing a confident and thin one.
