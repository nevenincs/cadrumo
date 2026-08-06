---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:3937cc57850702e1615c0694bd700edcf1078a1cd9317cd12e9c7061d1403667'
step_id: 'S235'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Add an AST recurrence gate that rejects new reducible production SHA-256 constructor and one-shot hexdigest bodies while allowing streaming, HMAC, HKDF, X509, and digest-byte uses

## Scope

- `src/cadrumo/core/tests/test_hashing_adoption.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. The gate was authored across three commits as the hashing consolidation progressed: introduced with `a1f1160e0c` (dropping the declaracion parser entries), shrunk by `604c8dce53` (dropping sixteen delegated production modules), and shrunk again by `d0f83e66e7` (dropping the corpus-manifest, observability, manuals, and mirror-manifest entries and correcting the gate's own prose).

- Add an AST-based recurrence detector (`_reducible_one_shot_sites`) that flags a reducible `sha256(<data>).hexdigest()` body — including one with a trailing slice — while never flagging a genuinely non-substitutable cryptographic use: incremental/streaming construction, raw digest bytes, keyed HMAC, HKDF key derivation, or an X509 certificate fingerprint.
- Ratchet a per-module grandfathered baseline (`_REDUCIBLE_ONE_SHOT_BASELINE`) in the reducing direction only: a new module or a higher per-module count fails; delegating a body and lowering or dropping its baseline entry is always allowed.
- Ground the baseline against real sites so it cannot silently mask a recurrence: every baseline entry must still host at least one reducible body today, or the grounding test fails.

## Outcome

`src/cadrumo/core/tests/test_hashing_adoption.py` carries three tests: `test_no_new_reducible_one_shot_sha256_body_lands` (the gate itself), `test_recurrence_gate_flags_a_new_reducible_body_and_allows_legitimate_uses` (the discrimination proof, run over nine synthetic sources — three reducible shapes that must be flagged, five non-substitutable shapes that must not), and `test_recurrence_baseline_is_grounded_in_real_sites` (the anti-staleness proof). The baseline dict (lines 46-55) now carries exactly three entries: `application/auth/_certificate_sources_operator.py` (1), `application/auth/_operator.py` (1), and `domain/calculations/registry/_validate_verdict.py` (1, with an inline comment explaining the module is deliberately left as-is because delegating it would push the module past the 300-line reviewability ceiling for a body that keeps `hashlib` regardless for two non-reducible streaming digests). None of these three sites is named by any Step in `W03.P10`.

Verified against HEAD: the baseline dict, the discrimination-proof source set, and the grounding test all match the description exactly. The gate passing green while these three residual sites hash inline is grounded, documented behaviour, not a masking bug.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/core/tests/test_hashing_adoption.py` reports 3 passed.

## Notes

This record was authored after the gate had already landed and been shrunk across three commits; it documents the verified state rather than performing new implementation work. The three residual baseline entries are intentionally out of scope for this phase's Steps, per the reasoning recorded inline in the baseline dict and in commit `d0f83e66e7`'s message.
