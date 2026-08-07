---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bb32a15db85fa64dc53f7eab334b7c165a07e53a01842f2ae62ce33c0d1b5f70'
step_id: 'S107'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## The blocker I reported was wrong, and the correction is the first finding

I told the coordinator no worked example was reachable, on the grounds that the
bundled IVA manual is a `source.pdf` plus a stub `structure/` extraction. The
stub part was true -- one chapter, one section, 846 bytes out of a 6.3 MB manual.
The conclusion drawn from it was not.

The PDF carries a real text layer: 350 pages, 823,518 characters, 78 pages
containing a worked example, 18 of those touching an intra-community operation.
I had checked one representation of the corpus and reported the thing itself as
absent, which is precisely the error the campaign has now made several times in
both directions. Searching the corpus rather than the filenames is what found it.

## The oracle

Manual práctico IVA 2025, page 38, in the section on *lugar de realización de las
entregas de bienes*. A Spanish company sells goods to a French company,
transport beginning in the Península and delivery in France. AEAT states the
outcome and its reasoning: the supply is located in the TAI because the transport
began there, with the parenthetical that an exemption may apply because the goods
are destined for another Member State.

That is a two-step -- located by art. 68, relieved by art. 25 -- and it is exactly
the pair the S98 grounding row for `R10_intra_community_supply` encodes, in that
order, with art. 25 as the establishing provision. The worked example was not
consulted when that row was written, so its agreement is independent
confirmation rather than a restatement.

## Why the expected value is a category and not a figure

Every existing manual oracle is a Modelo 100 payload keyed by casilla id, because
what those check is arithmetic. A place-of-supply rule does not produce a number;
it produces a localisation and the treatment that follows. The oracle is
categorical for that reason.

Forcing it into the numeric shape would have meant inventing amounts the manual
does not state, which is the fabrication the grounding rules exist to prevent. The
file is named without the `modelo-` prefix because the casilla-oracle loader globs
`modelo-*.json`, so a payload of a different shape is not picked up by a reader
expecting the other one.

## Why this is not tautological

The expected category comes from AEAT's own reasoning in the example, not from
running the classifier and recording what it said. The engine is fed the operation
the manual describes and must arrive at the same treatment independently.

The quoted Spanish is a verbatim substring extracted programmatically from the
bundled PDF rather than retyped, because an author-attested quotation is not a
quotation. A case asserts the bundled file's sha256 still equals the digest the
oracle names, so the provenance stamp attaches to the artefact the expectation
actually came from -- the failure mode being an AEAT-branded name sitting on text
nobody can re-derive.

## Verification

Oracle gate: 3 passed. The full `domain/iva` suite ran 399 passed and 11 failed;
every failure is `modelo 303 revision 2023-y-siguientes` registry validation from
another lane's in-flight work, with zero references to `manual_oracles` in the
log. Sequential, cache provider disabled, marker `unit`. `ruff` and `ty` clean.
Landed at `9a0290385d`, two files, 171 insertions, zero deletions.

Mutation, from outside the repository at plugin module scope with the
gate-binding assertion: `classify_iva` forced to return `DOMESTIC_GENERAL` for
every input returned 1 failed and 2 passed. The parity case reddened. The
article-pair case stayed green legitimately and is recorded as such -- the
mutation altered the category and not the matched rule id, which is the axis that
case asserts on, so its silence is correct rather than a hole.
