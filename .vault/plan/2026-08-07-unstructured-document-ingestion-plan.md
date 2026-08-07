---
tags:
  - '#plan'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:be882acf5bcdae280c456683568bc0f0866edb4912e010be388c5c7d89603384'
tier: L3
related:
  - '[[2026-08-07-unstructured-document-ingestion-adr]]'
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-08-06-invoice-canonical-structure-adr]]'
  - '[[2026-08-06-llm-invoice-read-reconciliation-adr]]'
---

# `unstructured-document-ingestion` plan

Build the transcription-anchored semantic ingestion pipeline the governing ADR decides, stage by stage, with every Step carrying a verification gate mapped to the corpus stage-oracle table.

## Description

Executes the unstructured-document-ingestion ADR (decisions D1 through D9): the four-stage pipeline behind the exactness probe, the anti-fabrication construction (anchoring, role resolution, arithmetic closure), the per-field provenance envelope, the widened loss-forbidden `InvoiceDraft` waist, the tabular column-role mapping lane, the engine abstraction under the amended gated-cloud ruling, and the two-lane measurement design. The package-split ADR governs the custody and boundary obligations W01 inherits, the canonical-invoice ADR governs the confirm boundary W02 P07 feeds, and the reconciliation ADR contributes the direction threading and counterparty rename consumed in W01 P03 and W02 P07.

Grounding against HEAD at authoring time, so no Step re-plans landed work: the canonical-format lane is closed and in HEAD (Facturae series, the discarded-counterparty projection fix, party names across Facturae, CII and UBL, the xml ingest crash fix, the vision-routing regression fix, and the whole VeriFactu and SII foundation with its batch reader, schema-derived mandatory enforcement, two-method CI oracle, payload probe, shape members and bundled schemas). None of that appears as work here. Two Steps in W02 P05 are closed at authoring time because the peer lane (unstructured-ingest-lead) already landed them, verified against HEAD rather than taken on report: the images-capability refusal boundary (`llm/_client.py`, `supports_images`, verified by `test_vision_capability_boundary.py`) and the Anthropic in-memory multimodal transport (`llm/_providers/anthropic.py`). They carry no exec records in this plan; this paragraph is the explicit record of why they are closed. The same lane owns the stage-2 product surface Step (W02.P05.S14), which is in flight and stays open until it lands. Two facts shape sequencing: stage 2 does not exist as a product surface today (the vision path collapses reading and reasoning into one image-to-fields call, and the text path uses no model), and `EvidenceInput` is not yet on the `application.ledger` facade, so W01.P01.S03 is a precondition of every consuming change.

Measurement discipline, carried from the ADR D9: the corpus at `Y:\code\llm-invoice-smoke\corpus` is external, read-only and not a git repository. Every measured result names key sha256 `e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593` (never the key's stale internal schema_version), and the corrected denominators are 48 stage1_reference_text transcriptions, 7 twin pairs, 130 vision-path documents, and 59 category-scorable documents. In-repo CI gates run only deterministic stages on bundled licence-clean fixtures with provenance sidecars, no mocks, no skips, and no model in CI. The measured harness lane owns every model-bearing figure, via the gated cloud route or a quiesced local run.

Explicitly deferred, carried from the ADR rather than dropped, and none planned here: handwriting recognition, multi-document scan bundles, counterparty resolution against the censo, bank-statement auto-detection redesign beyond the W03 fallback enrolment, eml ingestion, acquisition of real rendered Spanish documents and the hand transcription of the twelve real photographs (corpus work outside this repository), sanitizer wiring (peer-owned), and the reconciliation ADR's two open operator rulings (the domestic discriminator and the transcribed taxable base).

## Steps

## Wave `W01` - Contracts and the loss-forbidden waist

Delivers the typed foundations every later wave consumes: the core provenance and field-role taxonomies, the EvidenceInput facade promotion, the DocumentTranscription record with its encrypted cache, the widened InvoiceDraft with per-field provenance envelopes, and the projection-parity gate that makes the waist loss-forbidden. W02 and W03 depend on this wave. Authorized by the ADR decisions D1, D5 and D6 and the package-split ADR custody obligations.

### Phase `W01.P01` - Core taxonomies and facade preconditions

Lands the closed core enums and the facade promotion that every consuming change depends on.

- [ ] `W01.P01.S01` - Add the FieldOrigin provenance StrEnum (EXACT_STRUCTURED, TEXT_LAYER, VISION, TABULAR_MAPPED, OPERATOR) with facade export, gated by enum round-trip tests and the import-hygiene gate; `src/cadrumo/core`.
- [ ] `W01.P01.S02` - Add the closed FieldRole StrEnum for tabular column mapping including UNMAPPED, with facade export, gated by a test asserting every importer-consumed role is a member; `src/cadrumo/core`.
- [ ] `W01.P01.S03` - Promote EvidenceInput to the application.ledger public facade as a precondition of any consuming change, gated by the import-hygiene gate and a consumer-import test; `src/cadrumo/application/ledger/__init__.py`.

### Phase `W01.P02` - The transcription record and its encrypted cache

Lands the DocumentTranscription record with its custody tripwires and the secure-storage cache.

- [ ] `W01.P02.S04` - Add the single typed DocumentTranscription record (reading-order text with printed forms preserved, page count, source content address, origin with model identity and revision) carrying the EvidenceInput serialization tripwires, gated by a strict roundtrip and tripwire refusal tests; `src/cadrumo/application/ledger`.
- [ ] `W01.P02.S05` - Wire the encrypted transcription cache through core secure storage keyed by source content address plus transcriber identity, gated by a real-adapter roundtrip, an on-disk mutation anti-tautology proof, and the sensitive-persistence gate scan reaching the new module; `src/cadrumo/application/ledger`.

### Phase `W01.P03` - The widened draft, provenance envelopes, and the loss-forbidden waist

Widens InvoiceDraft, attaches per-field provenance, and lands the projection-parity and multi-recipient guards.

- [ ] `W01.P03.S06` - Add the per-field provenance envelope (FieldOrigin, verbatim anchor, grounding outcome, ambiguity candidates) to the draft model family, gated by a strict roundtrip with every defaultable field populated non-default; `src/cadrumo/application/ledger/_evidence_draft.py`.
- [ ] `W01.P03.S07` - Widen InvoiceDraft with a direction suggestion, retencion rate and amount, suplidos, discrepancy findings, and the transcription content address, verifying the counterparty rename against HEAD rather than re-landing it, gated by model and roundtrip tests; `src/cadrumo/application/ledger/_evidence_draft.py`.
- [ ] `W01.P03.S08` - Add the projection-parity gate asserting every draft field survives to the confirm-surface payload, proven by mutation: drop one field from the projection and observe red; `src/cadrumo/application/ledger/tests`.
- [ ] `W01.P03.S09` - Guard the multi-recipient case at the projection consumer so a batch-read record carrying several recipients surfaces rather than silently picking one, gated by a multi-recipient fixture test, inherited requirement from the einvoice batch-reader lane; `src/cadrumo/application/ledger`.
- [ ] `W01.P03.S10` - Surface the provenance envelopes on every operator-facing extract and confirm JSON payload at parity with casilla grounding, gated by the JSON schema conformance suite; `src/cadrumo/entrypoints/cli`.

## Wave `W02` - The document lane: acquisition, extraction, grounding, classification

Delivers stages S1 through S4 for documents: deterministic and vision transcription, the anchored semantic extraction surface, deterministic grounding with anchor checks, role resolution and arithmetic closure, and closed-set classification with deterministic direction derivation. Ends with the deletion of the Spanish-label regex extractor. Depends on W01. W04 measures what this wave builds. Authorized by ADR decisions D1 through D5 and D8.

### Phase `W02.P04` - S1 acquisition

Produces the faithful transcription from text-layer and vision sources.

- [ ] `W02.P04.S11` - Produce the deterministic text-layer transcription into DocumentTranscription with reading order and printed forms preserved, gated by fixture tests asserting byte-faithful printed forms; `src/cadrumo/application/ledger`.
- [ ] `W02.P04.S12` - Refit the vision path to a transcription-only role emitting DocumentTranscription with no field interpretation in S1, gated by schema-refusal tests that need no model, accuracy owned by the W04 measured lane; `src/cadrumo/llm/_evidence_draft_vision.py`.

### Phase `W02.P05` - S2 semantic extraction

Lands the anchored candidate schema and the local extraction surface, and records the engine-boundary work already landed by the peer lane.

- [ ] `W02.P05.S13` - Define the anchored candidate payload schema: strict, closed keys, a verbatim anchor per value, role evidence per identity field, gated by refusal tests including an out-of-schema key; `src/cadrumo/llm`.
- [ ] `W02.P05.S14` - Build the stage-2 semantic extraction surface over the transcription via LLMClient with role-named model settings, in flight in the unstructured-ingest-lead lane, gated by wiring tests mirroring test_local_text_reader_wiring.py, accuracy owned by the W04 measured lane; `src/cadrumo/llm`.
- [x] `W02.P05.S15` - Refuse an images-carrying request on an adapter that does not forward them via the supports_images capability boundary, landed at HEAD by the peer lane and verified by test_vision_capability_boundary.py; `src/cadrumo/llm/_client.py`.
- [x] `W02.P05.S16` - Carry the gated cloud multimodal transport on the Anthropic in-memory HTTP adapter for the measurement engine, landed at HEAD by the peer lane and verified by the capability-boundary suite; `src/cadrumo/llm/_providers/anthropic.py`.
- [ ] `W02.P05.S17` - Refuse cloud provider selection on real-evidence paths absent the explicit per-invocation consent acknowledgement, default-off and gestor-barred, gated by refusal tests on both the extract and confirm surfaces; `src/cadrumo/llm`.

### Phase `W02.P06` - S3 grounding and the regex deletion

Lands the deterministic grounding stage and deletes the Spanish-label regex extractor once the semantic reader is wired.

- [ ] `W02.P06.S18` - Enforce the anchor check: a candidate grounds only when its anchor occurs in the transcription and the typed value equals the deterministic parse of that anchor, proven by mutation with an off-document value observing red; `src/cadrumo/application/ledger`.
- [ ] `W02.P06.S19` - Resolve identity roles deterministically, excluding the taxpayer own NIF from counterparty candidacy and surfacing AMBIGUOUS with all candidates when role evidence does not pick exactly one, gated by the OP-PUR-COM-2026-0005_layout-minimal fixture never yielding a first-match id; `src/cadrumo/application/ledger`.
- [ ] `W02.P06.S20` - Emit arithmetic-closure findings over the identities total equals base plus cuota plus recargo plus suplido, cash equals total minus retencion, and per-rate sums, gated by both COM-2026-0005 fixture entries producing a blocking 890.00 versus 927.22 finding; `src/cadrumo/application/ledger`.
- [ ] `W02.P06.S21` - Route per-field degradation advisories through the typed Notice channel naming what was seen and why it was rejected, gated by envelope conformance tests; `src/cadrumo/entrypoints/cli`.
- [ ] `W02.P06.S22` - Delete the Spanish-label regex extractor family and its tests after the semantic reader is wired, gated by clean collection, zero remaining label-regex references, and the bundled fixtures passing through the new path; `src/cadrumo/application/ledger/_evidence_draft.py`.

### Phase `W02.P07` - S4 classification

Lands deterministic direction derivation and closed-set class and category selection.

- [ ] `W02.P07.S23` - Derive direction deterministically from the taxpayer own NIF role on the document and cross-check the verb-supplied kind, surfacing divergence as a finding, gated by real tests in both directions; `src/cadrumo/application/ledger`.
- [ ] `W02.P07.S24` - Integrate closed-set invoice class and category selection on the confirm suggestion path from registry-grounded allow-lists under the accepted suggest-review-apply contract, gated by an out-of-allow-list refusal test; `src/cadrumo/application/ledger`.

## Wave `W03` - The tabular lane

Delivers CSV and spreadsheet ingestion through the same pipeline: deterministic dialect normalization, the schema-level column-role mapping capability, deterministic row projection, importer consumption and statement-lane fallback enrolment, and row-level grounding. Depends on W01 for the FieldRole taxonomy and the widened draft, and on W02 P06 for the grounding primitives. Authorized by ADR decision D7.

### Phase `W03.P08` - Dialect normalization, column-role mapping, and consumers

Lands the whole tabular lane from dialect normalization through importer consumption and row-level grounding.

- [ ] `W03.P08.S25` - Normalize tabular dialects covering delimiter, decimal convention, encoding, preamble rows, summary rows and embedded newlines into one typed table, gated by all nine bundled operator CSV exports normalizing against the current 1-of-7 baseline; `src/cadrumo/adapters/inbound/financial`.
- [ ] `W03.P08.S26` - Build the semantic column-role mapping capability: observed headers to the closed FieldRole enum once per file, UNMAPPED surfaced and reported, never refuse-whole, gated by allow-list refusal tests, accuracy owned by the W04 measured lane; `src/cadrumo/llm`.
- [ ] `W03.P08.S27` - Project rows deterministically under a confirmed mapping so the model never touches a cell value, gated by a property test asserting projected values byte-equal their source cells; `src/cadrumo/adapters/inbound/financial`.
- [ ] `W03.P08.S28` - Consume the mapping lane from the invoice-book importer including a retencion role, gated by the libro registro fixture importing fully with unknown columns reported rather than refused; `src/cadrumo/entrypoints/cli`.
- [ ] `W03.P08.S29` - Enrol the mapping lane as statement-import fallback strictly after the exact fixed-layout providers, gated by a known-bank fixture still taking the exact provider and an unknown-format fixture reaching the mapping lane; `src/cadrumo/adapters/inbound/financial`.
- [ ] `W03.P08.S30` - Apply row-level S3 grounding to tabular rows where base, cuota and total are present, gated by a defective-row fixture surfacing a closure finding; `src/cadrumo/application/ledger`.

## Wave `W04` - Measurement and gates

Delivers the two measurement lanes the ADR D9 mandates: the in-repo CI gate lane on bundled licence-clean fixtures (injection regression, mutation-proof pass) and the offline measured harness lane pinned to the corpus key, producing the stage baselines and recording the acceptance floors. Depends on W02 and W03. Authorized by ADR decision D9 and the amended D8 engine-route ruling.

### Phase `W04.P09` - The in-repo gate lane

Bundles the licence-clean fixtures and lands the injection regression gate and the mutation-proof pass.

- [ ] `W04.P09.S31` - Bundle the licence-clean fixture subset with provenance sidecars, including both COM-2026-0005 entries, gated by the fixture-provenance gate cross-checking sidecar against physical evidence; `src/cadrumo/application/ledger/tests`.
- [ ] `W04.P09.S32` - Add the injection regression gate: an instruction-shaped transcription must cross the S2-S3 boundary with no unanchored value and no out-of-schema key, proven by mutation; `src/cadrumo/llm/tests`.
- [ ] `W04.P09.S33` - Run the mutation-proof pass over every W01 through W03 gate, breaking from outside the repo, observing red, restoring, and recording each red signature; `src/cadrumo`.

### Phase `W04.P10` - The measured harness lane

Builds the key-pinned harness and produces the stage baselines and recorded acceptance floors.

- [ ] `W04.P10.S34` - Build the harness runner pinned to key sha256 e2db6a49, recording model identity, revision and engine route on every result, stamping the corpus GAPS section-1 optimism caveat on every Spanish figure, and resolving twin pairs from the prose notes field until the corpus grows a structured link; `dev`.
- [ ] `W04.P10.S35` - Measure the S1 baseline over the 48 stage1_reference_text transcriptions, 7 twin pairs and 130 vision-path documents via the gated cloud route, with local production-model floors deferred to GPU headroom; `dev`.
- [ ] `W04.P10.S36` - Measure the S2 baseline over stage1_reference_text with fabrication on null-truth scored as a hard error and both COM-2026-0005 entries required to surface findings; `dev`.
- [ ] `W04.P10.S37` - Measure the S4 category baseline over the 59 category-scorable documents only, with the acquired-real set excluded by category_scorable false; `dev`.
- [ ] `W04.P10.S38` - Measure the tabular mapping baseline over the six csv_dialect descriptors, nine CSV exports and the libro registro header; `dev`.
- [ ] `W04.P10.S39` - Record the acceptance floors from the first measured baselines with the key hash, and wire subsequent harness runs to compare against them; `dev`.

## Parallelization

Waves are sequenced by default: W01 before W02 and W03, W04 last. W03 may start once W01 is complete and W02 P06 has landed its grounding primitives (S18 through S21), since the tabular lane consumes them at S30; the rest of W03 shares no files with W02. Within W01, P01 and P02 may run in parallel; P03 depends on both. Within W02, P04 and P05 may run in parallel after W01; P06 depends on both (S22, the regex deletion, additionally depends on S14, the wired semantic reader, and must never land before it, mirroring the package-split D5 window discipline); P07 depends on P06. Within W04, P09 may start as soon as W02 P06 lands; P10 depends on P09 for the fixture bundle and on the stages it measures. Hard ordering inside phases: S03 (the facade promotion) precedes every Step that imports `EvidenceInput`, S13 precedes S14, S31 precedes S32 and S33. S14 is owned by the in-flight unstructured-ingest-lead lane; before any edit near its surface, run `git diff` on the target files and abort on non-authored WIP.

## Sequencing hazards

The regex-deletion window: between S22 and a wired S14 there must be no state in which the text path has no reader. The two closed P05 Steps must not be re-executed; they are verification-only against HEAD. The corpus tree is never mutated by any Step.

## Verification

The plan is complete when every Step is closed and the following hold, each a verifiable check rather than an assertion:

- Every in-repo gate landed by W01 through W03 has a recorded mutation proof (break, observe red, restore), consolidated by S33. A gate without a recorded red is not counted.
- The projection-parity gate (S08) is red when any draft field is dropped from the confirm-surface payload, and green at HEAD.
- Both bundled COM-2026-0005 fixture entries produce findings on the live path: the checksum-failing id never grounds, the valid wrong-entity id resolves to AMBIGUOUS rather than a first-match, and the 890.00 versus 927.22 closure discrepancy is a blocking finding. Any configuration in which either entry scores clean fails the plan, per the corpus positive-control contract.
- The measured lane has produced and persisted baselines for S1, S2, S4 and the tabular mapping, each naming key sha256 e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593, the model identity and revision, and the engine route, with the Spanish optimism caveat attached to every Spanish figure, and the acceptance floors recorded (S39).
- The full-tree quality gates are green on the owner surface: `uv run --no-sync pytest --collect-only -q` collects clean, the import-hygiene and layering gates pass, and the JSON schema and documented-command conformance suites pass for every touched CLI surface. A red full-tree gate is triaged for ownership before any Step is closed against it.
- No Step is closed without a matching exec record, except W02.P05.S15 and S16, whose closure rationale is recorded in the Description (landed at HEAD by the peer lane before this plan existed, verified by the capability-boundary suite).
