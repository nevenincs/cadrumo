---
tags:
  - '#adr'
  - '#iva-catalogue-prose-grounding'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:410d588b24434137bd88ade54f03bf3a385937fbde55ae7a6cda91a183a88ca0'
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
unchanged.
