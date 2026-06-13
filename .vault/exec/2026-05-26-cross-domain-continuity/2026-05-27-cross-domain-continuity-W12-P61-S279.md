---
step_id: S279
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-27-cross-domain-continuity-W12-P61-S278]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W12.P61 — S279

## Objective

Annotate 10 application-service boundary helpers with `Mapping[str, object]`
return types to eliminate bare `dict[str, object]` UNTYPED_BOUNDARY sites at
JSON-parse, logging-extra, and `AeatError` context boundaries.

## Sites addressed (10)

| file | symbol | change |
|---|---|---|
| `auth/_diagnostics.py` | `_payload` | `-> Mapping[str, object]` + inline boundary comment |
| `auth/_diagnostics.py` | `_json_object` | `-> Mapping[str, object]` |
| `auth/_diagnostics.py` | `_summary_from_payload` | param `Mapping[str, object]` |
| `auth/_diagnostics.py` | `_detail_fingerprints_from_payload` | param `Mapping[str, object]` |
| `auth/_acquisition_lock.py` | `_status_context` | `-> Mapping[str, object]` + inline comment |
| `aggregation/_service.py` | `as_extra` | `-> Mapping[str, object]` |
| `operator_surface/_models.py` | `as_extra` | `-> Mapping[str, object]` |
| `filing/_review.py` | `_review_metadata_reset` | kept `dict[str, object]`; inline comment explains mutation requirement |

## Design decisions

`_review_metadata_reset` in `filing/_review.py` intentionally keeps
`dict[str, object]` because its two callers immediately mutate the returned
dict (`cleared["status"] = ...`) before passing it to `model_copy(update=...)`.
Changing to `Mapping` would break the mutation. An inline comment records this
rationale.

`Mapping` is the narrowest correct annotation for read-only boundary helpers
that return `dict` internally but are consumed only as opaque context payloads
by `AeatError(context=...)` or `logging.debug(..., extra=...)`.

## Verification

`uv run --no-sync pytest src/aeat/application/auth/ src/aeat/application/aggregation/ src/aeat/application/operator_surface/ src/aeat/application/filing/ -x -q`
— 349 passed, 1 pre-existing failure (registry calculation `bound casilla '15'`).

`ruff check` on all 5 modified files — clean.

## Commit

`b86b9bddb` — W12.P61.S279: annotate 10 application-service boundary helpers as Mapping[str, object]
