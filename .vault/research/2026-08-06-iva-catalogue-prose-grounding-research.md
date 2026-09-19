---
tags:
  - '#research'
  - '#iva-catalogue-prose-grounding'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:3fa943501a34327a673544d4321ebc32dceb10e6d171a14e730ee3fcffc872a1'
related: []
---
# `iva-catalogue-prose-grounding` research: where catalogue prose goes, and who reads it

## What was measured

The bundled IVA catalogue declares twenty categories. Every one routes its
operator-facing text through translation keys rather than storing the text:
`label`, `description`, `triggers_when`, `iva_treatment`, and a `quoted_text`
on each citation. Thirty-nine citations across the twenty categories, drawn
from twenty-four distinct LIVA articles, all of them `ley-37-1992`.

None of those keys exists in any of the four locale catalogues. Parsing each
YAML and reading the `iva.catalogue` subtree returns zero entries in Spanish,
English, Catalan and Hungarian alike.

The translation helper does not fail on a missing key. It falls back to a word
derived from the final key segment, so the catalogue resolves to generic
English nouns:

    tr('iva.catalogue.intra_community_service_supply.label')  ->  'Label'
    tr('iva.catalogue.domestic_general_21.label')             ->  'Label'
    tr('...intra_community_service_supply.citations.0.quoted_text')  ->  'Quoted text'

The second line is the one that dates the condition. `domestic_general_21` is a
long-standing category, not part of any recent change, and it degrades
identically. The catalogue has always rendered this way.

## Why nothing caught it

Two independent mechanisms both read as enforcement and neither can fire.

The locale scaffold reports all four catalogues clean. Its discovery walks the
codebase and some registry trees — it found the category-profile keys when
those landed — but it does not scan the IVA catalogue TOMLs. The keys were
therefore never enrolled in the parity or honesty ratchets. They cannot drift
because nothing is watching them.

The schema carries a validator whose name promises the missing check. It
asserts that the translatable value is non-empty. By the time it runs, the
catalogue loader has already resolved the key through the translation helper,
so what it validates is the fallback string, never the key. A guard that
inspects `'Label'` and finds it non-empty cannot fail, and has never guarded
anything.

## Who actually reads this prose

Consumers were enumerated rather than assumed.

The regulation record that holds `label`, `description`, `triggers_when` and
`iva_treatment` has no consumer outside its own domain package. No application
service, no CLI command, no rendering surface.

The citation formatter that composes `"<document_id>, <article>: <quoted_text>"`
likewise has no consumer outside the domain package beyond its own test.

The one component that wanted this prose already routed around it and recorded
why. The transaction classifier's prompt builder carries a comment stating that
the catalogue's own label fields are keys not carried in the locale catalogues,
so they cannot serve as hints, and that curated one-liners are the
authoritative prompt descriptions instead. That workaround is itself evidence:
the defect was noticed, worked around locally, and never recorded as a defect.

## The severity is not uniform, and that is the finding

For `label`, `description`, `triggers_when` and `iva_treatment` the consequence
is documentation-grade. Nothing renders them, so nothing is currently wrong for
an operator; the text is dead weight that reads as a feature.

`quoted_text` is different in kind. It is meant to carry the verbatim legal
text that makes a category's citation checkable against the bundled corpus,
which is the discipline that governs every other legally-grounded value in this
registry. Today every category's legal quotation resolves to the literal string
"Quoted text". No category's legal basis can be cross-checked — not weakly, but
not at all, because the evidence is absent from the record rather than merely
unverified.

That distinction is what makes this more than a cleanup. Twenty categories
carry citations that assert a legal basis and supply no text to support it.

## What the corpus can support

All twenty-four cited articles resolve in the bundled consolidated LIVA text.
No corpus work is a prerequisite: the verbatim text needed to ground every one
of the thirty-nine citations is already present in the repository.

## The two shapes available

Keep the indirection and enrol the keys. Scaffold discovery would have to be
extended to the catalogue TOMLs first, after which roughly a hundred and twenty
keys would be authored across four catalogues — close to five hundred values,
most of them verbatim Spanish legal text plus three translations each.

Store the prose inline and drop the indirection. Roughly a hundred and twenty
Spanish strings move into the file that already holds the citations they
belong to.

The second is not merely cheaper. Verifying a quotation against the bundled
corpus requires the literal text at the citation site; indirecting it through a
translation key means the record no longer carries its own evidence, whatever
the key resolves to. No amount of locale authoring restores that property,
because the property is about where the text lives rather than what it says.

## Adjacent finding, separate owner

The classifier's curated hint table covers eighteen of the twenty categories.
The two absent are the intra-community service categories added by in-flight
work. The prompt builder falls back to the category's own de-underscored value,
so both remain selectable and this is not an unreachable-surface defect. It
matters for a narrower reason: every other category carries a curated
explanation of when it applies, and the fallback conveys everything except the
services-versus-goods distinction that the new categories exist to draw. No
gate asserts parity between the hint table and the category enum.
