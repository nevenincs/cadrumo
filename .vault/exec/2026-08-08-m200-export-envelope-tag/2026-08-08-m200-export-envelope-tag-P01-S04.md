---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a9ccaba34e1e43aeb9008cb8f104ed55afe54b31079522aad49782c4709e6672'
step_id: 'S04'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

# add the envelope-footer export fragment reusing the existing computed closing-tag key

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0078-modelo-200-envelope-footer.toml`

## Description

- Add one export fragment declaring record `modelo-200-envelope-footer`,
  `record_type = "envelope_footer"`, `order = 77` (immediately after the DID
  record's `order = 76`), carrying a single field at offset 1 length 18 with
  `kind = "computed"` and `computed_key = "envelope_closing_tag"`.
- Reuse the existing computed key rather than authoring a Modelo 200 variant. The
  template already renders `</T` + modelo + a hardcoded discriminante `0` + year +
  period token + `0000>`, which is byte-identical to the example content sheet
  `DP200000` row 13 prints. No application code changed.

## Outcome

The layout now declares a closing-tag record where it previously declared none,
and because records render in `order` and the footer carries no binding fields or
suppression predicate, it lands last on every Modelo 200 export.

The discriminante is rendered twice in the file now — once by the open tag's
literal and once by this computed template's hardcoded default. Both are `0` and
both are correct for every filer this application can serve, but they are one
value with two authorities, so a future regime-modelling change must move them
together.

## Verification

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export.py -k "modelo_200" -n0 -q
    4 passed, 42 deselected in 18.08s

## Notes
