---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:b56887d566f474b64c655d5f3d1f5cf8f8aeed5cac31ce8afc919003e40c62d4'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S21 finding facts notice context`

## Scope

Reviewed W02.P06.S21 against the accepted blocker-spine decision, campaign plan, research, CLI contract, and repository quality constraints. Scope was limited to `verification_report_notices` in `_modelo_rendering.py` and the real natural-key CLI regression. The required contract is lossless projection of every validated finding `message_facts` item into string-valued `Notice.context`, preservation of existing notice facts and non-action semantics, fail-closed collision handling, and proof that native blocker codes survive the JSON envelope wire.

## Findings

No actionable S21 findings.

`verification_report_notices` continues to seed context with the finding's native `severity` and `kind`, then adds optional casilla, expectation, legal-reference, and source-reference facts. It now iterates the immutable validated `message_facts` map, converts every admitted scalar value with `str`, and inserts each key without filtering. This preserves string tokens, integers, booleans, and decimals in the `Mapping[str, str]` shape required by `Notice.context`. The finding model already validates stable locale-neutral keys/values and refuses presentation/action semantics before this boundary; the Notice model independently refuses reserved action keys and raw command prose.

Collision behavior is fail-closed. If a message-fact key already exists in the seeded context with a different rendered value, the function raises a named `ValueError` before constructing or emitting the notice. An identical duplicate is idempotent. No producer value silently overwrites native severity, kind, casilla, expectation, or grounding context.

The change does not infer an executable recovery action. `Notice.action` remains `None`; typed recovery continues to live on the command result. The added context is deterministic machine data, while localized prose still renders from the original message locale key and facts. Thus the implementation closes the ADR's fact-loss finding without creating a second action channel or duplicating application policy at the CLI layer.

The real integration regression executes profile creation, natural-key work creation/calculation/verification, envelope rendering, and JSON parsing. Its newly required jurisdiction-scope argument repairs the current real profile contract. It locates the actual cross-period blocking notice, preserves the native finding severity/kind, proves `blocker_codes` is non-empty on the wire, and proves every pipe-delimited blocker token is non-blank. It uses no fake, stub, mock, patch, monkeypatch, skip, expected-failure, or mirrored message-fact implementation.

## Verification

- Fresh semantic discovery located the finding producer, notice projection, envelope consumer, real integration test, and accepted blocker-spine decision before exact inspection.
- Exact natural-key integration node with marker selection disabled: 1 passed.
- Scoped Ruff: passed.
- Scoped `git diff --check`: passed.
- Full `_modelo_rendering.py` strict BasedPyright retains 388 longstanding diagnostics; exact inspection found zero diagnostics in the modified 880-913 range.
- Direct real-model all-value probe: context carried blocker string, integer, boolean, and decimal facts as deterministic strings while retaining native kind/severity/legal references.
- Direct real-model collision probe: conflicting `message_facts['severity']` raised `ValueError` naming the conflicting key before notice emission.
- Notice action boundary: emitted notice retained `action=None`; reserved action context remains rejected by the canonical Notice validator.
- Prohibited test-construct scan: no scoped hits; `fmt: skip` comments are formatting controls, not pytest skips.

## Recommendations

No corrective action is required for S21. Future envelope projections should continue to reuse this production function rather than re-copying selected facts. If collision behavior receives a dedicated checked-in regression later, construct real frozen finding/report models and assert the production refusal without mutation or patches.

Verdict: **PASS.** W02.P06.S21 carries validated native finding facts, including blocker codes, through the real notice/envelope wire as deterministic data, preserves all pre-existing context, fails closed on conflicts, and introduces no alternate action authority or test double.
