---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:97893f4c54421ea609fb43d2c1e27591ef41c247729fe5420f65256943ccde7a'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-08-07-m303-carry-reconciliation-S13]]"
---

# `m303-carry-reconciliation` audit: `M303 S13 filed-population measurement blocker`

## Scope

Audit whether S13 has a real Modelo 303 population: a persisted filed
declaration with a declaration-PDF artefact but no submitted-file artefact.
The step permits render recovery only after that population is measured; test
fixtures and static branch shapes are insufficient.

## Findings

### encrypted-live-corpus | high | The persisted population cannot be enumerated without an unlocked profile

The production path persists a `FiledDeclaracionObservation` through the
active-profile encrypted store. Its `list_observations()` reader requires the
same active bucket session as real capture. The read-only `aeat config profile
status --json` probe refused with `reason: absent`; no active profile was
unlocked. The storage inventory exposes only category-level state, not
decrypted artefact kinds. Therefore no count, including zero, is established.

### conditional-capture-shape | medium | Repository invariants do not prove submitted-file universality

The Sede capture records a submitted-file artefact only when a live declaration
row offers the archive link, and records a declaration-PDF artefact independently
when its copy link is available. The observation model requires one or more
artefacts but does not require a submitted file. This proves the target shape is
representable, not that an M303 record in the operator's live corpus has it.

### fixture-boundary | low | Exporter and bundled render specimens cannot answer the population question

The plan and prior S13/S15 history distinguish registry/exporter structural
evidence from AEAT-served filed evidence. Existing fixtures can validate a
grounded recovery parser if the population is measured, but cannot prove an
operator's persisted filing population is empty or non-empty.

## Recommendations

- Leave S13 open. Do not add a declaracion-render parser and do not mark the
  population empty.
- Under separately authorized active-profile access, enumerate the real
  `FiledDeclaracionObservation` records and count Modelo 303 rows partitioned
  by `submitted_file` and `declaration_pdf` artefact kinds. Retain only
  aggregate counts and the measurement timestamp in a follow-up record.
- If and only if the missing-submitted-file plus declaration-PDF count is
  non-zero, ground recovery on which AEAT render slot contains a value, never
  on the pre-printed C, I, or D letters, then obtain formal review before
  implementation.
