---
tags:
  - '#audit'
  - '#authority-health-completion'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:1b9d61473da95d59a0655881a2c26011abc9f5d053dc71358d1f7fb9af25cc2f'
related:
  - "[[2026-10-02-registry-health-repair-plan]]"
---

# `authority-health-completion` audit: `Maintenance blockers and acceptance receipts`

## Scope

Recorded 2026-10-04. Root owns the maintenance blockers, their repair orchestration and final requested authority publication under the operator's instruction: "Design the fix orchestration order: all blockers are yours to tackle". This audit preserves the previous run's observations; execution must refresh them against settled live inputs. It does not mark any repair complete.

Evidence: `C:/Users/hello/AppData/Local/Temp/cadrumo-authority-maintenance-503500c597674015888e0fdc18d1ce86/maintenance-report.json`, its `collapse/summary.json` and `collapse/input-manifest.json`, and the durable runtime receipts named below. The repair sequence is `2026-10-04-authority-health-completion-plan`. Existing technical work remains tracked in `2026-10-02-registry-health-repair-plan`.

## Findings

### conformance-diagnostics | high | Report and coverage use governed facts without an explicit candidate scope

`conformance report --json` and `conformance coverage --json` abort with `InternalInvariantError: Modelo obligation scope requires an explicit generation-pinned governed-fact scope`. In `dev/registry/conformance/profile.py`, `audit_bundled_registry_conformance` iterates `_NON_REGISTRY_MODELOS` before constructing its validated authority. `src/cadrumo/domain/calculations/registry/modelo_obligation_scope.py` correctly requires explicit fact authority. Repair developer composition and candidate cache ownership, retaining the runtime refusal and truthful no-validation diagnostics. Acceptance: both commands complete against the intended candidate; missing scope, stale generation and cross-candidate cache tests retain their refusals.

### candidate-health | high | Runtime loadability ignores the descriptor selected for the health assessment

`dev/registry/analysis/registry_status.py` accepts `authority_descriptor` and uses it for currency, while `_runtime_authority_loadable` calls `load_bundled_runtime_authority()` through the active default. A candidate can therefore be assessed with two different artifacts. Thread one explicit descriptor through artifact checks. Acceptance: an invalid candidate fails even when the active artifact is healthy; an isolated valid candidate can be assessed while the active artifact is stale.

### binding-consumers | high | Five filing-grade bindings have no typed consumers

The refreshed binding receipt is `var/storage/development/.logs/test-runs/2026-10-04/20261004T132513.527523Z-check-bindings-90572-cce74057/artifacts/binding-signal.json`. Findings are Modelo 303/2022 `modelo-303-recargo-equivalencia-super-reducido-cuota`; Modelo 347/2025-y-siguientes `modelo-347-contraparte-row-criterio-caja` and `modelo-347-contraparte-row-inversion-sujeto-pasivo`; and `modelo-347-contraparte-row-provincia-codigo` in both Modelo 347 epochs 2011-2024 and 2025-y-siguientes. Construct/form membership alone is not a typed consumption edge. Root owns all five findings regardless of earlier campaign exclusions. Preserve official applicability, repeated-row cardinality and actual producer/consumer types. Acceptance: a fresh complete census has zero unresolved filing-grade consumer failures.

### generated-targets | high | One stale target and one enrolled target have no current committed generation

The refreshed registry receipt is `var/storage/development/.logs/test-runs/2026-10-04/20261004T132513.656516Z-check-registry-5420-04afae4e/run.json`. Target currentness reports current 69, explained 7, stale 1, never-committed 1 and unreadable/excluded 82. The concrete stale target is Modelo 111/2019-y-siguientes; the never-committed target is Modelo 490/2021, already enrolled in `dev/registry/pipeline/generated_export_bootstrap_targets.toml`. The 82 other entries need evidence-based reconciliation against existing capability and transport rules, including actual missing authored inputs. Regenerate reviewed targets through their canonical owner with form/construct companions and source pins; never invent fixed-width layouts for native XML or applicability-only revisions. Acceptance: no unresolved currentness failures and complete, truthful disposition of the current target population.

### filing-proof | high | Closure rejects a Modelo 200 provenance pin and requires two independent proof channels

`conformance closure --check --json` rejects a generated provenance manifest digest that differs from `dev/registry/conformance_vectors/modelo_200_2025_y_siguientes.toml`. `dev/registry/filing_export_conformance_vectors.py` intentionally refuses this mismatch. Inspect source, map, profile, manifest, generated artifacts and official byte probes before updating any approved vector; retain pin-drift detectors. The accepted two-channel ADR also requires current secure replay evidence for eligible filing-grade closure. `dev/registry/conformance/authorities.py` currently composes the canonical live proof authority with `secure_replay_source=None` and `secure_replay_custody=None`. Refreshing the public hash cannot replace the secure channel. Acceptance: complete per-revision closure has both required channels through canonical authorized custody, with private values confined to encrypted/transient storage. Discover additional refusals early and keep them root-owned; absent real proof remains a blocker.

### stable-inputs | high | Successful snapshot compaction does not prove the changed live inputs

The full collapse assessed all 58 modelos as already minimal, all 160 indexed revisions and 3479 indexed temporal/capability coordinates. Snapshot equivalence, governed facts, indexed parity and cache invalidation passed. The run still failed because live registry/tool inputs changed: `inputs_stable=false`, `no_live_mutation=false`, `source_apply_ready=0`. Reported drift included Modelo 131/2025 export/provenance and edition/export interpreter modules. A fresh scoped Modelo 131 assessment passed as a no-op, but it cannot substitute for final complete live verification. Acceptance: settled canonical transactions, captured input receipts and one complete final run with unchanged live source, interpreting code, evidence and authority receipts.

### final-publication | high | Active authority currency is stale and can be repaired only by a successful final publication

The active logical generation recorded by the previous run is `f9e6cc9126b6ec3dccbac6a58b36ba25f340a8391c054a785e592c60289b904e`; refreshed source compilation produced `b3cbe7aed90481b88cc44b0823a24a63d641e368d07c73f008bbeba4c5e3e22d`. These are historical receipts, not planned fixed digests. Pre-publication acceptance must verify a complete isolated current candidate and every source-side gate; active currency remains pending until the canonical publisher installs the final generation. Acceptance: one final explicit full publication from unchanged accepted inputs, followed by current active descriptor, verified physical database identity, runtime adoption and the complete health sweep. Do not bypass the currency check or publish an intermediate generation to make diagnostics work.

## Recommendations

Follow the linked feature's L1 plan in order. Root owns all current and newly exposed maintenance blockers and the final publisher boundary. Preserve existing source-owner work and canonical journals, refresh the live census before editing shared targets, and append actual repair and acceptance receipts here as execution proceeds. Run full compaction once after writers settle; any input drift invalidates final acceptance and requires revalidation. The prior conformance validity/load, integrity, corpus checks and 11 focused tests are useful baseline observations, not final acceptance of the later live state.

Design validation 2026-10-04: the new 13-Step L1 plan and the existing campaign plan passed `vaultspec-core vault plan check` with no findings. `vaultspec-core vault check all` exited 0 with unrelated record warnings; the new feature's scoped check reported zero errors and zero warnings. The dependency review placed S11 normalization before S09 public proof and S10 secure replay so receipts bind settled producer inputs. All implementation Steps remain open. This pass created the plan/audit/index and appended the scoped ownership handoff; it makes no claim of repaired source, completed closure or authority publication.

Final dependency validation: the owning Step move verb placed S11 before S09 without renumbering immutable identifiers. The resulting PLAN022 warning is intentional and reviewed: execute the documented dependency order, not numeric sorting. A single prose blank-line finding introduced during the dependency edit was repaired through the body owner while preserving every Step row and state.
