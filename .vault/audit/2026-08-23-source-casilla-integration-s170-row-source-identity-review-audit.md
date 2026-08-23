---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:5a10d74e64f7f8fa5f325b89e60c5769a53941beeaf815e9a8612ba71359d929'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `s170 row source identity review`

## Scope

Independent review of the generic row-source identity carrier, migration boundary for existing M720 rows, coordinate validation, merge collision behavior, deterministic ordering, and raw-identity confidentiality.

## Findings

### s170-row-source-identity-review | low | resolved validator prose overstated exact bijection

The generic migration contract intentionally permits row values without identities while refusing every orphan identity. The validator name and docstring initially described exact bijection and missing-identity refusal. They now state the implemented subset/no-orphan rule and assign complete source-specific cohort validation to S176.

### s170-row-source-identity-review | pass | typed identity and confidentiality contracts are coherent

The identity member is strict and frozen, uses canonical source and digest types, rejects noncanonical opaque identities and non-positive indexes, sorts deterministically, and excludes raw identities from ordinary representations, generic dumps, JSON, validation errors, and collision diagnostics.

### s170-row-source-identity-review | pass | migration and collision semantics preserve ownership

Unidentified M720 rows coexist with identity-bearing rows without a compatibility alias. Identity keys must be a subset of value keys, and both exclusive and precedence merges refuse every second claim to an identity-bearing coordinate, including equal values and changed identities or fingerprints.

### s170-row-source-identity-review | pass | final verification is clear

Independent review reported zero critical, high, medium, or low findings after remediation. Forty-six focused source-mesh tests passed, and Ruff and the focused type checker were clean.

## Recommendations

Proceed to S171 for explicit encrypted serialization of the retained identity map. Keep generic dumps redacted, and make S176 enforce complete inventory three-operation cohort bijection rather than strengthening the generic migration boundary prematurely.
