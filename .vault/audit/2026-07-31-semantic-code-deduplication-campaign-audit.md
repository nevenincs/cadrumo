---
tags:
  - '#audit'
  - '#code-deduplication'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
---

# Semantic code-deduplication campaign audit

## Scope

This rolling, code-only audit covers production and test code. Each candidate begins with a VaultSpec RAG code query, is checked against complete implicated files and exact-symbol search, and is admitted only when two sites are behaviorally substitutable or a forwarding seam bypasses a canonical owner. Purposeful adapters, model-specific legal rules, and constraint-shape mismatches are excluded.

## Findings

Findings are appended here only after coordinator verification against the current `HEAD`, including consumer evidence and the canonical implementation's constraint shape.

### wizard-result-schema-registration-bridge | medium | filename-driven discovery retains a redundant CLI forwarding module

The semantic production query `guided wizard collects answers and converts them into typed profile command payload only:prod`, paired with its `only:tests` counterpart, reached a three-part chain. The canonical, strict result schemas are declared and registered in `src/cadrumo/application/wizard/_results.py:31-54`; the real Wizard producers construct those classes in `src/cadrumo/application/wizard/_commands.py:1501-1539` and `:1680-1699`. The CLI manifest builder in `src/cadrumo/entrypoints/cli/_app_contract.py:45-47,68-108,120-129` then searches only CLI payload packages by filename. `src/cadrumo/entrypoints/cli/_wizard_payloads.py:24-27` exists solely to re-export the two Wizard classes into that scanner's path.

This is a confirmed shim, not merely similarly named code: `src/cadrumo/entrypoints/cli/tests/test_wizard_payloads.py:30-49` proves both exports are object-identical to the Wizard owner, and the fresh-process manifest proof in `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py:983-1025` proves that the bridge alone determines whether the two command schemas appear. The canonical owner is an exact constraint-shape match and therefore a superset. Current `HEAD` still contains the bridge from `73f06fa1f2`, its deletion guard from `361c8243e9`, and the final seam test from `08a6f79a70`.

Remediate by adding an explicit lazy-import tuple of non-CLI schema-owner modules, including `cadrumo.application.wizard._results`, to `_ensure_result_schemas_registered`. Then delete `_wizard_payloads.py` and its bridge-only identity tests. Keep and rewrite the fresh-process test to prove the manifest loads both schemas from their canonical owner; the import remains confined to manifest/MCP registry construction, preserving cold CLI start behavior.

### ledger-file-evidence-manifest-write | medium | ledger persistence duplicates the attachment-service file-write core

The production/test semantic query `evidence attachment file ingestion validation secure bytes` found that `src/cadrumo/application/ledger/_evidence.py:457-472` calls `AttachmentStore.put_file`, constructs an `Attachment`, and calls `write_manifest` directly. This reproduces the byte-store and manifest core owned by `src/cadrumo/domain/attachments/_service.py:58-97,101-161` (`add_attachment`), whose public facade assigns this package byte custody and manifest writing in `src/cadrumo/domain/attachments/__init__.py:12`. The same domain service is already used for a sibling production ingestion route through `add_attachment_bytes` in `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py:254,291-305`; the two paths have real test coverage in `src/cadrumo/domain/attachments/tests/test_service.py:28-43` and `src/cadrumo/application/ledger/tests/test_evidence_input.py:40`.

The persistence, identity, namespace, MIME, bucket, timestamp, and manifest-validation constraints match. This is not yet a direct call substitution: the ledger constructs `captured_by` and `source_command` at `_evidence.py:469-470`, but `add_attachment` does not expose them even though the canonical `Attachment` model accepts both at `src/cadrumo/domain/attachments/_models.py:132-133`. That is an explicit, narrow signature-shape gap—not a reason to delete the ledger's PDF/image validation, resolved-path provenance, fiscal record, or audit-event steps. The shared write core itself was introduced by `673938a11f`, while the ledger bypass predates it and remains at current `HEAD`.

Remediate by extending `_build_attachment_manifest`, `_persist_attachment`, and `add_attachment` with optional `captured_by` and `source_command`, preserving their `None` defaults. Add a real service test that persists those values, then replace the ledger's `put_file`/`Attachment`/`write_manifest` block with one `add_attachment` call. This makes the domain helper a constraint-shape superset and removes the duplicated secure-write implementation without moving ledger-only behavior.

### casilla-noncanonical-reference-renderer | medium | three application paths redefine one registry-diagnostic fragment

The calculation/registry lane ran ten meaning-first code concepts, each against `only:prod` and `only:tests`, including casilla lookup and refused printed-box diagnostics. It found three private renderers of the same non-canonical reference diagnostic: `src/cadrumo/application/modelo/_registry_helpers.py:182-186` (called at `:132,:262,:346`), `src/cadrumo/application/filing/__init__.py:541-545` (called at `:524`), and `src/cadrumo/application/modelo/_result_disposition_resolution.py:220-224` (called at `:200`). All three already use `casilla_noncanonical_reference_targets` from the registry authority, respectively imported at `_registry_helpers.py:38`, `filing/__init__.py:120`, and `_result_disposition_resolution.py:60`.

Each accepts a token plus a non-empty `tuple[CasillaId, ...]`, differentiates one target from an ambiguous set, and names the same sorted canonical candidates. The result-disposition copy adds `repr()` around target IDs while the other two render bare IDs; targeted real tests assert the refusal and candidate presence but no surface treats this quotation difference as a contract (`application/filing/tests/test_build_draft_identity.py:147-192`, `application/modelo/tests/test_import_flow_validation.py:58-86`, `application/modelo/tests/test_result_disposition_resolution.py:181-219`). `git show 0e4c99e238` shows the three definitions arrived together as a WIP-safeguard commit, not as deliberately separated owners. The registry's canonical target resolver is at `src/cadrumo/domain/calculations/registry/_casilla_membership.py:76-102`, already re-exported through the registry facade.

Remediate by adding one quoted canonical diagnostic renderer beside the target resolver, re-exporting it through `domain.calculations.registry`, and replacing all five call sites before removing the three private functions. Preserve each calling layer's own exception type, translated prefix, and structured context. Pin identical singular and ambiguous rendering through real filing, import, and result-disposition refusal paths so subsequent changes cannot recreate a local formatter.

### invoice-evidence-advisory-decimal-normalisation | low | IVA advisory bypasses the canonical decimal-separator helper

Across 34 successful production/test RAG searches in the finance-input/output lane, the query `invoice printed IVA evidence decimal advisory` reached `src/cadrumo/application/ledger/_evidence_advisory.py:26-41` and its real behavior tests in `src/cadrumo/application/ledger/tests/test_evidence_advisory.py:13-40`. `_parse_amount` conditionally performs `replace(".", "").replace(",", ".")` before calling `Decimal`, duplicating the separator transform explicitly owned by `normalize_decimal_separators` in `src/cadrumo/core/decimal/_coerce.py:128-145` and re-exported by `core.decimal`. Sibling ledger evidence parsers already use that public helper at `_evidence_draft.py:292` and `_evidence_draft_vision.py:195`.

The local grammar admits only comma-decimal values with optional Spanish dot-thousands and plain dot-decimal values. `normalize_decimal_separators(text, strip_thousands="," in text)` is exactly substitutable under that grammar, while the advisory retains its distinct best-effort `Decimal`/`None` contract and non-authoritative behaviour. The historical canonicalisation in `38a4f6842b` migrated eight comparable sites after the advisory copy arrived in `57cdfc30d8`, leaving this one bypass at current `HEAD`.

Remediate by importing `normalize_decimal_separators` and replacing the local conditional transform with its parameterized call. Keep the local regex and `InvalidOperation` handling. Add a plain dot-decimal assertion beside the existing Spanish-thousands regression so the grammar that makes this substitution safe is explicit.

### custody-bucket-event-emission | medium | custody hand-copies the canonical derive-build-append-save primitive

Twelve meaning-first lifecycle/storage concepts, each searched separately across production and tests, found the custody audit trail at `src/cadrumo/application/user_profile/_custody.py:169-225`. Its private helper derives a bucket-event id, builds a `BucketEvent`, and persists `append_bucket_event(repository.load(), event)` itself. The canonical owner, `src/cadrumo/domain/buckets/_event_repository.py:51-115`, owns exactly that sequence as `emit_bucket_event`; its docstring and public facade explicitly establish it as the primitive every emitting domain shares. Existing consumers in `application/workflow/_events.py:114-123` and `application/inventory/_service.py:137-148` already use it.

The custody call shape is a direct canonical subset: repository, bucket, event type, timestamp, actor, object type/id, payload, and the required `payload_version=1` are all supplied. Its no-active-profile logged return and `StorageValidationError` best-effort policy remain custody-specific wrapper behavior; neither changes the durable write sequence. Current persisted-version protection confirms an explicit version must be preserved (`domain/buckets/tests/test_payload_version_contract.py:57-70`). The local copy landed in `0a66e96bd5`; the shared primitive followed in `3740b9f8f6`, and this site was never migrated.

Remediate by replacing only the manual construction and save sequence with `emit_bucket_event(..., payload_version=1)` inside the existing custody wrapper. Preserve its early return and exception handling, and retain the real recovery-create, recovery-rotate, passphrase-change, and secret-store-recovery assertions in `application/user_profile/tests/test_custody_audit_trail.py:68,99,114,128,159`.

### live-snapshot-canonical-json-hash | medium | live snapshots redefine the canonical content-id kernel

The core-infrastructure lane ran twelve semantic concepts across production and tests, including deterministic canonical JSON content hashing. The query `deterministic canonical JSON serialization used before content hashing` identified `src/cadrumo/application/live/_snapshot_base.py:115-132`, where `derive_snapshot_id_from_json` sorts keys, uses compact separators, encodes UTF-8, and SHA-256 hashes the result. `src/cadrumo/core/hashing.py:43-70` already owns this exact operation as `canonical_json_bytes` and `content_hash_hex`; both use Python's default `ensure_ascii=True`, so their output is byte-identical for the snapshot helper's JSON-safe dictionaries, including non-ASCII values.

The core helper accepts `object`, a strict signature superset of the application's recursive JSON dictionary alias. Live consumers are `application/live/_borrador_100.py:122`, `_notifications.py:92`, and `_justificante.py:194`; real snapshot-ID determinism tests sit in `application/live/tests/test_snapshot_base.py:319-353`. The duplicate arrived in `8e7c49766c`; `bae0d5008e` introduced the canonical kernel and migrated equivalent cross-layer sites byte-identically, leaving this preceding helper un-migrated.

Remediate by deleting `_CanonicalValue` and `derive_snapshot_id_from_json` without a compatibility alias, routing its three consumers directly to `content_hash_hex`. Move the shared determinism assertions to the core helper while retaining each caller's real snapshot-ID assertions, so existing identifiers stay pinned and the application no longer owns serialization mechanics.

### command-and-corpus-vector-ranking | medium | command search copies L2 and RRF ranking mechanics from corpus search

Fifteen paired semantic concepts over agent/search/MCP surfaces identified three byte-equivalent L2 normalisers: `application/command_search/_index.py:337-343`, `application/corpus_search/_retrieval.py:161-166`, and `application/corpus_search/_embed_build.py:196-201`. They are called from command semantic matrix/query ranking at `_index.py:291,309`, corpus retrieval at `_retrieval.py:154-155`, and corpus more-like-this indexing at `_embed_build.py:176`. Command search also copies reciprocal-rank fusion and `RRF_K = 60` at `_index.py:58,311-334`; corpus retrieval owns the equivalent, more general implementation at `_retrieval.py:38-41,169-187`.

The corpus RRF is the strict superset: it accepts arbitrary lexical and semantic rank maps plus explicit damping, while command search intentionally limits its candidate universe to lexical hits. Filtering command semantic ranks to those lexical keys before calling the shared helper preserves that constraint and its lexical-rank/key tie break. No new architectural dependency is required—command search already imports query embedding and capability surfaces through the public `application.corpus_search` facade. Real behavior is covered in `application/command_search/tests/test_command_index.py:85,92` and `test_command_ranking_golden.py:48,56`, alongside corpus ranking tests in `application/corpus_search/tests/test_embed_build.py:72` and `test_retrieval.py:31`. Corpus ranking arrived in `819276398c`; the command copies followed in `38778ae9c`.

Remediate by creating one corpus-search ranking module that exports L2 normalization, reciprocal-rank fusion, and `RRF_K` through the public facade. Repoint all three L2 consumers and both fusion sites, retaining command search's lexical-key filter. Preserve and extend the independent golden tests to pin the restricted candidate universe and deterministic ties.

### sede-csv-validator-constraint-drift | high | declarations capture rejects CSVs valid elsewhere in the same Sede boundary

The adapter query `parse external AEAT verification reference CSV code and cotejo URL`, paired across production and tests, found two incompatible validators in the outbound Sede package. The canonical `JustificanteRef` model permits uppercase alphanumeric CSVs of 8–32 characters in `src/cadrumo/adapters/outbound/aeat/sede/_schema.py:35-37,117-128`; the HTML parser uses the same 8–32 grammar in `_parse.py:46-48,156-170`. In contrast, `_declarations_remote.py:17,43-59` independently defines an 8–24 regex. Its URL extraction is used in both declarations capture paths—`_declarations_fetch.py:42,253` and `_declarations.py:104,693-699`—before the latter constructs `JustificanteRef`.

The 8–32 canonical shape has the same alphabet and minimum length but a more permissive maximum, so it is a strict constraint superset. The stricter helper currently rejects valid 25–32-character CSVs; `adapters/outbound/aeat/sede/tests/test_declarations_part1.py:511-552` even asserts that a 32-character value is too long, contradicting the model and parser. `test_parse.py:91-103` covers only a 16-character CSV, so cross-path conformance is missing. The canonical Sede schema/parser originate in `05be6c179e5`; the conflicting helper and test arrived later in the declarations-register split (`c6fa0dda7c0`).

Remediate with one typed CSV validator at the Sede schema boundary, shared by URL extraction and HTML parsing while translating validation failures to `SedeParseError`. Delete `_CSV_SHAPE_RE` and duplicate value grammar, retaining only URL/HTML extraction. Replace the contradictory test with 32-character acceptance and 33-character refusal through both capture consumers.

## Recommendations

1. Replace the Wizard registration bridge with an explicit lazy schema-owner import in the manifest builder, then delete the bridge and its bridge-only tests.
2. Extend the attachment service's file-ingestion signature for the two existing provenance fields before routing the ledger secure-write block through it.
3. Move the casilla-reference diagnostic fragment into the registry facade and test equivalent singular and ambiguous messages at every existing boundary.
4. Route the IVA advisory's permitted number grammar through `normalize_decimal_separators` rather than reimplementing its transform.
5. Route custody's durable audit-event sequence through `emit_bucket_event` while preserving its explicit version and recovery-only best-effort policy.
6. Retire the live snapshot JSON-hash helper in favour of `content_hash_hex`, preserving the existing persisted-ID fixtures.
7. Consolidate vector normalization and RRF in corpus search, with command search retaining only its lexical-candidate policy.
8. Centralize Sede CSV validation at the `JustificanteRef` boundary and test the full 8–32 contract through both declaration capture paths.
