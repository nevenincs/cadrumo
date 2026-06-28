---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity Code Review — #161 M151 Beckham régimen Path-B refusal stub

Commit `205e24e9d` — M151 impatriado declaración refusal stub (David round-10 SHOW-STOPPER).

## Verdict: APPROVE+FU

---

## Critical-Question Answers

**CQ1 — G5: Shared mechanism vs parallel implementation.**

M151 cleanly extends the existing `_STUB_ONLY_MODELOS` frozenset. No parallel mechanism was introduced. The commit also introduces `_STUB_MODELO_LOCALE_KEYS: dict[str, str]` as a dispatch table mapping each stub model code to its dedicated locale key — this is an additive, non-duplicated extension of the existing pattern. G5 PASS.

**CQ2 — Locale parity: four locales, semantic correctness, hu.yml gap.**

All four locales (es/en/ca/hu) are populated with semantically substantive translations. Each entry names Art. 93 LIRPF (Ley 35/2006), RD 439/2007 Arts. 113-120 RIRPF, Orden EHA/2887/2008 (BOE-A-2008-16237), and the G416 AEAT Sede URL. Hungarian is a full machine-translation (not a scaffold passthrough); adjacent keys such as `discard_help` remain scaffold passthrough in hu.yml confirming this is a known FORAL-001 gap, but the M151 key itself is substantively translated. G3 PASS. The commit message describes direct yml inserts ("add create_stub_modelo_151_refused key") with no mention of `python -m aeat.locales scaffold` — this is a G4 process violation (see finding LOCALE-001 below).

**CQ3 — Refusal message redirect appropriateness for an Irish-national executive.**

The English locale message is operator-readable and explicitly states: (a) the model is stub-only, (b) the Ley Beckham regime requires M151 not M100, (c) the AEAT Sede Electrónica G416 URL, (d) all three governing legal authorities. A user who arrives at `work create --modelo 151` having filed M100 previously will understand immediately that M151 is the correct declaración and exactly where to file it. CQ3 PASS.

**CQ4 — Anti-tautology: legal authority strings in diagnostic output.**

`test_work_create_151_refuses_with_legal_authority_message` asserts `"93" in result.output` and `"EHA/2887/2008" in result.output or "2887" in result.output` and `"sede.agenciatributaria.gob.es" in result.output or "Sede" in result.output`. These assertions would fail if the locale key were missing (the humanised fallback "Create stub modelo 151 refused" contains none of those strings) or if the legal citation were dropped from the locale text. The test is genuinely non-tautological. CQ4 PASS.

**CQ5 — `irpf_special_regime` axis check wiring.**

No `irpf_special_regime` axis check is wired in this commit. A grep across `src/aeat/` finds no `irpf_special_regime`, `special_regime`, or `beckham` symbols outside this test file. The commit is a pure refusal-stub (Path-B only); axis integration is explicitly deferred. This is a valid narrowly-scoped approach matching the SHOW-STOPPER description. CQ5: stub-only, axis deferred — noted as follow-up.

---

## Findings

### LOCALE-001 | MEDIUM | G4 violated: locale keys added by direct yml edit, not scaffold

The commit message reads "add create_stub_modelo_151_refused key" and the diff shows 8-line direct inserts into each yml. The G4 gate requires all locale key additions to go through `python -m aeat.locales scaffold` followed by an `audit` cycle. The neighbouring M721 key (`create_stub_modelo_refused`) was also added under the same pattern, so this is consistent with the prior precedent — but it does not make it compliant. Direct yml edits bypass the scaffold's key-ordering enforcement and the audit step that checks for orphaned scaffold values.

Remediation: run `python -m aeat.locales scaffold` and `python -m aeat.locales audit` and commit the diff. If the scaffold produces no structural change (i.e. the keys are in canonical order already), the audit output alone is sufficient confirmation.

### SAFETY-001 | MEDIUM | `_STUB_MODELO_LOCALE_KEYS` can KeyError if frozenset and dict diverge

`_guard_stub_modelo` executes `locale_key = _STUB_MODELO_LOCALE_KEYS[modelo_code]` unconditionally after confirming `modelo_code in _STUB_ONLY_MODELOS`. If a future contributor adds a code to `_STUB_ONLY_MODELOS` but omits the corresponding `_STUB_MODELO_LOCALE_KEYS` entry, the guard raises an uncaught `KeyError` at the CLI boundary. The dict and frozenset are adjacent in source and the docstring is clear, but there is no invariant-enforcement. The production `tr()` path has a humanised-key fallback for missing locale keys but that fallback path is never reached if the dict lookup crashes first.

Remediation: use `_STUB_MODELO_LOCALE_KEYS.get(modelo_code, "cli.app.modelo.work.create_stub_modelo_refused")` as a safe fallback, or add an `assert set(_STUB_MODELO_LOCALE_KEYS) == _STUB_ONLY_MODELOS` module-level guard (raises `AssertionError` only at import time during tests, not silently at runtime).

### LOCALE-002 | LOW | Commit cites `Orden HAC/117/2024` in task scope but locale text references `Orden EHA/2887/2008` only

The task brief asks for `Orden HAC/117/2024` to appear in locale citations. The commit uses `Orden EHA/2887/2008` (the original 2008 form approval) and does not reference `Orden HAC/117/2024` (the 2024 update). For strict legal grounding the 2024 actualisation order should also appear, or its absence should be documented as a deliberate scope decision. This is a LOW finding because the 2008 order is the foundational authority and the refusal is functionally correct.

---

## Standing Gate Results

| Gate | Result | Note |
|------|--------|------|
| G1 naked env reads | PASS | No `os.environ`/`os.getenv` in changed files |
| G2 typed pydantic at boundaries | PASS | No new boundary types introduced; `CliRefusedBoundaryError` is existing typed surface |
| G3 `tr()` for user messages | PASS | All four locales present with substantive legal citations |
| G4 locale scaffold process | FAIL | Direct yml insert without scaffold+audit cycle (LOCALE-001) |
| G5 no shims/duplication | PASS | M151 extends `_STUB_ONLY_MODELOS`; `_STUB_MODELO_LOCALE_KEYS` is a new non-duplicated dispatch table |
| G6 no tautological tests | PASS | Legal-authority string assertions are non-tautological |

---

## Summary

The core implementation is architecturally sound: M151 shares the M721 stub mechanism, all four locales carry substantive legal citations, the English message is operator-readable for a non-Spanish-national user, and the regression tests are genuinely non-tautological. Two findings require follow-up: a G4 process violation (direct yml edits) and a latent KeyError if the `_STUB_MODELO_LOCALE_KEYS` dict diverges from `_STUB_ONLY_MODELOS` in the future. Neither finding is a current crash risk in production — the keys are present and the dict is complete for the existing two stubs.

Verdict: **APPROVE+FU** — merge is safe. Follow-up items are LOCALE-001 (scaffold cycle) and SAFETY-001 (dict-divergence guard).
