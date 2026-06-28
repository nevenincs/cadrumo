---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - "[[2026-05-21-schema-hardening-plan]]"
---



# `schema-hardening` research: `warning-sidecar-debrief`

This debrief consolidates findings from the singleton semantic-role warning
sidecar work through W14. The purpose is to convert the closed pipeline into a
decision-ready follow-on slice, without turning source-visible legal identity
tokens into blind code normalization.

## Findings

### What changed through W14

The pipeline began with large singleton warning clusters in Modelo 100 and
Modelo 200. The first goal was not to rename roles, but to identify which
clusters were mechanical taxonomy noise and which represented legally specific
or year-specific concepts that must remain explicit.

Implemented hardening removed two broad suppressors:

- Broad autonomous-community token normalization was removed. Region-local
  singletons are now explicit `intentional_singleton` records where reviewed.
- Broad legal-reference token stripping was removed. Article, transitional
  provision, RDLeg, and LIS markers now stay in role identity unless a future
  policy says otherwise.

The current Modelo 100 and Modelo 200 warning census after W14 is:

- 2,262 distinct semantic roles.
- 454 unmarked singleton roles.
- 28 roles marked `intentional_singleton`.
- 0 emitted singleton typo warnings under the current validator.

### Main lessons learned

Repeated labels are not legal equivalence. The same visible caption can appear
under different autonomous-community, deduction-family, article, transitional,
or historic-regime contexts.

Warning suppression and semantic normalization are different operations. A
warning-sidecar helper may be acceptable for avoiding false-positive typo
warnings while still being unsafe as a metadata extractor or registry rewrite.

The safest successful pattern was exact-family allowlisting backed by source
lookup. Examples include Anexo C carryforward baskets, deferred-imputation
slots, and selected family-local generated/pending surfaces.

The least safe pattern is broad token stripping. Removing broad CCAA and
legal-reference suppression exposed legitimate source-specific singletons that
needed explicit registry policy rather than hidden validator behavior.

Intentional singleton markers are useful when the source row is legitimate and
current corpus repetition is absent. They must not become a shortcut for
avoiding source lookup; each marker needs a reason tied to source-visible
identity.

### Remaining broad suppressors

The W14 probe identified two remaining broad warning-suppression surfaces:

- `optional_or_numeric_token_strip`: disables warnings by stripping optional
  tokens and all numeric tokens.
- `axis_token_group`: suppresses one-token differences across mixed token
  groups such as relationship fields, internal/international, roman numerals,
  detail/other, and event date terms.

Disabling individual helpers against the current Modelo 100 and Modelo 200
corpus would expose:

| helper disabled | added warnings | conclusion |
|---|---:|---|
| `optional_or_numeric_token_strip` | 36 | Highest-risk remaining broad suppressor. |
| `axis_token_group` | 17 | Mixed legacy helper needing token-group review. |
| `correction_suffix` | 151 | Expected Modelo 200 correction-table noise; already source-audited as warning-only. |
| exact W08-W13 helpers | 0 | No independent current warning exposure. |

### Optional/numeric exposure examples

The broad optional/numeric helper currently hides several distinct families:

- C Valenciana year-specific public-aid roles, such as
  `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat_2020` vs
  `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat`.
- Estimacion objetiva agricultural variants, such as
  `irpf_eo_reintegro_subvenciones` vs
  `irpf_eo_agr_reintegro_subvenciones`.
- Prizes/gambling public-source or line variants, such as
  `irpf_ganancia_premios_juegos_pub_valoracion_b` vs
  `irpf_ganancia_premios_juegos_valoracion`.
- Cadastral numbered slots, such as `irpf_ganancia_inmueble_catastral_4` vs
  `irpf_ganancia_inmueble_catastral_1_b`.
- Cantabria, C Valenciana, and Murcia generated/pending year and line roles.
- Quoted-fund `coti` gain/loss branches, such as
  `irpf_ganancia_fondos_coti_ganancia` vs
  `irpf_ganancia_fondos_ganancia`.
- Modelo 200 `con mantenimiento de empleo` vs `sin mantenimiento de empleo`
  correction families.

These are not one uniform legal concept. They need source-specific slices.

### Axis-token exposure examples

The mixed `axis_token_group` helper currently hides:

- Anexo C `periodo` vs `aplicado` rows.
- RIC Canarias type-letter rows.
- Declarante birth/death date rows.
- Ascendiente/descendiente identity fields.
- Modelo 200 liquidacion roman-numeral roles.
- DI interna vs DI internacional RDLeg pending rows.
- Detalle vs otras correcciones resultado rows.

Some of these may be legitimate field axes; others are legally meaningful
section or regime identifiers. They should be split token group by token group.

### Recommended follow-on slices

1. Optional/numeric suppressor burn-down discovery. Manually group the 36
   exposed warnings into source families, then choose exact candidates for
   replacement allowlists or explicit singleton markers.
2. Optional/numeric first implementation slice. Replace only one source-backed
   family with an exact helper and tests, leaving the broad helper in place
   until enough families are covered.
3. Axis-token group review. Audit `interna/internacional`, roman numerals,
   `detalle/otras`, relationship, and event-date groups separately.
4. Modelo 200 correction-axis extraction readiness. Convert the already
   audited warning-only correction suffix contract into structured metadata
   only after the mismatch bucket policy is settled.
5. Cadastral family-local review. Continue to block global normalization, but
   inspect exact families where numbered cadastral slots are source-local and
   field-type stable.

### Research conclusion

The next ADR should decide that broad suppressors are debt and must be burned
down through exact, source-grounded families. The immediate sub-plan should
start with optional/numeric stripping because it has the broadest independent
current exposure and the clearest legal-risk profile.
