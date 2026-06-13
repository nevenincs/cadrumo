---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
related:
  - "[[2026-05-19-profile-lifecycle-disaster-plan]]"
---

# `cross-domain-continuity` W09.P41 -- #163 Code Review

## Status: APPROVE+FU

Commit `500b53f73` -- M720 NOT_APPLICABLE for impatriados (Art. 93.5 LIRPF) + M714 stub sweep

---

## Critical Questions

### Q1 -- Beckham axis dependency on half-implemented #162

The commit uses `profile.irpf_special_regime is IrpfSpecialRegime.IMPATRIADO` from the #162 axis. The dependency is safe in scope for this commit. The four HIGH gaps from the #162 review (SCHEMA-001: missing model_validator; WINDOW-001: `beckham_window_active` absent; CLI-001: wizard flags absent; LOCALE-001: no locale keys for wizard prompts) do not affect correctness here because:

- The M720 NOT_APPLICABLE pre-check is a pure enum equality test. It does not call `beckham_window_active`, does not read `special_regime_start_date`, and does not depend on the CLI wizard being wired.
- A profile reaching `derive_modelo_applicability` already carries a fully typed `TaxpayerProfile`; `irpf_special_regime` defaults to `None` (safe) and equals `IMPATRIADO` only when explicitly set.
- SCHEMA-001 (no model_validator for IMPATRIADO-requires-date) does not create a crash here because `special_regime_start_date` is never read in this commit.

The dependency is a compile-time safe import with no runtime hazard. The #191 follow-up (SCHEMA-001 + WINDOW-001 + CLI-001 + LOCALE-001) remains outstanding and is not papered over.

### Q2 -- beckham_window_active usage

`beckham_window_active` is not referenced anywhere in this commit. The pre-check is a simple enum identity test. No window-duration arithmetic is performed; the exemption is unconditional for any IMPATRIADO profile. This is correct at the applicability layer: the M720 obligation is suspended for the entire duration the taxpayer is under Art. 93. Window expiry is an orthogonal concern tracked under WINDOW-001 / #191. No inline duplication of WINDOW-001 occurs.

### Q3 -- Rationale quality for M720 NOT_APPLICABLE

`_IMPATRIADO_M720_EXEMPT_REASON` explicitly names LIRPF Art. 93, states the taxpayer tributas as IRNR, and cites DA 18a Ley 58/2003 (introduced by Ley 7/2012 DA 1a). The EUR 50.000 threshold is not cited -- correct, because the exemption fires before the payer-fact threshold check; an IMPATRIADO with zero foreign assets also gets NOT_APPLICABLE, which is legally correct.

`_IMPATRIADO_M720_LEGAL_REFS` includes `ley-35-2006:art-93`, `ley-7-2012:da-1`, and `orden-hap-72-2013:art-1`. All three resolve in the production registry -- confirmed by `test_seed_modelo_applicability_legal_refs_resolve_in_registry` loading a real `ValidatedRegistryAuthority`.

### Q4 -- Locale parity for M720 exemption refusal

`_IMPATRIADO_M720_EXEMPT_REASON` is a domain-layer Spanish string in a typed `ModeloApplicability` model. This is consistent with project convention: the domain layer returns typed objects; the CLI renders. No new `tr()` key was required for domain output. G3 PASS.

For the M714 stub sweep: `_STUB_MODELO_LOCALE_KEYS["714"]` maps to `cli.app.modelo.work.create_stub_modelo_714_refused`, present in es, en, ca, and hu. G4 PASS.

### Q5 -- Anti-tautology regression coverage

Three targeted tests are present in `test_modelo_applicability.py`:

- `test_impatriado_art93_exempts_modelo_720_even_with_bienes_declared` -- IMPATRIADO + bienes=True -> NOT_APPLICABLE. Asserts reason text and legal ref. Non-tautological: fails if the pre-check is removed.
- `test_general_regime_profile_with_bienes_declared_modelo_720_applicable` -- irpf_special_regime=None + bienes=True -> APPLICABLE. Counter-proof: removing the IMPATRIADO condition collapses both tests.
- `test_impatriado_exemption_does_not_affect_other_modelos` -- IMPATRIADO + M100 -> APPLICABLE. Scope isolation.

All 6 tests in the module pass (verified: `uv run pytest` run). G6 PASS.

### Q6 -- M714 stub sweep vs #159 duplication

`_STUB_ONLY_MODELOS` extended from {"151", "721"} to {"151", "714", "721"}. `_STUB_MODELO_LOCALE_KEYS` gains a "714" entry. No new guard function introduced -- the existing `_guard_stub_modelo` handles all three uniformly. Commit `4c239ed18` (#159) authored the M714 registry manifest stub and locale keys; this commit adds the CLI guard referencing them. No duplication: #159 owns the registry/locale side, #163 owns the CLI guard side. G5 PASS.

---

## Safety Domain

**G1 PASS** -- No naked env reads in any modified file.

**G2 PASS** -- `ModeloApplicability` carries typed fields. `PayerFact.BIENES_EXTRANJERO_ABOVE_THRESHOLD` maps to `profile.bienes_extranjero_above_threshold: bool` on `TaxpayerProfile`. No `dict[str, Any]` exposed at any boundary.

**G3 PASS** -- Domain layer strings are consistent with project convention. CLI layer calls `tr()` via existing pattern.

**G4 PASS** -- M714 locale key present in all four locale files (es, en, ca, hu).

**G5 PASS** -- No shims, re-exports, or duplication introduced. The pre-check and the rule entry are complementary, not duplicated paths.

**G6 PASS** -- Counter-proof test prevents trivially-always-true exemption. Legal-ref resolution test loads a real `ValidatedRegistryAuthority` against the bundled TOML tree.

---

## Findings

### CARRY-001 | HIGH (inherited, not new) | #191 follow-up still open

The four HIGH gaps from the #162 review (SCHEMA-001, WINDOW-001, CLI-001, LOCALE-001) tracked under follow-up #191 remain unaddressed. This commit is deliberately and correctly scoped to the applicability layer. No new action required on `500b53f73`. Carry noted to prevent #191 from being considered resolved by this landing.

### EXEMPT-001 | MEDIUM | Exemption unconditional on window expiry

The M720 NOT_APPLICABLE pre-check fires for any IMPATRIADO profile regardless of whether the six-year Beckham window has expired (`special_regime_start_date + 6 years < today`). A year-7 impatriado would incorrectly receive NOT_APPLICABLE -- after year 6 the taxpayer reverts to general IRPF residence and the M720 obligation is reinstated.

This is a direct consequence of WINDOW-001 tracked under #191. The production risk is currently zero: CLI-001 (wizard flags absent) prevents any operator from setting IMPATRIADO today, so no real profile carries this flag. Once #191 delivers `beckham_window_active`, the pre-check must be gated on it. A code comment at the guard site in `_applicability.py` should explicitly link to #191 so the dependency is not missed.

---

## Summary

Commit `500b53f73` is technically correct and safe for its stated scope. The IMPATRIADO enum test is the right gate at the applicability layer; the legal authority chain is fully grounded in the registry; all four locale files carry the M714 key; the three regression tests provide genuine non-tautological coverage with a counter-proof; all six standing gates pass.

EXEMPT-001 (MEDIUM) is a known consequence of the open WINDOW-001 gap. It poses no immediate production risk because CLI-001 prevents operator use. Must be addressed by #191 before wizard flags go live.

**Verdict: APPROVE+FU** -- safe to land. Follow-up #191 must gate the pre-check on `beckham_window_active(today)` before the CLI wizard flags for the IMPATRIADO axis go live.
