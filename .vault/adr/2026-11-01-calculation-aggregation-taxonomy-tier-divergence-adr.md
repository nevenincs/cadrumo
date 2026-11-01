---
tags:
  - '#adr'
  - '#calculation-aggregation-taxonomy'
date: '2026-11-01'
modified: '2026-11-01'
body_schema: 'body-v2'
body_hash: 'sha256:3b7a555452a8f393d07a175cf05b4625950b6264a694aa12b4b729e064dacc05'
related:
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-09-27-export-parity-renta-withholding-sources-adr]]"
  - '[[2026-06-10-calculation-aggregation-taxonomy-research]]'
  - '[[2026-09-27-export-parity-renta-withholding-sources-research]]'
---

# `calculation-aggregation-taxonomy` adr: `Block filing-bound precedence tier divergence instead of overwriting silently` | (**status:** `proposed`)

This is a proposed amendment to the accepted `2026-06-10-calculation-aggregation-taxonomy-adr`, drafted on the operator's ruling of 2026-11-01. The accepted record is unchanged until this proposal is authorized; the wording to apply then is given under "Proposed wording for the accepted record". It realises the amendment that `2026-09-27-export-parity-renta-withholding-sources-adr` (Constraints) announces and that its Step 4 relies on.

## Problem Statement

Implementation item 5 of the accepted taxonomy record declares the decimal precedence ladder profile, backend mesh, borrador, caller. Inside the mesh a duplicate claim is a hard error, but across tiers the higher tier simply wins. The accepted text treats this as safe because "the engine's consistency check adjudicates divergence". The code shows that no such check exists at the tier boundary.

- `resolve_calculation_binding_channels` builds the four tiers and overlays them with `merge_source_resolutions_by_precedence` (`src/cadrumo/application/modelo/calculation_resolution.py:171-182`, `src/cadrumo/application/aggregation/source_resolution_operations.py:357-366`). That overlay is `absorb_by_precedence` (`:172-180`), whose value step is plain `dict.update` on the decimal, enum, date and boolean channels (`:231-235`), with no comparison. The relation channel is overlaid the same way (`:256-258`).
- Two lower tiers never see the contest at all, because they drop the higher tier's keys before resolving. The profile tier excludes every binding the caller, borrador or backend supplied (`src/cadrumo/application/modelo/binding_resolution.py:147-153`). The borrador resolver skips caller-owned bindings (`src/cadrumo/application/modelo/borrador_binding.py:208`). The value that lost is never computed, so it cannot be compared.
- The operator's 2026-09-27 ruling in the export-parity record is that any disagreement between sources blocks until it is resolved and no source silently wins. Once the Modelo 100 credit casillas gain several sources (suffered-withholding records, borrador, ledger), the silent overlay becomes a route by which a filed figure replaces a different one without anyone seeing both.

## Considerations

These are the transitions that actually change a value today, measured at HEAD of `feature/renta-withholding`.

- **Profile versus a higher tier: suppression, not overwrite.** Profile resolves only the keys no higher tier supplied (`binding_resolution.py:147-153`), so the overlay never replaces a profile value. The live case is the 2025 Modelo 100 CCAA binding `renta-profile-tax-residence-ccaa`. It is profile-sourced and marked `aeat_prefilled` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/revision.toml:10382-10385`), so a borrador CCAA suppresses the profile CCAA unseen. A caller `--binding` on a profile binding suppresses it the same way, because the caller-override guard protects only mesh-owned sources (`src/cadrumo/application/modelo/calculation_bucket_actions.py:425-430`, `:495-502`).
- **Backend versus profile: no overlap.** Each binding declares one source, and profile is pre-mesh. A binding cannot be both, so the two never meet.
- **Borrador over backend: a real overwrite, latent today.** The borrador tier admits only bindings marked `aeat_prefilled` (`borrador_binding.py:185-195`, `:440-441`). Today the only decimal one is the `manual_input` 0596 certificate binding `renta-certificado-trabajo-retenciones` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:156-162`), and no backend resolver produces it, so nothing is overwritten yet. Plan Step P03.S06 moves `aeat_prefilled` onto the suffered-withholding bindings that a mesh resolver fills. From then on, the `dict.update` at `source_resolution_operations.py:231-235` replaces the certificate value with the borrador value without comparing them.
- **Caller over borrador: suppression.** The borrador resolver omits caller-owned keys (`borrador_binding.py:208`).
- **Caller over backend: a real overwrite, live today, for carry sources only.** The caller-override guard refuses LOCK sources before and after the mesh. It deliberately lets the CARRY tier through: `previous_filing`, `relation_prefill`, `iva_compensation_annual_partition`, `prorrata_regularizacion` and `activity_asset_disposal` (`src/cadrumo/application/aggregation/source_precedence.py:53-91`, `src/cadrumo/application/modelo/calculation_bucket_actions.py:495-502`). These mesh resolvers do not receive the caller's values, so they resolve the carried value and the caller tier replaces it in the overlay. `_reconcile_caller_overrides` then drops the matching unresolved advisory (`calculation_bucket_actions.py:291-350`). Nothing compares the two values.
- **Caller relation over relation_prefill: a real overwrite.** `merged_relation_values` lays caller `--binding`-derived and `--relation` values over the resolved relation values (`calculation_bucket_actions.py:322-326`).
- **Caller casilla over bound input: a real overwrite with a non-blocking advisory.** `_merge_bucket_bound_inputs` (`calculation_bucket_actions.py:964`) and `resolve_calculation_inputs` (`calculation_resolution.py:262-268`) let `--casilla` win over a bound value. `collect_operator_override_divergence_diagnostics` already reports the case where the values differ, and only that case (`src/cadrumo/application/modelo/_operator_override_advisory.py:48-96`, equality at `:75`), but the report is advisory. This is the existing prior art for exact both-present, both-different detection.
- **Previous-filing casilla lift: no overwrite.** It promotes a casilla override only where no binding value resolved (`binding_resolution.py:408`).
- **IVA wallet: outside the ladder.** It strips the M303 compensation binding before the mesh and raises `ModeloIvaWalletReconciliationBlocked` on conflict (accepted record, item 5). That remains as decided.
- **A blocking channel already exists.** Persisted `CalculationSourceIssue` rows on the calculation revision (`src/cadrumo/domain/modelos/calculation_revision_sources.py:231`) whose reason is in `GATE_REFUSED_REASONS` (`src/cadrumo/application/modelo/calculation_notes.py:67-77`) make `require_no_blocking_calculation_notes` refuse check, export and local filing (`src/cadrumo/application/modelo/calculation_note_gate.py:55-80`). Calculation and preview still run. That matches the posture plan Step P01.S01 sets for advisory values.
- "Filing-bound binding" exists only in prose. There is no typed flag. The typed concepts available are the revision's declared `RegistryAuthorityGrade` (`src/cadrumo/core/authority_grade.py:46-76`), a casilla's `input_kind`, `binding` and `alternate_bindings`, `export_refs` and `internal_only` (`src/cadrumo/domain/calculations/registry/schema_surfaces.py:419-490`), and the formula reference walkers (`src/cadrumo/domain/calculations/registry/runtime_graph.py:51-173`).

## Considered options

- **Keep the silent overlay and rely on advisories.** Rejected. It contradicts the operator's 2026-09-27 ruling and the no-silent-under-declaration discipline, and its own premise, an engine-side consistency check, does not exist at the tier boundary.
- **Make every tier exclusive, as inside the mesh, so any overlap is a hard calculation error.** Rejected. Equal values from two tiers would refuse, and so would legitimate corroboration (borrador agreeing with a certificate). Calculation and preview would become unusable while a source is being corrected.
- **Detect divergence only in the reconciliation step of export-parity Step 4, per casilla.** Rejected as the only control. Step 4 covers the declared cross-checks of the Modelo 100 credit casillas. The precedence overlay serves every modelo, and its overwrites would still be silent everywhere else.
- **Chosen: the overlay compares, and a divergent replacement on a filing-bound binding persists a blocking finding.** The ladder order stays. Equal values are silent. A difference persists a typed finding that blocks check, export and local filing until the source is corrected or an operator resolution record covers the exact values. Calculation and preview proceed with the ladder's winning value and show the finding.

## Constraints

- The ladder order of accepted item 5 stays: profile, backend mesh, borrador, caller. Intra-mesh exclusivity stays a hard error. LOCK refusals (`reject_caller_overrides_of_source_bindings`) stay. D3 (the IVA wallet's exclusive ownership and its refusal on conflict) is reaffirmed, not reopened.
- No per-modelo branches. The detector is one modelo-agnostic mechanism in the precedence overlay, and its scope is derived from typed registry data, not from modelo names or an allowlist.
- No new registry authoring field. Whether a binding is filing-bound is derived when the registry is hydrated, so the registry stays free-form.
- The operator resolution record is owned by `2026-09-27-export-parity-renta-withholding-sources-adr` Step 4 and plan Step P04.S20, and this record does not redesign it. The finding's envelope is shared with the Step 4 reconciliation finding, whose schema plan Step P01.S12 grounds.
- Per-binding capability grade is decided by the concurrently drafted `binding-capability-grade` ADR (plan Step P01.S01). This record depends on that ADR only as follows. A binding's capability grade decides whether its value may be filed. Filing-boundness decides whether a divergence on it blocks. The two block independently, and neither substitutes for the other.
- Private amounts are persisted only inside the encrypted calculation revision and the encrypted resolution record. They never appear in logs or plaintext caches.

## Implementation

We will replace the silent cross-tier overwrite with a comparing overlay. A higher tier that replaces a different lower-tier value on a filing-bound binding persists a blocking `precedence_tier_divergence` finding. The scope is plan Step P04.S07 of `2026-11-01-export-parity-plan`. Its write set is `src/cadrumo/application/aggregation/source_resolution_operations.py`, plus the tier construction and caller-channel merges it must reach: `calculation_resolution.py`, `binding_resolution.py`, `borrador_binding.py`, `calculation_bucket_actions.py`, `calculation_notes.py` and the domain helper that derives filing-boundness. Any path correction to that Step is recorded through the plan verbs.

1. **Filing-bound binding, defined.** A binding B of revision R is filing-bound when both of the following hold:
   - R's declared `authority_grade` is `RegistryAuthorityGrade.FILING`. The test reads the declared grade, not the rung the operation pins, because calculate pins `CALCULATION` (`src/cadrumo/application/modelo/_calculation_preparation.py:207`) while its persisted revision feeds check and export.
   - B reaches an exported casilla, meaning a casilla with non-empty `export_refs`. B reaches it either as its `binding` or one of its `alternate_bindings` on a `BOUND` casilla, or transitively: as a decimal, enum or date operand of a formula whose target feeds an exported casilla, or as the `target_binding` of a relation that does. An `internal_only` casilla on the path does not break the reach.
   - A binding consumed only by verification predicates, or by casillas without `export_refs`, is not filing-bound. The same goes for any binding in a revision graded below `FILING`.
   - The set is computed once per hydrated revision by a domain function beside `runtime_graph.py`, and the overlay consumes it. Relations and casilla inputs are filing-bound by the same reach rule.
2. **Equality.** Two values are equal only on the same typed channel:
   - `money`, `decimal` and `integer` use exact numeric `Decimal` equality, so `10.0` equals `10.00`. There is no tolerance and no rounding before comparison; registry rounding belongs to formulas, not inputs (`src/cadrumo/domain/calculations/registry/schema_rounding.py:13-37`). A sub-cent difference is a divergence.
   - `enum` compares the canonical typed-enum token after the resolver's own normalisation, never a label.
   - `date` uses calendar-date equality.
   - `boolean` uses identity.
   - `text` uses exact equality after the binding's declared normalisation.
   - A value of the same binding arriving on two different channels is a channel defect and stays refused by `reject_binding_channel_mismatch`; it is not a divergence.
3. **When a finding arises.** A finding arises only when two tiers both hold a value for the same key and the values differ.
   - A lower tier that is absent, unresolved or inapplicable is a fill, not a divergence, and produces no finding.
   - Equal values produce no finding and no advisory.
   - To make suppression comparable, the profile and borrador tiers resolve without excluding higher-tier keys, and the overlay alone decides precedence. This changes `binding_resolution.py:147-153` and `borrador_binding.py:208`. A lower tier that fails to resolve a key because a higher tier was meant to supply it reports absence, not an error. That last point is an implementation hypothesis to confirm against the profile resolver's required-fact refusals.
   - The covered transitions are borrador over backend, borrador over profile, caller over profile, caller over borrador, caller over carry-sourced backend values, caller relation over `relation_prefill`, and caller casilla over a bound input.
   - On a binding that is not filing-bound, a divergence is a non-blocking advisory with the same shape.
4. **Typed shape.** The finding carries the following fields:
   - reason `precedence_tier_divergence`;
   - modelo, filing year, period and work unit;
   - registry revision id and authority generation;
   - the binding, relation or casilla key, and the exported casillas it reaches;
   - the value channel;
   - the ordered tiers that held a value. Each tier gives its name (`profile`, `backend`, `borrador`, `caller`), resolver id, binding source kind, typed value and provenance (`source_ref` and fingerprint, or the borrador snapshot id);
   - the tier the ladder selected.

   It is persisted as a `CalculationSourceIssue` on the calculation revision. Its reason joins `GATE_REFUSED_REASONS` and the catalogue in `calculation_notes.py`, with locale text authored through `dev.locales`. The existing `operator_override_diverges_from_computed` advisory becomes this finding on filing-bound casillas and stays advisory elsewhere.
5. **Where it blocks and where it only informs.**
   - Calculation and preview persist a BORRADOR revision with the ladder's winning value and show the finding.
   - Check (verify), export and local filing refuse through `require_no_blocking_calculation_notes` while the finding is open. The finding also reaches the CLI handoff and the calculation report.
   - The IVA wallet keeps its calculation-time refusal.
6. **Resolution.**
   - Either correct the source in error, so that recalculation yields equal values and no finding: drop the override, deactivate or replace the borrador snapshot, fix the certificate or ledger record, or correct the profile fact.
   - Or create the operator resolution record of export-parity Step 4, which plan Step P04.S20 implements, keyed to modelo, revision, key, each tier with its value, and a stated reason.
   - The record accepts the ladder outcome; it never selects a different value. To file a lower tier's value, the operator removes the higher tier's source.
   - The record clears exactly its keyed finding and stops clearing it as soon as any keyed value changes.
   - A bare `--binding` or `--casilla` is not a resolution, because it states no reason and is not keyed to the value it replaced.
7. **Persistence and replay.**
   - The finding, with every tier's value, is persisted inside the encrypted calculation revision beside the existing replay overrides (`calculation_resolution.py:309`). Check and export therefore compare a resolution record against persisted values without resolving again.
   - Replaying a persisted revision under its pinned authority generation reproduces the same finding.
   - The revision records that the tier screen ran. Check, export and local filing refuse a revision persisted before this screen existed and give a recalculate remedy, because the absence of a finding there is not evidence of agreement. Revisions already `PRESENTADO` keep their history and are not re-adjudicated.
8. **Tests.** All run through the real overlay, resolvers and gate:
   - a per-channel equality table, covering `10.0` against `10.00`, a sub-cent difference, enum token against label, a date, and a boolean;
   - one case per covered transition producing exactly one finding with every tier's value and provenance;
   - equal values producing nothing;
   - an absent lower tier producing nothing;
   - a non-filing-bound binding producing an advisory, not a blocking finding;
   - LOCK refusal and the IVA wallet block unchanged;
   - an encrypted round trip of a persisted finding;
   - refusal in check, export and local filing;
   - a resolution record clearing exactly its key, and not clearing it after a keyed value changes (jointly with P04.S20);
   - an unscreened legacy revision refused;
   - the derivation of the filing-bound set, against a hand-built revision with direct, alternate, transitive-formula, relation-target and `internal_only` paths.

   The detector-teeth fixture is an isolated synthetic revision whose two tiers disagree on a filing-bound binding. It is run through two variants: one where the overlay value step is restored to bare `dict.update`, and one where a lower tier is built with a higher-tier exclusion list. The gate must fail on both. `test_precedence_ladder_conformance.py` additionally binds the overlay order to `CALLER_OVERRIDE_PRECEDENCE_LADDER`, whose docstring wrongly attributes the overlay to `merge_source_resolutions`.

## Rationale

The ladder answers which value the calculation uses. It never answered whether a filing may rest on a contested value, and the accepted record assumed a consistency check that does not exist. Blocking only filing-bound divergence keeps calculation and preview useful while a source is corrected. It leaves corroboration silent and puts the cost exactly where a wrong figure would reach AEAT. Deriving filing-boundness from authority grade and export reach avoids a hand-maintained flag that would drift. Reusing the persisted blocking channel and the Step 4 resolution record gives one disagreement vocabulary instead of two. Making the lower tiers resolve unconditionally is the only way to see the suppression cases, which are the commonest form of silent replacement today.

## Consequences

- Gains: no tier can silently replace a different filed value. Borrador, certificates and operator overrides become visible, auditable claims rather than winners, and the 0596 to 0606 credit work in P03 and P04 lands on a ladder that already refuses silent replacement.
- Costs: lower tiers do more resolution work. A new persisted reason, catalogue entry and locale text. A legacy-revision recalculation requirement.
- Workflow change: operators who override carried values must add a resolution record before checking or exporting. A recorded live invocation such as `--binding irpf.previous_year_economic_activity_net_income=<total>` (accepted record, amendment of 2026-08-13) now blocks until it is resolved, wherever the carried value differs.
- Reconsider if the resolution-record friction on legitimate carry overrides proves disproportionate. The candidate refinement is an override that carries its reason and mints the keyed record in the same invocation; it is not decided here.

## Impact on other modelos and what they must do

The overlay is shared, so the change reaches every modelo whose revision is graded `FILING`. Sessions working on other domains in parallel must do the following before or alongside P04.S07.

- **IVA (M303, M390; wallet sessions).** D3 is unchanged. The changes are these:
  - Caller overrides of `prorrata_regularizacion` and `iva_compensation_annual_partition` values that differ from the resolved value now block.
  - On filing-bound casillas, the casilla-channel operator override of a bound input becomes blocking. The documented case is the provisional prorrata percentage of LIVA art. 105.Uno (`_operator_override_advisory.py:1-11`).
  - IVA sessions must re-run their command-sequence and evaluation goldens, classify every new finding as a genuine divergence or a fixture artefact, and supply resolution records or corrected fixtures. They must not add exclusions.
- **Pagos fraccionados and Renta carries (M130, M131, M100).** Caller overrides of `previous_filing` carries and of `relation_prefill` folds (for example the M100 0604 fold) block on divergence. The 2025 M100 CCAA binding starts comparing profile against borrador.
- **Informative and annual reconciliations (M180, M190, M193, M200, M202, M353).** Caller overrides of relation and per-member carries block on divergence. Each owning session confirms its revision's declared authority grade, since revisions below `FILING` get advisories only.
- **Asset disposal (`activity_asset_disposal`).** The box shared with the filer is in the CARRY tier, so the same rule applies.
- **Registry authors, all modelos.** Do not mark a binding `aeat_prefilled` where a backend resolver also fills it unless the divergence that follows is intended. Do not grade a revision `FILING` to silence or to trigger the screen; grading follows the existing build rules.
- **Frontends (CLI, TUI, desktop, MCP projections).** Render the new blocking reason through the shared catalogue. The attention mapping in `calculation_notes.py` covers it. No frontend decides the outcome.
- **New resolvers or tiers.** Enroll under the ladder and this screen. A pre-exclusion list in a lower tier is a defect that the teeth gate detects.

## Proposed wording for the accepted record

To be applied to `2026-06-10-calculation-aggregation-taxonomy-adr` only once this proposal is authorized, as a dated amendment section. Accepted item 5 stays in place and is annotated "amended 2026-11-01".

> **Amendment 2026-11-01: tier divergence on filing-bound bindings blocks.** The precedence ladder of item 5 is unchanged in order. A higher tier that replaces a different lower-tier value on a filing-bound binding no longer wins silently: the overlay compares typed values exactly and persists a `precedence_tier_divergence` finding naming each tier, its value and its provenance. While the finding is open, check, export and local filing are refused; calculation and preview proceed with the ladder's value. Equal values produce no finding. The finding is resolved by correcting the source or by the operator resolution record of `2026-09-27-export-parity-renta-withholding-sources-adr` Step 4. Lower tiers resolve without excluding higher-tier keys, so that suppression is compared too. The phrase "the engine's consistency check adjudicates divergence" in item 5.4, and "the D2 carve-out extension ... is the relief valve" under Consequences, are read under this amendment. Caller overrides of carried values remain permitted, and a divergent one blocks until it is resolved. `iva_wallet_decision` remains outside the ladder (D3).

## Open questions

- Should a caller override be able to carry its reason and mint the keyed resolution record in the same invocation? Deferred to the P04.S20 design, with operator ruling.
- Should the casilla-channel override of a bound input on filing-bound IVA casillas, the prorrata provisional, block, or is it a narrowly keyed exception with legal grounding? This needs an operator ruling, because the operator's "any disagreement blocks" rule was stated for the Modelo 100 credits.
- Does the profile resolver refuse a required fact when a higher tier was meant to supply it? If so, unconditional resolution needs an absence result there. This must be confirmed against `src/cadrumo/application/aggregation/source_profile.py`.
- Is the finding envelope shared with the Step 4 reconciliation finding as one type, or as two types on one persisted reason? P01.S12 settles it.
