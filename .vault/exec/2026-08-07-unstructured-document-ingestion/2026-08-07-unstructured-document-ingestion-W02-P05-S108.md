---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8dc8d162d764f724930e166e79a1b69bcd373f05e617096a1ab19574caaabe94'
step_id: 'S108'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## What changed

`TransactionKind` documented its three Union-scheme members as resting on LIVA
art. 163 unvicies for their goods-or-services character. That article admits an
operation to the Esquema Unión; its own scope paragraph reaches "presten
servicios" and "ventas a distancia intracomunitarias de bienes" alike, so citing
it establishes neither limb.

The prose now separates admission to the scheme from placement, and names the
article that actually locates each member: art. 68 for the two goods members,
art. 69 for the services one. A short paragraph states the distinction explicitly
rather than leaving it to be inferred from the per-member lines.

## Why a docstring was worth a Step

Two readers derived the wrong nature from this prose before going to the statute,
and one of them nearly shipped a grounding row establishing GOODS from it. The
data written in the sibling Steps routes around the error; the description does
not, and it sits where the next reader will trust it. A docstring naming an
article is the source a careful author checks *instead of* the statute, which is
what makes an inaccurate one costly rather than untidy.

## The gate, and why it is narrow

The corrected claim is covered by the same mechanism that pins the data: one case
asserts against the bundled consolidated text that art. 163 unvicies really does
reach both limbs, so the reason survives independently of anyone restating it;
another asserts the enum prose never attributes placement to that article.

The prose check is deliberately narrow. It does not police wording. It matches
only the specific attribution that misled -- a sentence saying the operation is
*located* by art. 163 unvicies -- and it explicitly permits naming the article
beside a placement article, which is what the corrected text does. The first
version was blunter, keyed on a line containing both the article and the word
"located", and it failed on correct prose because the line wrap put the
qualifying word on the previous line. A gate that reds on the right answer is
worse than none.

## Verification

Gate: 14 passed, including the two new cases. Full `domain/iva`: 407 passed, 0
failed at the time of this change. Sequential, cache provider disabled, marker
`unit`. `ruff` and `ty` clean. Landed at `cfb4574dea`, two files, 67 insertions
and 3 deletions.

Mutation, from outside the repository at module scope: `TransactionKind.__doc__`
restored to the misleading form, 2,678 characters down to 609. Exactly one case
reddened -- the prose attribution check -- and the plugin's own
`pytest_collection_finish` re-read the attribute the gate reads to confirm the
mutation had landed on that class rather than on a copy.
