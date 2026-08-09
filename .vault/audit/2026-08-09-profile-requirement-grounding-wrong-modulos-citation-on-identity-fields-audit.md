---
tags:
  - '#audit'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:a50f8c3f944f21fc7a10bc7d53257e366f613b2502c7bea750ce24a0ee79ea1c'
related:
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
  - "[[2026-08-09-profile-requirement-grounding-registry-schema-legal-refs-drift-reference]]"
---

# `profile-requirement-grounding` audit: `orden-hac-1347-2024:art-4 wrongly cited on declarant-identity bindings`

## Status: RESOLVED

Fixed directly at the operator's request, after this document's own Recommendations section had deferred it as human-reviewed legal-provenance work. See the Resolution section below for what changed and how it was verified; the original Findings and Recommendations are preserved unmodified beneath it as the record of what was found and why it was initially left open.

## Context

Discovered while acting on the campaign's mandatory fresh-context honesty review, which flagged that P08.S35's grounding claim ("real independent grounding evidence") was procedurally overstated - it proves the ref STRING resolves against the catalogue and corpus, not that the ref is semantically apt for the field it is attached to. Spot-checking that gap against the bundled corpus surfaced a real, pre-existing citation defect, not a false alarm.

## Scope

Every registry file under `_data/registry/aeat/modelos/100/revisions/2024/` and every `schema.toml` field citing `orden-hac-1347-2024:art-4` for a declarant-identity or family-facts concept - bindings, casillas, the owning construct, the completeness manifest, and the schema fields that inherited the citation via P08.S35's carry.

## Findings

### `orden-hac-1347-2024:art-4` is the annual módulos order, not a declaration-identity authority

Read `src/cadrumo/_data/corpus/normatives/html/orden-hac-1347-2024.html.extracted.md` directly. Its Article 4 heading is "Aprobación de los signos, índices o módulos" - it approves the IRPF estimación objetiva / IVA régimen simplificado módulos tables for 2025. The whole order (articles 1-5) is entirely about which activities fall under módulos, exclusion magnitudes, and renuncia/revocación deadlines. Nothing in it establishes declarant identity, civil status, spouse/descendant facts, or the declaration model itself.

The registry's OWN legal catalogue entry (`_data/registry/aeat/legal/irpf.toml:925-939`) agrees: its `notes` field reads "Aprobacion de signos, indices o modulos de estimacion objetiva aplicables durante 2025" - the catalogue entry correctly describes what the order is; the defect is in which bindings cite it, not in the catalogue entry itself.

### Two legitimate use clusters, one illegitimate one

`grep -rl "orden-hac-1347-2024:art-4"` across the registry returns 85 files (later measured as 89 once casillas and the completeness manifest were counted - see Resolution). Two clusters are genuinely correct: Modelo 131 (Pagos Fraccionados - IRPF estimación objetiva, the `modulos-*` bindings, formulas, parameters, casillas) and the Modelo 100 2025-revision módulos-adjacent formulas/parameters (`revisions/2025/formulas/0030-...estimacion-objetiva...`, `revisions/2025/parameters/0032-...`, `0033-...`). Both are genuinely about módulos - correct citation.

The third cluster is wrong: roughly 26 `revisions/2024/bindings/*.toml` files for Modelo 100, all `source = "profile"` bindings for declarant-identity and family facts with no módulos connection whatsoever - `0007-...taxpayer-birth-date`, `0008-...declaration-type`, `0027-...tax-id`, `0028-...display-name`, `0029-...taxpayer-sex`, `0030-...marital-status`, `0031/0032/0033/0034/0037/0038/0039/0040-...spouse-*`, `0035/0036-...taxpayer-disability-grade/death-date`, `0041-...family-descendants-eu-eea-deduction`, `0042` through `0052-...family-descendant-*/family-ascendant-*`. Every one of these pairs `orden-hac-1347-2024:art-4` alongside `orden-hac-277-2026:art-3` (the Renta declaration-model-approval order, Article 3 = "Aprobación del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas" - confirmed correct by reading `orden-hac-277-2026.html.extracted.md` directly). The módulos order appears to have been carried alongside the correct declaration-model order as a generic per-binding default, the exact "restrictive/unrelated provision used as a default" pattern this project's own grounding rule warns about.

### This campaign's P08.S35 propagated the defect from bindings to schema

P08.S25 found 24 schema fields with registry-side `legal_refs` and an empty schema field; P08.S35 mechanically carried the registry union onto each field, explicitly reasoning "the citation already exists and was corpus-verified on its registry binding" - which assumed the EXISTING citation was correct, not merely that the ref STRING resolves. It did not independently verify semantic fit. Roughly 20 of the 24 fields S35 touched (`identity.tax_id`, `identity.name`, `identity.surnames`, `renta_taxpayer.*`, `renta_spouse.*`, `renta_family.cotizaciones_ss_madre_2024`, `renta_family.descendants_eu_eea_deduction`, `renta_family.minor_children_in_unit`) now carry `orden-hac-1347-2024:art-4` in their schema `legal_refs`, doubling the surface area of the pre-existing defect (registry bindings AND schema fields, instead of just registry bindings).

## Recommendations

As originally written, superseded by the Resolution below:

1. ~~Do not action this fix in the current campaign.~~ Superseded: the operator explicitly requested the fix, which is the human review this recommendation was waiting for.
2. ~~Open as tracked follow-up work, not silently dropped.~~ Superseded: actioned directly instead of deferred.
3. **Still valid, generalize the lesson for future grounding-carry work**: a registry citation's mere presence and catalogue/corpus resolvability is NOT evidence it is the RIGHT citation for the field it sits on. A mechanical carry should be paired with at least a spot-check read of the cited article's actual subject matter, not only a catalogue/corpus existence check.

## Resolution

Fixed by replacing `orden-hac-1347-2024:art-4` with `orden-hac-242-2025:art-3` across every file in the wrongly-cited cluster. `orden-hac-242-2025:art-3` - "Aprobación del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas", published 2025-03-14 - is the exact filing-year-2024 counterpart of the already-verified-correct `orden-hac-277-2026:art-3` (filing-year-2025), confirmed by reading `orden-hac-242-2025.html.extracted.md`'s own Article 3 heading directly, and already used elsewhere within the same 2024 revision (deadline windows, casillas, completeness manifest) before this fix.

**Full corrected scope** (larger than the original Findings' "~26 bindings, ~20 schema fields" - the original sweep only covered `source=profile` bindings and schema, not the casilla layer or the completeness manifest that both also carried the citation):

- **29** `revisions/2024/bindings/*.toml` files (the original estimate of 26 undercounted by 3).
- **30** `revisions/2024/casillas/*.toml` files - the casilla-level `legal_refs` declarations, a layer the original sweep did not cover.
- **1** construct (`constructs/0013-renta-2024-personal-family.toml`) - required by a registry-build validation gate that checks a construct's `legal_refs` covers every member binding's `legal_refs`; the registry failed to load until this was fixed too.
- **1** completeness manifest entry (`completeness/0001-manifest.toml`), recomputed from the live `calculation_closure_legal_refs` projection after the casilla/binding fix rather than hand-derived, and verified to match it exactly (`manifest_refs == closure_refs`).
- **20** schema.toml fields, recomputed from the live (corrected) `build_profile_grounding_index` union rather than a blind string swap.
- **2** Python test files (`test_profile_readiness_gate.py`, `test_services.py`) that had hardcoded the wrong citation as an expected/example value; corrected to the real one.

**Verification:**

```
uv run --no-sync python -c "from cadrumo.core.resources import resources; resources().modelos.authority"
(loads and validates cleanly - previously raised RegistryValidationError naming the construct/binding legal_refs mismatch until the construct was fixed)
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py -m unit
484 passed, 72 deselected in 85.95s (0:01:25)
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/domain/user_profile/tests/test_schema.py src/cadrumo/domain/calculations/registry/tests/ -m unit
55 failed, 3827 passed, 23 deselected in 738.47s (0:12:18)
```

All 55 failures triaged and confirmed unrelated: every one traces to `binding 'renta-2024-profile-deduccion-maternidad' has no supplied value` (a completely separate Modelo 100 2024 binding, file `0067-renta-2024-profile-deduccion-maternidad.toml`, numbered well outside the 0007-0052 identity/family range this fix touched) or to pre-existing Modelo 303/390 record-design relayout findings, neither of which shares a file with anything this fix changed - confirmed by grep (zero overlap) and by reproducing one failure in total isolation (`test_0610_equals_0595_minus_0609` alone, same error, same root cause). This is pre-existing ambient tree state unrelated to this fix, not a regression it introduced.

Zero remaining references to `orden-hac-1347-2024:art-4` anywhere under `revisions/2024/` (confirmed by `grep -rl`); the two legitimate módulos clusters (Modelo 131, Modelo 100's own 2025-revision módulos formulas) are untouched.

**Known follow-up this fix unblocks, not yet actioned**: a separate concurrent session's `cli-verb-profile-diagnostics` campaign (`P15.S51`) deliberately left two censal fiscal-ID refusal messages in unenriched prose specifically because grounding them would have surfaced this now-fixed citation. That disposition's own stated trigger ("becomes correct once the citation is fixed") now holds; picking it up is a small, separately-scoped task (two call sites plus their locale strings) for a future pass, not folded into this fix.
