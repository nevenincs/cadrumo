---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:4a95f3bac159f7e8c2496854cc289340371033f74d048acf23ba6a3cfdea40d6'
step_id: 'S06'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# Read the twelve modules that assert no provision in either form and record, per module, whether that silence is proper. Nothing measured so far says they are proper and nothing contradicts it, so this row exists to convert an untested assumption into a stated finding. A diagnostic about wiring rather than law correctly carries no provision. The disconfirming observation: any module found asserting a regulatory claim through a channel the earlier regex could not see, such as a formatted or multi-line message, belongs in the P02 population and this row must say so rather than close on the count

## Scope

- `src/cadrumo/application/`

## Description

- Enumerated every `CalculationSourceDiagnostic` construction site across `src/cadrumo/application/` (25 modules, matching the earlier census closely), then classified each SITE (not file) by whether its `message` argument or its `legal_refs`/`asserted_legal_refs` keyword asserts a specific legal provision -- using an AST walk over each construction's own keyword arguments, the same discipline the earlier census used, rather than a file-text grep. A file-text grep over-reports: several files carry `Art.`/`LIVA` strings only in module docstrings or unrelated helper-function comments, never inside a constructed diagnostic.
- Traced every `message=` argument that resolved to something other than a literal or f-string (a bare name, an attribute access, a helper-function call) back to its source, so an indirected message could not hide a legal claim from the scan the way the row's disconfirming observation warns about.
- Read each SILENT module's diagnostics against what they are actually about (missing carry, unresolved binding, storage degradation, operator-override precedence, structural settlement gaps) to judge whether the silence is a wiring diagnostic (correctly silent) or an eligibility/rate claim with no citation (a P02 gap).

## Outcome

**Fifteen modules measured silent, all correctly so.** Every one raises a diagnostic about a MECHANISM -- a missing prior filing, an unresolved binding, a storage-degraded read, an operator value overriding a computed one, a structural (not value-level) settlement gap -- never a claim about what the law requires, so citing nothing is the honest state, not an omission: `_atribucion_member.py`, `_evidence_advisory.py` (the confirmed false positive the ADR excludes by name -- its LIVA art. 97 text sits in the module docstring and two comments, never in a construction), `_oss_ioss.py`, `_source_mesh.py`, `_withholding_source.py`, `_iva_compensation_annual_partition.py`, `_multi_year.py`, `_prorrata_regularizacion.py` (`application/calculations`), `_relation_prefill.py`, `_calculation_source_staging.py`, `_official_box_advisory.py`, `_operator_override_advisory.py`, `_profile_binding.py`, `_rate_box_advisory.py`, `_settlement_grade_advisory.py`.

The row and its governing ADR say "twelve"; this measurement finds fifteen. Stated rather than reconciled to the prior figure -- the population moved under concurrent campaign work between the ADR's writing and this row's execution, and forcing agreement with a number instead of the current tree would be exactly the silent-drift failure `no-hardcoded-counts` exists to catch.

**Two disconfirming observations, escalated rather than fixed here.**

1. `_calculate_input.py` carries SEVEN sites the earlier census's channel could not see, spanning two legal topics, every one prose-only with zero typed grounding: four maternidad sites (`_maternidad_ceilings_unresolved_advisory`, `_maternidad_cotizaciones_ceiling_advisory`, `_maternidad_ambiguous_relacion_advisory`, `_maternidad_meses_withheld_advisory`) asserting Art. 58.1, Art. 61 norma 2ª and Art. 81.1 LIRPF, and three DT 12ª sites (`_dt12_window_decision` x2, `_dt12_parcial_guidance_advisory`) asserting LIRPF DT 12ª.4 (Ley 26/2014). This is a genuinely new P02 population, not a subset of anything already adjudicated in this feature's P02.S03/S04. **It bears directly on the standing art-81 HARD GATE**: `ley-35-2006:art-81-1` has no catalogue entry of its own -- only the whole-article `art-81` exists, the same two-vintage-excerpt entry the S03 gate already excludes four `_minimo_descendientes_advisory.py` sites over. Grounding these four maternidad sites hits the identical wall the moment anyone tries. The DT 12ª sites are different: `ley-35-2006:dt-12` already resolves cleanly (the sibling `_dt12_advisory.py`/`_dt12_antiquity_advisory.py` already cite it via `ModeloVerificationFinding`), so those three are adjudicatable now with no gate.
2. `_modelo_bindings.py::_recargo_rate_mismatch_diagnostics` asserts LIVA art. 161 (the recargo de equivalencia rate-pairing article) in a prose-only message with zero typed grounding. `ley-37-1992:art-161` resolves cleanly in the live catalogue. One site, no casilla in reach (the diagnostic is per-invoice, not per-casilla), so `asserted_legal_refs` is the mechanism a P02-shaped row would use.

## Notes

**One channel in `_modelo_bindings.py` is left unmeasured, honestly.** Six sites there build their message from `issue.detail`, a string carried on `aggregation.issues` entries rather than authored inline at the construction site. Tracing every producer of `aggregation.issues` to confirm none of them format a legal citation into `.detail` is a materially larger trace than this row's per-site AST read, and was not completed. Recorded as unmeasured rather than asserted clean -- if a later pass finds a legal claim riding through that channel, it belongs in the P02 population exactly as the row's disconfirming observation anticipates, and this note is why it would not be a surprise.

**No file was modified by this Step.** Read-only measurement and recording, as the row asks; the two escalations above are handed off rather than grounded here, consistent with `advisory-grounding` P02 (per-site adjudication) belonging to a different agent's delivered scope on this same feature during this campaign.
