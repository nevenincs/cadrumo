---
tags:
  - '#research'
  - '#casilla-schema'
date: '2026-08-10'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:21bbb47f272aded86a64b8daed7cb44c995888761f65e7853bb741dd4ca3dc1f'
related: []
---

# `casilla-schema` research: `modelo review projection discovery roll-up`

Question: what must a per-casilla read surface (CLI JSON and the planned TUI review screen) carry, and which code answers each of its questions today? This document rolls up six independent verification passes (including one blind re-derivation given questions with no expected values) plus an architecture pass that re-derived every canonicity claim. The evidence picture: the write side (registry -> engine -> persistence) is sound; the read side answers five operator questions in multiple competing places; and the step from a correct COUNT to a claim of the form "X is the canonical authority" failed repeatedly and must be re-checked every time it is made.

## Findings

### Measurement basis

Every figure below is a working-tree measurement taken 2026-08-10 unless marked HEAD. At the time of measurement HEAD did not import: `src/cadrumo/application/modelo/_preconditions.py:66` used `NoRecoveryOutcome` with no import at HEAD (the working tree adds it at line 17), so no runtime probe reaching `application.modelo` was possible at HEAD. The working tree carried a registry restructure and heavy churn; peers edit live.

The six basis-tracked numbers, re-measured at any new pin via a probe through `cadrumo.domain.calculations.registry.bundled_authority` (HEAD basis first, working-tree basis second):

- registry revisions: 91 vs 94 (M303 `2023-y-siguientes` replaced on disk by a four-revision split)
- relation (revision, relation) pairs: 75 vs 78
- relation-declaring revisions: 19 vs 22
- export-exemption casillas: 24 vs 42
- revisions with a completeness manifest: 53 vs 56
- revisions without one: 38 vs 38 (invariant across bases; tracked because it is the progress denominator population)

The root cause of three earlier rounds of moving numbers was mixing these two bases, not disagreement about the code. Any measurement pin must contain the committed registry restructure, or every 94-basis gate in the campaign is measured against a 91-basis corpus.

### Five operator questions with competing answers

**Q1 - does this casilla file an official box.** Four addressing mechanisms exist: CASILLA-kind export fields plus `row_field_casilla_ids` (derived by `fixed_width_record_casilla_ids`, `src/cadrumo/domain/calculations/registry/_export.py:138`, whose docstring declares it the sole derivation and documents the deliberate BINDING-field residual declared via `ExportExemptionReason.FILED_VIA_BINDING_FIELD`, `src/cadrumo/core/_export_exemption_reason.py:79`); xml-dictionary entries (M100 family); binding-record-derived fields (`derive_export_layouts_from_bindings`, `_export.py:90`); and runtime `bound_inputs_by_casilla_id` injection, which no build-time authority can see. Decoy answers measured wrong: numeric `casilla.number` (non-numeric on 32/129 M303, 30/2093 M100, 29/88 M390); `export_refs` (equals the canonical derivation on 87/94 revisions, understates on 7 - M349: 4 named vs 13 derived, 9 real boxes would read unfiled). 61 of 94 revisions declare no layout at all, so a boolean answer is fabricated for the majority of the corpus.

**Q2 - what counts as complete.** The only gated denominator is `revision.completeness_manifest` = calculation closure MINUS `internal_only`. Only the lower bound is gated: the missing-closure failure (`src/cadrumo/domain/calculations/registry/_validate_completeness.py:41-68`) refuses a manifest omitting a non-internal closure casilla, while nothing enforces that a manifest entry belongs to the closure - that inclusion holds by convention (0 violations observed). Absent on 38/94 revisions, 10 of which declare more than 5 casillas (largest M145 at 50) - there the denominator is UNDEFINED, not zero. Decoy: `len(revision.casillas)` understates M200 progress ~58x (manifest 56 vs declared 3250). Coverage spread: M130 100%, M390 98%, M303 62% (80 of 129, closure 82), M100 29% (600 of 2093), M200 1.7%, M036 3%. A ratio-token refusal already exists on ONE payload (`src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py:36`, seven tokens including `completeness`) with a denominator-trust reason and a `denominator_note` prose alternative; its reasoning is denominator-specific, not a tree-wide ban.

**Q3 - how does a relation reach a casilla.** Corpus: 78 (revision, relation) pairs across 22 revisions, 9 modelos, 0 unconsumed. Channel split (independently derived 4 times): casilla.binding 41, alternate_bindings 3 (all factual_evidence), formula-to-relation 34, formula-to-binding 0. The binding-only predicate resolves 44/78 (56%) and is blind to ALL 14 instalment_to_final_settlement relations. The most complete predicate in the tree lives ONLY in a test (`src/cadrumo/domain/calculations/registry/tests/test_cross_period_relation_consumption.py:52-73`) and implements THREE channels - its index at line 54 reads `casilla.binding` only, never `alternate_bindings`. It still scores 78/78 because the three alternate-fed relations are `factual_evidence`, filtered out by the value-feeding role set before the predicate runs. The full union is therefore a four-channel contract of which no complete implementation exists anywhere; a promotion must add the alternates channel, and a gate that only asserts 78/78 cannot detect its absence. `audit_registry_relation_handoffs` (`src/cadrumo/domain/calculations/registry/_handoffs.py:199-205`) joins via `bound_casilla_binding_ids` only and tolerates empty `target_casilla_ids` by design - it is the binding-channel inventory, NOT the full predicate.

**Q4 - where does a value come from.** Irreducibly three layers that must stay separate: declared (`InputKind`, 4 members), concrete (`BindingSourceKind`, 27 members, plus formula/operand lineage), realised (`ModeloValueKind`, 5 members). Collapsing loses the two live signals: a computed casilla landing EMPTY (broken chain) and a bound casilla landing LITERAL (operator override). The `modelo.requires` classifier (`src/cadrumo/application/modelo/_data_inventory.py:179-202`) buckets manual/ledger/profile only, reads `casilla.binding` never `alternate_bindings`, and by its own comment drops BOUND casillas sourced `previous_filing` / `relation_prefill` / `live_observation` - exactly the cross-period population.

**Q5 - what is blocking.** The one question with NO canonical answer anywhere: ~20 closed vocabularies, ~800 members, 11 mappings. `CrossPeriodCleanStateBlocker` has 21 members ending at `REGISTRY_REVISION_DIVERGENCE` (`src/cadrumo/application/calculations/_cross_period_models.py:49-91`; an earlier round published 23, and a later cold-reader pass re-asserted 23 by merging the adjacent `NoPriorObligationProvenanceKind` enum - both wrong the same way, the count is 21). `ModeloVerificationFindingKind` 7 x severity 2 x `VerificationCompletenessStatus` 3 (`src/cadrumo/domain/modelos/_verification_report.py:81-121`). The `modelo.readiness` payload carries three untyped-shape lists - `missing`, `missing_bindings`, `ledger_issues` - referred to throughout this feature as the readiness triple. Two duplicate enums carry the same four concepts with incompatible wire tokens: `DiscrepancyCause` (UPPER, `src/cadrumo/application/verification/_schema.py`) and `VerificationDiscrepancyCause` (lower, `src/cadrumo/domain/calculations/registry/_schema_verification.py`). A total-by-construction exemplar exists: `BLOCKING_REASON_BY_DISCREPANCY_KIND` (`src/cadrumo/application/ledger/_confirmation_gate.py:69-102`) maps every `DraftDiscrepancyKind` member and raises at import when one is unmapped.

### Envelope inventory

71 registered `modelo.*` schemas across 12 payload files, 66 distinct classes (`register_schema`, `src/cadrumo/core/json_contract.py:611`; also called non-decoratively, so a decorator grep undercounts). Grains differ: `modelo.work.calculate` and `modelo.casillas` (`CasillaRowPayload`, `src/cadrumo/entrypoints/cli/_modelo_payloads.py:825`) are casilla-grain and native; `modelo.work.verify` is finding-grain with `casilla_id` populated at only 8 of 34 construction sites - the 26 unset sites span 18 files, with `application/modelo/_verification_cross_period.py` carrying 9 (including every `CROSS_PERIOD_DEPENDENCY_UNCLEAN` emission, which never populates) and `_verification_actions.py` 8; the remainder are one-or-two-site advisory modules discoverable by a `ModeloVerificationFinding(` grep. `modelo.readiness` is binding/transaction-grain; `modelo.work.dependencies` carries source-side casillas only. Transport widening: `CrossPeriodDependencyEvidencePayload.blockers` is the typed enum domain-side, widened to `tuple[str, ...]` at TWO sites in `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py` (:341, :348) - boundary-only, not an untyped domain. One undocumented loss: finding `message_facts` are not copied onto the `Notice`, so blocker codes reach the envelope only as prose.

### Gap taxonomy A - registry data oversights (no design decision needed)

A-01 M720 boxes invisible to every casilla-keyed authority (layout declares 2 records with 0 inline fields; 43 binding-kind fields exist only after `derive_export_layouts_from_bindings`). A-02 dictionary parser digits-only while the casilla-id convention changed in 2024 (`src/cadrumo/domain/calculations/registry/_export_parse.py:254-260`; M100 non-numeric ids by revision 2020-2025: 0,0,0,0,30,33 - the NEWEST revisions are the divergent ones). A-03 manifest ships in four on-disk shapes (single-shape glob yields 22 of 53). A-04 phantom source kind `constant_value` at 4 production sites (`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:639,762`, `src/cadrumo/application/state_projection.py:782`, `src/cadrumo/application/modelo/_required_binding_gate.py:41`). A-05 `_BINDING_SOURCE_TO_READINESS` dict at `_modelo_discovery_cli.py:638-655`: 21 of 27 `BindingSourceKind` members fall through to the literal "ledger source", ungated, stranded in entrypoints. A-06 M200 multi-segment manifest retains internal-only `DP200014:bin-aplicada-maxima` while a single-segment-branch comment in `_record_design_coverage.py` denies the possibility. A-07 dormant enum members (`profile_schedule`, `UNRESOLVED_BINDING`, `INVALID_WAIVER`, 2 exemption reasons). A-08 the `no-silent-under-declaration` rule cited `_OFFICIAL_SOURCE_KINDS`, which does not exist in production; the live mechanism is `ObservationSourceKind.is_official_aeat` (corrected in the rule harness as part of this feature). A-09 initially classified 38 manifest-absent revisions as authoring debt; S80 canonical-closure adjudication corrected this to 38 manifest-absent revisions, 38 zero-closure revisions, and 0 required-manifest gaps.

### Gap taxonomy B - architectural, with the honest cut

Load-bearing: B-01 no blocker vocabulary spine (Q5). B-02 the discoverable surface is not the live surface - `application/verification` (sole export `verify_declaracion`, `_verify.py:448`, zero production importers while registry `application_links` TOML declares it a consumer), `verify_export`/`DeclaracionVerifyVerdict` (facade-exported at `src/cadrumo/application/filing/__init__.py:181,186,931,984`, production callers zero, test caller the fichero-BOE roundtrip gate), and the strict `resolve_bound_inputs_by_casilla_id` (production uses the permissive sibling). B-03/B-09 the provenance join fragmented 13 ways - including a divergent last-write-wins copy on a refusal path (`src/cadrumo/application/modelo/_calculation_modelo_adjustments.py:169-180`, ignores alternates) and three unfactored grouping loops (`src/cadrumo/domain/calculations/registry/_queries.py:838,854`, `src/cadrumo/application/calculations/_relation_prefill.py:1131-1133`) - while the consumption contract lives only in a test. B-05/B-08 the accepted `2026-05-21-state-read-projection-adr` is contradicted: `src/cadrumo/application/overview/_pipeline_health.py:178,194-214` reconstructs readiness from finding severities plus `CalculationRevisionState` with zero reads of `VerificationCompletenessStatus` / `granted_verificado_completo`, so INCOMPLETE renders as CALCULATED, indistinguishable from never-verified. B-11 no stable measurement base.

Reclassified as noise or non-gaps: B-04 (mostly a data problem; once A-01/A-02 land, three of four mechanisms fold into two existing facade functions; the runtime-injection residual is inherently build-time-invisible and owned by the export completeness gate), B-06 (a decision already recorded once, carrying an open scope question, not a defect), B-07 (severity collapse is documented design; only the `message_facts` drop is a defect), and B-11 as architecture (it is process).

### Existing assets confirmed reusable

Facade-exported and correct for their scope: `bound_casilla_binding_ids` (`src/cadrumo/domain/calculations/registry/_bindings.py:488`, exported `registry/__init__.py:987`; filters to BOUND, raises on a BOUND casilla with no binding, includes alternates), `fixed_width_record_casilla_ids`, `derive_export_layouts_from_bindings`, `derive_rate_box_partitions` (`registry/__init__.py:1024`). Private but production-critical: `resolve_calculation_binding_channels` (`src/cadrumo/application/modelo/_calculation_resolution.py:104`, absent from the package facade), `_casillas_by_binding` (`src/cadrumo/domain/calculations/registry/_rate_box_partition.py:164-180`; includes alternates but does NOT filter to BOUND - divergent by construction from `bound_casilla_binding_ids`, corpus-equivalent today because 0 non-BOUND casillas carry a binding). Both current consumers of the latter reach it through the facade-exported `derive_rate_box_partitions`, so there is no live boundary violation; promotion is a precondition of the NEW consumer. `CasillaProducerInventory` (`_schema.py:1148`) is a different grain, not a duplicate. The layered contract permits the read model in `application` and bars it from `core`/`domain` (`.importlinter:300-307` layers; domain barred from application at `.importlinter:49-127`); `adapters -> application` is the sanctioned direction (`src/cadrumo/adapters/inbound/tui/_app.py:28` imports `application.flows`).

### Verification epistemics - what failed and what held

Three rounds produced moving numbers until the basis split was identified. Ten corrections were logged against revision 1 of the discovery (classes: unverified negative claim, inverted reading, wrong inference from correct count, subset presented as total, unfair characterisation, overstated strength). The architecture pass then re-derived every canonicity claim and found three more: the open item crediting `audit_registry_relation_handoffs` with the correct predicate (false - binding channel only), the private-reach claim about `_casillas_by_binding` (overstated - consumers use the facade), and the undetected predicate divergence between the two join primitives.

A fourth pass - a fresh-context cold read of this feature's own documents before first dispatch - added two more corrections, both absorbed directly into this document and the plan: the consumption test implements three channels, not four (its 78/78 score survives only because the alternate-fed relations are filtered as factual_evidence), and several cited line numbers had drifted (`register_schema` :611 not :820, `FILED_VIA_BINDING_FIELD` :79 not :40, the CLI widening at two sites :341/:348). The same pass mis-asserted 23 blocker members; direct re-verification confirmed 21, the reader having merged the adjacent enum - counter-verification cuts both ways. Counts converged across passes; canonicity claims and cited line numbers are the classes to re-derive every time. The evidence favors: canonical derivations landed as importable code BEFORE any consumer, a small spine vocabulary over the blocker sets, deletion of the dead surfaces, and one application-owned read model - the decisions themselves belong to the four ADRs of this feature.

### Not investigated

HEADER-kind export fields (not casillas; single enumeration site accepted), the Sheets pull-path parity surface beyond its shared-resolver contract, M369/OSS dormant resolver status, and the wider TUI wizard flows outside the review screen.

## Sources

- `src/cadrumo/application/modelo/_preconditions.py:66` (HEAD import break; worktree fix at :17)
- `src/cadrumo/domain/calculations/registry/_export.py:90,138-177` (layout derivation; sole box derivation and BINDING-field residual)
- `src/cadrumo/core/_export_exemption_reason.py:79`
- `src/cadrumo/domain/calculations/registry/_validate_completeness.py:41-68` (lower-bound gate)
- `src/cadrumo/domain/calculations/registry/tests/test_cross_period_relation_consumption.py:52-73` (three-channel index at :54)
- `src/cadrumo/domain/calculations/registry/_handoffs.py:192-229`
- `src/cadrumo/domain/calculations/registry/_bindings.py:488-529`; `registry/__init__.py:983` (`bound_casilla_binding_ids` export), :1020, :1024, :1045
- `src/cadrumo/domain/calculations/registry/_rate_box_partition.py:164-180`
- `src/cadrumo/domain/calculations/registry/_queries.py:837,852`; `src/cadrumo/application/calculations/_relation_prefill.py:815-850,1131-1133`
- `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py:169-180`
- `src/cadrumo/application/modelo/_calculation_resolution.py:104,304`
- `src/cadrumo/application/modelo/_data_inventory.py:179-202`
- `src/cadrumo/application/calculations/_cross_period_models.py:49-91` (21 members)
- `src/cadrumo/domain/modelos/_verification_report.py:81-121`
- `src/cadrumo/application/ledger/_confirmation_gate.py:69-102`; `src/cadrumo/application/ledger/_preflight.py` (`IvaLedgerAggregationIssueReason`)
- `src/cadrumo/application/overview/_pipeline_health.py:64,178,194-214`
- `src/cadrumo/application/state_projection.py:1,782`
- `src/cadrumo/application/verification/_verify.py:85,448`; `src/cadrumo/application/verification/_schema.py` (`DiscrepancyCause`); `src/cadrumo/application/filing/__init__.py:181,186,931,983`
- `src/cadrumo/domain/calculations/registry/_schema_verification.py` (`VerificationDiscrepancyCause`)
- `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:638-655,639,762`; `src/cadrumo/application/modelo/_required_binding_gate.py:41`
- `src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py:1-36`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py:825`; `src/cadrumo/core/json_contract.py:611`
- `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py:341,348`
- `src/cadrumo/domain/calculations/registry/_export_parse.py:254-260`
- `.importlinter:49-127,300-307`; `src/cadrumo/adapters/inbound/tui/_app.py:28`
- Registry probes via `cadrumo.domain.calculations.registry.bundled_authority` over 94 revisions (working tree, 2026-08-10). Line numbers cite the working tree at that date; the tree churns, so re-confirm any locator before acting on it.
