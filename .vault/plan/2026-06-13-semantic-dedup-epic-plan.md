---
tags:
  - '#plan'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
tier: L3
related:
  - '[[2026-06-13-semantic-dedup-epic-audit]]'
  - '[[2026-06-13-semantic-dedup-epic-adr]]'
  - '[[2026-06-13-semantic-dedup-epic-research]]'
---
<!-- RETIRED: W02, P04, S08, S09, S10, S11, S12, S13, S14 -->







# `semantic-dedup-epic` plan

## Wave `W01` - Pass 1 — Confirmed Duplication Removal

Remove the three confirmed real-duplication clusters from discovery Pass 1 (F1 tax-id, F2 dormant fichero money stack, F3 bucket-id boilerplate). Each step names a per-file site and its action with a verification gate.


### Phase `W01.P01` - F1 — Consolidate Spanish tax-id validation

Collapse the duplicated NIF/NIE/CIF validation and control-letter computation in core/identity/_tax_id.py and core/identity/_documents.py onto one owning core, re-expressing both public surfaces over it.

- [ ] `W01.P01.S01` - Delegate _compute_nif_check_letter to the canonical nif_check_letter single source and remove the duplicate _NIF_LETTERS control-letter table; `src/aeat/core/identity/_documents.py`.
- [ ] `W01.P01.S02` - Consolidate the duplicated _validate_nif/_validate_nie/_validate_cif core into one owning module and re-express the other module's validators over it; `src/aeat/core/identity/_tax_id.py`.
- [ ] `W01.P01.S03` - Migrate the dual-module consumer to a single import site and run the identity validation test suite green; `src/aeat/domain/calculations/registry/_schema_scalars.py`.

### Phase `W01.P02` - F2 — Remove dormant fichero-BOE _formats money stack

Prove the adapters/outbound/aeat/export/_formats currency encode/serialise/deserialise stack has zero production consumers, then delete it or record an explicit retention rationale.

- [x] `W01.P02.S04` - Prove tree-wide that the _formats currency encode/serialise/deserialise path has zero production consumers outside its own package and tests; `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py`.
- [ ] `W01.P02.S05` - Delete the dormant _formats currency encode/serialise/deserialise path and its tests, or record an explicit retention rationale if a near-term consumer is planned; `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`.

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

## Description


## Steps







## Parallelization


## Verification

