---
tags:
  - '#audit'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:a3521e89abd0a1c9a49696ed79c4f9170aed41eca82974a415c1721a8d7f2241'
related:
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
  - "[[2026-08-09-profile-requirement-grounding-registry-schema-legal-refs-drift-reference]]"
---

# `profile-requirement-grounding` audit: `orden-hac-1347-2024:art-4 wrongly cited on declarant-identity bindings`

## Scope

## Findings

## Recommendations

## Context

## Scope

Discovered while acting on the campaign's mandatory fresh-context honesty review, which flagged that P08.S35's grounding claim ("real independent grounding evidence") was procedurally overstated - it proves the ref STRING resolves against the catalogue and corpus, not that the ref is semantically apt for the field it is attached to. Spot-checking that gap against the bundled corpus surfaced a real, pre-existing citation defect, not a false alarm.

## Findings

### `orden-hac-1347-2024:art-4` is the annual módulos order, not a declaration-identity authority

Read `src/cadrumo/_data/corpus/normatives/html/orden-hac-1347-2024.html.extracted.md` directly. Its Article 4 heading is "Aprobación de los signos, índices o módulos" - it approves the IRPF estimación objetiva / IVA régimen simplificado módulos tables for 2025. The whole order (articles 1-5) is entirely about which activities fall under módulos, exclusion magnitudes, and renuncia/revocación deadlines. Nothing in it establishes declarant identity, civil status, spouse/descendant facts, or the declaration model itself.

The registry's OWN legal catalogue entry (`_data/registry/aeat/legal/irpf.toml:925-939`) agrees: its `notes` field reads "Aprobacion de signos, indices o modulos de estimacion objetiva aplicables durante 2025" - the catalogue entry correctly describes what the order is; the defect is in which bindings cite it, not in the catalogue entry itself.

### Two legitimate use clusters, one illegitimate one

`grep -rl "orden-hac-1347-2024:art-4"` across the registry returns 85 files. Two clusters are genuinely correct: Modelo 131 (Pagos Fraccionados - IRPF estimación objetiva, the `modulos-*` bindings, formulas, parameters, casillas) and the Modelo 100 2025-revision módulos-adjacent formulas/parameters (`revisions/2025/formulas/0030-...estimacion-objetiva...`, `revisions/2025/parameters/0032-...`, `0033-...`). Both are genuinely about módulos - correct citation.

The third cluster is wrong: roughly 26 `revisions/2024/bindings/*.toml` files for Modelo 100, all `source = "profile"` bindings for declarant-identity and family facts with no módulos connection whatsoever - `0007-...taxpayer-birth-date`, `0008-...declaration-type`, `0027-...tax-id`, `0028-...display-name`, `0029-...taxpayer-sex`, `0030-...marital-status`, `0031/0032/0033/0034/0037/0038/0039/0040-...spouse-*`, `0035/0036-...taxpayer-disability-grade/death-date`, `0041-...family-descendants-eu-eea-deduction`, `0042` through `0052-...family-descendant-*/family-ascendant-*`. Every one of these pairs `orden-hac-1347-2024:art-4` alongside `orden-hac-277-2026:art-3` (the Renta declaration-model-approval order, Article 3 = "Aprobación del modelo de declaración del Impuesto sobre la Renta de las Personas Físicas" - confirmed correct by reading `orden-hac-277-2026.html.extracted.md` directly). The módulos order appears to have been carried alongside the correct declaration-model order as a generic per-binding default, the exact "restrictive/unrelated provision used as a default" pattern this project's own grounding rule warns about.

### This campaign's P08.S35 propagated the defect from bindings to schema

P08.S25 found 24 schema fields with registry-side `legal_refs` and an empty schema field; P08.S35 mechanically carried the registry union onto each field, explicitly reasoning "the citation already exists and was corpus-verified on its registry binding" - which assumed the EXISTING citation was correct, not merely that the ref STRING resolves. It did not independently verify semantic fit. Roughly 20 of the 24 fields S35 touched (`identity.tax_id`, `identity.name`, `identity.surnames`, `renta_taxpayer.*`, `renta_spouse.*`, `renta_family.cotizaciones_ss_madre_2024`, `renta_family.descendants_eu_eea_deduction`, `renta_family.minor_children_in_unit`) now carry `orden-hac-1347-2024:art-4` in their schema `legal_refs`, doubling the surface area of the pre-existing defect (registry bindings AND schema fields, instead of just registry bindings).

## Recommendations

1. **Do not action this fix in the current campaign.** Correcting ~26 registry bindings' `legal_refs` plus ~20 schema fields' `legal_refs` is filing-grade legal-provenance work requiring a human-reviewed pass per this project's calculation-grounding rule ("a legal catalogue entry... is a human-reviewed, filing-grade surface"), not a mechanical strip. `orden-hac-277-2026:art-3` alone appears sufficient for the identity/family cluster - it already covers the concept (declaration-model approval) these fields need - but that should be confirmed per-field, not assumed wholesale, before any citation is removed.
2. **Open as tracked follow-up work**, not silently dropped: remove `orden-hac-1347-2024:art-4` from the ~26 Modelo 100 2024 identity/family bindings and the ~20 schema fields that inherited it via P08.S35, verifying each field's remaining citation (`orden-hac-277-2026:art-3`, plus any field-specific LIRPF article already present) is sufficient on its own.
3. **Generalize the lesson for future grounding-carry work**: a registry citation's mere presence and catalogue/corpus resolvability is NOT evidence it is the RIGHT citation for the field it sits on. A mechanical carry (P08.S35's own pattern) should be paired with at least a spot-check read of the cited article's actual subject matter, not only a catalogue/corpus existence check - exactly the gap the fresh-context honesty review identified and this document closes out with a concrete, corpus-verified finding rather than a procedural note alone.
