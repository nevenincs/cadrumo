---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9646361d4c4a0609dbf58ed3e6b7745f333449727f70d488a335cdb427dc69b0'
step_id: 'S154'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Trace the fixed-width export rows that feed filed bytes, establish the codec refuses rather than truncates, and record the three bound shapes an annotation scan cannot see

## Scope

- `src/cadrumo/application/filing/`
- `src/cadrumo/domain/calculations/registry/fixed_width_codec.py`
- `.vault/audit/2026-08-31-semantic-consolidation-invisible-bounds-audit.md`

## Changes

- `A` `.vault/audit/2026-08-31-semantic-consolidation-invisible-bounds-audit.md`
- `verify:` probed `pad_fixed_width_text` -- "ES" renders into a 2-char field, "ESPANA" is REFUSED
- `verify:` read both guards: the padding contract and the encoded-byte-count check
- `verify:` probed `resolve_iva_rate_slot` -- 21 and 10 resolve, 210 / -5 / 0.21 refused

## Notes

No production change. The highest-consequence open item in the campaign resolves
to NOT A DEFECT, and establishing that was the work.

`_producer_snapshot.py`'s fixed-width export rows declare every field as
`str | None` -- `codigo_pais`, `ciudad`, `entero`, `decimal`, identically
unconstrained -- and they feed FILED BYTES. A sentinel flagged it as the one site
it most wanted traced, correctly: if the producer skipped validation a malformed
country code would reach an official document with no gate at all.

The gate is the codec. `pad_fixed_width_text` refuses a value longer than the
field's registry-declared length, and `_render_record_bytes` independently
refuses when the encoded byte count does not equal the declared count. Probed
rather than read: `"ESPANA"` in a two-character field is refused with
`fixed-width value exceeds length 2`. It does not TRUNCATE, which is the failure
that would have mattered -- a silently shortened code on a filed record.

The bound could not sit on the row model even in principle. The width comes from
the registry record design, per modelo and per revision; the row model is one
generated shape serving all of them.

That is the third time this session a field looked unbounded to an
annotation-reading scan and was not. The audit records all three -- a closed SET
resolved against, a CODEC refusing on its own contract, a shared VALIDATOR
carrying the policy -- because the mistake has a direction: adding a bound to a
field that already has an invisible one is not harmless tidying. It contradicted
the real policy once already, on the Modelo 720 currency code, and reddened a
test.
