---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:252aa6595acc1cd4d394877f9cf5f8597859532e08ebd7b1a44c3cc91a2c3d68'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---



# `facts-registry` audit: `S68 Article 95 retention review`

## Scope

Reviewed plan step `W03.P13.S68` against the governed-fact ADR, research,
consumer-migration reference, and current candidate diff. The scope was the
five exact BOE Article 95 redactions, source records, six authored rate facts,
adapter retirement, and focused tests; activity-selector and consumer work was
excluded.

## Findings

No critical, high, or medium findings. The captured source bytes and hashes
match their catalogue rows, each fact has exact non-overlapping windows and
citations, and none of the six identities remains in the adapter.

### article-95-publication-provenance | low | Source rows omit publication dates retained by their exact BOE captures

Each captured `<version>` wrapper includes `fecha_publicacion`, but the five
new source rows omit the optional `published_at` field. The hash, source URL,
amendment identity, retrieval date, and legal window still establish an
auditable evidence lane, but recording the already-retained publication date
would make the source catalogue self-contained for revision chronology.

### article-95-rate-regression-matrix | low | Direct value assertions cover only two facts and three of five redactions

The focused test asserts exact values only for the two professional-rate facts
at the first three starts. It exercises all six facts structurally, their
windows, citations, and evidence validation, but a wrong copied value in one
of the other four facts or in either later redaction would not fail a direct
value assertion.

## Recommendations

Populate `published_at` from each retained BOE wrapper when convenient. Expand
the Article 95 table-driven test to assert every fact value at every retained
redaction start before the broader consumer migration relies on them.
