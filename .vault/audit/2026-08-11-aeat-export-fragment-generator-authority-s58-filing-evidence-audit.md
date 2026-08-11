---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:cb65920dc39a1a2357e0f120933cb53db8e02f110f46c014a8c3cf0f39686ddb'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S58 immutable M303 filing evidence review`

## Scope

Reviewed S58 against the accepted M303 dual-keying ADR and its durable filing-instance evidence contract. The review covered the nominal `FilingEvidenceReference`, frozen M303 evidence models, A28 endpoint completeness and value/observation agreement, S59 annual-Orden snapshot binding, calculation-revision identity participation, encrypted catalogue round-trip, calculation and quickfile collection paths, verification, standard export, review-package assembly, deletion of prior value-arrival/reference surfaces, absence of mutation/backfill/compatibility paths, and the behavioral quality of the focused tests.

The evidence models are frozen and nominally referenced; complete evidence participates in `derive_calculation_revision_id`; calculation validates period, active IVA censo composition, exact S59 snapshot equality, simplified rows, A28 endpoint coverage, calculated values, and typed observations before persistence; verification reloads the selected revision evidence; and review-package `revision.json` includes the persisted evidence. Focused verification completed with 22 passing tests across the filing-reference, M303 evidence validation, CLI collection, S59 projection, and encrypted catalogue round-trip modules. The findings below remain release-blocking.

## Findings

### export-applicability-command | high | Real M303 export still requires a caller-supplied applicability envelope and every public path supplies none

The accepted S51/S58 contract makes `M303ExportApplicabilityEnvelope` an internal application assembly result and forbids it as a command or export input. The implementation retains `ModeloExportCommand.m303_applicability`, requires it in `export_modelo_revision` and `_build_export_producer_snapshot`, and uses its A28 boolean as the authority against persisted evidence. Meanwhile standard export, review-package export, and quickfile each construct the command with `m303_applicability=None`. Consequently every real M303 export path refuses before rendering, and the only path that can reach the new evidence-backed projection is an internal caller that injects the forbidden envelope. S58 therefore does not provide a working export/read path and does not assemble A28 applicability from the selected revision and canonical owners.

### legacy-evidence-tolerant-reader | high | The encrypted catalogue still accepts legacy M303-shaped revisions without filing evidence

`CalculationRevision.filing_instance_evidence` defaults to `None`, the catalogue repository reads revisions without joining their work units, and no schema cutover rejects pre-S58 identities. The added corruption test deletes evidence from a new evidence-bearing revision and sees an identity mismatch, but it does not represent a genuine pre-S58 record whose original digest omitted evidence. A bounded round-trip proof built such an old-identity revision with `filing_instance_evidence=None`; `CalculationRevisionCatalogueRepository.load()` accepted it and reported `legacy_without_evidence_loaded=True`. Operation-level export and verification guards do not satisfy the ADR requirement that existing pre-release M303 revisions are invalid with no tolerant reader, and other catalogue consumers can still observe the incomplete record.

### evidence-contract-tests | medium | The focused tests assert a guessed API name instead of proving absence of mutation and do not exercise real export entrypoints

`test_m303_evidence_is_not_exposed_as_a_revision_mutation` only asserts that one symbol named `author_or_replace_filing_instance_evidence` is absent. A differently named writer, command, model-copy path, or persistence update would pass, so the test is not a behavioral guard for the no-mutation contract. The CLI tests call `m303_filing_instance_evidence_from_cli` directly and never execute the registered calculate, quickfile, standard export, or review-package commands. This leaves the actual producer/consumer wiring unproved and allowed all three M303 export entrypoints to pass `None` into a service that requires the envelope.

## Recommendations

For `export-applicability-command`, remove `m303_applicability` from `ModeloExportCommand` and from the filing export call boundary. Add the single internal assembler required by the accepted S51 amendment, loading the selected revision plus canonical profile, period, observations, ledger, register, and revision-evidence owners, and derive/refuse A28 agreement there before any target creation.

For `legacy-evidence-tolerant-reader`, make the persistence cutover fail closed for historical calculation catalogues rather than defaulting the new evidence field. The read boundary must have enough authoritative work-unit/model context, or use an explicit current-schema cutover, to reject evidence-less M303 revisions while continuing to reject evidence on non-M303 revisions. Do not backfill or infer false/default evidence.

For `evidence-contract-tests`, replace the symbol-name assertion with real behavioral proofs that an existing revision cannot acquire or replace filing evidence and that changing evidence produces a distinct newly persisted revision. Execute the registered calculate and quickfile commands with a real evidence document, then execute standard export and review-package creation from that persisted revision without any caller-provided applicability envelope. Add a genuine pre-S58 encrypted-catalogue fixture whose old digest omits evidence and assert rejection at load.

## Re-review outcome

Verdict: **PASS. All three prior findings are resolved; no open S58 findings remain.**

`export-applicability-command` is resolved. `m303_applicability` and the retired applicability/value-arrival envelope types are absent from production. `ModeloExportCommand` and `export_draft` no longer accept a caller applicability override. Application export reloads the selected revision evidence and internally assembles supplier-regime and prorrata-transition arrivals, the canonical `ProrrataRegister`, differentiated-deduction contributions, the encrypted Bienes de inversion register, its regularisation result, and the final `M303FilingFacts`. The standard M303 export proof reaches the honest withdrawn-layout `ModeloExportUnsupportedError` with no target or temporary file, demonstrating that it passes the former command-envelope refusal boundary.

`legacy-evidence-tolerant-reader` is resolved. The calculation-revision catalogue namespace is cut over from schema V1 to V2, and encrypted load requires the inner envelope to equal the current V2 schema. The genuine legacy fixture derives the old evidence-less revision identity, persists it inside an inner V1 catalogue, and proves load rejects it with `unsupported_envelope_version`; there is no backfill, false inference, or tolerant read.

`evidence-contract-tests` is resolved. The guessed-symbol mutation test has been deleted. The domain test changes immutable M303 evidence, proves a distinct revision digest, and proves direct mutation raises Pydantic's frozen-instance validation error. The encrypted repository test persists original and changed-evidence revisions as two distinct keyed rows and proves both survive while the original evidence remains unchanged. The focused CLI tests retain real typed document loading and missing-document refusal without claiming a mutation-surface proof.

The simplified-regime scope mapping is also single-homed correctly. `m303_regimen_simplificado_scope_for_profile` is the one profile-composition mapping owner: GENERAL maps to the not-claimed S59 scope, SIMPLIFIED and MIXED map to evidence-required, and absent IVA composition refuses. Both workflow scope resolution and S58 evidence validation consume that function, so validation no longer redeclares composition semantics. Spanish IVA stem conformance introduces no competing S58 identity or alias; the reviewed S58 surfaces use the canonical IVA vocabulary.

Verification supplied for the re-review reports 62 passing export, persistence, and Spanish-conformance tests; 9 passing evidence/scope tests; 3 passing new identity, persistence, and CLI-focused tests; scoped Ruff and basedpyright at zero; and clean `git diff --check`. Independent bounded reruns in this review produced 29 passing export/persistence/Spanish tests, 9 passing evidence/scope tests, 3 passing identity/persistence tests, Ruff clean, basedpyright with 0 errors, 0 warnings, and 0 notes, and clean diff-check.

Exact real quickfile integration remains outside the S58 PASS proof. The previously reported peer `IndentationError` in `_workflow_gate.py` is no longer present in the current checkout. A direct integration rerun now collects and executes but stops earlier during unrelated profile-fixture creation because `tax_residence.jurisdiction_scope` is missing. It therefore does not prove the complete quickfile-to-export journey, but it also does not reopen any S58 finding: the reviewed standard export path independently proves revision-backed internal assembly reaches the canonical withdrawn-layout refusal.
