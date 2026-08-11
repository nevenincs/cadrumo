---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:259ffa1a9fd75af4c387c7258dd556dc5135164a5d7d14f0b662bb5bade2c26b'
step_id: 'S309'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S309 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Compare the supplied and extracted counterparty identifiers with the SAME-BEARER predicate rather than the identity token, because the confirm path currently refuses a match this codebase already calls the same bearer. Measured at HEAD: the comparison uses tax_id_identity_token, whose own docstring says normalisation is trim-and-uppercase and NOTHING MORE, deliberately never merging identifiers that differ in their characters. But one side of this comparison is what an on-host extractor read off a PRINTED document, and printed invoices hyphenate and space these identifiers routinely, which this codebase established while fixing the redaction funnel. The other side is an operator flag or a stored profile value, where the compact form is normal. So an operator supplying the compact spelling against a document printing the separated one is refused with a message telling them to check the tax id printed on the invoice, when the two name the same bearer. The canonical same-bearer predicate is same_tax_identifier, which compares on the separator-stripped form precisely so that a printed hyphenated value matches a stored compact one, and its docstring states it is deliberately looser than the identity token for exactly this reason. THE SITE CHOSE THE TOKEN ON A REASONED BUT INCOMPLETE ARGUMENT: its docstring justifies the choice against a checksum gate, which is correct and settles the validity axis, and describes the alternative as a local trim-and-uppercase, which is a distinction without a difference since the token IS trim-and-uppercase. The separator axis was never considered. This is the same disagreement the redaction funnel carried, where the funnel called two spellings different while the same-bearer predicate called them one, and it is an over-refusal on the ingestion confirm path. Gate it with a printed-separator fixture on both sides, and keep the checksum reasoning intact since the fix is about separators and not validity and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Compare the supplied and extracted counterparty identifiers with the SAME-BEARER predicate rather than the identity token, because the confirm path currently refuses a match this codebase already calls the same bearer. Measured at HEAD: the comparison uses tax_id_identity_token, whose own docstring says normalisation is trim-and-uppercase and NOTHING MORE, deliberately never merging identifiers that differ in their characters. But one side of this comparison is what an on-host extractor read off a PRINTED document, and printed invoices hyphenate and space these identifiers routinely, which this codebase established while fixing the redaction funnel. The other side is an operator flag or a stored profile value, where the compact form is normal. So an operator supplying the compact spelling against a document printing the separated one is refused with a message telling them to check the tax id printed on the invoice, when the two name the same bearer. The canonical same-bearer predicate is same_tax_identifier, which compares on the separator-stripped form precisely so that a printed hyphenated value matches a stored compact one, and its docstring states it is deliberately looser than the identity token for exactly this reason. THE SITE CHOSE THE TOKEN ON A REASONED BUT INCOMPLETE ARGUMENT: its docstring justifies the choice against a checksum gate, which is correct and settles the validity axis, and describes the alternative as a local trim-and-uppercase, which is a distinction without a difference since the token IS trim-and-uppercase. The separator axis was never considered. This is the same disagreement the redaction funnel carried, where the funnel called two spellings different while the same-bearer predicate called them one, and it is an over-refusal on the ingestion confirm path. Gate it with a printed-separator fixture on both sides, and keep the checksum reasoning intact since the fix is about separators and not validity

## Scope

- `src/cadrumo/application/ledger`

## Description

- Read the confirm-path comparison at HEAD rather than trusting the row account.
- Drive the shared predicate over both the separator axis the row names and the
  country-prefix axis a live case surfaced.

## Outcome

PREMISE EXPIRED on the axis the row names. The comparison already uses the
same-bearer predicate rather than the identity token, and the site docstring
carries the row own reasoning: it states that the comparison is on the
separator-stripped form and that the identity token would NOT match those
spellings. Driven directly, a hyphenated and a spaced identifier both match
their compact form.

A SECOND AXIS is open, found empirically rather than by reading, while
refitting the confirm CLI suite under a sibling row. A bundled document states
the seller identifier in its VAT form and an operator supplying the bare
national form is refused, because the predicate strips separators and a
country prefix is not a separator. The refusal message tells the operator to
check the tax id printed on the invoice, which is the same dead end the
separator axis produced before it was fixed.

It is NOT closed here, deliberately, and the reason is the size of the blast
radius rather than the difficulty. The obvious fix -- strip a leading alpha-2
from both sides -- would merge bearers across States, because the same
national body can exist under two different country prefixes. A correct rule
must know the counterparty own country, which the current two-argument
predicate cannot be told. And that predicate is consumed by the identity-role
resolver and the document-direction deriver, so loosening it silently changes
who counts as the taxpayer on every document read.

Rowed separately with that reasoning rather than absorbed, so the second axis
stays visible as work instead of disappearing inside a row closed on its first.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Worth carrying: this axis was invisible to reading and visible only to
driving. The row was written from the code, the fix for its stated axis had
landed, and nothing in the module suggested a second one. It surfaced because
an unrelated refit put a real bundled document through the real confirm path
with an operator-supplied value beside it -- which is the configuration the
defect needs and the one no unit case had assembled.
