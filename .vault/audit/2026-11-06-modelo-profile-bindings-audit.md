---
tags:
  - '#audit'
  - '#modelo-profile-bindings'
date: '2026-11-06'
modified: '2026-11-06'
body_schema: 'body-v2'
body_hash: 'sha256:6d68eb69747b8114e1ac141e2dc6ab68911f6346b81c65d4476d9969d574a425'
related:
  - "[[2026-11-06-modelo-profile-bindings-plan]]"
---

# `modelo-profile-bindings` audit: `Profile binding and form projection review`

## Scope

Independent Sol high review of the context projection slice against eeba75569e252da8f3cd72826e1953740d386583, performed 2026-11-06. Reviewed the six changed production files and new work-form profile-context tests under S02, plus the plan/reference and governing role/source contracts. M720 S04 and final integration evidence are not covered by this first review.

## Findings

No actionable code findings in the context slice. The shared identity/contact mapping preserves prior exporter key/value meanings; partial facts remain independent, absent facts remain unknown, and no presenter, representative or elected account is fabricated. Only registry-addressed context receives the values, while explicit saved casilla/binding data retain their separate paths. Filed, superseded and discarded heads omit current profile headers. Exact-profile custody and the caller's pinned authority remain in use.

The read guard opens profile facts for a declared producer context even if that producer is not an identity/contact key. The reviewer assessed this as a bounded efficiency observation, not an actionable correctness or custody defect: only the requested producer is rendered and unsupported keys remain unknown.

Verification reused: seven-module single-process focused pytest 63 passed; the follow-up explicit integration selection passed 16 cases including the three originally deselected exporter integration cases. Ruff, format and scoped ty checks passed all seven changed paths. The reviewer ran no duplicate tests.

Verdict at this checkpoint: PENDING for unreviewed M720 work and required combined integration gates. No critical/high finding reopens the context implementation. CHECKS2 owns combined check-code, check-registry-gate, test-gate and generation-dependent documentation acceptance on integrated TUI; this child owns change-specific local registry proof and publication.

### profile-provenance | high | Profile-tier fingerprints are omitted from persisted calculation evidence

Independent static review confirmed profile scalar values enter replay but their fingerprinted source references are discarded: `src/cadrumo/application/modelo/calculation_resolution.py:292` returns values without merged profile provenance, `calculation_bucket_actions.py:818` supplies mesh-only refs, and `calculation_actions.py:485` persists that argument. S04 remains open for a bounded propagation correction and real encrypted calculation/export proof. This is an existing-contract omission, not authority for a new source schema.

Preserve the established metadata merge, which records considered source tiers independently of the winning value. The actual resolve_profile_source_tier intentionally resolves lower-tier facts even when the caller supplies an override, to assess divergences. Therefore caller operator-layer values win while lower-tier profile fingerprints remain considered evidence. An initial suggestion to omit all overridden profile refs was corrected before implementation; selected-role-only filtering would change existing policy. Preserve unique primary refs, contributor-parent closure and canonical fingerprint-sensitive revision identity. Do not attest unconsumed row values while repairing the scalar path.

### s04-static-review | low | Implementation reviewed; final authority and encrypted proof pending

Independent Sol high review of the final uncommitted S04 delta found no actionable code findings. The two M720 providers retain their binding IDs and optional export geometry and select declaration-contact facts. TEXT routing is confined to calculation-only profile inputs without dictionary/XSD addresses. The scalar profile provenance correction reaches persistence, includes considered lower tiers under caller overrides, and excludes unconsumed rows. The shared mapper retains every previously persisted field; existing duplicate-primary and contributor-parent validation remains active. Nonpersisting evaluation retains profile evidence in its prepared channels and creates no revision identity, so its mesh-only divergence argument is not a parity defect.

The profile-provenance finding is implemented and statically reviewed, but remains pending real encrypted persistence proof after local publication. The reviewer performed no duplicate tests. Prior S02 review remains applicable.

An intermediate broad TEXT-channel change failed six existing precedence cases because dictionary/XSD-addressed M100 numeric controls were routed into the string channel. Restricting the change to calculation-only TEXT inputs restored all nine projection/precedence cases (2.40 seconds). Two candidate source/channel cases passed (1.48 seconds), and all 34 relocated provenance-consumer cases passed with explicit unit/integration selection (37.08 seconds). Scoped Ruff and ty checks passed. These checks used the prepublication authority; they do not establish adoption of the two M720 provider changes.

Overall verdict: PENDING final authority publication/adoption, six-case encrypted M720 acceptance, and coordinated acceptance gates. CHECKS2 requests rebasing the committed candidate onto the landed private-to-public sweep before handoff; the exact landed commit is pending. Its integrated full gates remain separately owned.

### s04-publication-validation | high | Binding grounding and generated form layout incomplete

The admitted target-current check on 2026-11-06 rejected both new profile providers for missing `official_source_guidance` evidence and source citations. It also rejected the stale form-layout digest and the two fields still presented as manual inputs. This is an actual source-completeness defect missed by the focused loader tests and static review; publication was not attempted. S04 remains open. The implementation owner is adding the enrolled AEAT citations, and the principal owns canonical layout regeneration and renewed validation. No validator waiver or handwritten generated output is authorized.

Before this refusal, the canonical M720 migration report passed equivalence and minimality with zero unresolved duplication and zero blocked work. The source fingerprint before/after was `991141c62321c34f651e20dcd94868d9c9357b2aa90e45d47c9b487cb251d9e2`, with 182433 physical bytes and 785 authored payload fields unchanged. Its generic summary reports compaction incomplete but source accepted and minimality passed; no normalization was applied. This evidence predates the grounding/layout repair and must be refreshed if its inputs change.

### s04-source-evidence-review | low | Specific contact guidance citations reviewed

Independent Sol high review verified the separate `aeat-modelo-720-contact-instructions` guidance role against the existing same-document pattern. The layout role remains unchanged, both references retain `pending_review`, and no approval is claimed. The bundled PDF matches SHA-256 `ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7` and 612620 bytes. Both citation sets match the extraction at physical page 6, lines 132-139, identifying declaration-contact telephone and name. Filing-year/period scope matches the existing design entry. This bounded evidence review passes; generated layout, full validation and runtime adoption remain pending.

### s04-generated-context | high | Regeneration would discard profile-owned contact display

Read-only generator tracing found that simply refreshing M720's existing generated layout would remove both contact fields: fixed-width anchoring admitted manual binding inputs but did not generate context for scalar profile providers. The existing runtime already supports `FormContextFieldBlock` addressed to the exact export field and reads its saved binding value. S04 therefore includes bounded generic generation of that existing read-only block, preserving official field ordering and exact export ownership. No model-name matching, new form schema or frontend default is introduced. FRONTEND independently confirmed that the same omission affects React, TUI and CLI; all consume this shared form. Implementation, focused generator proof and final generated-output review remain pending.

### s04-generator-review | low | Rebased generic context generation reviewed

Independent Sol high review found no actionable production defect in the generator and public-name adaptation on integrated base `9b456620bc`. Contexts use exact fixed-width export layout/record/field ownership, exclude repeated records/providers and row sets, preserve manual/casilla precedence and stay outside editable grids. Ambiguous layout ownership refuses. The canonical provenance mapper has no remaining old-name consumers, and S02 retains the integrated public identity helper. This is static review, not generated-output or runtime proof.

### s04-first-open | high | New work has no saved contact values before calculation

Independent creation tracing confirmed that `work_create_operation` creates or reuses the work unit without calculating, and React/TUI open it directly. Existing binding context projection reads saved revision overrides only. Therefore a generated read-only profile contact field would remain blank at first open despite populated canonical profile facts. BOSS explicitly confirmed first-open prefilling is in the original authorized scope. S04 includes an admitted, read-only live projection for exact declared profile binding contexts, preserving saved explicit answers, historical guards and absence; no values are persisted by form reads. The independent review must assess live-versus-saved precedence and no write-on-read, and the child must prove first-create behavior. FRONTEND owns complementary served-context rendering assertions.

### s04-first-open-error-review | low | Unknown context fallback preserves existing error contract

Independent review assessed the admitted binding-context helper's `RegistryValidationError` fallback. It matches existing profile-truth projection and yields unknown context without a readiness/filing claim or write. Exact export-context owner validation occurs before the catch and propagates; common invalid fact/channel errors use `ProfileBindingResolutionError(ModeloError)` and are not swallowed. Calculation diagnostics, refusals and persisted issue paths remain intact. No actionable silent-findings regression was found. Final first-open and encrypted-runtime proof remain pending.

### s04-first-open-static-review | low | Live-versus-saved projection reviewed

Independent Sol high review passes the final frozen first-open implementation. Exact registry-declared profile binding contexts select the admitted values; saved-key membership preserves empty, false and zero answers. Historical/unusable forms receive no live fallback, and the path introduces no persistence calls. The test design meaningfully covers creation, absence, overrides and repository stability. The rebased focused generator/context selection passed 24 cases in 4.07 seconds, with Ruff, format, scoped ty and whitespace checks passing. The reviewer ran no duplicate checks. Overall acceptance remains PENDING the nine-case encrypted module and final source validation/publication/adoption.

### s04-source-validation-resolution | low | Grounding and generated-output findings resolved

Canonical M720 generation wrote one fragment: only the two contact fields became exact export-addressed context blocks, with unchanged IDs/order and export geometry; independent review found no actionable issue. Full candidate validation then identified the owning construct's missing contact-guidance reference. Adding that one source reference closed the existing binding/construct evidence relationship without changing policy or scope; independent review agreed. A second generation wrote zero fragments. Refreshed source minimality/equivalence passed with zero duplicates/blocked work and unchanged fingerprint `53a5d5e136f483815d063c39a62ceab8fbeb2acbf176875f7f88361ed6f2133d`.

The subsequent target-current command exited zero and reported current canonical output matching the committed target. This resolves the source-grounding and generated-layout validation findings. Authority publication and the encrypted first-open/calculation/provenance/export tests are still required before final acceptance.

## Recommendations

Complete S04 local registry and real-flow proof, then review its interaction with this stable context slice. Reuse the passing focused evidence for unchanged files. Do not mark combined integration acceptance complete before CHECKS2 supplies it.

## Final scoped acceptance

The recommendations above have been completed for the child candidate. Final source minimality/equivalence and target currentness pass. Publication installed logical generation `29d247afb605e9ebce6bf596e9882186bb9296a55c28218e2d410375f17afeb5`; registry health confirms recorded and candidate identity equality. Strict binding checks report 9001 bindings/58 modelos and zero findings. Registry health reports eight passed lanes, zero failures and the existing nonblocking partial target-coverage disposition (56 excluded, 105 current, zero drifted); export placement has zero gaps/overlaps across 35870 fields.

Runtime evidence: the initial seven-module selection had 53 passes and two export fixture failures. No missing contact, first-open or provenance defect was hidden by those failures. The export fixture initially lacked the required manual Type-2 row; adding a foreign-asset source observation did not address that distinct manual export boundary. The final test supplies a synthetic manual asset row through normal draft inputs, leaving contact entirely in persisted replay, and checks case-preserving codec bytes rather than assuming uppercase conversion. The nine-case encrypted module passed in 5.31 seconds.

### s04-fixture-identity | medium | Corrected Type-2 declarant identity in the synthetic example

Final independent review found that DR720 physical page 11 requires Type-2 NIF/name to repeat Type-1 declarant identity; an earlier fixture incorrectly used an unrelated person. The test now supplies canonical declarant identity through the same explicit manual draft boundary, verifies Type-1/Type-2 identity equality and keeps the declaration contact distinct. The two affected cases passed in 2.84 seconds; seven unchanged cases retain the previous nine-case run's passing evidence. The source-role interpretation is corrected in the reference. This was a verification defect, not a production change or reason to weaken export validation.

Final independent Sol verdict: **PASS for the scoped candidate**, with no actionable findings remaining. The provenance, generated-layout, source-grounding and first-open findings are resolved. Eleven authoring-boundary tests also passed (137.89 seconds); final fixture Ruff, formatting and ty checks pass. All production and registry inputs were unchanged after the validated publication; only the corrected synthetic test inputs changed.

Integrated acceptance remains CHECKS2-owned: combined check-code, check-registry-gate, test-gate, full test-registry, frontend/native build and legitimate null-context fixture coverage, final integrated authority/document fixtures, integration and cleanup. This scoped PASS does not claim those pending combined gates passed.
