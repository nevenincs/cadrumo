---
tags:
  - '#plan'
  - '#profile-requirement-grounding'
date: '2026-08-08'
modified: '2026-08-09'
body_hash: 'sha256:a42bd742a970fa9b879ca8520d2c0fdaccabc5968e39c07da2e0a9ee12355e56'
tier: L2
related:
  - '[[2026-08-08-profile-requirement-grounding-adr]]'
  - '[[2026-08-08-profile-requirement-grounding-reference]]'
  - '[[2026-08-09-profile-requirement-grounding-audit]]'
---

<!-- RETIRED: S29, S30, S31, S32, S33 -->

# `profile-requirement-grounding` plan

## Description

Executes `2026-08-08-profile-requirement-grounding-adr` (accepted, amended 2026-08-09). Grounded in `2026-08-08-profile-requirement-grounding-reference` (note: the reference's claim that shipped `model_selectors` already carry `modelo_<code>` tokens was falsified by the amendment - zero such tokens exist in the shipped schema - and the reference has not yet been corrected; see `P05.S15`). Enriches the existing `ProfilePreflightRequirement` model with a human label, legal grounding, and the consuming modelo set, all sourced from data already loaded (`ProfileFieldDefinition` and `build_profile_grounding_index`), and threads the enrichment through the three surfaces that already share this model: the blocking readiness gate, `config profile preflight`, and `app modelo readiness`. No new schema or registry authority is introduced. Reconciling the separate `ProfileKey` and `_DEADLINE_RELEVANT_FIELDS` mechanisms against this canonical schema is explicitly out of scope for this plan and is deferred to a follow-up.

## Steps

### Phase `P01` - Enrich the requirement row and grounding union

Extend ProfilePreflightRequirement with label, legal_refs, and modelos; populate them in ProfilePreflightService.report() from the field object already in scope unioned with build_profile_grounding_index; cover with roundtrip and anti-tautology tests.

- [x] `P01.S01` - Add label, legal_refs, and modelos fields to ProfilePreflightRequirement; `src/cadrumo/application/user_profile/_commands.py`.
- [x] `P01.S02` - Populate the new fields in ProfilePreflightService.report() from the in-scope field object unioned with build_profile_grounding_index; `src/cadrumo/application/user_profile/_preflight.py`.
- [x] `P01.S03` - Add roundtrip and anti-tautology tests for the enriched ProfilePreflightRequirement; `src/cadrumo/application/user_profile/tests/`.

### Phase `P02` - Wire the three consumer surfaces

Thread the enriched requirement through the blocking-gate message, ProfilePreflightMissingPayload, and ModeloReadinessMissingRequirementPayload.

- [x] `P02.S04` - Add label, legal_refs, and modelos to ProfilePreflightMissingPayload and its construction site; `src/cadrumo/entrypoints/cli/_config_payloads.py`.
- [x] `P02.S05` - Add label, legal_refs, and modelos to ModeloReadinessMissingRequirementPayload and its construction site; `src/cadrumo/entrypoints/cli/_modelo_payloads.py`.
- [x] `P02.S06` - Render label and legal ref per missing field in the blocking-gate message by building the richer string in the context builder that feeds the existing profile_readiness_missing locale template; `the four locale catalogues needed no edit since the template's %{missing} placeholder was already generic - only the value passed into it changed; `src/cadrumo/application/modelo/_profile_readiness_gate.py`.

### Phase `P03` - Verify

Prove the enrichment with grounded regression tests, keep the JSON-schema-conformance and locale-parity gates green, and regenerate any affected generated CLI reference stubs.

- [x] `P03.S07` - Add a grounded regression proving the blocking-gate message text changes for a known missing field; `src/cadrumo/application/modelo/tests/`.
- [x] `P03.S08` - Run the JSON-schema-conformance and locale-coverage-parity gates and fix any red findings; `src/cadrumo/entrypoints/cli/tests/, src/cadrumo/tests/`.
- [x] `P03.S09` - Run apidocs scaffold --check and land regenerated CLI reference stubs if affected; `docs/api/`.

### Phase `P04` - Close out

Run mandatory code review and a fresh-context honesty review against this campaign's closure summary; action every finding as a fix, a recorded wontfix, or a linked follow-up before declaring the campaign complete. P04 does not depend on P05 or P06 closing - it reviews and records the state of P01-P03's surface; P05 (a different, concurrent session's scope - see P05's own note below) and P06 (this session's own follow-ups opened by P04.S10) remain open after P04 closes and are tracked independently.

- [x] `P04.S10` - Run the mandatory code review against the campaign diff and action every finding; `.vault/audit/`.
- [x] `P04.S11` - Run the fresh-context honesty review against the closure summary and close every item as fixed or a formally deferred follow-up; `.vault/audit/`.

### Phase `P05` - Execute the 2026-08-09 amendment: stop granting unassessed readiness

Implements the accepted 2026-08-09 amendment. The per-operation model_selectors axis carries zero modelo_ tokens, so the schema-required branch of ProfilePreflightService.report() is unreachable and the report returns ready=True for a profile declaring nothing. Make the unevaluated case distinguishable from a passing one, ground any axis population against official sources rather than inference, and open a detector for the deferred ProfileKey divergence. Ownership note: this phase is being executed by a separate, concurrent session, not the session that ran P01-P04 - S12 and S17 are that session's landed work, S13-S16 remain its open scope, and neither P04 nor P06 depends on this phase closing.

- [x] `P05.S12` - Make the unevaluated per-modelo case distinguishable from a passing one on ProfilePreflightReport, so a modelo matching no schema-required field reports not-assessed rather than ready; `src/cadrumo/application/user_profile/_preflight.py, src/cadrumo/application/user_profile/_commands.py`.
- [x] `P05.S13` - Surface the not-assessed signal as a CLI notice on config profile preflight and app modelo readiness, never as a clean bill of health; `src/cadrumo/entrypoints/cli/_config_payloads.py, src/cadrumo/entrypoints/cli/_modelo_payloads.py`.
- [x] `P05.S14` - Replace test_preflight_returns_ready_when_no_modelo_selectors_match, which encodes the current defect as the contract, with a regression asserting a profile declaring no facts is never reported ready for a modelo; `src/cadrumo/application/user_profile/tests/test_services.py`.
- [x] `P05.S15` - Inventory the grounded per-modelo profile-fact requirements from each modelo official form and its registry source=profile bindings, recording the evidence per token and refusing to infer any requirement that no source establishes; `correct the reference document's falsified model_selectors claim in the same action rather than leaving it standing beside the new inventory; `.vault/reference/, src/cadrumo/domain/calculations/registry/_profile_grounding.py`.
- [x] `P05.S16` - Populate model_selectors with the grounded modelo_ tokens from that inventory and prove the per-modelo branch now contributes, leaving _FILING_BASELINE_PROFILE_PATHS in force until it does; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [x] `P05.S17` - Add a parity gate failing with the field-level delta when the schema-required set and the PROFILE_KEYS-required set disagree, giving the deferred ProfileKey divergence a detector; `src/cadrumo/application/user_profile/tests/`.

### Phase `P06` - Follow-ups opened by the P04 code review

Tracks findings from the 2026-08-09 code-review and honesty-review audits that are real but were judged separable from the correctness fix batch already landed: the unmeasured hot-path authority tradeoff (including the duplicate report-build it subsumes), the two requirement-builder functions that remain unmerged despite being brought back into behavioural parity, the ADR's overstated Consequences claim, and the cross-modelo legal_refs scoping question.

- [x] `P06.S18` - Measure and reopen the hot-path authority decision: memoise build_profile_grounding_index per authority and thread it into require_profile_ready_for_modelo_work, keeping require_existing_profile_baseline_ready_for_modelo_work registry-free; `fold in removing config profile preflight's duplicate report build on the ready path; verification gate: a grounded regression asserting the blocking-gate refusal carries legal_refs for a field the grounding index covers, and a benchmark assertion bounding the added per-call cost; `src/cadrumo/application/modelo/_profile_readiness_gate.py, src/cadrumo/entrypoints/cli/_config/_profile_inspect.py`.
- [x] `P06.S19` - Merge ProfilePreflightService._requirement and _requirement_for_profile_path into one shared builder taking an optional grounding index; `verification gate: a parity test proving the merged builder's output is unchanged for every case the two prior functions covered; `src/cadrumo/application/user_profile/_preflight.py, src/cadrumo/application/modelo/_profile_readiness_gate.py`.
- [x] `P06.S20` - Correct the ADR's Consequences paragraph, which claims legal grounding and a per-operation why on the blocking refusal that the shipped code does not deliver (both baseline paths carry zero authority-independent legal_refs, and the per-operation axis is empty per the 2026-08-09 amendment); `state plainly which surfaces the grounding claim does and does not hold for; `.vault/adr/2026-08-08-profile-requirement-grounding-adr.md`.
- [x] `P06.S21` - Decide and record in the ADR whether a requirement row's legal_refs/modelos should be scoped to the caller's target modelo or remain the cross-modelo registry union as shipped; `a Modelo 303 preflight today can cite a Modelo 100 ministerial order as the legal basis for a missing tax id; `.vault/adr/2026-08-08-profile-requirement-grounding-adr.md`.

### Phase `P07` - Untracked findings inherited from the per-operation-axis audit, out of this ADR's implementation scope

The 2026-08-09 per-operation-axis-and-silent-defaults audit recorded two findings this campaign did not open rows for: a silent NIF/regime default reaching filing surfaces, and a no-op foral (CCAA) guard. Neither is caused by or fixable within this campaign's enrichment work - both predate it and live in unrelated modules - but per this project's close discipline an audit finding needs an owner, not silence. Scoped here as a distinct, separately-authorized unit of work rather than folded into P01-P06.

- [x] `P07.S22` - Ground and fix the silent tax-id/regime default: an absent profile yields NIF 00000000T and regime GENERAL across CLI surfaces instead of refusing or flagging the gap, per the per-operation-axis audit's finding two; `src/cadrumo/application/user_profile/_projections.py`.
- [x] `P07.S23` - Fix the no-op foral guard: tax_residence.ccaa being absent silently skips the parse_tax_region check instead of refusing, per the per-operation-axis audit's finding three; `src/cadrumo/application/modelo/_work_create_policy.py`.
- [x] `P07.S34` - Name the outstanding schema-required fields on the setup-incomplete refusal when the enumeration finds any, falling back to the existing generic wording for a cross-field-only failure, per the per-operation-axis audit's open ready-to-execute item; `src/cadrumo/application/modelo/_profile_readiness_gate.py, src/cadrumo/locales/{en,es,ca,hu}.yml`.

### Phase `P08` - CLI capability and legal-basis drift reconciliation

Expanded mandate: sweep every modelo registry schema and the user-profile schema for drift between ProfileKey (wizard-sourced) and ProfileFieldDefinition (schema.toml-sourced) declarations, and between registry source=profile binding legal_refs and the schema field's own legal_refs, then union every orphaned/undeclared side against grounded BOE/AEAT sources. Also reconciles the three CLI surfaces still reading the separate, disconnected ProfileKey mechanism (config profile status, wizard status, overview diagnostics) that the original ADR deferred.

- [x] `P08.S24` - Field-by-field parity audit between ProfileKey (domain/contribuyente/_keys.py, wizard-sourced) and ProfileFieldDefinition (schema.toml-sourced): every field present in one but not the other, every requirement-flag disagreement, every legal_refs/description mismatch; `persist as a dated reference document, no code changes in this step; `src/cadrumo/domain/contribuyente/_keys.py, src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, .vault/reference/`.
- [x] `P08.S25` - Sweep every modelo registry TOML under _data/registry/aeat/modelos/ for source=profile bindings and compare each binding's legal_refs against the corresponding schema.toml field's legal_refs; `record every field where one side carries grounding the other lacks, across the full registry not a sample; persist as a dated reference document, no code changes in this step; `src/cadrumo/_data/registry/aeat/modelos/, src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, .vault/reference/`.
- [x] `P08.S26` - Decompose the S24 and S25 inventories into one Step per discrete drifted field or surface once those inventories exist, each grounded against the bundled BOE or AEAT corpus before any value is added, and this row must not close without either the fan-out rows or an explicit recorded finding of zero drift; `decomposed from S24 and S25 findings, exact files TBD`.
- [x] `P08.S27` - Reconcile the three CLI surfaces that still read the separate ProfileKey-derived profile_health.missing_required mechanism and emit raw dotted paths (config profile status, wizard status, overview diagnostics): either wire them through the same enriched ProfilePreflightRequirement path this campaign built, or record a grounded reason each must stay on the separate mechanism; `src/cadrumo/entrypoints/cli/_config/_status_rendering.py, src/cadrumo/application/wizard/_status.py, src/cadrumo/application/diagnostics.py`.
- [x] `P08.S28` - Re-run the JSON-schema-conformance, locale-coverage-parity, and profile-key-schema-required-parity gates after the union, plus a grounded regression proving no field identified as drifted in S25/S26 remains unreconciled; `src/cadrumo/entrypoints/cli/tests/, src/cadrumo/tests/, src/cadrumo/application/user_profile/tests/`.
- [x] `P08.S35` - Add the 24 registry-grounded legal_refs to their schema.toml fields identified by S25, format-preserving and refusing on any target field not found, since each citation already exists and was corpus-verified on its registry binding and this is carrying it to the field, not new legal research; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [x] `P08.S36` - Run the mandatory fresh-context honesty review against the full P01-P08 closure and action every finding: strip campaign-metadata leaks from source comments and docstrings, correct the stale per-operation-axis docstring, and open a new audit finding for a real corpus-verified wrong legal citation the review's own gap analysis surfaced; `.vault/audit/, src/cadrumo/application/user_profile/_preflight.py, src/cadrumo/application/modelo/_profile_readiness_gate.py, four test files`.

## Parallelization

P01 is a hard prerequisite for P02 (the consumer surfaces cannot carry fields the row does not yet expose) and for P03. Within P01, S01 (model fields) must land before S02 (population logic); S03 (tests) follows S02. Within P02, S04, S05, and S06 touch independent files and may proceed in parallel once P01 is closed. P03 depends on all of P02 closing. P04 depends on P03 closing and reviews the surface P01-P03 shipped; it does not depend on P05, P06, or P07. P05 is a separate concurrent session's scope, sequenced only internally (S13-S14 depend on S12; S16 depends on S15; S17 is independent). P06's four Steps are independent of each other and of P05. P07's two Steps are independent of each other and of every other phase - they share no file with P01-P06.

## Verification

The plan is complete when every Step is closed (`- [x]`) with a matching execution record, the new roundtrip/anti-tautology tests in P01.S03 and the grounded regression in P03.S07 pass under a real (non-mocked) test run, the JSON-schema-conformance and locale-coverage-parity gates are green, and the P04 code-review and fresh-context honesty review close with zero outstanding unactioned findings. P04's own closure is independent of P05, P06, and P07 closing - those phases are tracked to completion separately and their remaining open Steps do not block declaring P01-P04 complete, provided each carries either a checked box with a matching execution record or stays visibly open with a named owner, as it does here.
