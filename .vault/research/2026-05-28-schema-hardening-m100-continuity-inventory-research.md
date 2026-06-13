---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-research]]'
---



# `schema-hardening` research: `m100-continuity-inventory`

Sampled Modelo 100 cross-revision casilla continuity candidates from the
committed registry after the continuity schema, loader, advisory inventory, and
strict opt-in validator landed. This artifact grounds the first data rollout
without treating repeated numeric casilla ids as proof of continuity.

## Method

Loaded the committed registry with `load_registry_tree`, selected modelo `100`,
and inspected the six revisions `2020` through `2025`. Every M100 revision is
currently in advisory continuity mode and declares zero
`casilla_continuidad_evolutions`.

For repeated casilla ids, compared the validator-owned drift fields: `label`,
`section`, `data_type`, `semantic_role`, and `legal_refs`.

Buckets below are evidence inventory samples, not final authoring decisions.
Any strict rollout must still author `continuidad_id` and evolution records with
legal/source grounding.

## Findings

M100 revision sizes:

- `2020`: 1531 casillas
- `2021`: 1693 casillas
- `2022`: 1852 casillas
- `2023`: 1929 casillas
- `2024`: 2064 casillas
- `2025`: 2236 casillas

Advisory drift summary for repeated ids is large: 75 revision-pair/field
summary rows. Representative pair `2020` to `2025` includes 724 label drifts,
1516 legal-reference drifts, 255 section drifts, 71 semantic-role drifts, and
21 data-type drifts.

### Continuous Candidates

Exact stable signature across repeated revisions is rare because legal
references and section paths frequently move. Six repeated ids were exact
stable-signature candidates in this pass:

- `0582`, present `2022` through `2025`: interest on prior regularisation,
  state part.
- `1038`, present `2023` through `2024`: other deductions.
- `1851`, present `2022` through `2024`: humanitarian aid to Ukraine.
- `1852`, present `2022` through `2024`: hosting displaced Ukrainian people.
- `1905`, present `2022` through `2024`: variable-rate mortgage cost
  compensation.
- `1945`, present `2023` through `2024`: Centenario del Hockey 1923-2023.

These are good first candidates for `unchanged` continuity only after checking
that their disappearance or continuation semantics are intentional.

### Evolved Candidates

1677 repeated ids drift only in `label` and/or `legal_refs` under the current
field comparison. Samples:

- `0001`, present `2020` through `2025`: label stable, legal references drift.
- `0043`, present `2020` through `2025`: rolling-year label text evolves and
  legal references drift.
- `0044`, present `2020` through `2025`: annual target year in the label
  evolves from 2018 to 2024, with legal-reference drift.
- `0062`, present `2020` through `2025`: label stable, legal references drift.
- `0063`, present `2020` through `2025`: property percentage label stable,
  legal references drift.

These are likely candidates for `legal_refs_evolved`, `label_evolved`, or
`label_and_legal_refs_evolved`, depending on source review.

### Repurposed Or Structural-Move Candidates

401 repeated ids drift in at least one of `section`, `data_type`, or
`semantic_role`. This bucket must not be treated as automatic repurposing:
many examples look like the 2025 form restructuring moved existing concepts
from `toma_datos_ampliada` into more specific sections. They still require
explicit decisions before template sharing.

Samples:

- `0003`, `2020` through `2025`: same work-income semantic role and money type,
  but 2025 moves section to `rendimientos_trabajo` and shortens label text.
- `0004`, `2020` through `2025`: work in-kind valuation, section moves in
  2025.
- `0008`, `2020` through `2025`: employer contributions to pension/social
  provision, section moves and label shortens in 2025.
- `0011`, `2020` through `2025`: work-income reductions, section moves and
  label shortens in 2025.
- `0224`, `2020` through `2025`: appears in data-type, section, and
  semantic-role drift summaries and needs direct source review before any
  continuity decision.

For this bucket, the safe rollout pattern is to author only a small audited
subset first and leave the rest advisory.

### Retired Candidates

19 repeated ids are absent from `2025` after appearing in earlier revisions:

- `0680`, `0681`, `0682`, `0686`: prior complementary/declaration
  rectification result fields, present `2020` through `2023`.
- `0687`, `0688`, `0696`, `0697`: rectification/compensation bank details,
  present only in `2020`.
- `0782`: Todos contra el cancer applied amount, present in `2020`, `2022`,
  `2023`, and `2024`.
- `0999`: generated amount pending application, present `2020` through `2024`.
- `1020`, `1038`, `1082`: other deductions with discontinuous revision
  presence.
- `1694`, `1851`, `1852`, `1905`, `1945`, `1949`: event, aid, or temporary
  measure fields absent from `2025`.

Retirement records should be authored only where the later form genuinely omits
the concept, not where the concept moved to another id.

## Next Data Slice

Do not enable strict continuity for all M100. The first safe rollout should
author a narrow metadata slice:

- one stable repeated id from the continuous bucket;
- one legal-reference-only evolved id;
- one label-and-legal-reference annual text evolution;
- one explicit structural-move candidate left advisory unless source review
  proves continuity;
- one retired candidate with clear disappearance evidence.

After that slice, strict validation should be enabled only for the covered
revision surfaces.
