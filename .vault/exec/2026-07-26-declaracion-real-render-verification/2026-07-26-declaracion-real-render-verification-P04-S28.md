---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S28'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Rule whether enum is a claim about the value space or merely a hint, since the schema enforces no enum-versus-text distinction and the answer decides whether the four flagged targets are defects or documentation

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Description

- Establish what production does with value_kind, rather than what the schema suggests.
- Rule on whether enum claims anything about the value space.
- Record the ruling where a future author meets it, and pin it as behaviour.

## Outcome

Ruled: value_kind is a parse directive, not a type declaration, and enum is a hint that makes no enforceable claim. The four flagged targets are documentation, not defects.

The evidence is that production reads value_kind in exactly three places and every one branches on amount. The classifier picks Spanish-decimal parsing plus the blank-box guard for amount and carries the raw token through otherwise; the hit-finder routes named-label amounts through the word-level positional pass; the page-word prepass decides whether a profile needs word extraction at all. Nothing distinguishes enum from text, and the classifier's own comment says so outright.

Nothing declares the permitted members of any enumeration either. There is no set to validate against and no consumer that would consult one, so enum is not a weakly-enforced constraint; it is an unenforceable one.

That also disposes of the apparent incoherence. value_kind says how to read a printed token and data_type says what the casilla holds, so they answer different questions and comparing them for coherence is a category error. This is the concrete form of the warning the governing record already carried, that a gate written against the naive rule would be wrong in both directions at once.

The alternative ruling, that enum is a claim and the four targets are therefore defects, was rejected because implementing it requires authoring a member list per target. Those are regulated AEAT values and no bundled evidence states them. Declaring the ruling and refusing to invent the sets is the honest option; inventing them to satisfy a coherence argument is the failure this campaign exists to refuse.

The ruling is recorded on the schema field and pinned by four assertions. The load-bearing one fails if anyone makes enum behave differently from text, which forces the prerequisite the ruling names rather than allowing a silent claim to appear. Two more stop the ruling outliving its own premises: one fails if a member-list field is added, one if the vocabulary gains a fourth member the ruling never adjudicated.

## Notes

The count needed correcting as I measured it. The governing record says four, and four is right for the declaration-PDF surface, but the estate-wide figure is eight: Modelo 180 carries four more on the export-record surface. Both the schema note and the test module now carry the scoped count with its as-of date and its method, because an unscoped four is exactly the shape of claim this campaign kept having to retract.

The four extra are if anything a stronger case for the same ruling, since no consumer reads value_kind on that surface at all. The ruling did not change, only its stated reach.

Verified by mutation rather than by inspection: routing enum down the amount branch fails the identity assertion, and the parser was restored byte-exactly afterwards. The mutation flips an assertion rather than merely killing a fixture, so it shows the contract is checked and not just exercised.

What this does not settle. Whether enum should become a claim is left open on purpose. The ruling is about what it is today and what must happen first if that changes; it is not an argument that the value spaces are not worth declaring.
