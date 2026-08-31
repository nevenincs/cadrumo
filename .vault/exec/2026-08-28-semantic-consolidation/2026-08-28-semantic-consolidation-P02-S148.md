---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0a21f200b69859ee9b8b3fe7bc92dfce4e91ca5f7e9b8cc65e1c1c97798750aa'
step_id: 'S148'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Adopt the UTC instant annotation at the three payloads that dropped an aware-timestamp guarantee their record makes

## Scope

- `src/cadrumo/entrypoints/cli/_config_bucket_history_payloads.py`
- `src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_config_bucket_history_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `verify:` probed the annotations directly -- bare datetime ACCEPTS a naive value, UtcInstant refuses it
- `verify:` `pytest cli/tests -k "bucket_history or ledger_rule or rule_payload" -n 0 -m ""` -> pass (7)

## Notes

Census of the timestamp class: 340 datetime-typed timestamp fields, 72 using
`UtcInstant`. The census alone does not say which of the remaining 265 are wrong,
and that is the interesting part -- the existing gate
`test_utc_instant_sources_are_aware.py` documents a field that legitimately
carries a NAIVE value, because AEAT prints a Europe/Madrid wall-clock time on the
justificante with no offset. Typing that one as an instant refused every real
receipt and broke a hundred and thirty-two tests. So "bare datetime" is not a
defect by itself.

The provable subset is narrower and comes from the typed divergence scan: a
payload whose record carries `validate_utc_aware` and which drops it in
projection. Three of those, each populated by copying the already-aware value
straight off the record (`event.occurred_at`, `inspection.created_at`,
`record.filed_at`), so adopting the annotation asserts what the value already
satisfies rather than tightening anything.

Checked before changing: `since` and `until` on the same bucket-history model
stay bare `datetime`, because they are operator-supplied filter bounds rather
than recorded instants and a naive `--since 2026-01-01` is a reasonable thing to
type.
