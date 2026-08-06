---
tags:
  - '#adr'
  - '#iva-catalogue-prose-grounding'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:d27b98d9b8418eb2a7238ea70c823a02bf529103a2732e1060902b9b0e9020b4'
related:
  - "[[2026-08-06-iva-catalogue-prose-grounding-research]]"
---
# `iva-catalogue-prose-grounding` adr: `catalogue prose is stored inline, not indirected through locale keys` | (**status:** `accepted`)

## Problem Statement

The bundled IVA catalogue's twenty categories route every piece of prose
through translation keys — label, description, trigger explanation, treatment
summary, and the verbatim quotation on each of thirty-nine citations. None of
those keys exists in any of the four locale catalogues, and none ever has.

The consequence for most of those fields is cosmetic, because nothing renders
them. The consequence for the citation quotations is not. `quoted_text` is
meant to carry the verbatim legal text that makes a category's citation
checkable against the bundled corpus. Today every one resolves to the literal
string "Quoted text", so no IVA category's legal basis can be cross-checked —
not weakly, but not at all, because the evidence is absent from the record
rather than merely unverified.

## Scope

In scope: the prose fields of the IVA catalogue registry — `label`,
`description`, `triggers_when`, `iva_treatment`, and each citation's
`quoted_text` — and the schema validator that purports to guard them.

Out of scope: the locale scaffold's discovery gap, which this decision removes
the consequence of without closing; the classifier hint table's coverage; and
any change to how modelo locales or category profiles handle their own prose.

## Findings

Full measurement is in the companion research document. In summary:

Zero of roughly a hundred and twenty catalogue keys exist in any of the four
locale catalogues. The translation helper falls back to a word derived from the
final key segment, so categories resolve to "Label", "Description", "Quoted
text". A long-standing category degrades identically to a newly added one,
which dates the condition to the catalogue's origin rather than to any recent
change.

Two mechanisms that read as enforcement cannot fire. The locale scaffold does
not scan the catalogue TOMLs, so the keys were never enrolled in the parity or
honesty ratchets. The schema validator that promises the check runs after the
loader has already resolved the key, so it inspects the fallback string and
finds it non-empty.

Consumer enumeration shows nothing renders this prose: the regulation record
has no consumer outside its domain package, the citation formatter none beyond
its own test, and the transaction classifier that wanted the text already
worked around it with curated constants, recording in a comment that the
catalogue's keys are not carried in the locale catalogues.

All twenty-four cited articles resolve in the bundled consolidated LIVA text,
so no corpus work is a prerequisite.

The verification pass that followed this decision split the thirty-nine
citations thirty-four to five. Five could not be grounded, in three distinct
shapes: an article that states a rule adjacent to the one its category claims,
a category whose situation the cited article does not address at all, and one
sentinel category that carries no legal basis because it denotes the absence of
a classification rather than a treatment.

Two of the thirty-four survived a careful hand-read and were still wrong. Both
were paraphrases close enough to the enacted text to pass inspection: one
collapsed a two-level enumeration into a single sentence, the other carried
wording the cited article does not contain. Neither was caught by reading; both
were caught the moment the stored text was read back against the corpus. That
is the strongest available argument that the replacement invariant had to be
machine-checked rather than author-attested.

## Constraints

The verbatim text must be verified against the bundled corpus as it is written,
not copied from wherever a key pointed. A quotation that cannot be verified is
left explicitly unresolved and recorded; inventing text would reproduce the
defect in a shape that looks correct.

The production files involved carry live uncommitted work from another agent,
so the change waits on that landing.

Any replacement invariant must be able to fail, and be proved to fail by
mutation rather than assumed to.

## Considered options

Enrol the keys and author four catalogues. Extend scaffold discovery to the
catalogue TOMLs, then author roughly a hundred and twenty keys across four
locales — close to five hundred values, most of them verbatim Spanish legal
text plus three translations each.

Store the prose inline and drop the indirection. Roughly a hundred and twenty
Spanish strings move into the file that already holds the citations they
belong to.

Leave it. The condition is long-standing and nothing currently renders the
affected fields.

## Considerations

The first option preserves four-language support for a surface that does not
exist, at roughly four times the authoring cost, and — decisively — preserves
the property that makes citation verification impossible.

The third fails on the citation half. A grounding breach across twenty
categories is not cosmetic, and it persists precisely because two gates report
clean over it.

## Rationale

Three supporting reasons and one that decides it.

No reader exists, so authoring four languages buys nothing until a surface
renders any of it. A translated surface nobody reads is the mirror image of a
field no surface can set.

The cost is asymmetric, roughly a hundred and twenty strings against five
hundred values plus a scaffold change.

The registry already stores legally-grounded prose inline, and the governing
rule for modelo locales states the position directly: the official Spanish is
the legal source, translations a separate layer added where an operator surface
exists. The IVA catalogue is a third pattern matching neither.

The deciding reason is structural rather than economic. Verifying a quotation
against the bundled corpus requires the literal text at the citation site. An
indirected quotation means the record no longer carries its own evidence,
whatever the key resolves to, so no amount of locale authoring restores the
property — the property concerns where the text lives rather than what it says.
Inline is not the cheaper shape in which `quoted_text` works; it is the only
one.

## Decision

Catalogue prose is stored inline in the registry TOML as authoritative Spanish,
and the translation-key indirection is removed for these fields.

The validator that cannot fail is removed or replaced. If a replacement
invariant is warranted — a non-empty quotation, a citation that resolves
against the corpus — it is written so that it can fail and mutation-proved.

## Implementation

Sequencing follows severity. The citation quotations are grounding evidence and
are corrected first, each verified verbatim against the bundled consolidated
LIVA text as it is written. The remaining four fields per category are
documentation-grade and follow in the same pass, because the mechanism is
identical.

The four documentation fields were deleted rather than authored. The
distinction that decides this is that their content was irrecoverable, not
merely untranslated: the keys resolved to a fallback derived from the final key
segment, so no prior Spanish text existed anywhere to move inline. Authoring
them would have meant writing new prose for a surface with no reader, under a
decision whose whole basis is that no such reader exists. Deletion is therefore
the honest form of the same decision, and a later operator surface can add the
fields back with content written for it.

A citation's grounding is now declared rather than assumed. Each carries a
state -- verified or unresolved -- and the record must hold the evidence for
whichever it claims: a verified citation carries its quotation and no reason, an
unresolved one carries its reason and no quotation. The second half matters as
much as the first, because the corpus check skips the unresolved state by
design, so candidate text parked there would never be read against anything
while reading as evidence to anyone who printed it.

The replacement invariant is corpus containment, not non-emptiness. The
normalised quotation must occur in the normalised corpus text for its own legal
reference, reusing the mechanism the registry already applies to declared
required text. It is mutation-proved with a plausible substitution -- correct
article, correct sentence shape, wrong rate -- which the prior non-emptiness
check accepts and this one rejects.

The change waits on the in-flight work in the same production files landing
first.

## Recommendations

Record the scaffold discovery gap separately. Removing these keys removes the
immediate consequence without closing the hole that let a hundred and twenty
keys sit outside every ratchet, and any future registry tree adopting
translation keys lands in the same position.

Expect the verification pass to surface citations whose article does not
support the claim its category makes. Those are real findings and must be
recorded rather than smoothed over by choosing a more agreeable quotation.

Should an operator surface later need translated catalogue prose, add the
established per-revision translation layer with the authoritative Spanish
remaining the legal source, rather than restoring key indirection at the
citation site.

One of the five unresolved citations needs a scope decision this decision does
not make. The zero-rated domestic category has no general Spanish zero rate to
cite, which suggests the category is either narrower than its name or should be
retired in favour of the exemption categories that carry real articles. Both are
substantive changes to a closed taxonomy with existing data, so the citation is
recorded unresolved and the question referred rather than settled here.

## Consequences

Twenty categories' legal bases become checkable against the bundled corpus for
the first time. That is the point of the change, and also its risk: the
verification pass may find citations whose article does not support the claim
the category makes.

Four-language rendering of catalogue prose is given up. Nothing renders it
today, so nothing regresses.

The scaffold's discovery blind spot is not closed. Removing the keys removes
the immediate consequence, but any future registry tree that adopts translation
keys lands in the same position.

A validator disappears that never guarded anything, which slightly reduces the
apparent number of checks over this registry while leaving the real number
unchanged. What replaces it raises the real number for the first time: thirty-
four quotations are now read back against the corpus on every catalogue
verification, and five categories state in the record itself that their legal
basis is unresolved and why.

The five unresolved citations are a visible gap where there was previously a
clean surface. That is an improvement in accuracy and a regression in
appearance, and the appearance was false.
