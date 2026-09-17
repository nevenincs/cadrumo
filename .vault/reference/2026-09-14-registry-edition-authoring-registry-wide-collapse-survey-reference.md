---
tags:
  - '#reference'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:8b83789852baeee01480534e43748a84e8d81824b3da35ee963539da7d1dfceb'
related: []
---
# `registry-edition-authoring` reference: `registry-wide collapse survey`

## Summary

Read-only canonical assessment of all 58 authored modelos, read-only migration plans for 200, 220, 296, 303, 390, 111 and 115, and a non-applying staged migration of Modelo 200. No live source data or published authority was changed. The all-modelo source fingerprints and sampled tooling fingerprints remained stable during the sweep; all individual assessments reported stable inputs.

The assessor found 77573 redundant authored values in 11890 findings across 36 modelos. All 58 assessments completed without an exception or blocked shape. Sixteen modelos have only one authored revision. Modelo 100 has zero redundant overrides, zero duplication findings and zero blocked entries after live replacement. Zero findings for explicit independent roots do not prove absence of shareable payload across those roots.

These are opportunities measured by the current checker, not projected byte savings or acceptance of an unbuilt candidate. Field counts and finding counts are distinct. A finding can contain several repeated fields. Broad authority, legal continuity and export acceptance were not established by this source-storage survey.

### Measured inventory

| Modelo | Authored revisions | Source bytes | Redundant values | Duplication findings |
| --- | ---: | ---: | ---: | ---: |
| 714 | 5 | 9124075 | 34771 | 3982 |
| 200 | 2 | 19507425 | 18942 | 3842 |
| 303 | 6 | 6166322 | 7626 | 1273 |
| 322 | 4 | 2052498 | 4205 | 705 |
| 036 | 2 | 1155849 | 2093 | 531 |
| 131 | 4 | 672161 | 1485 | 214 |
| 190 | 4 | 519088 | 1241 | 143 |
| 490 | 4 | 1907750 | 874 | 193 |
| 390 | 5 | 6365969 | 778 | 115 |
| 202 | 3 | 711396 | 765 | 140 |
| 353 | 2 | 680955 | 727 | 96 |
| 345 | 4 | 148935 | 690 | 104 |
| 193 | 4 | 325175 | 628 | 63 |
| 222 | 3 | 390108 | 408 | 75 |
| 232 | 2 | 1067686 | 351 | 52 |
| 189 | 3 | 87043 | 346 | 56 |
| 210 | 4 | 1438973 | 332 | 58 |
| 347 | 2 | 455759 | 294 | 50 |
| 180 | 2 | 219089 | 251 | 44 |
| 280 | 2 | 102040 | 181 | 29 |
| 123 | 2 | 119917 | 100 | 30 |
| 184 | 6 | 899976 | 80 | 15 |
| 308 | 4 | 99120 | 61 | 15 |
| 151 | 2 | 3379352 | 53 | 12 |
| 763 | 5 | 35079 | 46 | 10 |
| 165 | 4 | 113224 | 38 | 4 |
| 136 | 2 | 79730 | 33 | 7 |
| 270 | 2 | 117293 | 31 | 7 |
| 194 | 3 | 16607 | 30 | 4 |
| 721 | 2 | 38843 | 28 | 5 |
| 185 | 2 | 135459 | 23 | 5 |
| 188 | 2 | 22764 | 22 | 3 |
| 038 | 2 | 20304 | 12 | 2 |
| 341 | 2 | 53751 | 12 | 3 |
| 576 | 2 | 58011 | 10 | 2 |
| 182 | 2 | 30039 | 6 | 1 |
| 111 | 1 | 198962 | 0 | 0 |
| 115 | 1 | 60238 | 0 | 0 |
| 117 | 1 | 34986 | 0 | 0 |
| 122 | 1 | 64340 | 0 | 0 |
| 126 | 1 | 39009 | 0 | 0 |
| 128 | 1 | 34001 | 0 | 0 |
| 130 | 1 | 92114 | 0 | 0 |
| 145 | 1 | 62961 | 0 | 0 |
| 156 | 1 | 57789 | 0 | 0 |
| 181 | 1 | 74363 | 0 | 0 |
| 187 | 1 | 9676 | 0 | 0 |
| 216 | 1 | 88672 | 0 | 0 |
| 220 | 2 | 1179468 | 0 | 0 |
| 296 | 2 | 460737 | 0 | 0 |
| 309 | 4 | 345388 | 0 | 0 |
| 349 | 1 | 157612 | 0 | 0 |
| 360 | 1 | 369942 | 0 | 0 |
| 369 | 3 | 1074899 | 0 | 0 |
| 604 | 2 | 237412 | 0 | 0 |
| 720 | 1 | 54090 | 0 | 0 |
| 840 | 1 | 70329 | 0 | 0 |
| 100 | 6 | 7935344 | 0 | 0 |

### Conversion applicability

The reusable schema/loader and assessor support multiple modelos, but the complete family converter remains specialized. `dev/registry/modelo_100_family_delta.py:190` enumerates 2021 through 2025, and `migrate_modelo_100_field_deltas` in `dev/registry/edition_delta_migration.py` fixes the modelo to 100. Generalization must use actual authored revision identity, temporal/applicability branches and baseline relationships, not rename the function and retain a yearly loop.

Modelo 714 is the largest measured repeated-value target: 34771 redundant values, including 3842 binding-related findings. It already has predecessor declarations but still repeats substantial family payload. Modelo 200 follows with 18942 redundant values and 3842 findings: 3202 casilla findings and 578 projection-endpoint findings dominate. Modelos 303 and 322 contribute 7626 and 4205 redundant values respectively. These four account for 65544 of 77573 detected redundant values (84.49 percent).

The generic Modelo 200 command was actually staged with no apply flag. It kept 3345 and 3463 casillas fully authored, inherited zero members, reduced 19507425 bytes to 19507359 bytes (66 bytes), and left all 3842 duplication findings and 18942 redundant values. Source equivalence passed; minimality failed; complete was false; application was staged only; process exit was 1. Its successor remains a declared root because the manifest persists the earlier predecessor-row-without-lineage refusal. A separate export-readiness finding concerns Modelo 202 construct source references; it is not the cause of the missing storage conversion. Do not turn that readiness finding into the migration roadmap.

The read-only plans for 303 and 390 report existing predecessor chains as lift-only work. That does not perform the comprehensive family/field collapse used for Modelo 100. The remaining positive inventory includes both large unconverted families and smaller cleanup opportunities; existing predecessor declarations alone do not certify minimality.

### Explicit-root blind spot

The assessor reports zero for 220, 296, 309 and 604 while their explicit root declarations exclude earlier editions from its candidate comparison. A separate raw same-ID diagnostic found 1184 equal field values in 220, 419 in 296, 1292 across three 309 boundaries, and 225 in 604. These counts do not expand defaults or prove legal continuity/applicability, and are not added to the canonical total. They demonstrate why zero under a root policy is not a complete storage-sharing assessment. Cross-root reuse needs explicit baseline/override proof, not deletion of scope or identity distinctions. Modelo 369's parallel schemes must not be treated as a simple chronological chain.

### Next engineering work

Generalize the proven all-family converter and orchestration across actual modelo/revision identifiers; separate storage baseline eligibility from persisted migration-failure roots; extend independent assessment to report excluded cross-root opportunities distinctly; then stage 200 and 714 before the next large targets, 303 and 322. Prove whole-model typed equivalence, scoped provenance, temporal behavior, minimality and idempotence for each candidate. The user authorized a dry-run survey only, so no further data application was performed.

### Reproducible evidence

Scratch runner: `C:/Users/hello/AppData/Local/Temp/registry_collapse_survey.py`. Complete per-modelo assessments and summary: `C:/Users/hello/AppData/Local/Temp/registry-collapse-survey-20260914T203616/`. The runner exited 0. The supplemental raw root comparison is `registry_root_overlap_probe.py` in the same temporary parent, with results in `root-overlap.json` under the survey directory. Its final corrected run handles immutable mapping/tuple containers; an initial diagnostic incorrectly treated only dict/list containers as declarations and was superseded.

Staged command: `uv run --no-sync python -m dev.registry.edition_delta_migration --registry-root src/cadrumo/_data/registry/aeat --modelo 200 --work-dir C:/Users/hello/AppData/Local/Temp/m200-collapse-survey-dry-run-20260914T2039`. It exited 1 with complete=false. The report is `.logs/audit-runs/2026-09-14/20260914T203928.099357Z-report-registry-edition-migration-43424-0c779863/report.md`; its staged/reference trees remain in the named temporary work directory. No exact storage-savings estimate is claimed beyond this actual staged run.
