---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S13'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---




# Ratchet UNMODELED_OBLIGATIONS toward AEATs full form set and promote each to a grounded registry definition.

## Scope

- `src/aeat/_data/registry/aeat/modelos`

## Description

- Promote Modelo 216 (IRNR retenciones e ingresos a cuenta) out of `UNMODELED_OBLIGATIONS` into a grounded registry definition, per the S13 ratchet.
- Ground the M216 approving orden and its binding filing-deadline provision against the bundled authoritative corpus and the IRNR legal catalogue before authoring the registry manifest, revision, and deadline windows.

## Outcome

M216 is PROMOTED. It is removed from `UNMODELED_OBLIGATIONS`, is now a registry-loadable modelo, and its trimestral deadline windows resolve. The recognized-unmodeled residual drops to 25.

The corpus gap that blocked the prior pass is now closed. The binding deadline provision (Orden EHA/3290/2008 art 4) was fetched verbatim from the BOE consolidated text (BOE-A-2008-18497) and added to the bundled corpus, so the deadline window is grounded in the establishing provision rather than in guidance-tier instructions.

Corpus and legal catalogue authored:

- `src/aeat/_data/corpus/normatives/html/orden-eha-3290-2008.html` - new corpus excerpt carrying art 1 (aprobacion del modelo 216) at anchor `#a1` and art 4 (plazo de presentacion) at anchor `#a4`, both verbatim from BOE-A-2008-18497. Art 4 carries the trimestral plazo ("veinte primeros dias naturales de los meses de abril, julio, octubre y enero") and the grandes-empresas mensual modality.
- `orden-eha-3290-2008:art-1` and `orden-eha-3290-2008:art-4` legal-catalogue entries in `legal/irnr.toml`, both evidence_tier `legal_authority`, document_id BOE-A-2008-18497, corpus_ref resolving to the new bundled file, each with a distinctive `required_text` the evidence gate cross-checks against the corpus at build (art 4 pins "veinte primeros dias naturales de los meses de abril, julio, octubre y enero"). `reviewed_by` provenance is honest: agent-prepared, corpus-grounded, pending operator re-stamp.

Registry definition authored (`modelos/216/`, revision `2024-y-siguientes`, mirroring the M296 IRNR sibling under the same Orden HAC/56/2024 layout):

- manifest + revision: tax_domain irnr, cadence profile_based, legal_refs citing orden-hac-56-2024:art-1 (current form), orden-eha-3290-2008:art-1 (approval), orden-eha-3290-2008:art-4 (plazo), trlirnr-rdleg-5-2004:art-24 (withholding base). RD 1776/2004 art 15.1 was deliberately NOT cited: it is not in the bundled catalogue, and this pass does not fabricate a citation.
- casillas (money closure grounded in the bundled AEAT M216 instructions): 08/09 bases dineraria/especie, 10 base total, 11/12 retenciones dineraria/especie, 13 retenciones total, 20 resultados anteriores, 21 resultado a ingresar. Casilla 21 carries semantic_role `cuota_a_ingresar` with the canonical non_negative constraint shape.
- formulas: 10 = 08 + 09, 13 = 11 + 12, 21 = 13 - 20 (grounded in the instructions' own printed total rows).
- deadline_windows: 8 trimestral windows (2025 1T-4T, 2026 1T-4T), opening first-of-month, closing on day 20 (Apr/Jul/Oct/Jan following each natural quarter), each legal_refs = orden-eha-3290-2008:art-4 (legal_authority) with an official_source_guidance source, satisfying the deadline-window source-tier gate. The monthly grandes-empresas modality is out of this revision's scope.
- constructs, application_links (9 surfaces), completeness-manifest (closure = the 3 computed totals + 5 operands), reconcile-when-present verification (min_coverage 0), workbook_parity_refs.

Enum reconciliation: M216 removed from `UNMODELED_OBLIGATIONS` in `core/_modelo.py`; the enum member `Modelo.M216 = "216"` stays. It is now registry-backed, so the derived `CANONICAL_MODELO_FLEET` grows to 47 and the authorization-gate fleet-count test was updated (46 -> 47, name + docstring) as a grounded ratchet, matching the prior M182 promotion pattern.

## Gate evidence

- `bundled_authority()` loads and `validate_registry()` passes with M216 present (full-registry validation, includes verify_legal_catalogue with the new EHA/3290/2008 required_text cross-check).
- `auth.deadline_windows(2025, modelos=("216",))` returns the four trimestral windows Apr 20 / Jul 20 / Oct 20 / Jan 20; 2026 likewise.
- `test_modelo.py` (enum registry-parity) - 5 passed.
- `test_modelo_216_registry.py` (new durable test: validator accept, construct ownership, art-4 deadline grounding, day-20 windows derived from statute, engine computes 10/13/21) - passed.
- `test_deadline_window_source_tiers.py` - passed.
- `test_obligation_coverage.py` - passed (M216 dynamically excluded from the unmodeled advisory set).
- `test_modelo_authorization_gate.py` - 5 passed after the 47 fleet-count update.
- Registry collect-only clean (no import/collection errors).

## Notes

- Ratchet remains OPEN: 25 recognized-unmodeled obligations remain; S13 stays unchecked as a recurring ratchet step.
- Locale leaves DEFERRED: the four locale catalogues (`ca.yml`, `en.yml`, `es.yml`, `hu.yml`) are peer-staged (`MM`) in the shared index, so the M216 locale labels were not authored this pass to avoid clobbering peer WIP. Follow-up: `python -m aeat.locales modelo scaffold <locale> 216 2024-y-siguientes` once the locale WIP lands.
- Out-of-scope pre-existing failure observed and NOT owned by this surface: `test_catalogue_verification_normatives.py::test_orden_hac_242_2025_art_8_deadline_links_to_full_boe_corpus` asserts a stale sha256 for the `orden-hac-242-2025` corpus (committed-HEAD drift last touched by peer commit `2479085a8e`, unrelated to M216).
- RAG grounding queries this pass: code search "M210 IRNR registry modelo definition deadline window"; "legal catalogue corpus_ref required_text evidence gate legal grounding"; "deadline window trimestral quarterly opens closes first twenty natural days"; followed by targeted grep confirmation of the M296 IRNR sibling structure, the deadline-window source-tier gate, the `cuota_a_ingresar` canonical role, and the existing M216 source_refs.
