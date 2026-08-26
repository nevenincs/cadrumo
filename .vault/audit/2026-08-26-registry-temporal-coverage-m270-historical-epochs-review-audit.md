---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:7e7ab3531da530cd6b7242e8f8334611828dc5e45e1b4e0a53f9dc1424bf606f'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# `registry-temporal-coverage` audit: `Modelo 270 historical epochs independent review`

## Scope

Independent, read-only review of commits `1c0300eb2cc` and `25772c78eb` at
current HEAD for the Modelo 270 historical-epoch split. The review covered the
source corpus and catalogue entries, both revision trees, selectors, deadline
and application links, casillas, constructs, export layouts, locale moves, and
the focused parser, coverage, selector-mutation and registry-validation gates.
It also checked the governing temporal-coverage plan, its linked authority
record and research, and the open S51 execution record.

The BOE historical binary independently hashes to
`97dfc0a9640f2bdd32c97b89702427ba708c858fe173ab31a68d179f247c3b69`
at `867947` bytes. Its complete parser extraction gives the two 500-position
Tipo 1 and Tipo 2 records. The loaded epochs select `2013-2022` through 2022
and `2023-2024` through 2024, refuse 2025, use distinct Type 1 geometry at the
2023 boundary, and retain the same Type 2 geometry. The retired
`enrolled-modelo-270-layout` alias is absent while the legitimate procedure
source remains. No Modelo 270-specific selector, validator, or source-resolution
implementation was introduced.

Focused checks: the dedicated historical-epoch suite passed 7/7; direct
`RegistryValidator.validate_modelo` for Modelo 270 passed. The full authority
load remains blocked by independently changing Modelo 165 grade/parity work,
Modelo 200 revision/deadline collisions, and Modelo 309 continuity drift; no
Modelo 270 failure appeared in that output.

## Findings

### 2023-amendment-grounding | high | The controlling 2023 amendment is not enrolled as legal authority

`2023-2024/revision.toml` identifies Orden HFP/1286/2023 as the source of the
Type 1 period insertion and summary-slot movement, but neither the Modelo 270
legal catalogue nor any revision, casilla, construct, link, deadline, or layout
declares a legal reference for BOE-A-2023-24414. They instead cite only the
pre-amendment `orden-hap-2368-2013:art-1` and `:art-3`. The official amendment's
article 2, paragraphs eight and nine, creates the `PERIODO` field and moves the
Type 1 slots; its final provision sets first applicability for exercise 2023
and separately governs the two convention-backed operators. The AEAT design
binary proves the bytes, but cannot substitute for the missing legal authority
for the temporal/applicability claim. The present `0A` selector and annual
deadline may be correct for ordinary annual filers, but the registry does not
state or prove that limiting interpretation against the amendment's special
operator regime.

Remediation evidence (2026-08-26): BOE-A-2023-24414 was acquired through the
canonical published-document and HTML extraction tooling. Its Article 2 and
final-provision units are enrolled as `orden-hfp-1286-2023:art-2` and
`:df-unica`; the 2023--2024 revision binds both in applicability and legal
closure, while the Type 1 layout, its shifted fields, corresponding summary
casillas, export link, and construct bind the Article 2 change. The focused
mutation coverage proves the annual `0A` surface refuses the convention-only
monthly route and that every shifted Type 1 field carries the amendment ref.

### historical-layout-hash-prose | medium | Historical layout grounding comments name the current binary's digest

`2013-2022/export_layouts/0003-modelo-270-fichero-boe.toml` cites the correct
historical source id but says that source has digest
`d845cc47e3b60d01128d27dddcc3cffd2cf64bd6dfb24e0cd0d0467d66f95a92` and
`111633` bytes. Those are the 2023 AEAT binary's values. The registered
historical source and the actual BOE file are instead
`97dfc0a9640f2bdd32c97b89702427ba708c858fe173ab31a68d179f247c3b69` and
`867947` bytes. Runtime source references and hash tests remain correct, but
the human-facing evidence trace is self-contradictory.

Remediation evidence (2026-08-26): the historical layout comment now identifies
the BOE source and its independently pinned digest and byte count. Focused
coverage reads that comment and rejects both the current-design digest and byte
count, preventing a human evidence trace from drifting away from the source it
names.

## Recommendations

- For `2023-amendment-grounding`, enroll BOE-A-2023-24414 with precise legal
  anchors for the Type 1 change and applicability, propagate them through the
  2023--2024 revision surfaces, and add a non-tautological test covering the
  chosen handling of the convention-backed SELAE/ONCE exception. The follow-on
  decision is whether the ordinary `0A` Modelo 270 surface must explicitly
  refuse those operators or whether their convention route belongs outside this
  registry; do not infer monthly Modelo 270 support merely from the record
  field.
- For `historical-layout-hash-prose`, correct the historical layout comment to
  its BOE source's actual digest and byte count, then retain the existing
  independent hash and parser proof.

## Closure

Re-review of `255ac97952`: PASS. BOE-A-2023-24414 Article 2 and its final provision are independently present in the canonical HTML, enrolled as distinct legal authorities, and bound to the `2023-2024` applicability declaration. Article 2 is also bound to the inserted and shifted Type 1 fields, their corresponding casillas, the construct, and the export surface; the final provision remains present on the revision, construct, and layout authority. The annual `0A` route refuses the convention-only monthly route, and 2025 remains a visible refusal. The historical BOE hash comment now names its own source bytes; the 2013--2022 geometry/source, locale labels, and retired-alias absence remain sound. Focused parser, selector, mutation, coverage, validation, and lint checks pass. No unresolved Critical, High, or Medium finding remains.
