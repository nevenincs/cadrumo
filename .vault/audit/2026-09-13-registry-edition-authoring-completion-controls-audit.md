---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:ebcf0313c4e81eda6178428c10aa19a9ae43d26046d43621e153c0ca0bbfa22e'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
  - "[[2026-08-24-registry-completeness-closure-adr]]"
---

# `registry-edition-authoring` audit: `Registry completion controls and architectural unblock`

The registry is being held up by a mixture of real missing evidence, transformation constraints, and duplicated bookkeeping. The strongest simplification is to generate proofs of mechanical work, preserve the evidence they depend on, and report each unresolved cause once. Removing temporal scope or legal grounding would make the registry less trustworthy; requiring a person to restate a computable fact makes it harder to finish without improving trust.

## Scope

Read-only architectural review of modelo TOML controls and their readers, against the supplied completion enumeration. No authority compile, delta/chain screen, seeder, migration, render, or 52-edge harness was run. Recommendations are proposals, not changes to accepted contracts.

The independent field census read 20,564 TOMLs across all 58 modelos plus the analysis and pipeline sidecars, covering 146 revision manifests and 1,123 distinct TOML paths. It records raw declarations, not inherited members. Full keys, counts, types and sample locations are in `.logs/audit-runs/2026-09-13/registry-field-inventory.json`; the readable enumeration is `registry-field-inventory.md` beside it; the read-only reproducer is `registry-field-inventory.py`. Scan time and content fingerprint are embedded in the JSON. No in-scan modification was observed.

This is exhaustive source-shape enumeration within those roots, not a claim to have semantically verified every formula, provider selector or external catalogue. Shared legal/source catalogue fields are dependencies of this audit; their entire population was not included in the persisted census. No new legal interpretation is asserted.

The supplied `.logs/audit-runs/2026-09-12/write-manifest-registry-completion-enumeration.md` is historical measurement evidence. Its compile/chain/coverage totals are attributed to that report, not re-certified here. The worktree contains concurrent changes.

## Findings

### completion-denominators | high | One completion label combines different questions

The supplied report attributes 3,317 of 3,358 compile findings to modelos 100 and 036, and 45 blocked edges to absent export renders behind compilation. Those are affected locations, not 45 independent repairs. Its 7,043 refusals are ledger entries, 318 restatements are minimality judgments, and 620 structural-difference findings are measured facts. These populations cannot be summed into remaining work.

Separate four outcomes: schema/delta normalization; evidence coverage; validated capability; release completeness. The accepted closure ADR defines a conjunction over capability, connectivity and export proof. The edition-authoring ADR defines inheritance and restatement removal. Neither makes all diagnostic counters a zero target.

Live code already permits modelo-local planning: `dev/registry/edition_delta_migration.py:2078` loads a single modelo; `migrate_modelo:2130` stages one-modelo trees and proves them before applying. Do not present the historical global compile failure as proof that all planning remains impossible. Export and publication still have stronger authority requirements; their precise present failures need the owning session's next run.

### computable-dispositions | high | Source-default bookkeeping belongs in generated diagnostics

`source_default_dispositions.<family>.kind = "underivable"` and `reason` record that no common reference prefix can be lifted. The census finds 40 such family declarations across 28 manifests. The source-default algorithm can determine that fact. The screen suppresses the associated finding when the family is declared; schema validation rejects a disposition alongside a declared default but does not itself establish underivability.

Recommend removing this authored shape and its presence-based closure condition after replacing them with a shared derivation: default available, no useful default, or measurement failed. No useful default is a completed optimization check, not unfinished registry content. Evidence: `source_default_dispositions.py:1`, `schema.py:969`, `dev/registry/analysis/edition_delta_status.py:2197` and `:2281`.

### roots-as-backlog | high | Temporary inability to inherit is stored alongside permanent legal structure

There are 30 explicit `predecessor.none` declarations; 13 state `cause`, 17 leave it absent. Causes combine genuine parallel variants and official structure differences with missing lineage and unretired withdrawals. These last two may be repairable authoring debt. A valid full-copy root therefore does not mean delta normalization is finished.

The migration writer still puts blocker descriptions into `reason` and omits `cause`: `dev/registry/edition_delta_migration.py:801`. Its prose classifier is avoidable drift. Require structured causes from the writer, and derive whether a repairable cause still holds. Keep full-copy roots where materialization cannot preserve meaning/order; do not convert every root into an inheritance edge.

A further asymmetry is real: `restated_families` works on keyed families but is explicitly refused for casillas. That prevents a single differently laid-out casilla family from using the same local replacement mechanism. Extending that mechanism requires an explicit materialization decision and parity proof. Evidence: `revision_contracts.py:84`, `restated_families.py:87`, `keyed_families.py:146`.

### review-scope | high | Mechanical representation changes can invalidate a review claim

The live census has 141 explicit `agent_reviewed` stamps, no explicit operator-reviewed stamps, and five manifests without a review status. Forty-nine manifests declare `reviewed_against`. These counts do not establish which reviews actually occurred. Eighty-seven reviewer strings are the generic `agent-prepared-pending-operator`; the validator only requires nonblank attribution, so syntactic acceptance proves little about who reviewed what.

`validate_review_scope` requires a reviewed delta's `reviewed_against` to equal its predecessor. A full-copy-to-delta conversion thus changes the review contract even when output is equivalent. The field is meaningful today: it prevents silently widening a review. But it is not a content fingerprint, and unchanged predecessor names do not detect edited predecessor contents.

A follow-on decision should separate the original review receipt from a machine transformation receipt. A proven representation-only rewrite can preserve the original reviewed subject and evidence without inventing a new review. Changed legal meaning still needs review. Do not populate missing stamps automatically or erase pending work. Evidence: `schema_governance.py:166`, `:208`; `schema.py:823`.

### proof-freshness | high | Current evidence records are not bound to all inputs they prove

Render evidence accepts `modelo`, `edition`, matching `selected_revision`, and truthy `rendered_bytes`. The reader does not check `observed`, content fingerprints, scenario identity, or even a positive-integer type for byte length. The file is currently empty, so this is a latent weak proof contract rather than a demonstrated false pass. Evidence: `edition_delta_status.py:1565`.

Root-demotion verdicts claim an edge but are loaded under `(modelo, successor)`; `predecessor` is not part of the lookup. Freshness examines successor file mtimes, not predecessor, shared inputs or tool version. Three stored predecessor strings are empty. Touching identical files can invalidate proof; changing a dependency outside the successor can escape this freshness check. Evidence: `edition_delta_status.py:2510` and `:2543`.

Replace both with generated receipts keyed by exact subject, operation and dependency fingerprint. Keep timestamps as information, not proof identity. Keep the distinction between a hypothetical demotion verdict and an unconditional missing review: they authorize different work.

### verified-means-too-much | high | Extraction flags mix evidence quality and verification result

Extraction profiles have `confidence`, `provisional_pending_specimen`, `corpus_round_trip_verified`, and `verification_source`. The round-trip gate accepts the verified flag with any non-null verification source, including the allowed `historical_suppression` and `not_applicable` values. Several live profiles instead name `synthetic_from_aeat_published_text`; this is useful synthetic evidence, but its name must not imply a real filed-PDF test.

Replace the writable verified boolean with a generated verification receipt; retain distinct evidence kinds and explicit provisional capability. A suppression or non-applicability is not a successful round trip. This is a naming/contract finding, not proof that every extraction consumer currently overclaims. Evidence: `schema_extraction.py:229`, `dev/registry/compiler/_validate_extraction_profiles.py:82`; example `modelos/036/revisions/2025-02-03-y-siguientes/extraction_profiles/0001-declaracion-pdf.toml:35` under the registry root.

### lineage-evidence-home | high | Deleting unchanged rows can also delete edge evidence

The census finds 18,082 authored continuity IDs, 8,409 row origins, 4,477 row evidence fields, and 738 sidecar attestations. These are overlapping representations, not additive completion measures. A row's origin/evidence describe its own predecessor edge and cannot be inherited as if they described the next edge.

The sidecar mechanism is now present and wired into loader validation. It is the correct place to preserve continuation evidence when a semantically unchanged row is dropped. It must also be consumed consistently by grounding and totality readers; this audit did not rerun that integration proof. Absence origins belong on rows, and sidecars reject them. Evidence: `lineage_attestation.py:69`; `dev/registry/compiler/_loader_internals.py:510`.

Therefore the historical claim that 317 of 318 rows cannot be dropped is evidence of the earlier measured representation, not a permanent design limit or a live recount. Re-prove candidates after evidence relocation.

### current-enrollment | medium | The code has moved beyond the campaign labels

Bindings are already keyed, restatable and drop-eligible in `keyed_families.py:240`, with identity axes `provider.kind`, `value.data_type`, and `value.channel`. The census contains zero authored `restated_families` keys. This establishes implementation enrollment and absent source declarations, not successful corpus-wide migration or parity.

The comment in `restated_families.py:54` still names bindings as full-copy, contradicting the live policy table. Use that table as the single enrollment authority; remove obsolete prose. The historical “bindings enrollment not sayable” must be refined into code enrollment, corpus declarations, and proof status.

### legitimate-blockers | high | Missing evidence and unsafe identity cannot be cleared by renaming a state

Temporal selectors choose which revision applies. Continuity keys prevent unrelated concepts from merging. Legal/source references prove what a declaration means. Export geometry and value contracts keep generated bytes faithful. These are real controls.

The supplied report's missing forms/designs, modelo 036 selector ambiguity and modelo 100 adjudication boundary remain reported unresolved dependencies until their owners produce current proof. This audit neither re-establishes the historical counts nor authorizes mechanical guessing. A raw-copy equality proof can certify a refactor preserves existing behavior; it cannot establish that the original behavior was legally correct.

### bookkeeping-totality | medium | A complete refusal ledger is not a complete registry

The persisted ledger still contains 7,043 refusal rows and 15 stamping-in-progress entries; 31 refusals carry previous-run metadata. These are file contents, not a fresh seeder judgment. `ledger_totality` measures whether unresolved rows are accounted for, so it can be total while real work remains.

`excluded`, `load_failed`, `stamping_in_progress`, and carried entries are run outcomes, not waivers of registry correctness. Keep them generated and owned by the seeder. Partition work so one unjudgeable modelo does not stop safe work on another. Do not hand-edit the ledger to clear it. Evidence: `dev/registry/analysis/casilla_lineage_seed.py:1960`, `edition_delta_status.py:2448`.

## Recommendations

The following field register distinguishes the actual key families. “Remove” means replace their present role in the same change, not delete declarations ahead of their readers. Every observed TOML path, including ordinary calculation/export fields, is enumerated in the accompanying census.

| Fields / key family | Assessment and remediation |
|---|---|
| `modelo.id`, revision containment/`id`, member `id` | Keep identity. Remove repeated containment IDs where the loader already derives them; normalize edition-bearing member IDs only with atomic reference migration. |
| `valid_from`, `valid_to`; `period_selector.years/year_from/year_to/periods/period_overrides` | Keep legal selection. Do not use filing-period tokens to represent unrelated event timing. Resolve overlapping selection at the owning contract. |
| `modelo.inception.filing_year/legal_refs`; `inception.unauthored.earliest_authored/reason/legal_refs/source_refs` | Keep legal inception separate from first authored coverage. `unauthored` is debt, not non-applicability. |
| `pending_ejercicio_ordenes[].filing_year/expected_publication_year/approval_cadence/rests_on`; shared `supported_filing_years` | Keep promise and pending publication distinct from actual coverage. Derive gap classifications and retire pending declarations when their evidence changes. |
| `authority_grade` | Keep declared capability ceiling; validate effective support. Review status is a different fact. Do not demote merely to close a counter. |
| `family_dispositions.<family>.reason/legal_refs/source_refs` | Keep grounded non-applicability of an empty family. `populated/not_applicable/blocked_pending_evidence` are derived coverage values, not three editable TOML statuses. |
| `engineered_by`, `review_status`, `reviewed_by`, `reviewed_at`, `reviewed_against` | Move review evidence toward subject-bound receipts. `engineered_by` is schema-supported but absent in this census; no evidence here establishes it as a live blocking field. Never auto-sign. |
| `predecessor`; `predecessor.none.reason/cause/legal_refs/source_refs` | Keep explicit inheritance/full-copy choice. Require structured cause; separate temporary debt from permanent structural constraints in derived work reports. |
| `restated_families[].family/cause/reason` | Keep family-level replacement intent. Currently no authored instances; casillas unsupported. Extend only with explicit retirement/order/evidence semantics and parity proof. |
| `continuidad_id`, `form_number`, `semantic_role`, `data_type` | Keep distinct stable identity, printed location, role and type. Repeated numbers/IDs are candidates, not proof of identity. Scope continuity lookup by modelo. |
| `continuidad_origin`, `continuidad_evidence` | Keep grounded/seeded and the three absence meanings distinct. Relocate continuation claims to one edge evidence home when stripping rows. |
| `continuidad_validation` | Transitional strictness switch: only four authored strict settings, default advisory. Derive applicability of mandatory invariants and retire the switch after coverage is ready; do not flip it to manufacture progress. |
| `lineage_attestations[].family/member/continuidad_id/from_revision/to_revision/origin/evidence/legal_refs/source_refs` | Keep edge evidence. Exactly one member key; absence origins excluded. Avoid maintaining duplicate authored continuation claims. `member` is schema-supported, not present in current sidecar rows. |
| `casilla_continuidad_evolutions[].id/continuidad_id/from_revision/to_revision/evolution_kind/legal_refs/source_refs` | Keep actual retirement/semantic-change declarations. Generate only from proven rulings, not inferred absence. |
| `identifier_evolutions[].family/identifier/kind/replaced_by/to_revision/legal_refs/source_refs` | Keep explicit retirement/replacement for keyed families; update consumers atomically. |
| `source_refs`, `legal_refs`, `orden_aplicabilidad`; family `*_source_refs`; `additional_source_refs` | Keep evidence and edition defaults. Lift shared references mechanically while preserving resolved provenance; default plus additions is not inherently duplication. |
| `source_default_dispositions.<family>.kind/reason` | Remove authored optimization bookkeeping; derive underivability. |
| `completeness_manifest.source_ref/source_refs/legal_refs/casillas[].casilla_id/number/segmento` | Keep the edition's closure check, generate it from its owning inputs. Singular source names derivation; plural lists evidence, so not an automatic duplicate. Never inherit a predecessor's completeness claim. |
| `completeness_manifest.manual_extraction/manual_extraction_reason` | Schema-supported, absent in census. Keep method/evidence; replace a skip-shaped boolean with a verifiable alternate extraction receipt. |
| `extraction_profiles[].confidence/provisional_pending_specimen/corpus_round_trip_verified/verification_source` | Consolidate evidence state and generate proof results; remove ambiguous writable “verified” boolean. |
| `verification_expectations[].min_coverage/tolerance/rounding/computed_casilla_ids/externally_grounded_casilla_ids/reconcile_when_present_casilla_ids/reconciliation_total_casilla_ids/discrepancy_causes`; `verification_predicates[].predicate_id/expression/finding_kind` | Keep behavioral verification criteria. These are runtime contracts, not campaign review checkboxes. Do not weaken thresholds to achieve completion. |
| `dependency_classifications[].treatment/taxpayer_files_source/conditional_on_economic_activity/source_modelo/binding_refs/target_constructs` | Keep applicability and required dependency semantics. Deferred/advisory must remain visible and distinct from zero. |
| `ruling[].modelo/predecessor/successor/rationale/refuse_bare/grounded/new_on_form/new_on_form_stems/not_on_form/discontinued/held/held_stems/held_reason/withheld/withheld_reason` | Keep genuine adjudications; patterns are scoped work selectors. Held/withheld are unresolved work. Do not treat them as terminal facts about law. `merged` is supported by the seeder, not observed here. |
| Ledger `run.judged_at`; `refusal[].modelo/revision/casilla/predecessor/category/reason/carried_from_previous_run/carried_reason/last_judged/carried_runs` | Generated only. Keep observation freshness and refusal identity; never use row presence as registry completion. |
| Ledger `excluded[].modelo/reason`, `stamping_in_progress[].modelo/casilla/chain/stamped/unstamped`, `excluded_contradiction[].modelo/contradictions`, `summary.*`; supported `load_failed` | Generated execution/accounting outcomes. No exemption from correctness and no hand-authored remediation stamps. |
| Coverage `disposition[].modelo/filing_year/period/kind/classification/reason/authority` | Consolidate with canonical inception/coverage facts. `inception` closes legal absence; `unauthored` does not. Reader checks shape but leaves authority interpretation to the author. |
| Render `render[].modelo/edition/selected_revision/rendered_bytes/observed` | No entries currently. Replace informal receipt with generated input-bound proof. Date and byte length alone are insufficient. |
| Demotion `verdict[].modelo/predecessor/successor/verdict/reviewed_against_wall/measured_at/refusal/drifted_families/drop_would_lose/drop_would_lose_rows/evidence_source/would_acquire/note` | Generated, explicitly conditional proof. Include predecessor and dependency hashes in identity; derive `reviewed_against_wall`, not a parallel approval flag. |
| Generated-tree `dispositions[].kind/modelo/revision/source_ref/source_sha256/reason/reconsideration_condition`; kind-specific `remedy/differing_records/derivation_code/field_count/refusal_marker/supported_filing_years_floor/revision_last_filing_year` | Keep source-pinned exception facts. `republish` versus `repair_inputs` is consequential and cannot be inferred from drift alone. Replace count/substring matching with exact affected identities where practical. Only one below-floor row is present now; other kinds remain supported contracts. |
| Analysis `exception[].modelo/revision/casillas/category/reason/reference`; retirement/handoff `status/classification/remaining_conditions/*_step` | Diagnostic/work coordination sidecars, not modelo authority. Do not import these as permanent registry gates; retain one work-record owner. |
| `schema_version` and report schema numbers | Keep format compatibility/version identity. They do not measure progress. `migrated_unverified/dispositioned/member_restated/stale/uncovered/is_total` are report values, not modelo TOML fields to delete. |

Recommended sequence:

1. **Fix the completion report first:** publish separate normalization, evidence and release outcomes. Group repeated findings under one cause, list affected scope separately, and state whether work is runnable, dependency-blocked or conditional. Generate this view from existing owned measurements; add no manually maintained “done” field.
2. **Complete already implemented mechanical paths:** binding declarations where justified, reference lifting, sidecar evidence preservation, and source-identical drops. Use the existing isolated planning/proof path. Measurement and writer ownership remain with the sessions assigned by the operator.
3. **Make the small writer repair:** emit `predecessor.none.cause`, and remove stale enrollment prose. A structured cause must describe the actual reason, not merely pick the first blocker.
4. **Decide the architectural replacements:** machine receipts for review-preserving transformations, render/demotion/extraction proofs; derived source-default status; one coverage/inception truth; family-local casilla replacement if needed. Migrate readers and TOMLs together; do not retain two active contracts.
5. **Clear genuine source and semantic dependencies:** acquire the specific missing artefacts and resolve selector/identity ambiguities. Re-run each owning measurement once after its inputs settle. Normalize historical rows independently of whether they are promised for runtime filing.
6. **Claim release only from the accepted conjunction:** a successful normalization proof, a total ledger, a reviewed stamp, or a zero minimality count cannot substitute for supported, grounded capability and filing evidence.

Validation: census command `uv run --no-sync python .logs/audit-runs/2026-09-13/registry-field-inventory.py` exited 0. Normalized-text TOML parsing found no errors. One pipeline ledger contains raw carriage-return sequences that strict raw-byte TOML parsing rejects; universal-newline text parsing succeeds. This is recorded as a portability observation, not asserted as a live gate failure. No registry data, governance rule or production implementation was changed.

Document check: the feature-wide check reports 44 existing execution-record/plan-ledger errors outside this audit. Those are vault bookkeeping findings, not registry compile results; no existing execution record or plan was changed.
