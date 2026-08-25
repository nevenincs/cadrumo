---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5f3e0d16f0aa58cb2b149c42b4feadefecdf0342b0af4b7aad73c2b6089c12fc'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S115 structural helper selector review`

## Scope

Independent review of `8c45b90ed3`: the canonical selector schema and
discovery gate, the source-connectivity census, reviewed S112/S113 helper
handoff, inventory evidence locators, and generated feature-index provenance.

## Findings

### digest-primary-count-secondary | pass | count adds a distinct ratchet without replacing identity proof

Selector assignment computes and compares the SHA-256 digest before evaluating
`expected_capability_count`.  A selector still requires its digest in the
schema, while explicit rows reject both selector expectations.  The new count
therefore detects cardinality drift as a secondary invariant; it cannot accept
a different helper set with the same count or bypass the canonical digest.

### reviewed-helper-set | pass | exact two-helper maintenance creates no census rows

Live discovery produces the reviewed 267-member helper remainder at
`sha256:3b827ccf9f7fd2c3b30a37f042e9ede32be236d0b4600c8e3a09dcebbfeeeb6a`,
up from the recorded 265-member digest.  The delta is exactly
`revision_selection_coordinates` and `portal_integrity_error`.  Both remain
inside the existing `not_applicable` selector; the census gains no capability
IDs, candidate rows, destinations, owners, or lifecycle claims.

### inventory-locators | pass | all corrected locators identify live authority

The inventory evidence locators now name the live authoritative-closing
function at 1161 and projection function at 1367.  The service anchor remains
at 413.  The focused locator test retains mutation rejection, so stale or
missing evidence cannot silently validate.

### mixed-index-provenance | low | generated index correctly reflects concurrent feature documents

The S115 commit's generated index includes concurrently completed S114 and
S227 documents as well as S115.  This is derived feature-graph provenance, not
an S115 authority claim; the implementation-owned census, selector, schema,
and test diffs remain narrowly scoped.

## Recommendations

PASS.  Retain digest-first selector validation and the secondary count only as
an additional drift detector.  Keep both helper identities in the reviewed
`not_applicable` selector without promoting them to source candidates.
