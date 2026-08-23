---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:326b73c07a1d00697fd7538257f2ea338d44488f9359b3ec0d6a1bf984bd7e64'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `s42 inventory source ownership review`

## Scope

Independent review of S42 inventory caller-override ownership, single-home policy placement, selector-derived collision identity, equal and partial substitutions, alias refusal, undeclared manual behavior, and downstream binding boundaries.

## Findings

### s42-inventory-source-ownership-review | high | resolved planned target was not the ownership authority

`_calculate_input.py` parses values but does not own source precedence. The approved implementation uses the canonical `CALLER_OVERRIDE_PRECEDENCE_LADDER`; the calculation policy derives the lock set and the existing guard derives exact binding and casilla collisions from the revision. No second policy or hard-coded destination map was introduced.

### s42-inventory-source-ownership-review | medium | resolved lock-policy prose omitted promoted source families

The ladder and conformance documentation now describe deterministic inventory and annual-summary ownership alongside ledger and invoice families. The frozen conformance set matches the live declaration.

### s42-inventory-source-ownership-review | pass | collision refusal is complete and deterministic

Tests prove equal and different binding values refuse, one-, two-, and three-casilla substitutions refuse, semantic aliases fail before ownership matching, and replays retain typed value-free errors. Identical caller values do not receive a carve-out.

### s42-inventory-source-ownership-review | pass | undeclared manual behavior and downstream scope remain intact

A revision without inventory bindings keeps its manual casilla channel, proving the lock does not ban the numeric identifiers globally. S42 adds no inventory binding data, census connection claim, runtime repository composition, or CLI policy.

### s42-inventory-source-ownership-review | pass | final ownership policy is coherent

Independent review reported zero critical, high, medium, or low findings. Twenty-one focused tests, Ruff, the focused type checker, and diff hygiene were clean. Exploratory failures in stale IVA-selector and unrelated M349 tests were outside S42 ownership.

## Recommendations

Proceed to S43 and later binding work using the canonical inventory selector. Do not add a separate override map when real registry bindings replace the synthetic test revisions.
