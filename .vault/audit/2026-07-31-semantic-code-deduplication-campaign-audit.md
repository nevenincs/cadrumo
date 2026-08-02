---
tags:
  - '#audit'
  - '#code-deduplication'
date: '2026-07-31'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:4fb3d19faef5f9b56e6ea14ad2da6441f86cd0be9685cd50e14c4711e955c356'
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

**Adjudication update (2026-08-01):** this finding is resolved by DELETION, not by the remediation above. The accepted `2026-07-31-semantic-search-precompile-boundary-adr` retires the semantic halves of both corpus search and command search outright; the duplicated L2/RRF mechanics are removed rather than centralized, which the ADR's consequences section states explicitly. Commit `71a89d0d2d` (refactor(search): centralize semantic ranking, 2026-08-01 06:53) implemented the centralization remediation after the ADR's acceptance because no annotation existed here; the module it created (`corpus_search/_ranking.py`) is deleted by the in-flight boundary plan. Do not re-land the centralization. Reconciliation ruling: `2026-08-01-user-docs-search-consolidation-adr`.

### sede-csv-validator-constraint-drift | high | declarations capture rejects CSVs valid elsewhere in the same Sede boundary

The adapter query `parse external AEAT verification reference CSV code and cotejo URL`, paired across production and tests, found two incompatible validators in the outbound Sede package. The canonical `JustificanteRef` model permits uppercase alphanumeric CSVs of 8–32 characters in `src/cadrumo/adapters/outbound/aeat/sede/_schema.py:35-37,117-128`; the HTML parser uses the same 8–32 grammar in `_parse.py:46-48,156-170`. In contrast, `_declarations_remote.py:17,43-59` independently defines an 8–24 regex. Its URL extraction is used in both declarations capture paths—`_declarations_fetch.py:42,253` and `_declarations.py:104,693-699`—before the latter constructs `JustificanteRef`.

The 8–32 canonical shape has the same alphabet and minimum length but a more permissive maximum, so it is a strict constraint superset. The stricter helper currently rejects valid 25–32-character CSVs; `adapters/outbound/aeat/sede/tests/test_declarations_part1.py:511-552` even asserts that a 32-character value is too long, contradicting the model and parser. `test_parse.py:91-103` covers only a 16-character CSV, so cross-path conformance is missing. The canonical Sede schema/parser originate in `05be6c179e5`; the conflicting helper and test arrived later in the declarations-register split (`c6fa0dda7c0`).

Remediate with one typed CSV validator at the Sede schema boundary, shared by URL extraction and HTML parsing while translating validation failures to `SedeParseError`. Delete `_CSV_SHAPE_RE` and duplicate value grammar, retaining only URL/HTML extraction. Replace the contradictory test with 32-character acceptance and 33-character refusal through both capture consumers.

### modelo-year-only-revision-selection | high | missing-binding readiness independently resolves a Modelo revision and ignores `--as-of`

The legal/Modelo lane's paired `only:prod` and `only:tests` RAG queries found two implementations of the same year-scoped revision selection. `src/cadrumo/domain/calculations/registry/_queries.py:403-447` validates the Modelo and selects the sole revision whose `period_selector` includes the filing year, additionally constraining the result to the requested `as_of` validity window. It raises the established no-match and `AmbiguousRevisionSelectionError` outcomes and builds the report from that selected revision. `src/cadrumo/application/modelo/_binding_readiness.py:116-154` independently validates the same Modelo, finds covering revisions, raises the same ambiguity error, then chooses the first period of the sole revision—but has no `as_of` input.

This reaches one CLI command through two inconsistent resolution paths. `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:735-759` sends `--year --as-of` to `registry_bindings_for_year`, which delegates to the canonical query at `application/modelo/_registry_discovery.py:209-211`; its `--missing` calculation calls `profile_resolvable_binding_ids` without passing the report's as-of selection at `_modelo_discovery_cli.py:713-725`. The parallel tests already encode the same multi-revision-by-year shape in `domain/calculations/registry/tests/test_queries.py:367-378` and `application/modelo/tests/test_binding_readiness.py:207-217`. The canonical query was introduced first in `75c96d82df`; the later hardening of the two paths remained separate (`eff2560f4a` and `ee498fb785`).

Remediate with one typed, domain-owned year-revision selector that takes the optional effective date and returns the selected revision or the standard no-match/ambiguity outcome. Use it from both the report query and readiness, and thread the already resolved revision or `as_of` context through `--missing` so one command cannot select twice. Add an end-to-end case with two same-year revisions whose validity windows are disambiguated by `--as-of`.

### sandbox-namespace-inventory-row-parallel-schema | medium | sandbox preview wraps a canonical inventory row in an identical later schema

The schema-authority lane ran 28 service-backed code searches (14 semantic concepts, each against `only:prod` and `only:tests`) and found a strict shape duplicate. `src/cadrumo/application/bucket_maintenance/_contracts.py:246-252` defines the canonical `BucketNamespaceInventoryRow`, consumed by `BrowseBucketResult.rows` at `:255-266` and produced by `_service.py:891`. `src/cadrumo/application/bucket_maintenance/_sandbox.py:215-239` later declares `SandboxNamespaceInventoryRow` with the exact same frozen Pydantic configuration and `namespace`/`row_count` field constraints. `preview_discard_sandbox` immediately reconstructs every canonical browse row into that later class at `:479-488`.

The duplicate has no independent domain producer: its remaining uses are its package re-export and the CLI payload's descriptive reference (`entrypoints/cli/_config_sandbox_payloads.py:41`). The canonical browse contract is exercised against real secure storage in `application/bucket_maintenance/tests/test_service_browse.py`, while the preview consumer is covered end-to-end at `entrypoints/cli/tests/test_config_profile_sandbox.py:211-242`. History confirms order and intent: `ecc35d6c8a0` added the canonical browse row on 2026-06-03; `55739ebea28` added the duplicate on 2026-07-03 despite its preview description saying it reuses browse.

Remediate by deleting `SandboxNamespaceInventoryRow` and its export, setting `PreviewDiscardSandboxResult.namespaces` to `tuple[BucketNamespaceInventoryRow, ...]`, and returning `browsed.rows` directly. Preserve the existing preview behavior and add a regression assertion that the returned row remains the canonical type.

### packaging-pep503-name-normalisation | medium | release generators and smoke tooling each redefine the distribution-name identity rule

The helper-ownership lane's paired code searches found three named PEP-503 normalisers: `packaging/scoop/generate.py:45-46`, `packaging/homebrew/generate.py:138-139`, and `dev/packaging/smoke_core.py:258-260`. Each applies the same `[-_.]+`-to-`-` transformation and ASCII-equivalent lowercase/casefold behavior. A shared, already tested owner exists at `dev/packaging/constraint_effect.py:76-78` as `normalise_distribution_name`, whose test coverage includes repeated separators and dots at `dev/packaging/tests/test_constraint_effect.py:236-240`. Scoop and Homebrew use their copies to verify package metadata and dependency pins; smoke tooling uses its copy throughout installed-distribution validation.

There is also a less complete inline variant in `dev/packaging/python_cohort.py:116-131,135-170`, which applies only `casefold().replace("_", "-")` and therefore misses dots and repeated separator runs. This is latent constraint drift rather than a separate adapter: all sites compare the same wheel/sdist/`Requires-Dist` distribution identities. The independently added copies predate the shared helper (`cf65e6a892`, `c820d55cea`, and `f73c7fc144`; shared owner `1599784d5d`).

Remediate by making one import-safe `dev.packaging` PEP-503 normalisation owner available to both generators and smoke/cohort tooling, deleting the local named copies and enrolling the three inline cohort sites. Expand the shared behavior test with dotted and repeated-separator names; keep artifact-format parsing and error messages local.

### corpus-text-normalisation-parity-copy | medium | corpus extractor carries an explicitly byte-identical copy of registry text normalization

`src/cadrumo/domain/calculations/registry/_text.py:14-26` owns `normalise_corpus_text`: HTML entity and NBSP decoding, bounded tag removal, NFKD mark removal, whitespace collapse, strip, and lowercase. `dev/corpus/extract_manual_corpus_text.py:42-60` repeats all three regexes and the complete function. Its own comments and docstring explicitly require byte identity, and it is used to create sidecars at `:195`; the current test suite imports that private copy in `src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py:12,250`. The registry sidecar freshness test directly asserts every branch of equality—tags/entities, comparison operators, accents, NBSP, whitespace, and case—at `domain/calculations/registry/tests/test_sidecar_freshness.py:95-160`.

The copy was introduced in `ee5a92ee63a` and later moved in `20b6db245c` to avoid importing the heavyweight registry package outside an installed state-root environment. That constraint is real, but not a reason for two owners: the function is stdlib-only and semantically identical. Move it and its constants to a small import-light shipped module below the already import-light `cadrumo` root, then import that owner from both the registry and extractor. Replace the parity-copy test with direct behavior tests and an import-light smoke test.

### packaging-file-sha256-owner-split | low | Scoop and Homebrew generators copy an existing streamed file-digest implementation

The packaging queries found byte-equivalent `_sha256` helpers in `packaging/scoop/generate.py:49-54` and `packaging/homebrew/generate.py:123-128`. Each opens a path in binary mode, reads 1 MiB chunks, and returns a lowercase SHA-256 hex digest; they feed the generated artifact records at Scoop `:81` and Homebrew `:177`. `dev/packaging/_acquire_common.py:159-165` already provides the exact operation as `sha256_path`, with the same inputs, chunking, return and error behavior. The two generator copies were independently added in `c820d55cea` and `f73c7fc144`; the shared helper followed in `1678f67fb9`.

This is a safe behavior subset, but do not fold the independently computed digest helpers in the generator tests into the production helper—their independence is useful oracle evidence. Remediate by relocating the reusable digest to a dependency-light `dev.packaging` hashing owner (also considering the other `dev/packaging/evidence_release.py` copy), then import it in both generators while preserving independent test digest calculation.

### cli-dead-exit-code-authority | medium | an unused CLI table restates the live error-category process-exit mapping

The CLI contract lane found the actual exit-code authority in `src/cadrumo/core/errors/_registry.py:410-438`: `get_error_exit_code` maps each registered `ErrorCategory` to the process result. Both real CLI boundaries use that getter—`entrypoints/cli/_errors.py:508` and `_terminal_errors.py:353`—and their integration tests derive their expected code from it (`entrypoints/cli/tests/test_error_boundary_integration.py:18-89`, `test_command_group_import_failure_surface.py:28-102`, and `test_modelo_work_preview_maritime_exemption.py:29,191`).

`src/cadrumo/entrypoints/cli/_exit_codes.py:19-50` repeats the overlapping `ERROR=1` through `INTERNAL=6` and `LOCKED_BY_DESIGN=7` mapping, then reserves 8, 10, and 20. Exact symbol search finds no production or test import of `ExitCode`, no external `ExitCode.` use, and no consumer of its `exit_with` helper; it survives only through stale inventory references and prose. The duplicate projection agrees for every live registered category; its extra rows have no consumers. History establishes that the core getter arrived first in `129b549c03a` and the table followed later in `5e821520978`.

Remediate by deleting `_exit_codes.py` under the no-legacy policy, removing its two stale test-inventory exemptions and stale `ExitCode` prose. Retain the core registry getter and its existing end-to-end error-boundary tests as the sole contract.

### cli-root-output-format-bypass | medium | root `--format` repeats and weakens the canonical output-format admission contract

`src/cadrumo/core/output_rendering.py:51-56` declares the canonical `OutputFormat` enum (`text`, `json`), and `render_command_output` validates that contract at `:72-106`. The CLI instead defines raw `_FORMAT_TEXT`, `_FORMAT_JSON`, and unused `_FORMAT_TABLE` literals in `entrypoints/cli/_common.py:71-83`, branches on the JSON literal at `:142`, and registers the root `--format` as `str` in `entrypoints/cli/__init__.py:140-144`, manually normalising it at `:155-156`. The table literal has no reference beyond its declaration; a value such as `xml` passes Typer and is refused only late when rendering begins.

The canonical enum covers every live format and rejects the stale `table` token, so it is the strict usable superset. Existing tests prove only later renderer refusal (`core/tests/test_output_rendering.py:15,173-179` and `entrypoints/cli/tests/test_registry_cli.py:382-400`), not the root option's advertised accepted set or parse-time rejection. The raw root path predates the enum (`d201f619c2`); the canonical owner arrived in `a78f789ff0c` and never enrolled it.

Remediate by re-exporting/importing `OutputFormat` through the appropriate core facade, typing the Typer option with it, and carrying the enum through context and `_format_of`. Delete the three raw constants and add real CLI help and invalid-choice tests proving the accepted values and pre-dispatch refusal.

### cli-lazy-command-registration-double-declaration | medium | command wiring and its guarded dynamic-import allowlist enumerate the same modules separately

`src/cadrumo/entrypoints/cli/__init__.py:893-908` declares `_LAZY_COMMAND_MODULES` as the security allowlist used by `_lazy_loader` at `:911-932`. The same file independently repeats all twelve target modules as individual `_lazy(...)` registrations at `:950-962`; those registrations are the only consumers of the second list. The two target sets are equal today, but adding a command requires two edits and a mismatch produces the runtime `unregistered lazy CLI module` failure.

The security boundary does not require two sources of truth: one literal typed registration table of `(group, child, module)` values can derive the module allowlist for guarded `import_module` while driving every wiring call. Existing real behavior in `entrypoints/cli/tests/test_lazy_command_tree.py` proves cold-start non-import and on-demand Modelo/Wizard loading, but does not prove that every registered target is in the allowlist. The first wiring arrived in `2a00c2e8b24`; the independent security allowlist was layered on later in `6b8a5f1b071`.

Remediate by defining the one registration table, deriving `_LAZY_COMMAND_MODULES` from it, iterating it for `_lazy` wiring, and extending the lazy-tree behavior test across every table row. Keep the membership guard at the actual dynamic-import boundary.

### profile-bare-model-secure-persistence-kernel | high | five financial repositories repeat the same encrypted singleton load/save mechanics

The adapter/storage lane found the same bare-model persistence kernel across `adapters/persistence/profile/assets.py` (assets at `:147,181,221`; amortization at `:260,294,310`), `inventory.py:151,185,268`, `bienes_inversion.py:133,168,206`, and `prorrata_register.py:133,167,180,250`. Each binds a `SecureObjectRepository`, loads its default-key record with namespace/class/version constraints, returns an empty typed model when absent, deserializes `model_validate_json`, then saves the model's JSON bytes with the same current timestamp and secure-object metadata. The registry centralises the matching namespace definitions at `adapters/persistence/storage/_namespace_registry.py:262-315`: each is bucket-local, structured custody, financial, schema v1, and default-key based.

This must not be replaced with `SecureBoundRepository`: that class introduces an inner envelope and would change durable bytes. The repeated kernel is nevertheless parametrically substitutable through a typed bare-model `SecureSingletonRepository[T]` taking the registry definition, model parser/empty factory, and error translator. Domain `add`, `upsert`, movement, and error semantics remain thin concrete repository methods. Real encrypted-SQL round-trip and corruption behavior is already covered in `profile/tests/test_assets_roundtrip.py:71`, `test_inventory_roundtrip.py:85`, `test_bienes_inversion_roundtrip.py:63`, and `test_prorrata_register_roundtrip.py:85`. History gives clear copy order: assets/inventory were hardened in May/June; Bienes Inversion arrived on 2026-07-01 explicitly mirroring assets, and prorrata followed on 2026-07-06 citing Bienes Inversion.

Remediate by introducing the typed bare-model owner without altering payload serialization, exposing the existing `SecureObjectWrite` path for prorrata's co-emission case, and routing the five repositories through it. Retain their domain operations and add cross-repository durable-byte and corrupt-record assertions before deleting duplicated load/save blocks.

### outbound-provider-object-name-kernel | medium | local and Google Drive providers define identical safe-label and object-filename behavior

`src/cadrumo/adapters/outbound/storage/_local.py:83-94` owns `_validate_label` and `_filename`; `storage/_google_drive.py:100-109` repeats them as `_safe_label` and `_filename`. Both trim labels, replace each non-alphanumeric/non-`-_.` character with `-`, use `object` for blank values, cap the result at 64 characters, and construct `<8-character-HMAC-prefix>--<label>.bin`. Provider selection passes a single label through either path in `entrypoints/cli/_config/_google.py:607-635`; a direct function matrix covering blank, whitespace, ordinary, unsafe, overlong, and Unicode labels confirms equal output.

The same-day history is unambiguous: the local implementation landed first in `227f54970d5` and the Drive copy followed in `b4e918001de`. Do not merge their HMAC or namespace validation: local has intentionally stricter dot/alphabet constraints, which fails the constraint-shape gate. Real storage/provider behavior is covered by `adapters/outbound/storage/tests/test_local.py:52`, the LocalFileSystemProvider mirror in `entrypoints/cli/_config/tests/test_google_sync_push.py`, and the Drive pre-service boundary tests.

Remediate by extracting a small shared naming module with `sanitize_object_label` and `provider_object_filename(..., extension=".bin")`; retain local's sidecar-extension wrapper and the distinct provider validation policies. Add direct shared naming contract cases alongside the current integration tests.

### calc-sheets-dated-scalar-resolution-bypass | high | calc-sheet tariff lookup bypasses the ambiguity-safe registry parameter resolver

`src/cadrumo/application/storage/calc_sheets/_engine.py:363-389` defines `_resolve_scalar`, used by `_tariff_tables` at `:441`, to select a dated scalar parameter. `domain/calculations/registry/_formula_runtime_ops.py:233-252` already owns the public `resolve_parameter`, used by the formula runtime and re-exported through the registry facade. Both produce identical `Decimal` values for all 244 committed scalar dated-value cases when given the filing period; the canonical helper also accepts a more general date-axis mapping and fails closed on overlapping windows, whereas the sheet copy silently selects the last matching declaration. A synthetic overlapping-window probe produced `2` locally and canonical `expected exactly one ... found 2`.

The sheet copy landed in `b5426befab`; the stricter canonical resolver followed in `47a641c180` and never enrolled Sheets. Focused real engine, public parameter, and formula runtime tests passed (22 tests). Remediate by deleting `_resolve_scalar`, calling `resolve_parameter(definition, {"filing_period": filing_date})` from `_tariff_tables`, and translating the registry failure to the existing `CalcSheetsEngineError`. Replace the private-helper test with build-plan/real-snapshot parity and ambiguous-window refusal.

### registry-formula-dag-double-construction | medium | validation rebuilds the canonical runtime dependency graph

`src/cadrumo/domain/calculations/registry/_validate_formulas.py:25-44` builds a `TopologicalSorter` from formula targets and `expression_casilla_refs`; `registry/_runtime_graph.py:248-267` owns the same graph construction as `formula_evaluation_order`, consumed by the formula runtime. Both receive the same validated `ModeloRevision`; the runtime helper returns the required order and raises `CycleError`, which validation can translate to its existing validation error. Parity held across all 90 committed revisions, and a synthetic cycle produces the expected validator/runtime failures.

The canonical runtime order was present in `87ab1d06a8`; the validator copy arrived later in `2076d92e343`. Focused registry/runtime evidence passed (60 tests). Remediate by calling `formula_evaluation_order` from `validate_formula_dag`, catching `CycleError`, deleting its local graph reconstruction, and pinning shared order/cycle behavior.

### formula-reference-walker-fragmentation | medium | filing, relation prefill, calc-sheet layout, and tests recursively traverse expressions instead of using runtime-graph walkers

The registry runtime graph owns typed expression walkers at `src/cadrumo/domain/calculations/registry/_runtime_graph.py:36-93`: casilla, relation, binding, parameter, and date-binding references. Application copies occur in filing's `_collect_formula_binding_ids` (`application/filing/__init__.py:453-457,569-576`), relation prefill (`application/calculations/_relation_prefill.py:701-713`), and four calc-sheet layout walkers (`application/storage/calc_sheets/_layout.py:177-252`) that feed export/layout consumers. Two registry tests also reimplement casilla traversal in `tests/test_modelo_202_registry.py:304-312` and `tests/_modelo_100_registry_support.py:899-906`, contrary to the direct-import testing rule.

For every real typed `FormulaExpression`, the local and canonical values/order agree: 90 revisions, 1,256 formulas, and the layout's 37 binding, 2 date-binding, 142 parameter, and 34 relation references all matched. History is consistently later-copy: the public/canonical walkers predate their filing, relation, layout, and test counterparts. Focused real suites passed (28, 30, and 24 tests). Remediate by exporting the parameter/relation walkers through the registry facade, folding canonical results into any boundary-specific set/dedup wrapper, deleting all recursive copies, and adding whole-registry parity coverage for future leaf kinds.

### keyed-bracket-parameter-resolution-fragmentation | high | five formula runtimes repeat a declaration-order-sensitive parameter-table lookup

Five sites independently match a keyed bracket row by string key and filing-year window: M131 `_m131_modulos_coefficient` and `_m131_modulos_cuantia_exceso` (`_formula_runtime_m131.py:149-179,433-456`), M303 `_m303_modulos_iva_coefficient` and the cuota-minima lookup (`_formula_runtime.py:1138-1164,1257-1291`), and M210 `_m210_baseline_rate` (`_formula_runtime_irnr.py:211-229`). They have exact result parity across 10 keyed parameters and 892 committed rows, but the schema rejects only duplicate `(key, valid_from)` values, not overlapping year windows. A validated same-key overlapping example therefore resolves as `1` or `2` depending on declaration order.

The copies arrived in the M303, M210, and M131 additions (`aeaa7b935d4`, `a8c9507a0f6`, `4b497ddbd84`). Focused M210/M131/M303/schema suites passed (170 tests). Remediate with a registry-owned `resolve_keyed_parameter(parameter, key, filing_year)` that requires `keyed_bracket_table` and rejects more than one matching row. Route all five callers through it while retaining their local missing-to-zero/unresolved policy, and add schema overlap rejection or a fail-closed ambiguity regression plus whole-registry parity.

### runtime-scalar-parameter-provenance-copy | medium | M100, M131, and M210 repeat scalar admission, resolution, and operand-lineage mutation

`registry/_formula_runtime.py:920-937`, `_formula_runtime_m131.py:46-63`, and `_formula_runtime_irnr.py:467-484` each validate the same numeric parameter types, resolve with `resolve_parameter(ctx.date_context)`, raise the same typed error family, and append identical operand references/values to the evaluation context. Only the operation label differs. The same `_EvalContext` and validated parameter shape make a shared context-aware helper directly substitutable; value and provenance parity held across all 244 committed numeric dated values.

The copies landed successively in M100 (`6d6c03afe24`), M210 (`a8c9507a0f6`), and M131 (`4b497ddbd84`). Focused M100/M210/M131 behavior passed (42 tests). Remediate with one shared runtime-support helper parameterised by `op`, or an equivalent shared provenance protocol helper, and add a regression that pins value, lineage, and error context together.

### operator-json-schema-envelope-bypass | high | the sanctioned operator JSON funnel promises registered schema validation but manually emits unchecked envelopes

`src/cadrumo/core/json_contract.py:195-257,423-481` owns the strict frozen `SchemaEnvelope` and registered output-schema contract. Its `emit_json_success` path at `:331-394` instead accepts `result: object` and manually creates the six JSON keys without constructing `SchemaEnvelope` or consulting `SCHEMA_REGISTRY`; `application/operator_output/_emit.py:28-57` propagates that bypass despite documenting registered-schema validation at `:45-48`. Direct production probes emitted exit-zero success JSON for a blank command/raw dictionary and for `not.registered` with a rogue dictionary.

Existing core and CLI tests only parse already-correct emitted data or verify registry/tree metadata; `application/operator_output/tests/test_operator_output.py:36-42` explicitly preserves permissive unregistered output. The schema/manual primitive originated together in `b8c61a73626c`; the operator funnel promised the stricter invariant later in `5ea737b647ae04a`. Remediate at the operator funnel: resolve the exact registered schema, validate the result, instantiate the specialised `SchemaEnvelope` before redaction/serialization, reject blank/unregistered/mismatched calls, and replace the permissive test with real refusal and all-registered runtime-construction coverage.

### cli-metadata-invocation-token-authority | medium | help/version token recognition is copied across startup, output, and logging boundaries

The exact token set `{--help, -h, --version, -V}` is independently implemented at `entrypoints/cli/__init__.py:1141-1143`, `entrypoints/cli/_common.py:76-78`, and `core/logging.py:107-120`. The copies control startup state isolation and progress sink selection, output's sandbox/profile bypass, and settings-derived logging initialization. The parameterised startup predicate is a strict superset of the argv-bound copies; logging's executable-identity check is an orthogonal outer guard. In-process Click invocations can leave process `sys.argv` different from the startup's explicit argument list, permitting disagreement even when downstream tests pass.

Logging's copy appeared in `2559742eae4c`; the startup/output versions followed in `993d9d3b38c`; an executable-name adjustment later retained the split. Existing fast-path/help tests prove downstream behavior but no predicate parity or logging-metadata case. Remediate by extracting an import-light pure `is_metadata_invocation(arguments: Sequence[str])`, passing actual invocation arguments/context to startup and output, retaining the logging executable guard before delegation, and adding shared table-driven plus end-to-end state/logging/output coverage.

### output-language-normalisation-authority-bypass | medium | six consumers reimplement the closed output-language admission rule

`src/cadrumo/core/_config_support.py:158-170` owns `coerce_output_language_setting`: trim, lowercase, admit exactly `OutputLanguage`, and return `None` for unsupported values. Equivalent admission appears in `core/i18n/_render.py:135-139`, `adapters/persistence/storage/runtime.py:244-248`, `storage/bucket/_output_language_hint.py:24-29`, `entrypoints/cli/_language_argv.py:26-37`, `entrypoints/cli/_config/_custody.py:36-48`, and `application/registry/_corpus.py:754-778`. Their enum/string/bool/typed-refusal return shapes are caller projections, not different validation policy.

Some early copies predate the canonical helper, but the CLI argv, storage, bucket-hint, and custody paths postdate it (`ba496c80`, 2026-06-06). Focused unit and integration evidence passed across rendering, storage hints/runtime, argv, registry, and login target locale (49 tests total across stated suites). Remediate by exposing the canonical coercer through the core facade, routing all six through it, retaining Settings precedence and registry refusal locally, and pinning blank/trimmed/uppercase/invalid/enum parity.

### corpus-manifest-payload-validation-double-path | medium | on-disk and ZIP manifest loading repeat the same schema, version, and self-digest validation kernel

`src/cadrumo/core/corpus_manifest/__init__.py:387-440` parses an on-disk `CorpusManifest`, rejects future versions, reconstructs its canonical body, and verifies `manifest_sha256`. Later `_load_bundle_manifest` at `:621-644` repeats all four stages for ZIP members; only source-label and structural-error translation differ. `assert_corpus_clean` consumes the Path wrapper at `:455`, while `verify_corpus_bundle` and signature verification consume the ZIP wrapper at `:600`. The accepted JSON/schema/version/body/tamper constraints are identical.

The Path owner comes from `44be8a7b48`/`bc19562ccec` (2026-05-01); the ZIP copy from `ad5f7ba8eb` (2026-07-03). Real filesystem and ZIP evidence passed (15 tests). Remediate with one raw `str | bytes` payload validator accepting a boundary-specific structural-error translator/source label, keep I/O wrappers separate, and add malformed/future-version parity tests.

### sede-auth-gate-redirect-detector-copy | medium | NIF/IVA and compensation-wallet navigation repeat the same Sede authentication-redirect detector

`src/cadrumo/adapters/outbound/aeat/sede/_nif_iva_check.py:496-512` and `_iva_compensation_wallet_parsing.py:220-230` implement the same `str -> bool` detector: empty refusal, URL splitting, case-insensitive AEAT apex/subdomain admission, and configured `auth_gate_4033` path matching. Both read `Settings.external_constants().aeat`; their state-machine consumers are NIF/IVA navigation at `_nif_iva_check.py:394` and wallet navigation at `_iva_compensation_wallet.py:143,187,258,367`. A six-case current-code matrix, including uppercase host/path, wrong host/path, empty, query/fragment, and port, matched exactly.

The NIF owner came first (`5b7899c1377`, then `75c96d82dff` hardening); the wallet copy followed in `589b474c3f6`. Focused real behavior passed (9 tests). Remediate to one Sede `_adapter_utils` detector, retain the fuller NIF test matrix as shared-helper coverage, and keep both live-boundary cases.

### iva-wallet-host-policy-predicate-bypass | medium | wallet parsing manually realigns with, rather than uses, the registry remote-state host policy

`src/cadrumo/domain/calculations/registry/_remote_state_guard.py:452-465` owns `_host_within_policy`, the exact-host plus validated-suffix admission predicate. Wallet parsing reimplements it at `_iva_compensation_wallet_parsing.py:488-502`, whose docstring explicitly says it merely aligns with the read guard. Its consumers are representation-form admission, discovered-wallet URL auditing, and navigation target checks (`:241,:472` and `_iva_compensation_wallet.py:452-453`). For the wallet `_READ_GUARD_POLICY`, both predicates admit/reject identically—including case folding and raw-netloc port/userinfo refusal—across a seven-host matrix.

The wallet copy (`589b474c3f6`) predates the canonical predicate (`0b8551677d5`), but a later wallet change (`c45e2b4119d`) manually realigned it instead of enrolling the owner. Remediate by exporting the policy predicate through the registry facade, locating/importing the wallet policy where parsing can use it, and deleting the local predicate while preserving path/method checks.

### login-profile-lifecycle-resolution-bypass | high | login resolves tombstoned identifiers through ad hoc UUID/label fallthrough instead of the lifecycle-aware profile resolver

`src/cadrumo/application/workflow/_profile_bucket_scan.py:156-199` owns `resolve_profile_bucket`: UUID-first resolution, exact-label fallback, one lifecycle filter, and ambiguity semantics. `application/user_profile/_login_session.py:306-350` later re-composes `read_profile_bucket_by_id` and `read_profile_bucket` in `_resolve_login_target` and `_resolve_selected_target`, consumed by `login_profile` at `:401-405`. With real manifests, a tombstoned UUID X and live bucket Y labelled X make the canonical resolver return `None`, named login select Y/active, and bare selected login accept X/tombstoned—an authentication target disagreement.

The canonical resolver was added first in `25ee7cad` (2026-06-04); the bypass arrived in `49072127` (2026-07-24). Focused real named/unknown login and lifecycle-resolution evidence passed (5 tests). Remediate both login resolvers through `resolve_profile_bucket`, retaining only local blank/unknown `ProfileNotFoundError` translation. Add real-manifest regressions for tombstoned selected pointers and UUID-shaped label fallthrough.

### active-profile-health-mixed-snapshot-label | high | projection and whoami re-read a manifest after health assessment, allowing inconsistent label and next-action snapshots

`assess_active_profile_health` at `src/cadrumo/application/workflow/_profile_health.py:118-171` already resolves the active manifest and uses `registered_pointer.label` at `:241`, but `ActiveProfileHealth` (`:62-78`) omits that result. `state_projection.py:266-292` and MCP `build_whoami_identity` in `_harness_tools.py:248-289` then resolve the same manifest again solely for a label. A real-storage proof assessed an incomplete profile as Alpha, renamed its manifest to Bravo, then projected the captured health: it emitted `label=Bravo` alongside `next_action='aeat config profile edit Alpha'`.

The health owner predates both duplicated reads (`932f5a22`, then `f8240761` and `27442b69`). Projection/health evidence passed (2 tests) and whoami integration passed (1 test). Carry the manifest label/pointer through an internal typed health assessment and consume that snapshot in projection/whoami; do not widen the external repair JSON (`_config/_repair_profile.py:110-112`)—keep the field serialization-excluded or internal. Add a real rename-between-assessment-and-projection regression and retain the active-label whoami proof.

## Recommendations

1. Replace the Wizard registration bridge with an explicit lazy schema-owner import in the manifest builder, then delete the bridge and its bridge-only tests.
2. Extend the attachment service's file-ingestion signature for the two existing provenance fields before routing the ledger secure-write block through it.
3. Move the casilla-reference diagnostic fragment into the registry facade and test equivalent singular and ambiguous messages at every existing boundary.
4. Route the IVA advisory's permitted number grammar through `normalize_decimal_separators` rather than reimplementing its transform.
5. Route custody's durable audit-event sequence through `emit_bucket_event` while preserving its explicit version and recovery-only best-effort policy.
6. Retire the live snapshot JSON-hash helper in favour of `content_hash_hex`, preserving the existing persisted-ID fixtures.
7. Consolidate vector normalization and RRF in corpus search, with command search retaining only its lexical-candidate policy.
8. Centralize Sede CSV validation at the `JustificanteRef` boundary and test the full 8–32 contract through both declaration capture paths.
9. Resolve each Modelo filing year once through a typed domain selector, including `as_of`, and carry that selection into missing-binding readiness.
10. Use `BucketNamespaceInventoryRow` directly in sandbox discard preview rather than recreating the identical row schema.
11. Establish one import-safe PEP-503 name normaliser for release, smoke, and cohort metadata checks.
12. Extract corpus text normalisation to an import-light shared module and remove its enforced parity copy.
13. Consolidate streamed packaging file hashing without weakening independent test-oracle digest checks.
14. Delete the unconsumed CLI exit-code table and preserve `get_error_exit_code` as the only process-exit authority.
15. Make the root `--format` option consume the typed core `OutputFormat` contract rather than accepting late-refused strings.
16. Derive lazy CLI module registration and its guarded import allowlist from one typed command table.
17. Extract a typed, byte-preserving bare-model secure-singleton repository for the five financial default-key stores.
18. Share provider-safe object-label and filename generation while retaining provider-specific integrity validation.
19. Route calc-sheet dated scalar selection through the ambiguity-safe registry resolver.
20. Reuse runtime graph construction and expression walkers throughout validation, application boundaries, and tests.
21. Centralize keyed-bracket parameter lookup and make overlapping validity windows fail closed.
22. Consolidate scalar-parameter resolution and operand provenance across Modelo runtime modules.
23. Enforce the registered `SchemaEnvelope` at the operator JSON funnel before serializing success output.
24. Centralize CLI metadata-token recognition and pass the actual invocation arguments to each boundary.
25. Route every output-language admission point through the core closed-set parser.
26. Share corpus-manifest payload validation while retaining Path/ZIP boundary error translation.
27. Consolidate Sede auth-redirect and remote-host policy predicates without loosening navigation-specific checks.
28. Route login target selection through lifecycle-aware profile resolution and carry one manifest snapshot through health projection/whoami.
