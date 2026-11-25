---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-11-16'
modified: '2026-11-16'
body_schema: 'body-v2'
body_hash: 'sha256:4d4d49422bc2ad140b1a15ba2b1c457c760acb5bc0629c0390d423f8975a06ad'
related:
  - "[[2026-11-14-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `m840 plan close review`

## Scope

Plan-close review of the Modelo 840 source-casilla plan, all seven Steps across P01 to P03: the typed IAE profile facts and their operator entry, the export generator's repeat semantics for the anexo Relacion de locales, the regenerated Modelo 840 edition, the producers over stored facts only, and the per-year export round trip. The review traced the workflow from the profile facts through the producers and the export builder to the parsed round trip, against the plan and its governing ADRs, and ran the Modelo 840 export, producer, anexo and resolution tests (163 passed) and the P01 profile tests (61 passed) on 2026-11-16.

## Findings

### m840 plan close review | medium | P01 Steps were unchecked and unlogged although their work had landed

`P01.S01` to `P01.S03` were open in the plan and had no ledger rows, while commit `79cf6612c9` carries all three: the IAE facts in `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`, the typed records in `src/cadrumo/domain/contribuyente/iae_local_facts.py` and `src/cadrumo/domain/contribuyente/iae_local_record.py` with their schema migration, and operator entry through `src/cadrumo/application/user_profile/iae_records.py` with wording in the four locales. Resolved at plan close: its tests pass (custody round trip, schema migration, record and row admission, 61 passed), the three Steps are closed through the plan verb and their rows logged with that verification.

### m840 plan close review | low | An unrelated desktop test is logged under S06

The ledger row `S06 M native/desktop/tests/ux/window-ux-audit.test.mjs` lies outside the plan's filing scope and is unrelated to Modelo 840. It was a fix carried in the same change; it is noted here as a scope exception rather than plan work.

### m840 plan close review | low | Producers read stored facts only and keep typed refusals

`src/cadrumo/application/filing/export_producer_m840.py:116` reads only the typed Modelo 840 profile facts; an absent fact resolves to no value, never a default or zero, and an inadmissible profile type yields no value for every key (`export_producer_m840.py:141`), so the layout's required flag decides legality. The surface classes derive from the Regla 14 surface vocabulary, keeping total, rectified and computable surfaces distinct. The round trip enumerates years from the registry envelope (`test_m840_export_round_trip.py:83`); no year literals, suppressions, skips or mocks of the behaviour under test were found. No defect.

## Recommendations

None blocking: no critical or high finding, so the plan closes. Delta-minimality and edition lanes for the 840 edition were not rerun here; they belong to the wide registry sweep owned by QUALITY and rest on the ledger's recorded target-current pass.
