---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4805c962c2db536ff18b0d5d1f1449ec72bfab2289d4c8e9678098b23e20bc45'
step_id: 'S130'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

- `src/cadrumo/adapters/inbound/einvoice`
- `src/cadrumo/application/ledger`

## Description

- Land the gate first, red, so a sweep catching the change mid-flight takes a
  failing test rather than silent unproven behaviour.
- Add the party postal code to the parsed e-invoice record, absent by default.
- Read it from each format's own dedicated element: Facturae, UBL and CII.
- Carry both parties' codes through the structured projection into the draft.
- Mutation-prove the readers and, separately, the refusal to default.

## Outcome

A country code cannot separate Spain's three IVA territories, so a Spanish
party's territory is settled by its postal code or not at all. The exact reader
exposed no address of any kind, so a Facturae, CII or UBL document resolved
**neither** party's territory while a text-read document resolved both.

That is the inversion this path has produced before: the most machine-readable
documents in the corpus getting the least out of the pipeline, because the data
is structured, present, and simply never read. The regime legend had the same
shape until its structured carry landed, which is what makes this a real gap
rather than an oversight.

### Read from a dedicated element in all three formats, never parsed out of a blob

The distinguishing question was whether each format states the code on its own or
only inside a composite address string, because splitting a code out of a blob is
an inference rather than a read. All three state it separately, confirmed against
the bundled corpus rather than from memory where a specimen existed:

Facturae carries `AddressInSpain/PostCode` — the corpus specimen prints `08009`
for the seller and `45007` for the buyer. UBL carries
`cac:PostalAddress/cbc:PostalZone` and CII `ram:PostalTradeAddress/ram:PostcodeCode`,
both the EN16931 BT-38 and BT-53 mapping. No composite string is parsed anywhere,
so the "stop and report" branch the row anticipated never had to fire.

Facturae's sibling `OverseasAddress` block is deliberately **not** read. A party
established abroad has no Spanish IVA territory to resolve, so anything recovered
there would be a value the resolver must discard — and that block states its code
jointly with the town rather than on its own, which is exactly the composite this
work refuses to split.

### The safety asymmetry is enforced at the reader, not only at the resolver

An absent or unreadable code yields nothing. The resolver already refuses to
default an absent code to the mainland, and its docstring argues the case, but a
*reader* that defaulted would hand it a well-formed mainland code and the
resolver's refusal would never get the chance to fire. So the property is proven
on both sides of the boundary, and the proof that it is proven is a mutation
rather than an assertion.

### Provenance follows the path's established shape, and its gap is path-wide

The structured projection builds no provenance envelopes for any field — not for
the tax id, not for the regime legend, not for these codes. The postal codes
therefore carry none either, which matches the path rather than inventing an
origin for one field. The row anticipated that no production site constructs an
exact-structured field origin; that is confirmed, it is path-wide rather than
specific to this change, and no origin was fabricated to paper over it.

## Verification

The gate, five cases through the real encrypted evidence path:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_path_postal_codes.py -n0 -m "unit" -p no:randomly
    5 passed in 2.56s

Regression across the e-invoice adapter and the whole ledger application suite:

    uv run --no-sync pytest src/cadrumo/adapters/inbound/einvoice/tests src/cadrumo/application/ledger/tests -n0 -m "unit or integration" -p no:randomly
    939 passed, 15 warnings in 243.49s (0:04:03)

Lint, format and type checks clean under `ruff check`, `ruff format` and
`ty check`.

### Mutation proofs

Both installed from a plugin module **outside** the repository at plugin scope,
each asserting the replacement is not the original so a patch that never landed
cannot pass as a proof, and each printing on install. No tracked file was edited.

Blinding all three per-format readers:

    MUTATION INSTALLED: all three postal readers blinded
    4 failed, 1 passed in 3.34s

Every recovery case reddens. The single green is the no-address case, which
expects nothing and legitimately still gets it.

Defaulting an absent code to a mainland one — the forbidden default, applied
deliberately:

    MUTATION INSTALLED: absent codes default to the mainland
    1 failed, 4 passed in 3.18s

Exactly the safety-asymmetry case reddens, which is the point of running this
second mutation at all: that case passed *before* the behaviour existed, when
every field was absent, so without this proof it would be indistinguishable from
a vacuous assertion. The mutation shows it discriminates.

## Notes

**No Cross Industry Invoice is bundled anywhere in the corpus.** The only CII
artefact in the tree is a malformed fragment used to prove the parser refuses
one. The CII case therefore uses a specimen built from the EN16931 mapping rather
than a real document, and the case says so in its own docstring. It establishes
that the CII branch is reached and correctly scoped; it cannot establish that a
real-world CII invoice states its address the way the specimen does. It is
included rather than omitted because the alternative was a reader that exists and
is never exercised — the built-and-unreached shape this campaign has shipped
repeatedly. A real CII specimen is worth acquiring for the corpus.

The bundled UBL specimens state no address at all, so the element is injected into
a copy in `tmp_path`, anchored on each party's own wrapper rather than the shared
party tag — anchoring on the shared tag would have put both addresses in the
supplier and left the customer bare, and the case would still have passed on a
reader that only ever looked at one side. The corpus tree is never written to.

**The production half reached the tree under another author's commit.** A
sweeping whole-index commit took the parser and projection changes before they
could be committed here; the landed content is byte-identical to the final
version, verified by an empty diff afterwards. The test half was committed
deliberately ahead of the behaviour and was not swept, so the ordering rule held
even though the second commit was not the author's.

**The shared index was found poisoned a second time** while checking it before
staging: five files staged as pure deletions totalling over seven hundred removed
lines, the inverse of another lane's landed commit. It resolved on its own before
this Step's final commits. It is recorded because a poisoned index endangers only
a **bare** commit — an explicit pathspec cannot pick up foreign staged entries —
so the pathspec discipline, not luck, is what kept these commits clean through it.
