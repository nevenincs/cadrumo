---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` audit: `W09.P45 operator-surface review`

## Scope

Reviewed the W09.P45 operator-surface fixes for S356, S358, S219, S331, and S330.

- S356 adds operator-visible `iva_category` rendering to human `ledger list` output while preserving the existing typed JSON row contract. The audit covered the projection code, the real CLI regression test, the S356 plan row close, and the S356 execution record.
- S358 adds royalty/SGAE guidance to the existing `ledger classify --irpf-category` help text without adding automatic classification heuristics. The audit covered the locale leaves, the real CLI help regression, the S358 plan row close, and the S358 execution record.
- S219 localizes the `NO_PENDING_OBLIGATION` workflow-gate refusal for `modelo work file` through the existing error-rendering boundary. The audit covered the exception mapping, registry key, locale leaves, renderer tests, the S219 plan row close, and the S219 execution record.
- S331 localizes malformed modelo work `KEY=VALUE` guidance and the cross-period not-applicable verify advisory. The audit covered the shared parser, localized finding text, real CLI malformed-binding regression, existing row-parser coverage, locale leaves, the S331 plan row close, and the S331 execution record.
- S330 localizes modelo lifecycle state labels in text renderers while preserving raw enum tokens in JSON payloads. The audit covered the shared modelo renderer, locale leaves, real object-based renderer tests, the S330 plan row close, and the S330 execution record.

## Findings

### w09-p45-s356 | low | no findings

No findings for the ledger-list IVA-category display fix. Human `ledger list` output now renders the persisted `iva_category` value in a localized column aligned with the row payload, including translated headers. JSON output remains on the existing typed row contract.

### w09-p45-s358 | low | no findings

No findings for the royalty guidance fix. The `--irpf-category` help text now points operators to the category catalogue and explains the Art. 25.4 versus Art. 27 distinction without advertising `capital_mobiliario` as a public ledger category id and without adding a heuristic classifier.

### w09-p45-s219 | low | no findings

No findings for the no-pending-obligation localization fix. `NO_PENDING_OBLIGATION` now resolves its human refusal text through the active output language while preserving the raw `abort_code`, `stage`, workflow result summary for telemetry, and non-`NO_PENDING_OBLIGATION` workflow summaries.

### w09-p45-s331 | low | accepted locale serializer churn

No behavioral findings for the malformed `KEY=VALUE` localization fix. The shared modelo work parser now explains `KEY=VALUE` as key on the left of one equals sign and value on the right, and the cross-period not-applicable verify advisory uses localized operator prose while retaining legal and source references.

The locale CLI rewrote nearby YAML scalars while setting the S331 leaves. This is accepted as CLI-owned serialization churn because locale files must be updated through `aeat.locales`, not hand-edited.

### w09-p45-s330 | low | no scoped findings

No scoped findings for the lifecycle-state label fix. Modelo work-unit and calculation-revision text renderers now display localized human state labels, while `WorkUnitPayload.state` and `CalculationRevisionPayload.state` remain raw enum-token values for machine consumers.

Residual edge noted by review: other modelo CLI surfaces outside the touched renderer may still print raw `revision.state.value` in text output. Keep that as a follow-up candidate under the broader R9 language-effectiveness work rather than broadening S330 into unrelated renderer ownership.

## Recommendations

No follow-up required for S356, S358, S219, S331, or the scoped S330 renderer fix.
