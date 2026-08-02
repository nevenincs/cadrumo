---
tags:
  - '#plan'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-08-02'
body_hash: 'sha256:a628ceec8227d0b7237de97f3efed5ef3f6a0b99bf3107b10a7182d1c727e8a5'
tier: L3
related:
  - '[[2026-06-13-semantic-dedup-epic-audit]]'
  - '[[2026-06-13-semantic-dedup-epic-adr]]'
  - '[[2026-06-13-semantic-dedup-epic-research]]'
---

<!-- RETIRED: W02, P04, S08, S09, S10, S11, S12, S13, S14 -->

# `semantic-dedup-epic` plan

## Description

## Steps

## Wave `W01` - Pass 1 — Confirmed Duplication Removal

Remove the three confirmed real-duplication clusters from discovery Pass 1 (F1 tax-id, F2 dormant fichero money stack, F3 bucket-id boilerplate). Each step names a per-file site and its action with a verification gate.

### Phase `W01.P01` - F1 — Consolidate Spanish tax-id validation

Collapse the duplicated NIF/NIE/CIF validation and control-letter computation in core/identity/_tax_id.py and core/identity/_documents.py onto one owning core, re-expressing both public surfaces over it.

- [x] `W01.P01.S01` - Delegate _compute_nif_check_letter to the canonical nif_check_letter single source and remove the duplicate _NIF_LETTERS control-letter table; `src/aeat/core/identity/_documents.py`.
- [x] `W01.P01.S02` - Consolidate the duplicated _validate_nif/_validate_nie/_validate_cif core into one owning module and re-express the other module's validators over it; `src/aeat/core/identity/_tax_id.py`.
- [x] `W01.P01.S03` - Migrate the dual-module consumer to a single import site and run the identity validation test suite green; `src/aeat/domain/calculations/registry/_schema_scalars.py`.

### Phase `W01.P02` - F2 — Remove dormant fichero-BOE _formats money stack

Prove the adapters/outbound/aeat/export/_formats currency encode/serialise/deserialise stack has zero production consumers, then delete it or record an explicit retention rationale.

- [x] `W01.P02.S04` - Prove tree-wide that the _formats currency encode/serialise/deserialise path has zero production consumers outside its own package and tests; `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py`.
- [x] `W01.P02.S05` - Delete the dormant _formats currency encode/serialise/deserialise path and its tests, or record an explicit retention rationale if a near-term consumer is planned; `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`.

### Phase `W01.P03` - F3 — Extract shared repository bucket-id resolver

Replace the per-domain copy-pasted explicit-or-active-bucket resolver bodies with one shared helper parameterised by error_type.

- [x] `W01.P03.S06` - Add one shared resolve_repository_bucket_id helper parameterised by error_type as the single explicit-or-active-bucket resolver; `src/aeat/core/identity/_bucket.py`.
- [x] `W01.P03.S07` - Redirect every per-domain resolve_*_repository_bucket_id function to the shared helper and remove the copied bodies; `src/aeat/domain/filing/_runtime_repository.py`.

## Wave `W03` - Pass 3 — Structural Sweep Removal

Clean duplications surfaced by the whole-tree structural symbol sweep (production function names defined in 3+ files), confirmed fully substitutable and landed.

### Phase `W03.P05` - F5 — Consolidate storage_validation_error factory

Promote one canonical storage_validation_error to storage/errors.py and remove the seven byte-identical per-module copies and constants.

- [x] `W03.P05.S15` - Promote one canonical storage_validation_error to storage/errors.py and redirect the seven duplicate storage-module copies, removing the duplicate defs and message-key constants; `src/aeat/adapters/persistence/storage/errors.py`.

## Wave `W04` - Pass 4 — Behavior-Preserving Removal Sweep

Land every behavior-preserving consolidation surfaced by the structural sweep and the F4 re-examination, per the corrected directive that only behavior-changing merges are blocked.

### Phase `W04.P06` - F6 — Dedupe live-CLI metric-line and auth-preflight guard

Consolidate the identical _metric_line formatter and auth-preflight registration guard onto shared helpers.

- [x] `W04.P06.S16` - Consolidate the live-CLI _metric_line and auth-preflight guard onto shared helpers in _app_live_auth_preflight and redirect rendering, expedientes, justificante, notifications; `src/aeat/entrypoints/cli/_app_live_auth_preflight.py`.

### Phase `W04.P07` - F7 — Dedupe live-CLI active-bucket guard

Consolidate the four identical _bucket_id guards onto a shared resolve_active_bucket helper.

- [x] `W04.P07.S17` - Consolidate the four identical _bucket_id active-bucket guards onto a shared resolve_active_bucket helper; `src/aeat/entrypoints/cli/_app_live_verify_cli.py`.

### Phase `W04.P08` - F4 — Consolidate European-decimal separator parsing

Promote a canonical normalize_decimal_separators and redirect the eight inline separator sites.

- [x] `W04.P08.S18` - Promote canonical normalize_decimal_separators and redirect the eight inline European-decimal separator sites; `src/aeat/core/decimal/_coerce.py`.

### Phase `W04.P09` - F8 — Dedupe ledger _require_transaction guard

Consolidate the two identical application-ledger _require_transaction guards onto _actions_common.

- [x] `W04.P09.S19` - Consolidate the duplicate _require_transaction guard in _review_projection onto the canonical in _actions_common; `src/aeat/application/ledger/_review_projection.py`.

## Wave `W05` - Pass 2 — RAG cluster sweep (10 actionable clusters)

Action the ten actionable duplication clusters confirmed by Pass-2 discovery (audit 2026-06-14-semantic-dedup-epic-audit), ordered low-risk to shape-sensitive. Each step is one atomic relocation commit: canonical-site move plus every consumer update plus baseline updates plus clean collect-only, tagged relocation:<symbol>.

### Phase `W05.P10` - Warm-up — zero public-shape-change delegations

Delete-local + import-canonical for the four highest-confidence clusters with no public shape change: C4-2 _display_decimal, C2-1 selector_as_dict, C1-3 round_to_cents outlier, C3-1 iva_rate_kind.

- [x] `W05.P10.S20` - C4-2 Delete the duplicate _display_decimal and import the canonical from _actions_common; `src/aeat/application/ledger/_review_projection.py`.
- [x] `W05.P10.S21` - C2-1 Replace the three private selector-as-dict clones with the canonical selector_as_dict; `src/aeat/domain/calculations/registry/_binding_selector_utils.py`.
- [x] `W05.P10.S22` - C1-3 Replace the inline euro-cent quantize outlier with round_to_cents; `src/aeat/application/filing/_export.py`.
- [x] `W05.P10.S23` - C3-1 Consume the canonical iva_rate_kind and remove the rebuilt _iva_rate_to_iva_kind dict; `src/aeat/domain/iva/_invoice_classification.py`.

### Phase `W05.P11` - CLI active-bucket guard consolidation

C6-1: add a stateless active_bucket_id_or_refuse helper to _common and route the four ledger-family per-file copies through it.

- [x] `W05.P11.S24` - C6-1 Add stateless active_bucket_id_or_refuse to _common and route the four ledger-family copies through it; `src/aeat/entrypoints/cli/_common.py`.

### Phase `W05.P12` - File-hash family delegation

C1-2: delegate the five re-implemented chunked-read SHA-256 loops to core.hashing.hash_file/sha256_file, the pdf site retaining its error-wrap.

- [x] `W05.P12.S25` - C1-2 Delegate the five chunked-read SHA-256 loops to core.hashing.hash_file/sha256_file; `src/aeat/core/hashing.py`.

### Phase `W05.P13` - sha256_hex consolidation

C1-1: redirect the two named helper redeclarations then sweep the ~50-site inline hashlib.sha256().hexdigest() tail onto core.hashing.sha256_hex; enumerate with rg because RAG under-returns this tail.

- [x] `W05.P13.S26` - C1-1a Redirect the two named sha256-hex helper redeclarations to core.hashing.sha256_hex; `src/aeat/adapters/persistence/storage/sql/_secure_object_crypto.py`.
- [x] `W05.P13.S27` - C1-1b Sweep the inline hashlib.sha256().hexdigest() full-digest tail onto sha256_hex; `src/aeat/core/hashing.py`.

### Phase `W05.P14` - Factory and kernel extractions

C2-2: parameterized uppercase-alpha + unique-tuple validator factory in _binding_selector_utils. C5-1: shared content-hash verify kernel in outbound/storage.

- [x] `W05.P14.S28` - C2-2 Extract a parameterized uppercase-alpha and unique-tuple validator factory and route the copies through it; `src/aeat/domain/calculations/registry/_binding_selector_utils.py`.
- [x] `W05.P14.S29` - C5-1 Extract a shared content-hash verify kernel and route the two storage backends through it; `src/aeat/adapters/outbound/storage/_local.py`.

### Phase `W05.P15` - Shape-sensitive payload base extraction

C4-1: extract the common base of LedgerTransactionPayload and have the review payload extend it; serialized JSON must stay byte-identical per test_json_schema_conformance.

- [x] `W05.P15.S30` - C4-1 Extract the common base payload and have the review payload extend it, keeping serialized JSON byte-identical; `src/aeat/application/ledger/_models.py`.

## Wave `W06` - Pass 3 — cross-cutting concept families

Action the cross-cutting duplication clusters from the Pass-3 RAG swarm (serialization/formatting, error construction, repository/config, CLI rendering) that the directory-scoped Passes 1-2 missed. Each step is one atomic relocation commit (canonical-site move + consumer updates + baseline/apidocs updates + clean collect-only), tagged relocation:<symbol>. Big mechanical sweeps (inline ConfigDict, canonical-JSON kernel) are scripted with a dry-run review and committed via explicit owned-file pathspec; design extractions (catalogue base, snapshot-repo migration) verify against the conformance and roundtrip gates.

### Phase `W06.P16` - Quick canonical-consume wins

Delete-local + consume-canonical for small high-confidence clusters: A2 canonical_decimal_string, A3 display-decimal delegation, B3 resolve_error_message reuse, D1 id-truncation helper.

- [x] `W06.P16.S31` - A2 Replace the two zero-collapse canonical-decimal-string copies with domain canonical_decimal_string; `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `W06.P16.S32` - A3 Delegate _display_decimal and _decimal_to_string to core.decimal.format_decimal; `src/aeat/application/ledger/_actions_common.py`.
- [x] `W06.P16.S33` - B3 Reuse resolve_error_message and remove the inline localized-message copies; `src/aeat/entrypoints/cli/_modelo_cli_support.py`.
- [x] `W06.P16.S34` - D1 Extract one id-truncation display helper for the four ledger-rules sites; `src/aeat/entrypoints/cli/_ledger_rules_cli.py`.

### Phase `W06.P17` - Strict-frozen config consolidation

C2 module-local _STRICT_FROZEN re-declarations and C1 the 115-file inline ConfigDict literal tail onto the canonical STRICT_FROZEN_CONFIG; constraint-divergent ConfigDicts (extra keys) excluded.

- [x] `W06.P17.S35` - C2 Replace module-local _STRICT_FROZEN re-declarations with the aliased canonical import; `src/aeat/core/_models.py`.
- [x] `W06.P17.S36` - C1 Sweep the inline strict-frozen ConfigDict literal tail onto STRICT_FROZEN_CONFIG; `src/aeat/core/_models.py`.

### Phase `W06.P18` - Canonical-JSON content-hash kernel

A1 add a core.hashing canonical-JSON helper and route the ~12 cross-layer json.dumps(sort_keys,separators).encode()+sha256 sites through it; plus the datetime ISO-parse helper for the Z-suffix sites.

- [x] `W06.P18.S37` - A1 Add core.hashing canonical-JSON content-hash helper and route the cross-layer json+sha256 sites through it; `src/aeat/core/hashing.py`.
- [x] `W06.P18.S38` - A1b Add a core ISO-datetime parse helper for the Z-suffix fromisoformat sites; `src/aeat/core/time.py`.

### Phase `W06.P19` - Repository and error structural extractions

B1 secure-object catalogue integrity-error wrapper, B2 migrate hand-rolled live-snapshot repos onto SecureSnapshotRepository, C3 single-catalogue repository base, C4 ledger catalogue helper triplet.

- [x] `W06.P19.S39` - B1 Extract a secure-object catalogue integrity-error wrapper and route the exact-shape repositories through it; `src/aeat/adapters/persistence/storage/errors.py`.
- [x] `W06.P19.S40` - B2 Migrate the borrador/censo/justificante hand-rolled snapshot repos onto SecureSnapshotRepository; `src/aeat/application/live/_snapshot_base.py`.
- [x] `W06.P19.S41` - C3 Extract a single-catalogue secure repository base and route the four substitutable catalogue repos through it; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W06.P19.S42` - C4 Extract a shared ledger catalogue load/save helper for the evidence and business-invoice modules; `src/aeat/application/ledger/_evidence.py`.

## Wave `W07` - Pass 5 - Adjacent-domain hardening

Extend the completed first-pass canonical-home decisions to audited adjacent-domain consumers, adding one evidence-backed action row at a time.

### Phase `W07.P20` - Hardened signing-key publication

Route maintainer corpus-signing key persistence through the established hardened atomic secret-write owner without changing the keypair wire contract.

- [x] `W07.P20.S43` - Route corpus-signing keypair publication through the hardened atomic text writer and retain real key reload-and-signing proof; `src/cadrumo/core/corpus_manifest/_bundle_signing.py`.

### Phase `W07.P21` - Replay artifact persistence

Route durable replay trace and envelope artifacts through the canonical atomic text writer while preserving redaction and persistence-error boundaries.

- [x] `W07.P21.S44` - Persist replay trace and envelope artifacts through the atomic text writer while retaining redaction and caller-specific persistence errors; `src/cadrumo/core/observability/_store.py`.

### Phase `W07.P22` - Justificante target matching

Move shared receipt-to-filing target comparison into the Justificante domain record, including its optional presentation-identity refinement.

- [x] `W07.P22.S45` - Route filing, import, live, overview, and filed-history receipt target checks through one Justificante matching contract; `src/cadrumo/domain/justificante/_schema.py`.

### Phase `W07.P23` - Atomic export publication

Route ledger and filing payload publication through the core atomic byte-write owner without moving ledger-event or modelo-render ordering.

- [x] `W07.P23.S46` - Persist ledger and filing export payloads through atomic_write_bytes while preserving their existing post-write behavior; `src/cadrumo/application/ledger/_actions_export.py; src/cadrumo/application/filing/_export.py`.

### Phase `W07.P24` - Filing-grade evidence policy

Establish one typed eligibility policy beside ExternalEvidenceKind and route cross-period, overview, and filed-history consumers through it.

- [x] `W07.P24.S47` - Replace duplicated justificante-backed ExternalEvidenceKind sets with one domain eligibility policy; `src/cadrumo/domain/modelos/_filing_record.py; src/cadrumo/application/calculations/_cross_period_clean_state.py; src/cadrumo/application/overview/_calendar_evidence.py; src/cadrumo/application/live/_filed_observation_persistence.py`.

### Phase `W07.P25` - Official observation-source taxonomy

Introduce one public typed official-AEAT capability for calculation observation provenance without conflating it with external filing-evidence eligibility.

- [x] `W07.P25.S48` - Type official filing-observation source kinds and route persistence, cross-period, and overview classification through their shared capability; `src/cadrumo/application/calculations/_observations_repository.py; src/cadrumo/application/live/_filed_observation_persistence.py; src/cadrumo/application/calculations/_cross_period_clean_state.py; src/cadrumo/application/overview/_calendar_evidence.py`.

### Phase `W07.P26` - Atomic official-manual publication

Publish streamed official PDFs and their manifests without exposing a partially replaced authoritative pair.

- [x] `W07.P26.S49` - Publish streamed official manual PDFs through a bounded sibling staging primitive and publish the manifest atomically only after successful PDF replacement; `src/cadrumo/domain/manuals/_fetch.py; src/cadrumo/domain/manuals/tests/test_fetch.py`.

### Phase `W07.P27` - Registry casilla-constraint projection

Preserve complete registry-owned constraint semantics in filing validation instead of reinterpreting partial bounds.

- [x] `W07.P27.S50` - Route filing schema projection and validation through the complete registry CasillaConstraints contract, including sign semantics; `src/cadrumo/application/filing; src/cadrumo/domain/calculations/registry; src/cadrumo/application/filing/tests`.

### Phase `W07.P28` - MCP envelope parser authority

Make every in-process MCP result use the strict core JSON envelope contract.

- [x] `W07.P28.S51` - Route MCP in-process result decoding through the strict core envelope parser while preserving transport-specific acquisition; `src/cadrumo/entrypoints/mcp; src/cadrumo/core; src/cadrumo/entrypoints/mcp/tests`.

### Phase `W07.P29` - Registry scalar input routing

Route filing scalar inputs through the registry data-type family rather than an incomplete text-only branch.

- [x] `W07.P29.S52` - Classify filing input channels through the canonical registry scalar family and preserve its typed validation for non-text string casillas; `src/cadrumo/application/filing; src/cadrumo/domain/calculations/registry; src/cadrumo/application/filing/tests`.

### Phase `W07.P30` - MCP transport error-envelope authority

Project MCP installation and timeout transport refusals through the canonical error-envelope contract.

- [x] `W07.P30.S53` - Route MCP timeout and installed-CLI resolution refusals through one canonical transport-error envelope with parity coverage on direct and execute paths; `src/cadrumo/entrypoints/mcp; src/cadrumo/core; src/cadrumo/entrypoints/mcp/tests`.

### Phase `W07.P31` - Local spreadsheet decimal boundary

Use the canonical finite European-decimal parser for local casilla spreadsheet ingestion.

- [x] `W07.P31.S54` - Route local casilla spreadsheet values through canonical finite European-decimal normalization while preserving row-specific refusal context; `src/cadrumo/application/modelo; src/cadrumo/application/modelo/tests`.

### Phase `W07.P32` - Google Sheets numeric input authority

Use one finite decimal coercion policy for spreadsheet pull values and refuse malformed numeric edits.

- [x] `W07.P32.S55` - Route Google Sheets numeric casilla and binding edits through canonical finite coercion and refuse malformed or non-finite values without zero substitution; `src/cadrumo/adapters/outbound/google; src/cadrumo/adapters/outbound/google/tests`.

### Phase `W07.P33` - Invoice taxable-base precision authority

Give invoice creation and review editing one cent-precision parser for the same taxable-base field.

- [x] `W07.P33.S56` - Route review invoice taxable-base edits through the canonical two-fractional-digit amount parser and retain independent precision regression coverage; `src/cadrumo/application/review; src/cadrumo/application/review/tests`.

### Phase `W07.P34` - Declarations Sede URL authority

Keep declarations listing and cotejo URL primitives in one non-shadowed authority.

- [x] `W07.P34.S57` - Remove duplicate declarations-fetch Sede URL assignments and retain landed-origin plus static single-definition coverage; `src/cadrumo/adapters/outbound/aeat/sede; src/cadrumo/adapters/outbound/aeat/sede/tests`.

### Phase `W07.P35` - Strict IVA history selection

Route Modelo 303 strict history persistence through the shared filed-observation ranking and ordering authority.

- [x] `W07.P35.S58` - Delegate strict Modelo 303 IVA history selection and ordering to the shared filed-observation selector while retaining input and reload guards; `src/cadrumo/application/live; src/cadrumo/application/live/tests`.

### Phase `W07.P36` - Registry casilla input resolution

Centralize registry snapshot lookup and casilla-key normalisation while preserving caller-specific refusal contracts.

- [x] `W07.P36.S59` - Extract typed registry snapshot and casilla normalisation authority for amendment/import and fail-soft readers; `src/cadrumo/application/modelo; src/cadrumo/application/modelo/tests`.

### Phase `W07.P37` - Calculation input revision projection

Use the canonical work-unit registry resolver for calculate input normalisation.

- [x] `W07.P37.S60` - Project the canonical work-unit snapshot resolver in calculate input and retain stale/correct revision behavior; `src/cadrumo/application/modelo; src/cadrumo/application/modelo/tests`.

### Phase `W07.P38` - Sede navigation timeout authority

Keep the settings-backed navigation timeout accessor in the Sede browser constants boundary.

- [x] `W07.P38.S61` - Centralize the Sede navigation timeout accessor and preserve declarations timeout behavior under a settings override; `src/cadrumo/adapters/outbound/aeat/sede; src/cadrumo/adapters/outbound/aeat/sede/tests`.

### Phase `W07.P39` - Notification table-domain classification

Classify neutral summary rows from their notifications or communications table semantics.

- [x] `W07.P39.S62` - Carry summary-table semantics into notification row classification and cover neutral communication rows; `src/cadrumo/adapters/outbound/aeat/sede; src/cadrumo/adapters/outbound/aeat/sede/tests`.

### Phase `W07.P40` - Notification landed-origin provenance

Record the validated AEAT host that served notification evidence rather than the requested host.

- [x] `W07.P40.S63` - Pass validated notification landing origins into parser provenance and cover sibling-host snapshot and row URLs; `src/cadrumo/adapters/outbound/aeat/sede; src/cadrumo/adapters/outbound/aeat/sede/tests`.

### Phase `W07.P41` - Validation context redaction

Use one core redaction policy for flow and wizard diagnostics.

- [x] `W07.P41.S64` - Re-home validation-context redaction in core and prove flow/wizard parity across sensitive context shapes; `src/cadrumo/core; src/cadrumo/application/flows; src/cadrumo/application/wizard`.

### Phase `W07.P42` - Cl@ve provider common mechanics

Share target, probe, and browser-resource mechanics while retaining provider-specific auth surfaces.

- [x] `W07.P42.S65` - Extract provider-neutral target, probe, and browser lifecycle helpers for Cl@ve Móvil and Cl@ve Permanente; `src/cadrumo/adapters/outbound/aeat/auth; src/cadrumo/adapters/outbound/aeat/auth/tests`.

### Phase `W07.P43` - Envelope header validation

Use one required-header validator for flat payload and multi-segment envelope serialization.

- [x] `W07.P43.S66` - Route envelope required-header checks through the shared validator with caller-specific wording and parity coverage; `src/cadrumo/adapters/outbound/aeat/export/_formats; src/cadrumo/adapters/outbound/aeat/export/_formats/tests`.

### Phase `W07.P44` - Modelo projection decimal wire format

Render projection payload decimals through the canonical CLI JSON normalization authority.

- [x] `W07.P44.S67` - Replace Modelo projection decimal stringification with canonical JSON wire formatting and pin exponent-free values; `src/cadrumo/entrypoints/cli; src/cadrumo/entrypoints/cli/tests`.

### Phase `W07.P45` - Modelo 145 export encoder authority

Render M145 communication layouts through the canonical fixed-width encoder while retaining record-specific error semantics.

- [x] `W07.P45.S68` - Adapt M145 record values to canonical fixed-width export specs and prove money/text byte parity for the registry layout; `src/cadrumo/application/modelo; src/cadrumo/adapters/outbound/aeat/export; src/cadrumo/application/modelo/tests`.

### Phase `W07.P46` - Diagnostics date-bound parsing

Make supplied blank diagnostic and ledger date bounds refuse through the canonical required-date gate.

- [x] `W07.P46.S69` - Route diagnostics and ledger supplied date bounds through the shared ISO date parser while retaining absent-option behavior; `src/cadrumo/entrypoints/cli; src/cadrumo/entrypoints/cli/tests`.

### Phase `W07.P47` - Ledger lifecycle validation rendering

Use the canonical localized all-error renderer for ledger lifecycle validation failures.

- [x] `W07.P47.S70` - Remove the lifecycle-local ledger validation formatter and assert localized split refusals through the shared formatter; `src/cadrumo/entrypoints/cli; src/cadrumo/entrypoints/cli/tests`.

### Phase `W07.P48` - IVA legal-reference authority

Bind IVA catalogue citations and rate records to registry legal identities and bundled corpus evidence.

- [x] `W07.P48.S71` - Replace IVA free-form citation identities with a registry legal-reference bridge and verify article/corpus grounding; `src/cadrumo/domain/iva; src/cadrumo/domain/calculations/registry; src/cadrumo/domain/iva/tests`.
- [x] `W07.P48.S73` - Replace free-form IVA rate-record legal references with a registry-backed source bridge and verify every shipped rate reference; `src/cadrumo/domain/iva; src/cadrumo/domain/calculations/registry; src/cadrumo/domain/iva/tests`.
- [x] `W07.P48.S159` - Bundle reviewed article-level foreign VAT authority corpus and migrate every shipped rate row to plural registry legal identities; `IVA rate catalogue; foreign VAT legal catalogue; authoritative corpus sidecars; IVA rate verification tests`.

### Phase `W07.P49` - Foreign-asset threshold authority

Resolve Modelo 720 and 721 declaration thresholds from their effective registry parameters rather than duplicated core constants.

- [x] `W07.P49.S72` - Route foreign-asset declaration thresholds and grounding through effective registry parameters and prove 720/721 revision parity; `src/cadrumo/core; src/cadrumo/application/aggregation; src/cadrumo/domain/calculations/registry; src/cadrumo/**/tests`.

### Phase `W07.P50` - Modelo 303 carry-forward policy

Share the registry-verified Modelo 303 compensation derivation policy between filed persistence and Sede parsing.

- [x] `W07.P50.S74` - Extract the Modelo 303 carry-forward derivation and operand policy while retaining boundary-specific evidence and provenance mapping; `src/cadrumo/application/live; src/cadrumo/adapters/outbound/aeat/sede; src/cadrumo/domain/iva_compensation; src/cadrumo/**/tests`.

### Phase `W07.P51` - Profile effective-fact projection

Make every consumer of a profile fact use one stable effective-value selection and rendering policy.

- [x] `W07.P51.S75` - Route output-language hint refresh and active profile resolution through one effective-fact projection.; `src/cadrumo/application/user_profile; focused real-behavior tests`.

### Phase `W07.P52` - Registry diff temporal selection

Make registry comparisons consume the canonical year-only revision selector and preserve application-boundary diagnostics.

- [x] `W07.P52.S76` - Delegate registry diff revision selection to the temporal authority, including validity-window and refusal parity.; `src/cadrumo/application/registry; focused real-registry tests`.

### Phase `W07.P53` - IVA wallet amount policy

Keep the non-negative wallet mutation invariant in one application policy guard.

- [x] `W07.P53.S77` - Extract shared non-negative validation for IVA wallet seed, correction, and override mutations.; `src/cadrumo/application/modelo; real wallet boundary tests`.

### Phase `W07.P54` - Product command identity normalization

Make runtime rendering and locale maintenance use one stale-command replacement policy.

- [x] `W07.P54.S78` - Centralize stale CLI executable normalization under product identity and route renderer and locale manager through it.; `src/cadrumo/core; src/cadrumo/locales; focused identity and locale tests`.

### Phase `W07.P55` - One-based export coordinates

Ensure registry export layouts cannot represent a coordinate rejected by binding and BOE wire encoders.

- [x] `W07.P55.S79` - Centralize the positive one-based export offset constraint across registry, binding, and BOE wire models.; `src/cadrumo/core; registry and export schema tests`.

### Phase `W07.P56` - Renta WEB replay decimal parsing

Make replay expectation serialization reuse the production Renta WEB decimal parser.

- [x] `W07.P56.S80` - Route Renta WEB replay expected values through the canonical decimal parser and fixed-point serialization adapter.; `src/cadrumo/domain/calculations/registry; Renta WEB replay tests`.

### Phase `W07.P57` - Declaration verification period context

Make verification fixture period dates consume the typed domain period authority.

- [x] `W07.P57.S81` - Replace declaration verification local filing-date mapping with Period and calculation_filing_date.; `src/cadrumo/adapters/inbound/declaracion/tests; domain period contract tests`.

### Phase `W07.P58` - Envelope scalar normalization

Use one fixed-point and POSIX-path normalizer across envelope and direct JSON output.

- [x] `W07.P58.S82` - Route JSON envelope scalar conversion through the core output renderer normalizer.; `src/cadrumo/core/json_contract.py; core JSON contract tests`.

### Phase `W07.P59` - CLI formula provenance identifiers

Keep every casilla provenance projection constrained by the registry FormulaId contract.

- [x] `W07.P59.S83` - Type Modelo provenance formula identifiers with FormulaId and prove cross-surface refusal parity.; `src/cadrumo/entrypoints/cli/_modelo_payloads.py; CLI payload tests`.

### Phase `W07.P60` - Ledger issue detail projection

Keep ledger and Modelo readiness issue text as strict as the domain preflight contract.

- [x] `W07.P60.S84` - Constrain ledger and Modelo readiness issue detail payloads to the domain preflight minimum.; `src/cadrumo/entrypoints/cli/_ledger_payloads.py; src/cadrumo/entrypoints/cli/_modelo_payloads.py; CLI payload tests`.

### Phase `W07.P61` - Profile validation severity projection

Keep profile-validation CLI severities constrained by the canonical core severity enum.

- [x] `W07.P61.S85` - Project profile validation severity as BaseSeverity and reject arbitrary CLI tokens.; `src/cadrumo/entrypoints/cli/_config_payloads.py; profile inspection commands; CLI payload tests`.

### Phase `W07.P62` - Profile registry severity authority

Use the core severity primitive for profile-registry contract findings while excluding informational outcomes.

- [x] `W07.P62.S86` - Replace profile registry contract severity enum with BaseSeverity and update all consumers.; `src/cadrumo/domain/user_profile/_registry_contract.py; affected registry contract tests`.

### Phase `W07.P63` - Overview twelve-month boundary

Use the legal recargo anniversary utility for historical overview warnings.

- [x] `W07.P63.S87` - Route overview twelve-month warning arithmetic through the canonical recargo anniversary helper.; `src/cadrumo/domain/deadlines; src/cadrumo/application/overview/_explain.py; overview tests`.

### Phase `W07.P64` - Overview prescription boundary

Use the retention domain's legal floor and safe calendar arithmetic for overview warnings.

- [x] `W07.P64.S88` - Expose retention's whole-year helper and route overview prescription warnings through it.; `src/cadrumo/domain/retention; src/cadrumo/application/overview/_explain.py; retention and overview tests`.

### Phase `W07.P65` - Registry citation transport contracts

Preserve strict legal citation projections through every registry-citation CLI envelope.

- [x] `W07.P65.S89` - Replace permissive citation payload dictionaries with application projection models.; `src/cadrumo/entrypoints/cli/_registry_corpus_payloads.py; registry corpus payload tests`.

### Phase `W07.P66` - Modelo finding transport contract

Preserve typed verification finding kind, severity, grounding, and message requirements in CLI JSON.

- [x] `W07.P66.S90` - Type Modelo verification finding payloads from the domain contract and reject malformed rows.; `src/cadrumo/entrypoints/cli/_modelo_payloads.py; _modelo_rendering.py; CLI payload tests`.

### Phase `W07.P67` - Registry diff identifier contracts

Keep typed registry identifiers and legal references intact in revision-diff CLI payloads.

- [x] `W07.P67.S91` - Type registry diff payload IDs and legal references to match application diff rows.; `src/cadrumo/entrypoints/cli/_registry_diff_payloads.py; diff payload tests`.

### Phase `W07.P68` - LLM HTTP success boundary

Make all LLM provider adapters accept only 2xx HTTP responses.

- [x] `W07.P68.S92` - Reject non-2xx LLM provider responses in the shared HTTP checker.; `src/cadrumo/adapters/outbound/llm/_providers/base.py; provider tests`.

### Phase `W07.P69` - LLM retry-delay validation

Refuse non-finite and negative retry hints at the shared LLM provider boundary.

- [x] `W07.P69.S93` - Require finite non-negative Retry-After seconds in the LLM provider parser.; `src/cadrumo/adapters/outbound/llm/_providers/base.py; provider tests`.

### Phase `W07.P70` - LLM malformed response boundary

Convert malformed successful provider responses into typed provider errors.

- [x] `W07.P70.S94` - Normalize malformed LLM provider response shapes to LLMProviderError.; `src/cadrumo/adapters/outbound/llm/_providers; provider response tests`.

### Phase `W07.P71` - Config repair payload contract

Make nested config-repair JSON rows strict typed projections.

- [x] `W07.P71.S95` - Type config repair report sections and diagnostic rows at the CLI boundary.; `src/cadrumo/entrypoints/cli/_config_payloads.py; config repair payload tests`.

### Phase `W07.P72` - Storage byte-length integrity

Refuse provider metadata whose byte length disagrees with downloaded payload bytes.

- [x] `W07.P72.S96` - Share exact payload byte-length validation across local and Google storage reads.; `src/cadrumo/adapters/outbound/storage; storage provider regression tests`.

### Phase `W07.P73` - Ledger evidence media normalization

Classify PDF and image evidence from one normalized media-type token.

- [x] `W07.P73.S97` - Use canonical media-type normalization for ledger evidence input classification.; `src/cadrumo/domain/attachments; src/cadrumo/application/ledger; evidence input tests`.

### Phase `W07.P74` - Recargo legal-reference ownership

Keep overdue recovery legal grounding solely on the resolved registry band.

- [x] `W07.P74.S98` - Remove the redundant recovery legal reference and read grounding from RecargoBand.; `src/cadrumo/domain/deadlines; recargo regression tests`.

### Phase `W07.P75` - Google OAuth endpoint trust boundary

Validate persisted OAuth endpoints as canonical Google HTTPS origins before library use.

- [x] `W07.P75.S99` - Enforce strict canonical Google OAuth endpoint URLs on client and token records.; `src/cadrumo/adapters/outbound/google/_records.py; OAuth record and flow tests`.

### Phase `W07.P76` - Drive pagination containment

Refuse repeated Drive page tokens at every production list boundary.

- [x] `W07.P76.S100` - Share repeated-token validation across Drive folder, namespace, and object pagination.; `src/cadrumo/adapters/outbound/storage; src/cadrumo/adapters/outbound/google; Drive listing tests`.

### Phase `W07.P77` - Active pointer identity contract

Validate active-profile pointer bucket selectors with the canonical BucketId.

- [x] `W07.P77.S101` - Type BucketPointer bucket_id as canonical BucketId and cover whitespace and length refusal.; `src/cadrumo/core/_bucket_pointer.py; core pointer tests`.

### Phase `W07.P78` - Borrador snapshot identity contract

Constrain Modelo 100 snapshot and supersession links to canonical SnapshotId.

- [x] `W07.P78.S102` - Type Borrador100 snapshot identities with SnapshotId and cover malformed persisted values.; `src/cadrumo/application/live/_borrador_100.py; Borrador snapshot tests`.

### Phase `W07.P79` - Review queue enum transport

Keep review severity and state closed at the CLI JSON boundary.

- [x] `W07.P79.S103` - Type review queue payload severity and state with canonical review enums.; `src/cadrumo/entrypoints/cli/_review_payloads.py; review payload tests`.

### Phase `W07.P80` - Profile archive transport contract

Preserve canonical archive integrity metadata in CLI JSON results.

- [x] `W07.P80.S104` - Type archive CLI digest, version, timestamp, size, and profile identity fields.; `src/cadrumo/entrypoints/cli/_config_payloads.py; archive CLI tests`.

### Phase `W07.P81` - Validate Modelo deadline posture invariant

Make the one-sided, non-negative voluntary-deadline state an enforced application and CLI transport contract.

- [x] `W07.P81.S105` - Enforce valid date and exactly-one non-negative deadline posture across application and CLI payload boundaries.; `src/cadrumo/application/modelo/_work_plazo.py; src/cadrumo/entrypoints/cli/_modelo_payloads.py; focused deadline tests`.

### Phase `W07.P82` - Guard malformed Drive folder-list entries

Convert malformed successful Drive file rows into typed storage failures before document classification.

- [x] `W07.P82.S106` - Validate each successful Drive folder-list row before document classification and refuse malformed id/name/MIME entries with typed context.; `src/cadrumo/adapters/outbound/google/_document_link_resolver.py; real generated-client folder-list tests`.

### Phase `W07.P83` - Require canonical Drive content digests

Refuse unverified Google Drive payload metadata before bytes can cross the read boundary.

- [x] `W07.P83.S107` - Require a well-formed full SHA-256 content hash on every Google Drive read and refuse missing, MD5-only, or malformed metadata.; `src/cadrumo/adapters/outbound/storage/_integrity.py; src/cadrumo/adapters/outbound/storage/_google_drive.py; focused integrity tests`.

### Phase `W07.P84` - Unify Drive app-properties contract

Make provider serialization and metadata reads use the public typed Drive app-properties record.

- [x] `W07.P84.S108` - Replace obsolete Drive commit-log fields with the runtime storage metadata contract and validate writes and reads through it.; `src/cadrumo/adapters/outbound/google/_records.py; src/cadrumo/adapters/outbound/storage/_google_drive.py; focused record tests`.

### Phase `W07.P85` - Validate Google API response mappings

Refuse malformed successful Google API bodies at the common execution boundary.

- [x] `W07.P85.S109` - Reject non-mapping 2xx Google API bodies with typed action context before endpoint-specific consumption.; `src/cadrumo/adapters/outbound/google/_api.py; real HttpRequest response tests`.

### Phase `W07.P86` - Type ledger snapshot identities

Use canonical transaction and hex-64 snapshot identities throughout ledger filing snapshots and evidence.

- [x] `W07.P86.S110` - Replace weak ledger snapshot, fingerprint, and transaction fields with canonical identity aliases and refuse malformed persistence values.; `src/cadrumo/domain/modelos/_ledger_filing_snapshot.py; snapshot and evidence persistence tests`.

### Phase `W07.P87` - Harden ledger export CLI projections

Preserve canonical ledger export metadata and row contracts across JSON transport.

- [x] `W07.P87.S111` - Type ledger export metadata and nested rows with canonical identity, date, amount, currency, digest, and non-negative size constraints.; `src/cadrumo/entrypoints/cli/_ledger_payloads.py; export payload round-trip/refusal tests`.

### Phase `W07.P88` - Harden overview calendar payloads

Reuse calendar read-model state and range invariants at the overview CLI transport boundary.

- [x] `W07.P88.S112` - Type calendar evidence and range payloads with canonical closed states, CSV consistency, and ordered-date validation.; `src/cadrumo/entrypoints/cli/_overview_payloads.py; focused overview payload tests`.

### Phase `W07.P89` - Type Modelo filing-record transport

Project filing records and external evidence through their canonical domain contracts.

- [x] `W07.P89.S113` - Type Modelo filing records and external evidence with canonical enums, dates, identities, and grounding consistency.; `src/cadrumo/entrypoints/cli/_modelo_payloads.py; filing-record payload tests`.

### Phase `W07.P90` - Type Google sync probe provider kind

Project Google sync probe provider kind through the canonical storage enum.

- [x] `W07.P90.S114` - Type the Google sync probe provider kind from the canonical storage contract and refuse invalid transport values.; `src/cadrumo/entrypoints/cli/_config/_google_payloads.py; Google sync probe payload tests`.

### Phase `W07.P91` - Type telemetry status tier

Project telemetry status tier through the canonical telemetry enum.

- [x] `W07.P91.S115` - Type telemetry status output from the canonical telemetry tier and reject unknown transport values.; `src/cadrumo/entrypoints/cli/_diagnostics_payloads.py; diagnostics telemetry payload tests`.

### Phase `W07.P92` - Type profile capability payloads

Project profile capability decision transport through its canonical enums.

- [x] `W07.P92.S116` - Type capability and source payload fields with canonical capability enums and refuse malformed values.; `src/cadrumo/entrypoints/cli/_config/_capabilities_payloads.py; capability payload tests`.

### Phase `W07.P93` - Type Censo pull fact payloads

Project Censo facts through the canonical profile-path and provenance contract.

- [x] `W07.P93.S117` - Adopt canonical user-profile facts in Censo pull payloads and reject malformed paths and provenance.; `src/cadrumo/entrypoints/cli/_config/_censo_payloads.py; Censo payload tests`.

### Phase `W07.P94` - Type collaboration recipient payloads

Project recipient public-key rows through their canonical identity and fingerprint contract.

- [x] `W07.P94.S118` - Adopt canonical recipient fingerprint records at the collaboration CLI boundary and reject malformed identity/key/timestamp/fingerprint data.; `src/cadrumo/entrypoints/cli/_config/_collab_payloads.py; collaboration payload tests`.

### Phase `W07.P95` - Type notification snapshot transport

Project notification capture/listing rows through canonical snapshot contracts.

- [x] `W07.P95.S119` - Project notification snapshots through canonical identities, timestamps, source URL, and derived row counts.; `src/cadrumo/entrypoints/cli notification payloads and notification tests`.
- [x] `W07.P95.S120` - Correct notification transport test formatting and rerun scoped lint and diff checks.; `src/cadrumo/entrypoints/cli/tests/test_live_notifications_verbs.py; notification lint verification`.

### Phase `W07.P96` - Preserve IVA wallet authority history

Project full persisted wallet authority decisions to the CLI audit surface.

- [x] `W07.P96.S121` - Carry wallet authority reason and capture/decision timestamps through JSON and text history projections.; `src/cadrumo/entrypoints/cli/_app_live_payloads.py; live IVA history projection tests`.

### Phase `W07.P97` - Preserve live IVA diagnostic references

Expose the canonical redacted IVA authentication diagnostic reference.

- [x] `W07.P97.S122` - Carry the safe live IVA authentication diagnostic reference through the CLI payload and pull-evidence projection.; `src/cadrumo/entrypoints/cli/_app_live_payloads.py; src/cadrumo/entrypoints/cli/_app_live.py; live IVA auth tests`.

### Phase `W07.P98` - Type live IVA outcome taxonomies

Project live IVA auth and surface outcomes through canonical enum taxonomies.

- [x] `W07.P98.S123` - Type live IVA auth and surface outcome discriminants with canonical enums and reject unknown values.; `src/cadrumo/entrypoints/cli/_app_live_payloads.py; src/cadrumo/entrypoints/cli/_app_live.py; live IVA payload tests`.

### Phase `W07.P99` - Type config check diagnostics

Project dependency and preflight diagnostic rows through canonical contracts.

- [x] `W07.P99.S124` - Type config-check dependency and preflight rows with canonical service, check, and severity contracts.; `src/cadrumo/entrypoints/cli/_config/_check_payloads.py; config-check tests`.

### Phase `W07.P100` - Type Google credential-source selection

Project Google credential-source selection through its canonical kind/config model.

- [x] `W07.P100.S125` - Validate Google credential-source payloads against canonical selection and impersonation configuration contracts.; `src/cadrumo/entrypoints/cli/_config/_google_credential_source_payloads.py; credential source tests`.

### Phase `W07.P101` - Type operator contract manifest

Validate the CLI contract manifest against the canonical operator-surface model.

- [x] `W07.P101.S126` - Replace the extra-allow contract manifest shell with canonical manifest validation and malformed-shape refusal tests.; `src/cadrumo/entrypoints/cli/_app_contract_payloads.py; contract manifest tests`.

### Phase `W07.P102` - Normalize Drive root overrides

Apply canonical persisted Drive root configuration when an environment override is blank.

- [x] `W07.P102.S127` - Normalize whitespace Drive root overrides before precedence selection and cover persisted fallback.; `src/cadrumo/adapters/outbound/storage/_factory.py; storage factory tests`.

### Phase `W07.P103` - Type root status branches

Replace the root status extra-allow transport shell with canonical branch validation.

- [x] `W07.P103.S128` - Validate each root status response as the canonical help, landing, or overview branch and reject incomplete or cross-branch payloads.; `src/cadrumo/entrypoints/cli/_root_payloads.py; root callback tests`.

### Phase `W07.P104` - Type ledger provider availability

Project provider availability through its canonical closed enum and non-empty executable contract.

- [x] `W07.P104.S129` - Type provider rows with the canonical LLM provider enum, require a CLI binary, and reject malformed transport values.; `src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py; ledger provider payload tests`.

### Phase `W07.P105` - Type ledger classification rules

Route rule and apply transport through the canonical classification-rule contract.

- [x] `W07.P105.S130` - Validate rule and apply payloads through canonical rule identity, regex, classification, priority, actor, and timestamp contracts.; `src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py; src/cadrumo/entrypoints/cli/_ledger_rules_cli.py; ledger rule tests`.

### Phase `W07.P106` - Verify ledger rule transport

Complete lint and focused regression evidence for canonical ledger rule transport.

- [x] `W07.P106.S131` - Correct the rule transport annotation and rerun selected rule regressions, lint, and diff checks.; `src/cadrumo/entrypoints/cli/_ledger_rule_payloads.py; ledger rule payload tests`.

### Phase `W07.P107` - Validate declaration tax identifiers

Use the canonical Spanish tax-ID checksum validator at the declaration parser boundary.

- [x] `W07.P107.S132` - Validate extracted NIF, NIE, and CIF candidates with the canonical checksum contract and refuse invalid controls.; `src/cadrumo/adapters/inbound/declaracion/_parser.py; declaration parser tests`.

### Phase `W07.P108` - Type Borrador snapshot identities

Require canonical content-addressed snapshot identities across Modelo 100 live snapshots.

- [x] `W07.P108.S133` - Adopt canonical SnapshotId fields for Modelo 100 snapshots and update affected persistence fixtures to valid content-addressed identities.; `src/cadrumo/application/live/_borrador_100.py; Modelo 100 snapshot tests`.

### Phase `W07.P109` - Type review queue transport

Preserve canonical review severity and state enums through the CLI boundary.

- [x] `W07.P109.S134` - Pass native review enums through queue projections and reject malformed severity or state transport values.; `src/cadrumo/entrypoints/cli/_review.py; review payload tests`.

### Phase `W07.P110` - Separate agent layout payloads

Reject cross-layout field contamination in agent materialisation results.

- [x] `W07.P110.S135` - Enforce layout-exclusive fields on agent materialisation payloads and cover contaminated workspace and plugin refusals.; `src/cadrumo/entrypoints/cli/_app_agent_workspace_payloads.py; agent workspace tests`.

### Phase `W07.P111` - Type export reconciliation transport

Project maintenance reconciliation through canonical export operation constraints.

- [x] `W07.P111.S136` - Enforce canonical export IDs, purpose, nonblank reconciliation rows, and nonnegative counts at the maintenance CLI boundary.; `src/cadrumo/entrypoints/cli/_app_maintenance_payloads.py; reconciliation CLI tests`.

### Phase `W07.P112` - Type catalogue invoice transport

Validate catalogue invoice and bulk-import CLI payloads through canonical invoice contracts.

- [x] `W07.P112.S137` - Adopt canonical invoice identity, enum, date, amount, count, and bulk-refusal constraints in catalogue invoice transport.; `src/cadrumo/entrypoints/cli/_ledger_catalogue_invoice_payloads.py; catalogue invoice tests`.

### Phase `W07.P113` - Validate registry period tokens

Route registry snapshot, selector, and previous-filing period tokens through the canonical period union while retaining declared administrative coordinates.

- [x] `W07.P113.S138` - Adopt the canonical registry period-token union across snapshot references, period selectors, and previous-filing selectors with administrative-token parity.; `src/cadrumo/domain/calculations/registry period-token models and tests`.

### Phase `W07.P114` - Validate registry citation links

Type legal permalinks and source URLs with the canonical external-link contract, preserving HTTPS fragments through operator citation projections.

- [x] `W07.P114.S139` - Adopt a fragment-preserving canonical HTTP URL type for registry legal and source references, derive citation projections from it, and reject malformed link records.; `src/cadrumo/domain/calculations/registry/_schema_references.py; src/cadrumo/application/registry/_corpus.py; registry and corpus citation tests`.

### Phase `W07.P115` - Advertise MCP canonical error envelopes

Expose the shared error-envelope branch in per-verb MCP output schemas so direct and meta transport failures remain schema-valid.

- [x] `W07.P115.S140` - Derive per-verb MCP output schemas as canonical success/error unions and prove both transport error envelopes satisfy the advertised contract.; `src/cadrumo/entrypoints/mcp/_tools.py; MCP schema and transport tests`.

### Phase `W07.P116` - Fail closed on missing citation anchors

Use one anchored corpus-unit reader for legal verification and citation lookup so a missing or ambiguous anchor cannot consume unrelated authoritative text.

- [x] `W07.P116.S141` - Centralize anchored extracted-corpus resolution, refuse missing or duplicate anchors, and prove registry verification and citation lookup cannot fall back to unrelated units.; `src/cadrumo/domain/calculations/registry/_legal.py; src/cadrumo/application/corpus_search/_citation_lookup.py; legal grounding and citation lookup tests`.
- [x] `W07.P116.S156` - Regenerate cited normative extraction sidecars with canonical article anchors and inventory non-article anchor mappings before enabling fail-closed legal reference resolution.; `dev/docs/preprocess/_html.py; cited normative corpus sidecars; legal-reference migration tests`.
- [x] `W07.P116.S157` - Map remaining legal-reference subsection and non-article fragments to one extracted corpus unit, then enable the shared fail-closed anchor resolver without raw or whole-document fallback.; `legal catalogue corpus references; dev/docs/preprocess; registry legal verification; citation lookup tests`.
- [x] `W07.P116.S158` - Derive atomic Madrid manual corpus units for each reviewed legal fragment before admitting them through the shared fail-closed resolver; `Madrid legal catalogue and Renta 2025 extracted corpus sidecars`.

### Phase `W07.P117` - Align MCP thinning schemas with runtime branches

Represent both unthinned zero-row result arrays and linked non-empty resource summaries in the MCP schema published for a thinned command.

- [x] `W07.P117.S142` - Model zero-row inline and non-empty linked thinning branches in MCP result schemas, retaining resource summaries and proving runtime/schema parity.; `src/cadrumo/entrypoints/mcp/_result_thinning.py; MCP thinning schema and integration tests`.

### Phase `W07.P118` - Canonicalize imported submission coordinates

Build imported filing audit records with the submission domain identity helper and preserve aware receipt instants while retaining documented naive Madrid interpretation.

- [x] `W07.P118.S143` - Use the canonical first-attempt submission identity and timezone-aware instant conversion for justificante imports, with real draft/receipt regression coverage.; `src/cadrumo/application/filing/_import.py; src/cadrumo/application/filing/tests/test_import.py`.

### Phase `W07.P119` - Close auth probe verdict projections

Carry the closed provider-probe taxonomy through private outcomes and public auth state projections so malformed values cannot become an apparent readiness verdict.

- [x] `W07.P119.S144` - Replace widened auth probe-result strings with the canonical closed enum across probe and projection models, then refuse malformed outcome values in real operator projections.; `src/cadrumo/application/auth/_operator_probes.py; src/cadrumo/application/_state_projection_auth.py; auth projection tests`.

### Phase `W07.P120` - Verify evidence bundle work-unit binding

Execute the documented work-unit existence check during evidence bundle verification so an orphaned manifest cannot report as verified.

- [x] `W07.P120.S145` - Verify the referenced work unit exists before emitting a verified evidence-bundle report, with real orphaned-manifest refusal coverage.; `src/cadrumo/application/evidence/_service.py; src/cadrumo/application/evidence/tests`.

### Phase `W07.P121` - Verify corpus source bytes on every integrity check

Remove metadata-keyed digest reuse from source-corpus verification so same-size, timestamp-restored tampering cannot receive a stale integrity verdict.

- [x] `W07.P121.S146` - Hash corpus source bytes for each verification and refuse same-size timestamp-restored tampering with a real temporary-corpus regression.; `src/cadrumo/domain/calculations/registry/_corpus_catalogue.py; registry corpus verifier tests`.

### Phase `W07.P122` - Centralize agent evaluation lifecycle ordering

Give declared golden trajectories and observed live scoring one immutable command-stage order so lifecycle changes cannot drift between evaluators.

- [x] `W07.P122.S147` - Move the agent evaluation lifecycle-stage order to the shared model contract and prove both declared and observed scoring retain real ordering refusals.; `src/cadrumo/agent/eval/_models.py; src/cadrumo/agent/eval/_runner.py; src/cadrumo/agent/eval/_live_scoring.py; agent eval tests`.

### Phase `W07.P123` - Re-arm golden profile confirmation after identity switches

Make declared profile-confirmation evaluation enforce the same re-confirmation boundary after a profile switch as the real live identity gate.

- [x] `W07.P123.S148` - Model profile-switching commands in golden confirmation scenarios and refuse every mutation lacking confirmation since the latest switch, with switch-then-mutate regression coverage.; `src/cadrumo/agent/eval/_models.py; src/cadrumo/agent/eval/_runner.py; agent evaluation tests`.

### Phase `W07.P124` - Preserve immutable smoke evidence checkpoints

Make the smoke-manifest checkpoint honor the same no-overwrite evidence contract as distribution evidence before any completed work directory can be pruned.

- [x] `W07.P124.S149` - Refuse duplicate smoke-evidence checkpoint destinations before staging or pruning, with a pre-seeded immutable-artifact regression.; `dev/packaging/evidence.py; dev/packaging/tests/test_evidence.py`.

### Phase `W07.P125` - Require token-bounded desktop oracle matches

Ensure a desktop capture proves the requested normalized numeric value rather than accepting a larger or embedded digit sequence.

- [x] `W07.P125.S150` - Match normalized desktop oracle values as whole numeric tokens and refuse embedded or larger numeric replies, with locale-preserving regressions.; `dev/packaging/desktop_capture.py; dev/packaging/tests/test_desktop_capture.py`.

### Phase `W07.P126` - Fail closed for real-client release evidence

Require a connected, successful real-client session with a recorded tool call before a required client lane may mint passed release evidence.

- [x] `W07.P126.S151` - Validate the real-client session proof before minting passed client evidence and refuse disconnected, errored, or tool-less sessions with real-cohort regressions.; `dev/packaging/distribution_evidence_emit.py; dev/packaging/tests/test_distribution_evidence_emit.py`.

### Phase `W07.P127` - Constrain preprocess source provenance paths

Make the sidecar schema accept only canonical POSIX-relative repository locators, refusing absolute, drive-qualified, and traversal provenance.

- [x] `W07.P127.S152` - Validate canonical POSIX-relative preprocess source paths at the schema boundary, with absolute, drive, backslash, and traversal refusal coverage.; `dev/docs/preprocess/_schema.py; dev/docs/preprocess/tests/test_sidecar_contract.py`.

### Phase `W07.P128` - Refuse assetless landing pages before publish

Require the built landing page to reference bundled assets during preflight, before upload and cache invalidation.

- [x] `W07.P128.S153` - Reject landing builds with no bundle references during artifact preflight, with a complete-build blank-page regression.; `dev/deploy/frontend_static_site.py; dev/deploy/tests/test_frontend_static_site.py`.

### Phase `W07.P129` - Enforce exact clean-corpus licence admission

Permit only explicit clean licence tokens and bounded version suffixes so prohibited NC and ND material cannot enter the evidence corpus.

- [x] `W07.P129.S154` - Replace prefix-based evidence-corpus licence admission with exact normalized tokens and version suffixes, with NC and ND refusal coverage.; `dev/_build_evidence_corpus.py; dev/tests/test_build_evidence_corpus.py`.

### Phase `W07.P130` - Validate release download URL projections

Refuse malformed or non-HTTPS release base URLs before deriving downloadable asset links from a sealed cohort.

- [x] `W07.P130.S155` - Validate release base URLs before download-latest asset projection, with malformed and non-HTTPS URL refusal coverage.; `dev/docs/download_matrix.py; dev/docs/tests/test_download_matrix.py`.

### Phase `W07.P131` - MCP zero-row result thinning

Keep the runtime and advertised MCP result schemas aligned for empty and resource-linked bulk arrays.

- [x] `W07.P131.S160` - Align MCP result-thinning runtime and descriptor schemas for inline zero-row arrays and non-empty resource links.; `src/cadrumo/entrypoints/mcp/_result_thinning.py; src/cadrumo/entrypoints/mcp/_tools.py; src/cadrumo/entrypoints/mcp/tests`.

### Phase `W07.P132` - Auth probe verdict projection

Preserve the canonical closed provider-probe verdict through certificate-source operator results.

- [x] `W07.P132.S161` - Project certificate-source probe verdicts through the canonical closed ProviderProbeResult contract and refuse malformed values.; `src/cadrumo/application/auth/_operator_results.py; src/cadrumo/application/auth/_certificate_sources_operator.py; src/cadrumo/application/auth/tests`.

### Phase `W07.P133` - Desktop capture numeric oracle

Compare captured desktop numeric values by normalized numeric value rather than punctuation-stripped substrings.

- [x] `W07.P133.S162` - Make desktop capture numeric comparison exact and token-bounded after locale-aware normalization.; `dev/packaging/desktop_capture.py; dev/packaging/tests`.

### Phase `W07.P134` - Streamed digest ownership

Use one import-light streamed SHA-256 owner across packaging, corpus, and release cohort tooling.

- [x] `W07.P134.S163` - Re-home packaging, corpus, and Homebrew streamed SHA-256 callers onto one canonical digest owner.; `dev/packaging/_hashing.py; dev/packaging; dev/corpus/sync_aeat_record_design_corpus.py; packaging-homebrew.yml; tests`.

### Phase `W07.P135` - Packaging command transcript boundary

Establish one typed packaging subprocess result that projects truthfully into release evidence.

- [x] `W07.P135.S164` - Consolidate audited packaging subprocess runners behind one typed command-result and transcript projection boundary.; `dev/packaging; dev/packaging/tests`.

### Phase `W07.P136` - Finite Modelo 100 draft bindings

Admit only canonical finite decimal binding values before Modelo 100 calculation resolution.

- [x] `W07.P136.S165` - Route Modelo 100 borrador decimal bindings through the canonical finite decimal contract.; `src/cadrumo/application/modelo; src/cadrumo/application/modelo/tests`.

### Phase `W07.P137` - Fixture provenance gate owner

Use one fixture-support reader and discriminator for PDF and sidecar provenance gates.

- [x] `W07.P137.S166` - Consolidate PDF producer and sidecar provenance discrimination under the shared fixture support owner.; `src/cadrumo/tests/fixtures; src/cadrumo/domain/calculations/registry/tests`.

### Phase `W07.P138` - UTC submission audit records

Enforce canonical UTC-aware timestamps before submission ordering and persistence contracts.

- [x] `W07.P138.S167` - Validate submission attempt and presented-record timestamps through the canonical UTC-aware contract.; `src/cadrumo/domain/submission; src/cadrumo/domain/submission/tests`.

### Phase `W07.P139` - Canonical observability run identity

Make filesystem validation consume the canonical observability run-ID contract.

- [x] `W07.P139.S168` - Re-home observability filesystem run-ID validation on the canonical RUN_ID_PATTERN.; `src/cadrumo/core/observability; src/cadrumo/core/observability/tests`.

## Wave `W08` - Post-audit critical integrity remediation

Address verified critical and high-severity findings appended after Wave 7, with isolated ownership and real-behavior evidence.

### Phase `W08.P140` - Restore MCP descriptor serializability

Repair the critical tools/list output-schema contract without changing the success/error semantic branches.

- [x] `W08.P140.S169` - Adapt MCP output schemas to the SDK top-level serialization contract while retaining canonical result branches.; `src/cadrumo/entrypoints/mcp; MCP memory-session tests`.

### Phase `W08.P141` - Make recipient replay consumption atomic

Replace the verified non-atomic read-modify-write replay path with a durable concurrent-consumption contract.

- [x] `W08.P141.S170` - Make recipient replay consumption atomic under concurrent access and preserve durable replay refusal semantics.; `recipient replay persistence and focused concurrent-consumption tests`.

### Phase `W08.P142` - Enforce UTC timestamp boundaries

Route report, revision, and declaration-summary timestamps through the canonical UTC-aware authority.

- [ ] `W08.P142.S171` - Validate verification-report, revision-lifecycle, and declaration-summary timestamps through the canonical UTC-aware contract.; `src/cadrumo/domain/modelos; persistence profile adapters; filing calculation; focused UTC regressions`.

### Phase `W08.P143` - Constrain measurement report aggregates

Reject contradictory score/row aggregate fields and preserve valid measurement-report construction.

- [x] `W08.P143.S172` - Enforce consistency between measurement-report rows and aggregate scenario counts, failures, and pass state.; `src/cadrumo/agent/eval/_report.py; agent evaluation report tests`.

### Phase `W08.P144` - Constrain agent evaluation score invariants

Refuse contradictory discovery and live-evaluation state before it is reported as a passing result.

- [x] `W08.P144.S173` - Validate discovery and live-score reached, scenario, and tool-error invariants before computing pass state.; `src/cadrumo/agent/eval/_live_scoring.py; agent evaluation scoring tests`.

### Phase `W08.P145` - Validate supplied registry completeness manifests

Ensure an explicit completeness manifest cannot omit a required non-internal calculation-closure member.

- [x] `W08.P145.S174` - Compare a supplied manifest against the derived non-internal calculation closure and refuse omissions.; `src/cadrumo/domain/calculations/registry; registry completeness tests`.

### Phase `W08.P146` - Restore certificate-secret backend importability

Repair the auth import-time NameError blocking MCP memory-session verification.

- [x] `W08.P146.S175` - Restore the canonical certificate-source name import so auth and MCP test collection is importable.; `src/cadrumo/application/auth; focused auth import regressions`.

### Phase `W08.P147` - Bind IVA reconciliation decisions to the canonical bucket

Prevent reconciliation from persisting a decision through a repository unrelated to the observation bucket.

- [x] `W08.P147.S176` - Derive or verify the IVA decision repository against the canonical observation bucket before persistence.; `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py; IVA wallet reconciliation tests`.

### Phase `W08.P148` - Enforce UTC bucket-session instants

Reject naive and non-UTC session lifecycle instants before timeout arithmetic or persistence.

- [x] `W08.P148.S177` - Validate bucket-session lifecycle instants through the canonical UTC-aware contract.; `src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py; bucket-session tests`.

### Phase `W08.P149` - Bind recipient encryption keypairs to their bucket

Refuse foreign recipient keypair payloads and make first-use minting concurrency-safe.

- [x] `W08.P149.S178` - Refuse foreign recipient keypair bucket identities and make first-use keypair minting race-safe.; `src/cadrumo/application/modelo/_review_package_recipient_encryption.py; recipient encryption tests`.

### Phase `W08.P150` - Constrain ReviewProjection aggregate contracts

Reject direct construction whose aggregate counts or pass state contradict the review rows.

- [x] `W08.P150.S179` - Enforce ReviewProjection row, aggregate-count, and pass-state consistency at model construction.; `src/cadrumo/application/flows/_review.py; review flow tests`.

### Phase `W08.P151` - Validate live-score trajectory identity and lifecycle

Refuse a supplied scenario that differs from the trajectory and reject lifecycle-stage re-entry.

- [x] `W08.P151.S180` - Require live-score scenarios to match their trajectories and reject repeated lifecycle-stage observations.; `src/cadrumo/agent/eval/_live_scoring.py; live harness and lifecycle tests`.

### Phase `W08.P152` - Bind review-package signing keys to their bucket

Refuse foreign signing-key payloads and make first-use signing-key minting concurrency-safe.

- [x] `W08.P152.S181` - Refuse foreign signing-key bucket identities and make first-use signing-key minting race-safe.; `src/cadrumo/application/modelo/_review_package_signing.py; signing tests`.

### Phase `W08.P153` - Type review-package CLI contracts

Replace primitive review-package transport fields with the canonical manifest, identity, count, and timestamp contracts.

- [ ] `W08.P153.S182` - Validate review-package CLI transport fields through the canonical manifest, identity, count, and timestamp contracts.; `src/cadrumo/entrypoints/cli/_modelo_review_package_payloads.py; review-package CLI tests`.

### Phase `W08.P154` - Type ledger status transport

Project ledger status bucket identity and counts through canonical domain constraints at the CLI boundary.

- [x] `W08.P154.S183` - Validate ledger-status bucket identity and non-negative counts through canonical contracts.; `src/cadrumo/entrypoints/cli/_ledger_payloads.py; ledger status payload tests`.

### Phase `W08.P155` - Make flywheel evidence identity collision-safe

Ensure promoted scenarios cannot overwrite distinct failure, tool-error, or narration evidence sharing a coarse signature.

- [ ] `W08.P155.S184` - Include failure, tool-error, and narration evidence in flywheel promotion identity and refuse distinct-content overwrites.; `src/cadrumo/agent/eval/_flywheel.py; report and flywheel tests`.

## Parallelization

## Verification
