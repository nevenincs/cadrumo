---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-cross-domain-continuity-W09-P41-S299]]"
---

# cross-domain-continuity Code Review — S299 M303 SIMPLIFICADO ledger-preflight bypass


## Status: APPROVE+FU

No CRITICAL or HIGH issues. Two LOW findings documented below. Safe to merge;
follow-up items are tracked.

---

## Critical Question Answers

**CQ1 — Bypass layer:** Engine layer. The bypass lives in
`_raise_if_ledger_preflight_blocks_calculation` inside
`src/aeat/application/modelo/_actions.py`. Régimen detection reads
`iva.regime` from the profile via `_iva_regime_for_bucket`, which goes through
`UserProfileLifecycleRepository` + `record_to_path_values`. The call site at
line ~907 is within the `calculate_modelo_revision` function body; no CLI or
registry layer is involved. This is the correct layer.

**CQ2 — Refusal message cites Orden HFP / #227:** The bypass issues no
operator-facing defect-of-record refusal. It is a silent early-return. The
pre-existing `ModeloAggregationBindingError` at lines 1348-1351 (which fires
only for GENERAL-regime clients) is a plain f-string, not a `tr()` call and
does not mention Orden HFP. The task brief states the bypass "surfaces a
defect-of-record refusal naming the missing forfait-IVA authority" — this does
NOT happen in the committed code. The bypass is a clean early-return; the
SIMPLIFICADO client proceeds to calculate (or fails later on missing casilla
47-58 inputs). There is no Orden EHA/672/2007 citation or #227 corpus-retrieval
roadmap surfaced to the operator. See LOW-001 below.

**CQ3 — Locale parity:** No new locale keys were added by S299 or its bundled
S218 `_actions.py` changes. The bypass path emits no user-facing message; it
returns silently. The existing `errors.refused.ledger_preflight` key (present
in es/en/ca and aliased in hu) is unchanged and untouched. G4 is satisfied by
omission: no scaffold passthrough, no new keys.

**CQ4 — Regression tests:** Two tests in
`src/aeat/application/modelo/test_simplificado_ledger_bypass.py`:
- `test_simplificado_bypasses_ledger_preflight_when_transactions_are_unclassified`
  — calls `_raise_if_ledger_preflight_blocks_calculation` directly; asserts no
  error raised for `iva_regime=SIMPLIFICADO` with a blocking transaction present.
- `test_general_profile_raises_preflight_error_when_transactions_are_unclassified`
  — same inputs, `iva_regime=GENERAL`; asserts `ModeloAggregationBindingError`
  matches `"ledger preflight"`.

The anti-tautology proof is real: the match string `"ledger preflight"` is a
literal substring in the raised error at line 1349, which would not appear via a
humanised-key fallback. Both tests use real adapters (`isolated_runtime_profile`,
real `TransactionCatalogueRepository`, real registry snapshot). G6 satisfied.

**CQ5 — Wizard catalogue `_SETUP_OPTION_INFOS`:** Neither `a062b1e89` nor the
bundled `056625869` touches `src/aeat/application/wizard/_commands.py`. The
`iva-regime` option was already present in `_SETUP_OPTION_INFOS` at line 208
before this work. No parity delta introduced; no #228 repeat.

**CQ6 — Anti-tautology:** The anti-tautology proof at line 157 asserts
`match="ledger preflight"` against `ModeloAggregationBindingError`. The literal
string `"ledger preflight blocks modelo calculation"` is hardcoded at
`_actions.py:1349` — it is NOT a `tr()` call, so a humanised-key fallback would
produce a different string and the match would fail. The anti-tautology is
structurally sound.

---

## Findings

### SAFETY-001 | LOW | `ModeloAggregationBindingError` raises a bare f-string, not `tr()`

`_actions.py` lines 1348-1351 raise `ModeloAggregationBindingError` with a
bare hardcoded English string containing no `tr()` call. This is an existing
pre-S299 condition (not introduced by this commit), but the bypass added
directly above it at lines 1333-1337 is silent and contributes no new G3
violation. Pre-existing drift only; not introduced by S299.

Pre-existing; not introduced here. No action required for this review cycle.

### INTENT-001 | LOW | No defect-of-record refusal for SIMPLIFICADO surfaced

The task brief stated the bypass should "surface a defect-of-record refusal
naming the missing forfait-IVA authority (Orden EHA/672/2007) and #227 corpus
retrieval task." The committed implementation is a silent early-return that
allows calculate to proceed. This is arguably a better UX (the operator gets a
calculate attempt rather than a locked refusal), but it diverges from the
documented Path-B intent.

If the operator has not supplied casillas 47-58, the calculate will fail later
with a missing-input error rather than a grounded legal refusal citing Orden
EHA/672/2007. This is a scope-alignment question for the coordinator: the
present implementation is safe and correct mechanically, but the named follow-up
(#227 forfait corpus) is the only path that will make the SIMPLIFICADO calculate
actually complete. Recommend a follow-up ticket confirming whether the silent
bypass or a grounded defect-of-record refusal is the intended operator
experience for #169 Path-B.

---

## Gate Results

- G1 naked env: clean — no `os.environ`/`os.getenv` in changed files.
- G2 typed boundaries: `_iva_regime_for_bucket` returns `str | None`; all
  callers handle `None` via set membership (`None not in frozenset`). Clean.
- G3 tr() for user messages: bypass path emits no user-facing message. Existing
  pre-S299 error string is a bare f-string but that is pre-existing. No new
  G3 violation introduced.
- G4 locale scaffold: no new keys added; no yml structure edits. Clean.
- G5 no shims: bypass integrates as a conditional early-return inside the
  existing function — no parallel calculate path, no duplicate entrypoint.
  Clean.
- G6 anti-tautology: confirmed by match string analysis above. Clean.
