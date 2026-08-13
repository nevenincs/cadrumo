---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:30fc06fc6306c22ad26b810b1ed8bb04bb01f721ec04a43c0551250eee5387f5'
step_id: 'S31'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# adjudicate `bucket_id` in `adapters/persistence/profile/` — zero model fields, row's premise does not survive contact

## Scope

- `src/cadrumo/adapters/persistence/profile/`

## Description

- Re-derived the denominator with an AST probe over a fresh `git archive
  HEAD` extraction of `adapters/persistence/profile/`, pydantic
  model-field-only, `tests/` excluded, before touching anything — per this
  campaign's standing discipline and the explicit instruction to decline
  rather than force a row whose premise does not survive contact.
- Result: ZERO `bucket_id` pydantic model fields anywhere in this package.
  Confirmed two ways: the AST probe found no `bucket_id` AnnAssign on any
  class, and a full class-level scan found only TWO pydantic `BaseModel`
  subclasses in the whole package (`_TransactionIndex`,
  `_PersistedTransactionTimestampWitness` in `transactions.py`), neither
  declaring `bucket_id`. A raw grep of every `bucket_id` occurrence in the
  package confirms every one is a repository `__init__` or function
  PARAMETER (`_secure_objects_for_bucket(bucket_id: str)`,
  `ModeloDraftRepository.__init__(self, *, bucket_id: str | None = None,
  ...)`, and the same shape across every sibling repository) — the
  package is a runtime-configured adapter layer, not a persisted-model
  layer, so it has no `bucket_id` FIELD population to retype at all.
- This is the exact census defect the reference document already named
  for this row, now measured rather than merely suspected: its `bucket_id`
  cell reads "24 [sites]... far wider than the census count suggests many
  sites are function parameters, not model fields; the plan's `W04.P06.S31`
  scope is model-field-only, matching the census's own methodology." The
  24 (and the document's separately-measured 233 tree-wide, itself a
  count of ALL fields including already-typed ones, not a bare-only
  count) were never claims about THIS package specifically — re-deriving
  per-package rather than trusting either aggregate figure is what
  surfaced the zero.
- Measured the real population's actual location instead of stopping at
  "not here": a tree-wide AST probe (same methodology, `src/cadrumo/`
  whole tree, model-field-only, bare-only) finds 81 bare `bucket_id`
  model fields, distributed `entrypoints` 55, `application` 20, `llm` 2,
  `core` 1, `domain` 1, `adapters` 2 (elsewhere in `adapters/`, not
  `persistence/profile/`). No other row in this plan names `bucket_id` —
  this population has no home anywhere in the plan as currently rowed.

## Outcome

ADJUDICATED CLOSED, no code changed. The row's own gate ("retype every
classified `bucket_id` pydantic model field... across the
persistence-adapter package") is met vacuously and correctly: there is
nothing to retype in the scoped package, confirmed by measurement rather
than assumed from the row's silence. Forcing a retype here would have
meant inventing work the package does not contain.

The real 81-site population is NOT executed by this row — reported as a
finding rather than autonomously carved into a new Step, because it is
roughly 8x the size of this Wave's largest prior Step (`W04.P06.S30`'s 11
sites) and its dominant share (55 of 81) sits in `entrypoints/`, the
CLI/MCP wire-facing layer `W08.P13` already has standing concern over
(golden-schema pinning for identifier fields this plan retypes) — a
retype there plausibly changes JSON-schema-conformance and MCP
`output_schema` shape, which is a different risk profile than an
application-layer model field and deserves its own scoping decision, not
a forced fit under this row's narrow gate.

## Notes

No code touched, so no test suite was run against a change. The
measurement commands themselves were re-run twice with identical results.
Reported to the team lead alongside this record rather than left implicit
in a closed checkbox — an adjudicated-empty row and a row that quietly
absorbed a wrong-scope 81-site population would both read as "done" from
the checkbox alone, and only one of them is.
