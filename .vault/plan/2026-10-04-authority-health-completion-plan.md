---
tags:
  - '#plan'
  - '#authority-health-completion'
date: '2026-10-04'
tier: L1
related:
  - '[[2026-09-09-registry-generator-adr]]'
  - '[[2026-09-09-registry-edition-authoring-adr]]'
  - '[[2026-09-11-binding-schema-adr]]'
  - '[[2026-09-09-facts-registry-governed-fact-catalogue-adr]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-adr]]'
  - '[[2026-08-24-registry-completeness-closure-adr]]'
  - '[[2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr]]'
  - '[[2026-10-02-registry-health-repair-plan]]'
modified: '2026-10-04'
body_schema: body-v2
body_hash: 'sha256:1124eef7eb5262fbf9373cfffe4fd466fe126e3d9d3df0dc2dfaa200e57459bd'
---

# `authority-health-completion` plan

Repair the maintenance blockers, prove a settled complete candidate, and deliver the requested current authority.

## Description

Approved 2026-10-04

Authorization: the operator requested all authority compaction and health commands followed by publication after green signals, then instructed: "Design the fix orchestration order: all blockers are yours to tackle". Root owns every blocker in this repair boundary, including the five current binding findings, additional closure/currentness defects revealed during repair and final authority publication. This continuation supersedes the prior retained-publisher and excluded-binding ownership clauses for these maintenance findings. It preserves unrelated work and existing technical campaign history.

Baseline evidence is recorded in `2026-10-04-authority-health-completion-audit` and the referenced maintenance receipts. The prior full run proved complete isolated snapshot equivalence/minimality but rejected changed live inputs. Report and coverage crash on implicit governed-fact scope; candidate health mixes selected and active descriptors; bindings have five real consumer failures; targets include stale 111 and never-committed 490; closure rejects a Modelo 200 vector pin and requires a secure proof channel. Currency is stale. Refresh the dynamic inventory first; the recorded counts and digests are observations, not acceptance constants.

The order is deliberate: reliable diagnostics and candidate artifact selection come before semantic source repairs; binding and target writes settle before public-vector evidence is reviewed; all public and secure closure evidence comes before final complete compaction and candidate acceptance. The single final publisher runs only after those source/candidate gates pass. Active authority currency becomes green after that publication; demanding it before publication would make the authorized remedy impossible. Candidate verification must use the actual isolated descriptor throughout, never the currently active generation as a substitute.

Decision coverage: `2026-09-09-facts-registry-governed-fact-catalogue-adr` and `2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr` govern explicit scope, candidate identity, runtime refusal and S02-S03/S12-S13. `2026-09-11-binding-schema-adr` governs actual typed consumer closure in S04-S05. `2026-08-10-aeat-export-fragment-generator-authority-adr` and `2026-09-09-registry-generator-adr` govern canonical target producers, source pins, companions, truthful target reconciliation and S06-S09. `2026-09-09-registry-edition-authoring-adr` governs baseline/delta semantics, complete assessment, equivalence, minimality and idempotence in S08/S11-S12. `2026-08-24-registry-completeness-closure-adr` and `2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr` govern the existing derived closure predicate and S01/S09-S10/S12-S13. The existing `2026-10-02-registry-health-repair-plan` remains the home of its broader technical work; this plan owns the current maintenance delivery boundary.

These narrow repairs fit accepted decisions. Do not create another compiler, authority loader, closure campaign or proof standard. If investigation requires a new capability/transport policy, a different health contract or a change to proof requirements, route that costly choice through the ADR owner before dependent implementation. Accepted unsupported/native transport declarations remain truthful; missing supported inputs or required proof remain root-owned blockers. No fabricated legal evidence, arbitrary drift disposition, capability downgrade, ignored partial lane, guessed binding consumer or copied private proof is an acceptable route to green.

Proof-cohort dependency: execute S01-S08, then S11, then S09-S10, S12 and S13. S11 settles normalization and rechecks all affected generated target/provenance receipts before either proof channel is pinned. If normalization changes a producer input, regenerate its affected target canonically and repeat scoped minimality/currentness until the source cohort settles. Public-vector review may reveal a real producer defect; repair that defect and settle the cohort again before accepting either channel's evidence. The complete S12 run verifies this settled state without live source mutation.

## Steps

- [ ] `S01` - Reconcile current writer ownership, settle canonical transactions and inventory every live maintenance blocker and required proof receipt; `Existing registry-health-repair handoff, dev/registry/pipeline transaction owners, .authority/, fresh isolated health receipts and authority-health-completion audit`.
- [x] `S02` - Bind conformance report and coverage to one explicit candidate governed-fact scope and generation-safe cache; `dev/registry/conformance/profile.py, manager.py, defining composition helpers and conformance tests, preserve src/cadrumo/domain/calculations/registry/governed_fact_scope.py refusal`.
- [x] `S03` - Make all candidate artifact health checks use the selected descriptor and preserve active defaults; `dev/registry/analysis/registry_status.py and defining descriptor/runtime load helpers, candidate health CLI composition and focused descriptor consistency tests`.
- [x] `S04` - Resolve the Modelo 303 2022 recargo binding through its official applicable typed consumer; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/bindings/0001-declarations.toml, exact source-grounded casilla or typed consumer delta and focused binding tests`.
- [x] `S05` - Close the four Modelo 347 repeated-row binding consumer edges across both declared epochs; `src/cadrumo/_data/registry/aeat/modelos/347/revisions/{2011-2024,2025-y-siguientes}/, dev/registry/mappings/modelo_347/{2011,2025}/, corresponding row producer/consumer tests`.
- [x] `S06` - Regenerate the stale Modelo 111 target from reviewed current source inputs with complete companions; `dev/registry/pipeline canonical legacy transaction recovery entrypoint, journal/lock owners and real recovery tests, Modelo 111 2019-y-siguientes source-pinned target and complete companions`.
- [ ] `S07` - Commit the enrolled Modelo 490 2021 target through the canonical source-pinned bootstrap publication path; `dev/registry/pipeline canonical historical static bootstrap/supersession orchestration and isolated publication/refusal tests, enrolled Modelo 490 2021 source-pinned target, unchanged authority grade and generated companions`.
- [ ] `S08` - Reconcile the complete target population and regenerate every repair-affected target in dependency order with truthful capability evidence; `dev/registry/analysis generated target census, existing registry-health-repair supported target work, reviewed source/map/profile inputs, bootstrap/disposition owners and affected generated export/construct/form companions`.
- [ ] `S11` - Normalize all settled affected revisions and prove complete minimal storage, equivalence, idempotence and focused repair checks; `Canonical registry edition migration/collapse owners, changed registry/modelo components including form layouts, affected success/refusal tests and required code/data checks`.
- [ ] `S09` - Repair public closure proof from reviewed generation and official bytes while preserving provenance pin mismatch refusals; `dev/registry/conformance_vectors/modelo_200_2025_y_siguientes.toml, dev/registry/filing_export_conformance_vectors.py, dev/registry/tests/test_pinned_conformance_vector.py and additional required public vectors discovered by the complete closure census`.
- [ ] `S10` - Complete every eligible closure receipt through current authorized secure replay and canonical custody composition; `dev/registry/conformance/authorities.py, filing_export_coverage.py, canonical two-channel proof and secure custody ports, current source-owned draft/producer replay evidence and metadata-only acceptance receipts`.
- [ ] `S12` - Verify stable complete compaction and every source gate against one isolated current authority candidate; `dev/registry/registry_collapse_verification.py full inventory, isolated canonical candidate publisher, explicit candidate health descriptor, conformance/binding/target/corpus/package checks and unchanged input manifests`.
- [ ] `S13` - Publish the final full authority generation and prove active reader adoption with all final health signals resolved; `dev/registry/pipeline publish-authority owner, .authority/authority.current.json and selected database via canonical publication only, final integrity/runtime/currency receipts, integrated review, audit and Step ledger`.

## Parallelization

Root is the accountable owner of every Step. Execute mutable repair Steps sequentially, handing off existing source writers before touching their paths. This plan does not dispatch agents. Independent read-only inspections may overlap with isolated outputs; source generation, bootstrap/disposition ledgers, vectors, shared registry declarations and active authority publication have one writer at a time. Preserve unrelated worktree/index changes and canonical lock/journal recovery.

S12 requires completed source/interpreter/evidence writes and stable receipts at both boundaries. No S13 publication occurs during compaction or while any required source-side gate is unresolved. If another writer changes inputs, stop acceptance, incorporate the change, rerun affected tests and repeat complete verification. Keep the active authority intact throughout earlier repairs.

## Verification

Per-Step proof: S01 records the fresh ownership/transaction/health/proof census; S02 runs real report/coverage plus explicit-scope, fresh-candidate and cache-refusal tests; S03 proves descriptor consistency using both healthy-active/bad-candidate and stale-active/good-candidate fixtures; S04-S05 use fresh typed binding census and real consumer/producer tests rather than membership-only fixtures; S06-S08 use source-pinned canonical target previews/publications, generated form/construct parity and honest per-entry inventory; S09 proves official public bytes and rejects altered/stale pins; S10 proves real production export replay, source-owned draft/producer identity, matching custody and receipt validity without persisting private values in the vault.

S11 precedes S09-S10. Recheck all affected generated targets, manifests and source pins after normalization; finish any canonical regeneration and repeat scoped minimality/currentness before producing public or secure proof receipts. S11 uses the canonical non-applying assessment/normalizer for changed modelos and applies only proved redundant storage changes. Require complete keyed-family assessment, effective equality including form layouts, zero unresolved redundancies and a second no-op. Run relevant success/refusal tests for touched boundaries and the repository's required format/import/type/lint checks for changed code/data. Use `uv run --no-sync python -m pytest -o addopts='' -n 0 ...` where the current environment lacks a standalone pytest launcher; do not disable meaningful acceptance tests.

S12 runs `uv run --no-sync python -m dev.registry.registry_collapse_verification --registry-root src/cadrumo/_data/registry/aeat --source-root src/cadrumo/_data --work-dir <fresh-isolated-work-dir>` after all writers settle. Require complete live assessment, stable registry/interpreting-code/evidence/authority receipts, no live mutation, effective equivalence, minimality, temporal/capability coverage, indexed snapshot and governed-fact parity, cache invalidation and all real source acceptance gates. Discover actual counts from the receipts; the previous 58/160/3479 results cannot approve changed inputs. Stage a complete candidate through the canonical publisher's explicit isolated destination and assess its own descriptor, loadability, currency, runtime boundaries and package behavior.

The acceptance sweep covers `just check-registry`, `just check-bindings`, conformance validity/report/coverage/closure, source-load, runtime-load, integrity, declaration screens, corpus text, corpus sidecars, data format and the focused authoring/compiler/runtime/package tests appropriate to changed boundaries. Screens are reviewed observations; unexplained defects are owned, while row count alone is not a release predicate. Resolve every required failed/partial health lane through the governing evidence contract; do not relabel it just to pass. Pre-publication artifact currency/load checks explicitly assess the candidate. Active currency is pending until S13; all other required source/candidate gates must already pass.

S13 invokes the real full `just registry-publish-authority` publisher once from accepted unchanged inputs, rather than relying on `--if-stale` to detect interpreter-only changes. The publisher revalidates the actual source cohort; no unsupported byte-for-byte promotion API is assumed. Verify its returned logical generation, active descriptor and physical database SHA/size, reader adoption, final active `check-registry`/integrity/runtime-load and the remaining required checks. Abort publication on input drift; retain/restore a reader-accepted prior generation only through the canonical recovery mechanism if the publisher fails. Record final review and receipts in the audit and each Step's execution ledger before checking completion.

Use the framework's integrated read-only review cadence at the completed source boundary and final delivery. Review scope/generation consistency, actual binding consumption, closure channels, generated companions and stable input receipts. Validate this plan with `vaultspec-core vault check all` and `vaultspec-core vault plan check`; maintain plan structure/progress/ledger only through owning verbs.
