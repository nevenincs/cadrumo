---
tags:
  - '#research'
  - '#crossperiod-filing-deadlock'
date: '2026-06-19'
modified: '2026-06-19'
related: []
---

# `crossperiod-filing-deadlock` research: `Filing reachability: gate-refusal and silent-grant surface`

RAG-grounded (`uv run --no-sync vaultspec-rag search ... --type code`) survey of the filing pipeline's gate surface, verified at HEAD `7208bb3f0`. It backs the cross-period deadlock ADR and frames the filing-persona campaign under one mandate: make every correctly-computed filing REACHABLE — replace silent or over-strict gate refusals with evidence-disclosing, locally-completable paths so a taxpayer can drive every period of a chain to an export. The campaign's twelve findings (C0 to C4, H1 to H3, M1 to M4) are not independent bugs; they share one root signature — a correct calculation engine sitting behind a gate that either grants silently or refuses without an actionable, locally-completable path.

## Findings

### The unifying root signature

Every persona testimonial reports the same shape: the arithmetic is right, but the pipeline either (a) emits a silent zero / silent grant that under-declares without alerting the operator, or (b) refuses (verify / file / export) with no path the operator can actually complete locally. Live AEAT submission is prohibited, so EXPORT (a `.boe` the human reviews and files) is the local finish line; any gate whose only remediation is "obtain official AEAT evidence" is, for a fresh local reconstruction, an unreachable wall. The mandate splits the remedy by failure mode: a silent path must surface a visible advisory (`no-silent-under-declaration`); an over-strict refusal must offer a locally-completable, evidence-disclosing path (the human still files externally, so the app discloses the basis rather than refusing).

### Failure mode A — over-strict refusal with no locally-completable path

- **C0 (cross-period deadlock).** `work file` aborts `NO_PENDING_OBLIGATION` for any past period (`compute_obligation_schedule` derives the year from `today.year`, `src/aeat/domain/deadlines/_engine.py:474`), and the dependent period's cross-period clean-state gate (`src/aeat/application/calculations/_cross_period_clean_state.py:1033`, demanded at `src/aeat/application/modelo/_verification_actions.py:900`) hard-blocks on official-evidence a never-filed chain cannot produce. Net: only the first period of a chain exports. Decided in the companion ADR — allow late local `work file` with the existing recargo marker, and admit a complete local chain to verify/export with a disclosing advisory.
- **C3 (M100 withholding deps).** Verify raises about 33 blocking `cross_period_dependency_unclean` for withholding/instalment modelos (111/115/123/130/131) an employee never files; no not-applicable path. Same gate (`_cross_period_clean_state.py` requirement derivation), same remedy shape as C0: a profile-state not-applicable suppression mirroring the pre-activity facet.
- **H2 (opaque DRAFT_HAS_ERRORS).** The post-grant workflow gate aborts `DRAFT_HAS_ERRORS` (`src/aeat/application/workflow/_engine.py:856` / `:991`, helper `_engine_helpers.py:70`) with no findings list and no persisted report — a refusal with zero actionable content. Remedy: enumerate the draft ERROR findings into the abort via the typed `Notice` channel.
- **M4 (mandatory casilla 02 at zero).** The required-casilla gate (`src/aeat/application/modelo/_verification_actions.py:1411`) blocks a zero-expense filer until they hand-enter `--casilla 02=0`. Remedy: treat a mandatory numeric casilla with no input as a declared zero (with a visible AVISO), not a refusal.

### Failure mode B — silent grant / silent-zero (under-declaration without alert)

- **C1 (M303 casilla 65 silent-zero).** Absent `jurisdiction_scope` defaults casilla 65 to 0, which silently zeroes casilla 66/71 and the compensación generation (`src/aeat/application/modelo/_profile_binding.py:232`). The operator sees a zero result with no indication the cause is an unset profile field.
- **C4 (M100 resultado chain silent drop).** With the 130/131 relations unsupplied, casillas 0604/0609/0610/0670 are ABSENT from the revision with only a non-blocking AVISO, and the relation ids are not even listed by `bindings list --missing` (`_taxation_comparison.py:146`, settlement chain `test_modelo_100_settlement_chain.py:243`). The resultado silently vanishes — a `no-silent-under-declaration` breach. Remedy: emit every casilla (provenance row even when the bound input is absent) and surface the unmet relation ids.
- **H1 (no ledger base/expense aggregation).** M303 populates cuotas while leaving taxable bases (07/28) at 0 (cuota-without-base, AEAT-rejectable); M130 drops casilla 02; M100 maps no ledger income (`src/aeat/domain/calculations/registry/_ledger_bindings.py`, mesh `src/aeat/application/aggregation/_modelo_bindings.py:443`). The operator must inject every base by hand or silently under-declare.
- **H3 (M200 cuota chain break).** Cuota íntegra (00562) computes correctly but never propagates to cuota a ingresar (00599 stays 0) — a positive-activity entity would silently file zero (`modelos/200/.../records/formulas.toml:206`).
- **The silent-zero machinery is shared.** The absent-binding paths that resolve to a provenance-marked zero are `_bindings_previous_filing.py:84`, `_relation_prefill.py:376`, `_formula_initial_values.py:225`, and the binding aggregation `_modelo_bindings.py:254`. These are correct as a calculation primitive (a genuinely-absent prior IS zero), but the calling surfaces (verify, `bindings list --missing`, CLI rendering) must DISCLOSE which zeros are absent-by-design vs. unset-by-mistake — the C1/C4 defects are the disclosure gap, not the zero itself.

### Cross-cutting: the disclosure plumbing already exists

The remedies are idiomatic because the disclosure machinery is already present and was confirmed by RAG:

- **Advisory findings that keep the grant open.** `_classify_verification_outcome` (`src/aeat/application/modelo/_verification_actions.py:1502`) grants whenever no finding is BLOCKING, so a WARNING advisory discloses without refusing. The established advisory shapes are `unstamped_revision_advisory` and `operator_declared_suppression_advisory` (`_cross_period_clean_state.py`), plus the missing-evidence advisory.
- **Typed Notice channel.** `cli-notices-are-the-only-diagnostic-channel` already mandates one typed `Notice` spine for every operator-facing diagnostic — the route for H2's draft errors and every refusal next-action.
- **Recargo / extemporaneidad infra.** The `Recovery` marker (`src/aeat/domain/deadlines/_models.py:768`, `still_filable=True`, Ley 58/2003 art-27) and the calculate-path recargo notice (`_modelo_rendering.py:223`) already make late filing admissible-with-disclosure — C0's Decision A reuses them.
- **Tiered cross-period bypass.** `_cross_period_clean_state_findings` (`_verification_actions.py:657`) already admits an unclean-at-verdict dependency as non-blocking under a typed condition (the iva-wallet decision bypass) — the template for C0/C3's locally-clean tier.

### Design principle (the mandate, operationalised)

A gate may refuse only when it can name a path the operator can complete WITHOUT contacting AEAT (export is the finish line). Otherwise it must grant-with-disclosure: emit a visible, typed advisory recording the non-official / absent-by-design / late basis, and let the artefact be produced for the human to review and file externally. A silent zero is never acceptable as a final state — every absent or non-official value must surface through the `Notice` / advisory channel. This single principle resolves all twelve findings; the per-finding fix sites are inventoried in the companion reference `2026-06-19-filing-campaign-remediation-reference`, and C0 is decided in `2026-06-19-crossperiod-filing-deadlock-adr`.
