---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:dd57612f538b336a0ebd2c439eb1e0b8bf51119b6a1bfd1c9679bee9bb8facb3'
step_id: 'S141'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Give the RETMAR mandatory-filing determination its own function and answer it from the original facts, so the renderer stops repairing a value the incomplete-profile rerun clears

## Scope

- `src/cadrumo/application/calculations/_maritime_exemption_service.py`
- `src/cadrumo/application/modelo/_maritime_preview.py`
- `src/cadrumo/entrypoints/cli/_modelo_maritime_cli.py`

## Changes

- `M` `src/cadrumo/application/calculations/_maritime_exemption_service.py`
- `M` `src/cadrumo/application/modelo/_maritime_preview.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_maritime_cli.py`
- `A` `src/cadrumo/application/modelo/tests/test_maritime_preview_retmar_mandatory_filing.py`
- `verify:` `pytest .../test_maritime_preview_retmar_mandatory_filing.py -n 0 -m ""` -> pass (3)
- `verify:` `pytest .../test_maritime_exemption_service.py -n 0 -m ""` -> pass

## Notes

The renderer computed `result.retmar_mandatory_filing or facts.retmar_registered`.
That `or` was not defensive padding: on the incomplete-profile path the preview
reruns the resolution against facts with the RETMAR flag deliberately CLEARED --
the only way to get observations from incomplete data -- so the rerun result
carries false on exactly the branch where the real answer may be true. The CLI
was reaching past the muddled result to the untouched fact and repairing it.

Right answer, wrong place, and untested as such: the end-to-end test asserts the
flag is true for a registered taxpayer, which the `or` also satisfies, so the two
sources were never distinguished. A second condition joining the service
determination would have left the renderer returning the old answer, and a
registered taxpayer would have been told their filing is optional.

The determination is now its own function, the preview answers from the ORIGINAL
facts through it, and the renderer reads. The new regression asserts the two
DISAGREE on the warning path -- result false, preview true -- which is only
meaningful once the preview stops reading the rerun, and a third case pins that
the preview agrees with the service over every input rather than restating it.

Two failures in the CLI test module are a peer's tuple-versus-list tightening on
observation legal_refs and source_refs, untouched by this change.
