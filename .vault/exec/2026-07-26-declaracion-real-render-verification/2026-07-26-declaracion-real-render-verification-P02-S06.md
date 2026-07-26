---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S06'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Audit the coverage floors across all 29 profiles, route R3 vacuous zero floors and route R4 over-strict unit floors, reporting which refuse a real filing over one blank optional box

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`
- `.vault/audit`

## Description

- Parsed every registry `revision.toml` and `extraction_profiles/*.toml` under
  `src/cadrumo/_data/registry/aeat/modelos` with `tomllib`, filtered to
  `surface = "declaracion_pdf"`, and read `min_coverage` and
  `failure_semantics` for all 29 profiles.
- Swept for the R3 shape (`min_coverage = 0` paired with
  `failure_semantics = "fail_hard"`) and confirmed the exact set.
- Swept for the R4 shape (`min_coverage = 1` / `1.0` with `fail_hard`) and
  confirmed the exact set.
- Read the `required` boolean on every target casilla, per profile, from
  each revision fragmented `casillas/` subdirectory, to rank R4 exposure by
  registry-asserted evidence rather than raw target count alone.
- Where `required` was absent from every target on a profile, read the
  target casilla labels directly to reach a qualitative exposure judgement,
  and recorded that judgement as a separate, weaker tier from the
  registry-asserted ones.

## Outcome

R3: confirmed exactly three profiles carry `min_coverage = 0` /
`fail_hard` -- `111`, `130`, `390` -- matching the dispatch brief known set.
The governing ADR `declaracion-real-render-verification` (D2) now grounds two
of the three on evidence: `111` keeps its zero floor with four specimens and
a worst case of 1 of 29 targets absent, `390` keeps its zero floor for the
opposite reason of having exactly one specimen (D2: "where only one specimen
exists, no floor is set"). `130` carries zero specimens of any kind (see
`P02.S09`), so its vacuous floor is not yet grounded the way its two
siblings now are -- it remains an open D3 evidence gap rather than a settled
case, and the finding record says so explicitly.

R4: confirmed exactly 23 profiles carry `min_coverage = 1` / `1.0` /
`fail_hard`, matching the dispatch brief count. Ranked by the registry own
`required` field where declared (131 x3, 123 x2, 115 at the sharpest
exposure -- every target self-declared optional; 202 and 232 x2 partially
optional), and by qualitative label reading where the field is entirely
absent (the five `100` revisions, 21 targets each, with 8 belonging to a
conditional actividades-economicas sub-chain; the nine identifying/resumen-
total profiles at lowest exposure). The document keeps the registry-asserted
tiers and the qualitative M100 judgement in separate, explicitly labelled
groups rather than blending them, since they are different strengths of
evidence.

Findings and full detail: see the specimen-less static route audit document
for this feature, sections `r3-vacuous-zero-floor-confirmed-exactly-three-
profiles` and `r4-over-strict-unit-floor-spans-23-profiles`.

## Notes

Exec-record creation for this feature was initially blocked (the CLI's
ADR-existence gate did not resolve an ADR linked only via the plan
`related:` frontmatter); the closing rationale was recorded in the audit
document Scope section as a fallback. The coordinator authored the
governing ADR and the block cleared; this record replaces that fallback
note for `P02.S06`.
