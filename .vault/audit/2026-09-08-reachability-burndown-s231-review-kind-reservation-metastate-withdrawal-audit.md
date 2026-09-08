---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:6ccdec7ed787205f17ce8146cf5b32d39ce189c85875c9b5628932b98b0f3349'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S231]]"
  - "[[2026-09-04-reachability-burndown-adr]]"
  - "[[2026-09-04-reachability-burndown-reference]]"
---

## Scope

Reviewed W05.P12.S231 against the accepted reachability authority, the exact five-file implementation/test diff, the live review selector, cadence addition, and Step Record. The review assessed removal of the reserved-token development vocabulary while preserving generic fail-closed selection and representative error rendering.

## Findings

No findings.

The deleted `_RESERVED_KINDS` map and `reserved_kind_reason` accessor had no live parser consumer. Their only behavioral surface was the dedicated `ReviewKindReservedError` constructor and self-only tests; the production selector never admitted or dispatched the two named tokens. They therefore encoded prospective/non-emitted review kinds as product metastate, contrary to the accepted reachability decision.

The material selector behavior remains. `_resolve_internal_kinds` accepts only the live source-kind mapping and rejects every unknown token through the generic `ReviewError`, with a privacy-safe message that lists accepted kinds without echoing the raw operator value. Existing operator tests cover the accepted mapping, unknown-token refusal, and source-kind filtering. The broader typed filter parser continues to fail closed on malformed, unknown, duplicate, and invalid values while redacting sensitive values.

Deleting the dedicated error registry row does not weaken rendering: no live path raises that class. The CLI registry contract now uses live `FilterParseError` as its representative refused application error, retaining category and rendering coverage rather than preserving a dead exception solely for the test.

No reserved-name replacement, compatibility facade, classification list, or source dependency on dev/tests was added. The cadence addition accurately generalises the owning rule.

The Step Record lists every S231 path, Ruff, both marker lanes, and the exact detector. Independent rerun confirms Ruff and the selected 53-test unit lane pass; the record reports the complementary 30 non-unit tests passing. The exact detector's remaining-backlog failure and 303 to 302 symbol movement, with module and orphan counts unchanged, are consistent with deleting the one reported accessor.

## Recommendations

Approve W05.P12.S231 and close it through the plan workflow.
