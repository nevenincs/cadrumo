---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:03c43af0d434ed59f9703bd20046079e38e1fb669acf6f09bc0d1e6152ecbef8'
step_id: 'S18'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace registry-suite-red-at-head with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-08-13-registry-suite-red-at-head-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Sweep every export field declaring padding left_zero across all modelos and both directory shapes, export_layouts and export, since Modelo 349 uses the latter. 127 total fields, 12 files across Modelo 131, 145, 180 and 349. Classification is structural, not per-field judgement - integer, decimal and money fields are always safe because Decimal of int of digits is indifferent to leading zeros, so the parse-side lstrip is inert once the value is reinterpreted numerically - 108 of 127. Only data_type text fields return the stripped string directly with no numeric reinterpretation, and 19 of those are genuine fixed-width identifiers whose value space includes leading zeros by construction rather than zero-fillable quantities - NIF, dos digitos numericos provincia codes 01-52, INE municipio codes and Spanish codigo postal codes, all province-prefixed. Confirmed the class is live, not latent - src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py parses a Sede-captured filed declaration's fixed-width bytes back into persisted ObservedCasillaValue and ObservedHeaderFact records for every casilla-kind and header-kind field, taking the post-unpad string unchanged with no downstream re-validation, so a previously-filed Modelo 180 or 349 declaration carrying a low-numbered NIF or a province, postal or municipio code in 01-09 gets silently shortened on capture and that wrong value then carries forward into previous-filing bindings for later years. Fixed the 19 by changing padding from left_zero right to none none, which is what these fields structurally are - fixed-width identifiers that always exactly fill their slot, never actually padded by left_zero on render, only ever damaged by its unpad on parse. Did not touch the codec, only the nineteen field declarations, across two Modelo 180 revisions times eight ids and one Modelo 349 revision times three ids. Proved byte-for-byte render identity for every present value across all nineteen fields by direct rendering under both declarations and diffing, zero mismatches across fifty seven sampled values including low-numbered NIFs and provinces 01, 09, 28 and 52. The absent-value behaviour does move, and this is the one place render output changes - today an absent required-in-practice text field renders as a string of zeros, for example 000000000 for a NIF or 00 for a province, which looks like plausible data rather than an omission - after the fix it renders as spaces, an honest blank. Neither is correct for a field that is actually required, and both are covered by the pending fix making required bite for text, but the row states the behaviour moved rather than letting a reader discover it. Wrote a regression test exercising the real capture path, not the codec in isolation - test_low_numbered_identifiers_survive_submitted_file_capture in the sede adapter's declarations test module builds a synthetic Modelo 180 filed declaration carrying a low-numbered NIF and a province of 01 for six of the nineteen fields including one header field, feeds it through _observed_casillas_from_submitted_file and _observed_header_facts_from_submitted_file exactly as the production capture path calls them, and asserts every persisted value retains its leading zeros. Proved the test would have failed before the fix via a runtime monkeypatch of the loaded field objects back to left_zero right, outside the repo and without touching the tracked registry file, reproducing the exact corruption - 00098765Z became 98765Z, 01 became 1, 01001 became 1001 - confirming the test is the one that would have caught this. and ## Scope

- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/export_layouts/0001-0001-modelo-180-declarante.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/export_layouts/0001-0002-modelo-180-perceptor.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0001-modelo-180-declarante.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0002-modelo-180-perceptor.toml`
- `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0010-record-declarante.toml`
- `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0020-record-operador.toml`
- `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0030-record-rectificacion.toml`
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Sweep every export field declaring padding left_zero across all modelos and both directory shapes, export_layouts and export, since Modelo 349 uses the latter. 127 total fields, 12 files across Modelo 131, 145, 180 and 349. Classification is structural, not per-field judgement - integer, decimal and money fields are always safe because Decimal of int of digits is indifferent to leading zeros, so the parse-side lstrip is inert once the value is reinterpreted numerically - 108 of 127. Only data_type text fields return the stripped string directly with no numeric reinterpretation, and 19 of those are genuine fixed-width identifiers whose value space includes leading zeros by construction rather than zero-fillable quantities - NIF, dos digitos numericos provincia codes 01-52, INE municipio codes and Spanish codigo postal codes, all province-prefixed. Confirmed the class is live, not latent - src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py parses a Sede-captured filed declaration's fixed-width bytes back into persisted ObservedCasillaValue and ObservedHeaderFact records for every casilla-kind and header-kind field, taking the post-unpad string unchanged with no downstream re-validation, so a previously-filed Modelo 180 or 349 declaration carrying a low-numbered NIF or a province, postal or municipio code in 01-09 gets silently shortened on capture and that wrong value then carries forward into previous-filing bindings for later years. Fixed the 19 by changing padding from left_zero right to none none, which is what these fields structurally are - fixed-width identifiers that always exactly fill their slot, never actually padded by left_zero on render, only ever damaged by its unpad on parse. Did not touch the codec, only the nineteen field declarations, across two Modelo 180 revisions times eight ids and one Modelo 349 revision times three ids. Proved byte-for-byte render identity for every present value across all nineteen fields by direct rendering under both declarations and diffing, zero mismatches across fifty seven sampled values including low-numbered NIFs and provinces 01, 09, 28 and 52. The absent-value behaviour does move, and this is the one place render output changes - today an absent required-in-practice text field renders as a string of zeros, for example 000000000 for a NIF or 00 for a province, which looks like plausible data rather than an omission - after the fix it renders as spaces, an honest blank. Neither is correct for a field that is actually required, and both are covered by the pending fix making required bite for text, but the row states the behaviour moved rather than letting a reader discover it. Wrote a regression test exercising the real capture path, not the codec in isolation - test_low_numbered_identifiers_survive_submitted_file_capture in the sede adapter's declarations test module builds a synthetic Modelo 180 filed declaration carrying a low-numbered NIF and a province of 01 for six of the nineteen fields including one header field, feeds it through _observed_casillas_from_submitted_file and _observed_header_facts_from_submitted_file exactly as the production capture path calls them, and asserts every persisted value retains its leading zeros. Proved the test would have failed before the fix via a runtime monkeypatch of the loaded field objects back to left_zero right, outside the repo and without touching the tracked registry file, reproducing the exact corruption - 00098765Z became 98765Z, 01 became 1, 01001 became 1001 - confirming the test is the one that would have caught this.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/export_layouts/0001-0001-modelo-180-declarante.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/export_layouts/0001-0002-modelo-180-perceptor.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0001-modelo-180-declarante.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0002-modelo-180-perceptor.toml`
- `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0010-record-declarante.toml`
- `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0020-record-operador.toml`
- `src/cadrumo/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/export/0030-record-rectificacion.toml`
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2.py`

## Description

- Classify all 127 `left_zero` fields by semantic type across both export directory shapes.
- Replace zero padding with exact-width text handling for the nineteen identifier fields whose leading zeros are data.
- Prove byte-identical rendering for present values and exercise the real submitted-file capture path with low-numbered identifiers.

## Outcome

Commits `766fac308b`, `f6e8ce5f2c`, and `e2703627e8` repair the Modelo 349 and
Modelo 180 declarations and add the production-path regression. Present values
render byte-for-byte identically, while parsed NIF, province, municipality, and
postal identifiers retain their leading zeros.

## Notes

Absent required text fields now render as honest blanks instead of plausible zero
identifiers; enforcing requiredness itself remains owned by its existing contract.
