---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:ec973e36c0405ccfb148117b6d8c1b913db4acca71e1d23443cdd41890b5acf0'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` audit: `W09.P45 operator-surface review`

## Scope

Reviewed the W09.P45 operator-surface fixes for S356, S358, S219, S331, S330, S226, S328, S204, S333, S221, and S225.

- S356 adds operator-visible `iva_category` rendering to human `ledger list` output while preserving the existing typed JSON row contract. The audit covered the projection code, the real CLI regression test, the S356 plan row close, and the S356 execution record.
- S358 adds royalty/SGAE guidance to the existing `ledger classify --irpf-category` help text without adding automatic classification heuristics. The audit covered the locale leaves, the real CLI help regression, the S358 plan row close, and the S358 execution record.
- S219 localizes the `NO_PENDING_OBLIGATION` workflow-gate refusal for `modelo work file` through the existing error-rendering boundary. The audit covered the exception mapping, registry key, locale leaves, renderer tests, the S219 plan row close, and the S219 execution record.
- S331 localizes malformed modelo work `KEY=VALUE` guidance and the cross-period not-applicable verify advisory. The audit covered the shared parser, localized finding text, real CLI malformed-binding regression, existing row-parser coverage, locale leaves, the S331 plan row close, and the S331 execution record.
- S330 localizes modelo lifecycle state labels in text renderers while preserving raw enum tokens in JSON payloads. The audit covered the shared modelo renderer, locale leaves, real object-based renderer tests, the S330 plan row close, and the S330 execution record.
- S226 localizes calculation result-summary casilla labels through registry-provided `localized_labels` while preserving official Spanish fallbacks and raw machine ids. The audit covered result-summary row construction, text and JSON payload rendering, focused isolated-storage regression coverage, the S226 plan row close, and the S226 execution record.
- S328 localizes overview calendar text-mode shift labels for known deadline-shift tokens while preserving raw `shift_reason` tokens in JSON payloads. The audit covered the overview text renderer, locale leaves, focused CLI/formatter regressions, the S328 plan row close, and the S328 execution record.
- S204 verifies that the project-wide i18n placeholder parity validator no longer reports SURPLUS kwargs for production `tr()` call sites. The audit covered the S32 parity validator, focused SURPLUS test, full placeholder parity module, locale audit, the S204 plan row close, and the S204 execution record.
- S333 locks `overview calendar --help` custom option help localization with a real Hungarian console regression. The audit covered the help-honesty test, live console output, the S333 plan row close, and the S333 execution record.
- S221 adds a bucket-local non-secret output-language hint so critical storage errors can render through the active or target profile language when the relevant bucket can be identified but the encrypted profile bucket cannot be opened. The audit covered the storage sidecar, runtime fallback, target-bucket readiness fallback, profile write/select refresh path, focused CLI regressions, import-provenance cleanup, the S221 plan row close, and the S221 execution record.
- S225 documents and hardens the malformed active-profile pointer language boundary. The audit covered settings/i18n fallback, the active-pointer error suggestion, the real CLI malformed-pointer regression, the S225 plan row close, and the S225 execution record.

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

### w09-p45-s226 | low | no scoped findings

No scoped findings for the result-summary label localization fix. The application summary row retains the official Spanish `label` as fallback, carries registry `localized_labels`, and the text and JSON renderers select the active output-language display label without changing `casilla_id`, `role`, or decimal value semantics.

Residual edge noted by review: the focused regression covers real Modelo 130 Catalan rendering and the typed payload row, but not a full JSON envelope parse or a separate missing-locale fallback assertion. Risk is low because the fallback is a direct `localized_labels.get(language, label)` projection.

### w09-p45-s328 | low | no scoped findings

No scoped findings for the overview-calendar shift-label localization fix. Text output now maps known shift tokens through locale-backed `tr()` calls, leaves official holiday names untouched, and preserves raw `shift_reason` values in JSON payloads for machine consumers.

Residual edge noted by review: the focused coverage exercises English text rows, Catalan weekend-token formatting, accented Spanish locale output, and JSON token preservation. It does not enumerate every supported language across every shift token, but locale scaffold and audit cover the key set.

### w09-p45-s204 | low | no scoped findings

No scoped findings for the SURPLUS-kwarg placeholder parity closure. The live S32 parity validator reports no surplus `tr()` kwargs for the production source tree, and the full placeholder parity module is green across ORPHAN, SURPLUS, and SHADOW checks.

Residual edge noted by review: the AST validator intentionally skips dynamic translation keys whose first argument is not a string literal. That leaves dynamic-key interpolation correctness to targeted call-site tests, but S204's named static-key surplus set is closed.

### w09-p45-s333 | low | no scoped findings

No scoped findings for the overview-calendar custom help localization closure. The real console regression now proves `--language hu app overview calendar --help` renders the command and custom option descriptions in Hungarian and does not leak the English custom `--from` or `--all-profiles` descriptions.

Residual edge noted by review: Typer's built-in `--help` option description and global help chrome still render in English. That belongs to S332's broader global help-localization scope, not S333's inconsistent custom-option scope.

### w09-p45-s221 | low | no scoped findings

No scoped findings remain for the readable-pointer malformed-DEK language fallback. The encrypted profile record remains authoritative, while the new bucket-local sidecar stores only a supported output-language code and lets storage-runtime error rendering fall back to that hint when the active pointer is readable but the profile bucket cannot be opened. The review-discovered `config switch` target-bucket edge is also covered: when a target bucket fails readiness before the active pointer changes, the CLI render language is pinned to the failed target bucket's hint unless an explicit output language is already active.

Residual edge noted by review: malformed active-profile pointers cannot identify the bucket and therefore cannot use this hint path. That edge remains S225's pre-profile error-language scope.

### w09-p45-s225 | low | accepted Spanish fallback

No scoped correctness findings for the malformed active-pointer language closure. When settings loading fails because the pointer itself is malformed, i18n now falls back to the default Spanish language so the integrity error renders cleanly instead of recursively failing during error-message rendering.

The implementation deliberately does not guess the Catalan profile language: a malformed pointer carries no trustworthy bucket id, so neither the encrypted profile record nor the bucket-local S221 language hint can be selected safely. The recovery suggestion now documents `language fallback=es` until the active-profile pointer is readable.

## Recommendations

No follow-up required for S356, S358, S219, S331, the scoped S330 renderer fix, the scoped S226 result-summary localization fix, the scoped S328 overview-calendar shift-label fix, the S204 SURPLUS-kwarg parity closure, the scoped S333 overview-calendar custom help regression, the scoped S221 readable-pointer malformed-DEK language fallback, or the S225 malformed-pointer Spanish-fallback hardening.
