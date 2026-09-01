---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:2116990f19f5746d2331c12294df3476d62ade8e9c2a5304050af267e37dfd61'
step_id: 'S66'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Teach the export-coverage join to consult a record's declared `RecordDiscriminator`, closing Modelo 349 and turning the rest of the ratchet back into ordinary authoring. DONE 2026-08-28. THIS WAS NOT A WIDENING but the third instance today of the same shape: a declaration exists, is authored, and the checker cannot see it -- after `_record_literals` missing binding-carried constants and the ratchet missing the aux-header and filing-envelope branches. `RecordDiscriminator`'s own docstring names this exact ambiguity: a literal-prefix matcher 'cannot tell two records apart when they share their leading literal fields (AEAT models several Tipo-2 record sub-shapes that all start with the same record-type literal)'. The PARSER already consulted it while reading binding rows; the coverage join did not, so two records with identical prefixes tied and fell to the weaker layout-wide question even though the registry declared how to tell them apart. AEAT'S OWN WORDS CORROBORATE THE MAPPING, which is what took this from inference to reading: at the discriminator coordinate (@147+32) Modelo 349's operador sheet says `desc='Blancos'` while its rectificaciones sheet says `desc='RECTIFICACIONES'`, subdivided into BASE IMPONIBLE O IMPORTES RECTIFICADOS and BASE IMPONIBLE DECLARADA ANTERIORMENTE. So `requires='blank'` matches a run AEAT itself calls filler, read through the same Blancos/Ceros vocabulary the row parser already treats as authoritative -- not a reading of prose. IMPLEMENTED AS A TIE-BREAKER ONLY, reached solely when the declared constants leave more than one record at the same agreement score, so it can turn 'no join' into a join and can NEVER change one the constants already decided; where the discriminator is silent it returns None and the sheet stays unjoined rather than taking an arbitrary winner -- silence is never read as agreement. MEASURED registry-wide: unjoined sheets 11 -> 9, exactly Modelo 349's two, with nothing else moving. Ratchet entries deleted. THE CONSEQUENCE FOR THE REST IS THE BIGGER RESULT: an earlier reading called the remaining rows permanently unshrinkable because AEAT publishes no distinguishing constant. That was wrong. `ExportRecordDefinition.discriminator` is a REGISTRY concept rather than an AEAT one, so a discriminator can be AUTHORED where AEAT prints no constant, with M349 as the worked example. M184, M193 and M296 are now ordinary registry authoring rather than an ADR-grade blocker. A heredoc silently dropped the regex word boundary for the second time today; the emitted line was grepped rather than trusted, which matters here because without it RECTIFICACIONES need only START with a filler word to be misread

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py and the join ratchet gate`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S66.md`
- `verify:` `& .venv\Scripts\python.exe -m pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py src/cadrumo/domain/calculations/registry/tests/test_modelo_349_registry.py::test_committed_modelo_349_record_design_round_trips_declarante_operador_rectificacion` -> `pass`

## Notes

- Fresh verification at current HEAD: `5 passed in 224.01s (0:03:44)`. Immutable implementation provenance is `ce7ed9c74ef76a656170e5c8060e4b68fa510779`; it contains no captured historical literal test output, so this fresh result is not presented as historical output.
