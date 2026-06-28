---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-27-cross-domain-continuity-w09-p41-s361-review-exec]]"
---

# `cross-domain-continuity` Code Review


## Status: PASS

Commit `4c239ed18` is approved for merge. No Critical or High findings.

---

## Critical-question answers

**Q1 — G5: Does M714 extend `_STUB_ONLY_MODELOS` to `{"151", "714", "721"}`?**

Confirmed. `_modelo.py` line 1323 reads `frozenset({"151", "714", "721"})`. The guard entry for `"714"` was landed in the prior M151 commit (`205e24e9d`) as documented in the commit message. The current commit carries no `_modelo.py` diff; the frozenset is already in the correct final state. G5 satisfied.

**Q2 — Frozenset/dict parity: Does `_STUB_MODELO_LOCALE_KEYS` include `"714"` and match the frozenset?**

Confirmed. `_STUB_MODELO_LOCALE_KEYS` at lines 1327-1331 contains all three keys — `"151"`, `"714"`, `"721"` — with dedicated locale keys for 151 and 714 and the shared key for 721. The dict is a strict superset of the frozenset; the guard dispatch at line 1362 uses `_STUB_MODELO_LOCALE_KEYS[modelo_code]` after a frozenset membership check, so no KeyError is possible for any registered stub. SAFETY-001 constraint satisfied.

**Q3 — Locale parity (es/en/ca/hu): substantive translations, not scaffold passthroughs?**

- `es.yml`: full substantive text, cites Ley 19/1991, Orden HAC/1023/2021, BOE-A-2021-7593, Comunitat Valenciana threshold. Landed in M151 commit.
- `en.yml`: full substantive text, same authorities in English. Landed in M151 commit.
- `ca.yml`: full substantive Catalan text added in this commit — Llei 19/1991, Orden HAC/1023/2021, CV threshold €600.000. Not a scaffold passthrough.
- `hu.yml`: full substantive Hungarian text added in this commit — Ley 19/1991, Orden HAC/1023/2021, Valenciai Közösség threshold. Not a scaffold passthrough.

`uv run python -m aeat.locales audit` reports `missing=0` for all four locales. The three stub keys are reported as `extra` (not wired to a scaffold baseline), which is expected for guard-only locale keys.

Parity confirmed for all four locales.

**Q4 — Refusal message legal authority content:**

All four locales cite:
- Ley 19/1991 Art. 28 (Impuesto sobre el Patrimonio / Impost sobre el Patrimoni / Vagyonadó).
- Orden HAC/1023/2021, BOE-A-2021-7593.
- Threshold: net wealth > €700.000 general, €600.000 Comunitat Valenciana.
- Redirect: `sede.agenciatributaria.gob.es/Sede/patrimonio.html`.

All four content requirements satisfied.

**Q5 — Anti-tautology regression tests:**

Three tests in `test_modelo_714_stub_refusal.py`, all passing (3/3 green, 22s):

- `test_work_create_714_refuses_with_legal_authority_message`: asserts non-zero exit, no Traceback, `"19/1991"` or `"1991"` in output, `"HAC/1023/2021"` or `"1023"` in output, `"Sede"` in output, no `"could not evaluate"`, no `"Modelo desconocido"`. Genuine behavioral assertions against the running locale system — not tautological.
- `test_work_create_714_registry_loader_accepts_without_integrity_error`: roundtrip through `load_registry_tree` + `RegistryValidator` + `build_snapshot` against real bundled registry. Asserts `revision.id == "2021-y-siguientes"`. Not tautological.
- `test_work_create_714_refusal_fires_before_profile_check`: invokes without a created profile; asserts legal-authority strings appear, proving guard fires on registry state before active-profile resolution.

G6 satisfied. Tests use `invoke_cached_cli` + `isolated_profile_storage_root` — real adapters, no mocks.

---

## Safety domain

No crash paths introduced. `_guard_stub_modelo` performs a frozenset membership check before indexing the dict — no KeyError possible. `CliRefusedBoundaryError` is the established boundary error type; `tr()` is used for the message. Resource safety: no handles opened. Concurrency: no shared mutable state introduced. G1 (no naked env reads): confirmed absent. G2 (typed pydantic at boundaries): guard operates above the adapter layer, no boundary struct needed.

## Intent domain

The commit implements the M714 Path-B refusal pattern identically to M721 (#157) and M151 (#161): registry stub + guard extension + locale keys + behavioral tests. No extra features, no parallel systems. Architectural compliance with the established `_STUB_ONLY_MODELOS` mechanism confirmed.

## Quality domain

No findings. The `_guard_stub_modelo` docstring is updated to include M714. Locale entries are substantive. Test module docstring accurately describes the obligation law and threshold.

---

