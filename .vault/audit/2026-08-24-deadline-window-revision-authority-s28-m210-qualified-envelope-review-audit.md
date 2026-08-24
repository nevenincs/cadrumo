---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0e15c69a452ae80de06328332016e60a6eb77d9920ce3b27d3932a75d44564ef'
related: []
---
# `deadline-window-revision-authority` audit: `s28 m210 qualified envelope review`

## Scope

Reviewed the current S28 implementation against the accepted M210 plazo-keying and deadline-window revision-authority decisions. The review covered qualified `EVENT-N` work-to-annual plazo resolution, Modelo 210 enrollment in the sole result-disposition specification, calculate/verify notice coverage, tipo-28 silence, and semantic/exact searches for redeclared resolvers, enums, maps, and parsers.

## Findings

### envelope-proof | high | The calculate and verify envelope matrix does not exercise either envelope

`test_calculate_and_verify_project_exactly_one_grounded_qualified_plazo_notice`, the tipo-28 test, and the EVENT imputadas test call `calculated_m210_plazo_notice` directly before and after a domain verification helper. They do not invoke `calculate_modelo_work_revision`, `_run_work_calculate`, or `work_verify`, and they construct the same one-element tuple locally on both sides. Consequently the tests cannot detect a dropped `ModeloWorkCalculationServiceResult.plazo_notices`, missing CLI notice append, duplicate notice introduced by envelope composition, or verify transport regression. This does not prove the Step requirement that the real calculate and verify envelopes emit exactly one identical grounded notice, or zero for tipo 28.

### period-authority-reuse | medium | EVENT qualification bypasses the canonical selector matcher

The new branch in `_resolve_projected_filing_window` classifies every M210 `PeriodKind.EXTENDED` request as the event family and directly requires an annual target. The registry already owns symbolic-to-concrete event matching in `selector_period_matches_request`, exported through the registry facade. Bypassing it re-declares the effective `EVENT-N` family test as a broader period-kind rule and can drift if another extended M210 token is admitted. The bridge should first prove that canonical `EVENT-N` covers the requested registry token through `selector_period_matches_request`, while retaining the sole deadline matcher and exact qualifier/ambiguity logic in `_plazo.py`.

No duplicate filing-window resolver, `ResultDisposition` enum, official tipo-renta map, or period parser was otherwise introduced. Modelo 210 is correctly enrolled in the existing `_DISPOSITION_SPEC`, and tipo 28 remains without a fabricated offset.

## Recommendations

Add transport-level calculate and verify envelope regressions for the complete qualified matrix, asserting exact notice cardinality and equality from emitted payloads, including zero notices for tipo 28. Replace the broad `PeriodKind.EXTENDED` event-family predicate with the canonical `selector_period_matches_request("EVENT-N", period.registry_token)` decision and pin a non-event extended-token refusal test.
## Re-review

APPROVE. Both prior findings are resolved in the current implementation.

The matrix now obtains calculate notices from the real `calculate_modelo_work_revision` application result and verify notices from the emitted JSON `app modelo work verify` envelope. It asserts exact filtered cardinality and identical grounded context for ingreso codes 01 and 35, cuota cero, devoluciÃ³n, and EVENT imputadas code 02, while both surfaces remain empty for ungrounded tipo 28.

The qualified M210 event bridge now delegates `EVENT-N` family recognition to the canonical `selector_period_matches_request` authority. Unqualified requests and other modelos stay on exact semantic-coordinate matching, and the ambiguity refusal remains intact. Work creation uses that same selector matcher rather than a local event parser.

The `typed=True` cache partition is a sound validation fix: `ResultDisposition` is a `StrEnum`, so separating argument types prevents a previously cached typed request from allowing an equal raw string to bypass validation at the cached function boundary. No second resolver, result enum, tipo-renta map, period parser, or selector authority was introduced.

Focused verification reported 25 passing tests across disposition derivation, deadline resolution, real M210 calculate/verify projection, and the existing inmobiliaria flow; the envelope matrix file passed all 7 cases. No new findings remain.
