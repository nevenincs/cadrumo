---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-04'
modified: '2026-07-17'
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

Batch 1 (2026-07-04): M222 and M220 are PROMOTED, dropping the residual 25 -> 23 and growing `CANONICAL_MODELO_FLEET` 47 -> 49. See the "Batch 1" section below.

Batch 2 (2026-07-04): six M182-template informativas (165, 233, 156, 038, 185, 186) are PROMOTED, dropping the residual 23 -> 17 and growing `CANONICAL_MODELO_FLEET` 49 -> 55. See the "Batch 2" section below.

Batch 3 (2026-07-04): five further informativas (179, 181, 270, 234, 238) are PROMOTED, dropping the residual 17 -> 12 and growing `CANONICAL_MODELO_FLEET` 55 -> 60. See the "Batch 3" section below.

Final tail (2026-07-04): the remaining 12 recognized-unmodeled obligations are PROMOTED, dropping the residual 12 -> 0 and growing `CANONICAL_MODELO_FLEET` 60 -> 72. The ratchet is now COMPLETE: `UNMODELED_OBLIGATIONS` is EMPTY. See the "Final tail" section below.

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

## Batch 1 (2026-07-04): M222 + M220 (IS consolidación fiscal, grupos)

Both are PROMOTED from `UNMODELED_OBLIGATIONS`, dropping the residual 25 -> 23 and growing `CANONICAL_MODELO_FLEET` 47 -> 49 (auth-gate fleet-count test bumped 47 -> 49, name + docstring). Enum members `Modelo.M222`/`Modelo.M220` stay; only the UNMODELED entries were removed. Both are grounded strictly against corpus that was ALREADY bundled (no BOE fetch was needed, none was fabricated).

M222 (pago fraccionado IS en régimen de consolidación fiscal — quarterly) has GOLD-tier self-contained grounding in the bundled Orden HFP/227/2017 (BOE-A-2017-2778), the same orden that approves M202:

- Two new legal-catalogue entries in `legal/is.toml`: `orden-hfp-227-2017:art-2` (M222 approval, anchor `#a2`, required_text pins "Se aprueba el modelo 222" + "Régimen de consolidación fiscal") and `orden-hfp-227-2017:art-5` (the plazo article naming 222, anchor `#a5`, required_text pins "modelo 222, pago fraccionado a cuenta del Impuesto sobre Sociedades para los grupos fiscales" + "primeros veinte días naturales de los meses de abril, octubre y diciembre"). Both `legal_authority`, cross-checked against the bundled corpus at build; `reviewed_by` honest agent-prepared, pending operator re-stamp.
- Registry `modelos/222/`, revision `2025-y-siguientes`: manifest (tax_domain is, cadence quarterly, legal_refs art-2 + art-5 + `ley-27-2014:art-40`), declaration-header casillas (decl.ejercicio filing_year, decl.tipo-declaracion), construct, 3 application_links (deadline/filing/workflow), workbook_parity_ref (record-design anchor), and 6 trimestral deadline_windows (2025+2026 1P/2P/3P) each `legal_refs = orden-hfp-227-2017:art-5`, opening first-of-month Apr/Oct/Dec and closing on day 20 (derived strictly from the statutory "primeros veinte días naturales", not from engine output).

M220 (declaración anual IS del grupo fiscal — annual) has SILVER-tier grounding: the bundled Orden HAC/657/2025 excerpt (BOE-A-2025-12818) was transcribed for M200 and carries the dedicated "Se aprueba el modelo 220" approval clause only in the untranscribed part of art 1; the bundled text names 220 verbatim once, in art 3 (pago mediante domiciliación bancaria, "Modelos 200 y 220").

- One new legal entry `orden-hac-657-2025:art-3` (anchor `#modelo-200`, required_text pins "Modelos 200 y 220, mediante domiciliación bancaria" + the July domiciliation window) — the bundled provision of the approving orden that names Modelo 220. Its notes state plainly that the dedicated 220-approval clause is not in the bundled excerpt. The binding filing plazo is the general IS declaration plazo of `ley-27-2014:art-124` (already bundled, verbatim "25 días naturales siguientes a los 6 meses posteriores a la conclusión del período impositivo").
- Registry `modelos/220/`, revision `2024-y-siguientes`: manifest (tax_domain is, cadence annual, legal_refs art-3 + art-124), declaration-header casillas, construct, 3 application_links, workbook_parity_ref, and 2 annual deadline_windows (2024/2025 0A) `legal_refs = ley-27-2014:art-124`, opening 1 July and closing on the 25th natural day (advanced to the next business day at year end), mirroring the sibling M200 windows.

Both revisions are deliberately scheduling/applicability-grade (declaration-header casillas only, no formulas): no authoritative Modelo 222 or 220 diseño de registro is bundled in the corpus, so authoring numbered money-closure casillas would fabricate form structure. That calc surface is deferred until a DR is bundled; no casilla number was invented.

Batch 1 gate evidence:

- `bundled_authority().validate_registry()` passes with M222 + M220 present (full-registry validation incl. legal-catalogue required_text cross-check of the three new entries).
- `deadline_windows(2025, ("222",))` = 1P/2P/3P Apr 20 / Oct 20 / Dec 20; `(2026,("222",))` likewise. `deadline_windows(2024,("220",))` = 0A 1 Jul -> 25 Jul; `(2025,("220",))` = 1 Jul -> 27 Jul.
- New durable tests `test_modelo_222_registry.py` (5) + `test_modelo_220_registry.py` (5) pass: validator accept, approval/plazo grounding tier + document_id, deadline-provision citation, statute-derived windows, and registry-backed / out-of-UNMODELED assertions.
- `test_modelo.py` (enum parity) 5, `test_modelo_authorization_gate.py` 5 (fleet 49), `test_obligation_coverage.py`, `test_deadline_window_source_tiers.py` 4 — all pass. Touched-surface collect-only clean (registry/core/overview: 3950 collected, 0 errors).
- Pre-existing, not owned: `entrypoints/mcp/tests/test_client_handshake.py` + `test_serving_gates.py` fail collection with `ModuleNotFoundError: pywintypes` (pywin32/MCP env gap, unrelated to this registry change).
- RAG grounding queries this batch: `vaultspec-rag` code search "M202 IS pago fraccionado registry modelo deadline window" and "registry legal catalogue corpus_ref required_text evidence gate plazo"; vault `--doc-type adr,research` "UNMODELED_OBLIGATIONS ratchet promote registry modelo grounded"; followed by targeted grep confirmation of the M202/M200 sibling structure, the M347 minimal-modelo shape, the HFP/227/2017 art-2/art-5 corpus anchors, and the deadline-window source-tier gate.

## Batch 2 (2026-07-04): six M182-template informativas (165 / 233 / 156 / 038 / 185 / 186)

All six are PROMOTED from `UNMODELED_OBLIGATIONS`, dropping the residual 23 -> 17 and growing `CANONICAL_MODELO_FLEET` 49 -> 55 (auth-gate fleet-count test bumped 49 -> 55, name + docstring). Every one is GOLD-tier grounded against corpus that was ALREADY bundled (transcribed under prior operator-authorized fetch); no new fetch was needed and nothing was fabricated. Each bundled orden carries BOTH an approval article (art 1, anchor `#a1`) and a plazo article with pinnable verbatim text — confirmed by reading all six corpus files before grounding.

Per-form grounding (each: a new `legal/modelo-<n>.toml` with the approval entry, the plazo entry, and the two per-modelo sources — `enrolled-modelo-<n>-procedure` official_source_guidance + `enrolled-modelo-<n>-layout` layout_authority — mirroring `modelo-182.toml`; plus a registry tree mirroring the Batch-1 declaration-header shape):

- 165 (certificaciones a socios de entidades de nueva/reciente creación, ANNUAL) — Orden HAP/2455/2013 (BOE-A-2013-13798); approval art 1 `#a1`, plazo art 4 `#a4` ("se realizará en el mes de enero de cada año"). 3 annual January windows (2024-2026).
- 233 (gastos en guarderías / educación infantil, ANNUAL) — Orden HAC/1400/2018 (BOE-A-2018-17772); art 1 + art 4 (enero). 3 annual windows.
- 156 (cotizaciones afiliados/mutualistas deducción maternidad, ANNUAL) — Orden HAC/3580/2003 (BOE-A-2003-23509); art 1 + art 4 ("entre los días 1 y 31 de enero del año siguiente"). 3 annual windows.
- 038 (operaciones de entidades en registros públicos, MENSUAL) — Orden HAC/66/2002 (BOE-A-2002-1041); art 1 + plazo art 6 `#a6` ("durante cada mes natural respecto de las inscripciones autorizadas en el mes inmediato anterior"). 12 monthly windows (2025), each closing the last natural day of the following month.
- 185 (informativa mensual cotizaciones afiliados/mutualistas, MENSUAL) — Orden HAC/1197/2025 (BOE-A-2025-21726); art 1 + art 4 ("diez días naturales siguientes a la finalización del mes"). 12 monthly windows (2025), each closing the 10th of the following month.
- 186 (nacimientos y defunciones, Registro Civil, MENSUAL) — Orden HAC/539/2003 (BOE-A-2003-5304); art 1 + art 4 ("el del mes natural siguiente ... con una periodicidad mensual"). 12 monthly windows (2025), last natural day of the following month.

Grade: all six are scheduling/applicability-grade — declaration-header casillas (`decl.ejercicio` filing_year, `decl.tipo-declaracion`) only, no formulas, no detail-row bindings. No authoritative diseño de registro is bundled for any of the six, so no numbered form casilla is fabricated (the M182 detail-row donor bindings were NOT copied — that schema is 182-specific and grounded in its own DR). The two header casillas reuse M347/M182's proven `filing_year` / `tipo_declaracion` roles.

Batch 2 gate evidence:

- `bundled_authority().validate_registry()` passes with all six present (full-registry validation incl. legal-catalogue required_text cross-check of the 12 new legal entries against the six bundled corpus files, and the source sha256 match).
- Deadline windows resolve: `deadline_windows(2024,("165"/"233"/"156",))` = 1 Jan -> 31 Jan 2025; `deadline_windows(2025,("038"/"186",))` = 12 monthly windows each opening the 1st and closing the last natural day of the following month; `("185",)` = 12 windows closing the 10th of the following month.
- New parametrized durable test `test_modelo_informativas_batch2_registry.py` (6 modelos x validator-accept + approval/plazo grounding + deadline-cadence + annual/monthly window resolution + out-of-UNMODELED) — 45 passed together with test_modelo.py, test_modelo_authorization_gate.py (fleet 55), test_obligation_coverage.py, test_deadline_window_source_tiers.py.
- Touched-surface collect-only clean (registry/core/overview: 3966 collected, 0 errors). Pre-existing/unowned: `entrypoints/mcp` tests still fail collection on `ModuleNotFoundError: pywintypes` (env gap, unrelated).
- Committed as a single atomic commit (all six together): splitting per-form would leave a broken intermediate state, because the enum removal of a modelo from `UNMODELED_OBLIGATIONS` without its committed registry tree breaks the `registry_modelo_codes == enum - NON_REGISTRY` parity gate. All six were built and green together, so one atomic commit is the correct clean state.
- RAG grounding queries this batch: `vaultspec-rag` code "M182 informativa registry modelo deadline window enrolled procedure source" and "monthly deadline window period_kind monthly period token format"; then grep-confirmed the M182 template (legal file + two per-modelo sources + minimal tree), the M111 monthly window period format ("2025 01"), and read all six bundled corpus files verbatim to pin approval + plazo required_text.

## Batch 3 (2026-07-04): five informativas (179 / 181 / 270 annual, 234 / 238 event-driven or RGAT-delegated)

All five are PROMOTED from `UNMODELED_OBLIGATIONS`, dropping the residual 17 -> 12 and growing `CANONICAL_MODELO_FLEET` 55 -> 60 (auth-gate fleet-count test bumped 55 -> 60). Every one is grounded against corpus already bundled; every orden was pre-verified bundled AND every corpus file read before grounding, confirming each carries an approval article (art 1, `#a1`) and a plazo article with pinnable verbatim text. Nothing was fabricated.

Three are clean annual-January (full calendar deadline windows, exactly the Batch-2 shape):

- 179 (cesión de viviendas con fines turísticos, ANNUAL) — Orden HAC/612/2021 (BOE-A-2021-10163); art 1 + art 4 "entre el 1 y el 31 de enero de cada año". 3 annual January windows (2024-2026).
- 181 (préstamos/créditos y operaciones financieras sobre inmuebles, ANNUAL) — Orden EHA/3514/2009 (BOE-A-2009-21165); art 1 + art 6 "entre el día 1 y el 31 del mes de enero de cada año". 3 annual windows.
- 270 (resumen anual retenciones premios de loterías, ANNUAL) — Orden HAP/2368/2013 (BOE-A-2013-13228); art 1 + art 3 "en el mes de enero de cada año". 3 annual windows.

Two carry NO calendar deadline windows — a deliberate, non-fabricated deadline-shape decision (the lead flagged this and endorsed "note the deadline-shape"):

- 234 (DAC6 mecanismos transfronterizos, EVENT-DRIVEN) — Orden HAC/342/2021 (BOE-A-2021-5780); art 1 approval + art 4 plazo "en el plazo de los treinta días naturales siguientes al nacimiento de la obligación" (per RGAT art 46.3, RD 1065/2007). This is a per-event 30-día deadline, NOT a calendar window; RGAT art 46 is not bundled, so NO deadline_windows and no deadline application link are authored — a fixed date is not fabricated. cadence = `profile_based`.
- 238 (DAC7 operadores de plataformas, ANNUAL) — Orden HAC/72/2024 (BOE-A-2024-2092); art 1 approval + art 9 plazo "tendrá carácter anual y su plazo de presentación será el establecido en el apartado 6 del artículo 54 del Reglamento General" (RD 1065/2007). The orden delegates the specific window to RGAT art 54.6, which is not bundled and does not state the month verbatim; rather than fabricate the January dates, NO deadline_windows and no deadline link are authored. The annual periodicity and the plazo article are grounded verbatim. cadence = `annual`.

Both windowless modelos validate: the registry validator requires a revision to declare at least one casilla and official workbook-parity coverage (both satisfied), and only enforces "deadline_windows require a deadline application link" (vacuously true when there are none) — it does NOT require a revision to carry deadline windows. RGAT confirmation: `rg` found only `rd-1065-2007` arts 3/10/11/18/54-bis bundled — arts 46 and 54.6 are absent, so the event/delegated windows are genuinely ungroundable from the bundled corpus.

Per modelo: a new `legal/modelo-<n>.toml` (approval + plazo legal_authority entries with corpus_ref + required_text, and two per-modelo sources mirroring modelo-182.toml) + a declaration-header registry tree (manifest, revision, two header casillas, application_links, construct, workbook_parity_ref; plus deadline_windows only for 179/181/270). No detail casillas, no bindings — no bundled DR, so no form casilla fabricated.

Batch 3 gate evidence:

- `bundled_authority().validate_registry()` passes with all five present (incl. legal-catalogue required_text cross-check of the 10 new legal entries and source sha256 match).
- `deadline_windows(2024, ("179"/"181"/"270",))` = 1 Jan -> 31 Jan 2025; `deadline_windows(2025, ("234"/"238",))` = [] (windowless, by design).
- New parametrized test `test_modelo_informativas_batch3_registry.py` (validator accept, approval/plazo grounding, window-shape per modelo, annual resolution, event/delegated windowlessness, out-of-UNMODELED) — 42 passed together with test_modelo.py, test_modelo_authorization_gate.py (fleet 60), test_obligation_coverage.py, test_deadline_window_source_tiers.py.
- Touched-surface collect-only clean (registry/core/overview: 3984 collected, 0 errors). Pre-existing/unowned: `entrypoints/mcp` `pywintypes` collection error (env gap).
- Committed atomically (all five together) — same parity-gate reasoning as Batch 2.
- RAG grounding queries this batch: `vaultspec-rag` code "informativa registry modelo event-driven deadline window RGAT 30 días" and "registry validator revision requires deadline windows or casilla workbook parity"; then grep-confirmed the bundled RGAT article set (arts 46/54.6 absent), the validator's per-revision requirements (`_validate_revision_sections.py`, `_validate_application_links.py`), and read all five bundled corpus files verbatim.

## Final tail (2026-07-04): remaining 12 obligations -> residual 0

The last 12 recognized-unmodeled obligations were PROMOTED across four atomic commits, closing the ratchet. `UNMODELED_OBLIGATIONS` is now EMPTY (residual 0) and `CANONICAL_MODELO_FLEET` / `FLEET_SIZE` reached 72. Every promotion followed the established grounded-registry-definition pattern (approval + plazo legal-catalogue entries with corpus_ref + required_text, a registry tree, deadline windows only where the bundled corpus states them verbatim); nothing was fabricated, and deadline-shape decisions (windowless where the establishing provision was ungroundable from the bundled corpus) were preserved.

Commits:

- `ab78e1ee73` — promote M848 and land the grounder's M341/M380 out of `UNMODELED_OBLIGATIONS` (25 files, grounder WIP preserved).
- `774a35ac3b` — promote M140 + M143 (IRPF solicitudes de abono anticipado).
- `7f9668cbaf` — promote M490 / M604 / M763 (new-tax autoliquidaciones) and extend `TaxDomain` for the new tax families.
- `119898311a` — promote the final tail M592 / M576 / M121 / M122; residual `UNMODELED_OBLIGATIONS` now 0.
- `ddc5508d89` — ratchet the canonical fleet-count authorization gate 62 -> 72 after the final grounding.

Final tail gate evidence (re-verified at HEAD this pass):

- `UNMODELED_OBLIGATIONS` residual is 0 (`len(UNMODELED_OBLIGATIONS) == 0`).
- `bundled_authority().validate_registry()` passes with all 72 modelos present (full-registry validation incl. the legal-catalogue required_text cross-checks and source sha256 matches for every promoted form).
- `FLEET_SIZE == 72` (derived from `CANONICAL_MODELO_FLEET`).
- `test_obligation_coverage.py` — 10 passed (the coverage report partitions the full AEAT universe into disjoint buckets with an empty recognized-unmodeled residual).
- `access_gate` authorization suite — 10 passed at fleet 72.

## Notes

- Ratchet CLOSED: `UNMODELED_OBLIGATIONS` is empty (residual 0), so every recognized AEAT obligation is now a grounded registry definition. S13 is closed. Any future AEAT-published form re-opens the ratchet as a fresh promotion, but no residual remains to carry.
- Historical (superseded): earlier passes of this record noted the ratchet OPEN after Batches 1-3 (residual 12). That is now resolved by the Final tail above.
- Locale leaves DEFERRED: the four locale catalogues (`ca.yml`, `en.yml`, `es.yml`, `hu.yml`) are peer-staged (`MM`) in the shared index, so the M216 locale labels were not authored this pass to avoid clobbering peer WIP. Follow-up: `python -m aeat.locales modelo scaffold <locale> 216 2024-y-siguientes` once the locale WIP lands.
- Out-of-scope pre-existing failure observed and NOT owned by this surface: `test_catalogue_verification_normatives.py::test_orden_hac_242_2025_art_8_deadline_links_to_full_boe_corpus` asserts a stale sha256 for the `orden-hac-242-2025` corpus (committed-HEAD drift last touched by peer commit `2479085a8e`, unrelated to M216).
- RAG grounding queries this pass: code search "M210 IRNR registry modelo definition deadline window"; "legal catalogue corpus_ref required_text evidence gate legal grounding"; "deadline window trimestral quarterly opens closes first twenty natural days"; followed by targeted grep confirmation of the M296 IRNR sibling structure, the deadline-window source-tier gate, the `cuota_a_ingresar` canonical role, and the existing M216 source_refs.
