---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:cd2d48afc360baade2ffab003c292d3fde6a38ef8fa83df2e0bca1c4cf953028'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
  - "[[2026-08-14-test-harness-sanity-successor-adr]]"
  - "[[2026-08-14-test-harness-sanity-semantic-test-corpus-drift-audit]]"
---

# `test-harness-sanity` audit: `fixture census`

## Scope

The successor ADR's D1 requires a census record for every consolidated cluster
before its deletions can be treated as closeable: decorator form, name, scope,
autouse behavior, constraints, teardown, consumers, visibility boundary, and
nominated owner, proving substitutability rather than asserting it. This
record covers every cluster this campaign's `find_observation` /
`resolve_convenio_rate` / `declared_manual_inputs` /
`_modelo_validation_failures` batches produced directly, plus every peer
cluster named in the wave's own accounting, each independently re-opened and
read against the live tree rather than taken on report. None of these are
pytest fixtures in the decorator sense except `active_profile_isolated_backend_fixture`;
the rest are plain shared helper functions, so "decorator form" and "autouse"
read N/A for them and that is recorded explicitly rather than left blank.

Grounding: `uvx vaultspec-rag search "MANUAL_INPUT binding source kind unrouted casilla silent blank" --type vault --doc-type adr` surfaced `2026-06-10-calculation-aggregation-taxonomy-adr` before the `declared_manual_inputs` consolidation, confirming the name collision with the manual-input allowlist is coincidental (see the finding below). `uvx vaultspec-rag search "test proving the AEAT adapter refuses to perform a live submission only:tests"` and a matching extractor-tamper query located real non-consolidation candidates; grep alone would have needed the exact error-class name in advance to find either.

## Findings

### resolve_convenio_rate | census | 12 sites, one canonical owner, confirmed rate/citation-safe

- **Decorator form / scope / autouse:** N/A — plain function, not a fixture.
- **Name:** `resolve_convenio_rate(*, tipo_renta: str, country_code: str, base: str) -> tuple[Decimal, Decimal]`.
- **Constraints:** drives the real registry engine (`calculate_registry_snapshot`) over the live Modelo 210 snapshot; no mock, no hand-computed rate. Every treaty rate literal and legal-citation assertion (`convenio-es-{be,de,fr,nl,pt,us}-*:art-{10,11,12}`) stayed in its call site, never moved into the helper.
- **Teardown:** none — no persistent state, each call opens/derives its own `isolated_runtime_profile` at the caller.
- **Consumers (12, verified by grep, zero stray local definitions remain):** `test_modelo_210_convenio_es_{be,de}_canones.py`, `_de_dividend.py`, `_fr.py`, `_fr_canones.py`, `_nl_canones.py`, `_pt_canones.py`, `_us_canones.py` (8, canones income class), `_es_be.py`, `_es_nl.py`, `_es_pt.py`, `_es_us.py` (4, dividend/interest income class).
- **Visibility boundary:** module-private (`_convenio_rate_support.py`, no leading-underscore export needed beyond the module itself), consumed only by the 12 sibling test files in `src/cadrumo/application/calculations/tests/`.
- **Nominated owner:** `src/cadrumo/application/calculations/tests/_convenio_rate_support.py`.
- **Substitutability proof:** all 12 bodies were byte-identical modulo the `surface=` diagnostic label; verified by direct read of all 12 files before editing. Before/after failure-set diff (sorted FAILED/ERROR ids, `application/calculations/tests/`, 393 lines) is empty — zero regressions, zero fixes.

### declared_manual_inputs | census | 3 sites, one canonical owner, name collision recorded and NOT yet renamed

- **Decorator form / scope / autouse:** N/A — plain function.
- **Name:** `declared_manual_inputs(oracle_payload_name: str) -> dict[CasillaId, Decimal]`, added alongside the pre-existing `read_manual_worked_example`.
- **Constraints:** reads `ManualWorkedExamplePayload.declared_inputs` off a bundled AEAT-manual worked-example oracle JSON; asserts `declared is not None` before use.
- **Teardown:** none — pure read of a bundled corpus file.
- **Consumers (3):** `test_m100_2021_cuotas_integras_escala_aragon_manual_worked_example.py`, `test_m100_2022_...py`, `test_m100_2024_...py`, all in `src/cadrumo/domain/calculations/registry/tests/`.
- **Visibility boundary:** module-level export from the EXISTING shared support module, not a new one — `_manual_oracle_support.py` already carried `read_manual_worked_example` and all 3 consumers already imported it, so this is the narrowest common owner rather than a new module.
- **Nominated owner:** `src/cadrumo/domain/calculations/registry/tests/_manual_oracle_support.py`.
- **Name-collision finding, grounded (recorded here per operator direction):** the name still reads, out of context, like the dangerous `MANUAL_INPUT` / `DEFERRED_SOURCE_KINDS` registry binding source-kind allowlist that `2026-06-10-calculation-aggregation-taxonomy-adr` governs — the mechanism this repo's own rules treat as a serious defect surface because it can silence a binding-source refusal and leave a casilla silently blank. It is unrelated by MEANING: this function reads what the AEAT-published Manual Práctico PRINTS for a worked example, to seed a test scenario without re-transcribing the same figures twice. Confirmed via the `ManualWorkedExamplePayload` docstring in `_external_grounding.py` and the ADR search above, before any consolidation was made — grounding prevented treating an unrelated name match as a reason to hesitate on an otherwise safe, purely mechanical merge. Plan step `W09.P30.S131` now owns the rename; recommended target `oracle_declared_figures`, reasoning: "oracle" keeps the module's existing vocabulary (`read_manual_worked_example`, `ManualWorkedExamplePayload`) rather than inventing a new noun, and "figures" (not "inputs") drops the half of the name that actually matches the allowlist's own vocabulary (`BindingSourceKind.MANUAL_INPUT`). Not renamed yet, as instructed.
- **Substitutability proof:** all 3 bodies byte-identical except the closed-over `_ORACLE_PAYLOAD_NAME` constant, which is already a per-file module constant and is now passed as the parameter. `ruff check` clean on all touched files (caught and fixed one broken import — `read_manual_worked_example` was still directly used for `.expected_by_casilla_id` in all 3 files and had to stay imported alongside the new name).

### modelo_validation_failures | census | 3 sites, one canonical owner (existing shared module)

- **Decorator form / scope / autouse:** N/A — plain function.
- **Name:** `modelo_validation_failures(modelo: ModeloDefinition) -> list[str]`.
- **Constraints:** runs the REAL `RegistryValidator(minimal_catalogues()).validate_modelo(modelo)` and returns the accumulated failure-message lines, or an empty list; never raises past this function, so callers assert on message text.
- **Teardown:** none.
- **Consumers (3):** `test_referential_integrity_part1.py`, `_part2.py`, `_part4.py` in `src/cadrumo/domain/calculations/registry/tests/`.
- **Visibility boundary:** added to the EXISTING `_referential_integrity_support.py`, which all 3 consumers already imported for `minimal_catalogues`, `minimal_modelo`, etc. — narrowest common owner, no second support module created.
- **Nominated owner:** `src/cadrumo/domain/calculations/registry/tests/_referential_integrity_support.py`.
- **Substitutability proof:** all 3 bodies byte-identical, confirmed by direct read; all 3 close over the identically-imported `RegistryValidator` / `RegistryValidationError` / `minimal_catalogues`. Consolidation left `ModeloDefinition` a dead import in all 3 consumer files (it was only used in the deleted local function's signature) — caught by `ruff check`, removed from each file's import list rather than left dangling.

### verification, application/calculations + registry/tests directories | census | failure-set diffs

`application/calculations/tests/` (covers `find_observation`, `resolve_convenio_rate`): baseline 376 failed / 317 passed / 2 warnings / 17 errors; post-edit identical; sorted FAILED/ERROR id diff empty (393 lines each side). First attempt at this diff raced a background pytest run against live file edits and was discarded rather than reported — the re-run above is the race-free measurement.

`domain/calculations/registry/tests/` (covers `declared_manual_inputs`, `modelo_validation_failures`): baseline 1388 failed / 3062 passed / 14 warnings / 204 errors, captured before any B20/B21 edit. Post-edit run was still in progress at the time this record was drafted; the exact diff is appended by the authoring session once it completes, per the same never-report-an-unsound-measurement discipline used above.

### scoped_attribute | census | 10 sites, one canonical owner

- **Decorator form:** `@contextmanager` (not a pytest fixture — a context-manager helper).
- **Scope / autouse:** N/A, not a fixture; reached per-call via `with scoped_attribute(...)`.
- **Name:** `scoped_attribute(target: object, name: str, value: object) -> Iterator[None]`.
- **Constraints:** hand-rolled save/restore performing the identical mutation `monkeypatch.setattr` would, deliberately avoiding the `monkeypatch` fixture this repo's real-behaviour convention bans from production tests — the module's own docstring states this rationale.
- **Teardown:** `finally: setattr(target, name, original)` — always restores, even on exception in the with-block.
- **Consumers:** 10, verified by grep for `attribute_scope import scoped_attribute` across `src/`.
- **Visibility boundary:** reached cross-package through the module's own path (`from cadrumo.tests.attribute_scope import scoped_attribute`), per `cadrumo/tests/__init__.py`'s documented submodule-direct-reach convention rather than facade promotion.
- **Nominated owner:** `src/cadrumo/tests/attribute_scope.py`.

### _repo_at + _ephemeral_secure_repo | census | verified 10 consumers, not 8

- **Decorator form:** both `@contextmanager`.
- **Scope / autouse:** N/A, not fixtures.
- **Names:** `_ephemeral_secure_repo(tmp_path, database_name) -> Iterator[tuple[Path, Any, SecureObjectRepository]]` (opens under a fresh `EphemeralMasterKeyProvider`); `_repo_at(db_path) -> Iterator[SecureObjectRepository]` (opens against an existing path, no key provider — for reopening the same on-disk database under the same key established elsewhere).
- **Constraints:** both create the schema (`Base.metadata.create_all(engine)`) against a real SQLite engine — no mock.
- **Teardown:** both `finally: engine.dispose()`.
- **Consumers:** grep for `_secure_objects_support import` under `adapters/persistence/storage/sql/tests/` returns **10** files, not the 8 in the original assignment list (`test_apply_batch.py`, `test_secure_objects_part1/2/3.py`, `test_secure_objects_schema_lineage.py`, `test_secure_object_absent_revision.py`, `test_secure_object_decode_order.py`, `test_secure_object_digest_identity.py`, `test_secure_object_integrity_agreement.py`, `test_secure_object_revision_lineage_coverage.py`). Recorded as found, not silently corrected to match the expected count.
- **Visibility boundary:** module-private, `adapters/persistence/storage/sql/tests/` only.
- **Nominated owner:** `src/cadrumo/adapters/persistence/storage/sql/tests/_secure_objects_support.py`.

### serve_directory | census | verified 7 consumers, not 5; real socket-fd leak fix confirmed in the docstring

- **Decorator form:** `@contextmanager`.
- **Scope / autouse:** N/A.
- **Name:** `serve_directory(directory: Path) -> Iterator[tuple[socketserver.TCPServer, int]]`.
- **Constraints:** binds `("127.0.0.1", 0)` (ephemeral port), serves on a daemon thread.
- **Teardown:** `finally: httpd.shutdown(); httpd.server_close(); thread.join(timeout=5)` — the module's own docstring states this consolidates five byte-identical copies that had drifted apart in name only, and that the server "always shuts down cleanly ... including on an exception," which reads as the fd-leak fix referenced in the assignment.
- **Consumers:** grep for `_http_serve_support import serve_directory` under `dev/` returns **7** files, not 5 (`test_deployment_search_parity.py`, `test_pagefind_inject_site.py`, `test_palette_ranking.py`, `test_prorrata_smoke_gate.py`, `test_search_page_fulltext_class_ranking.py`, `test_search_page_inline_ladder.py`, `test_search_page_query_param.py`). Recorded as found.
- **Visibility boundary:** underscore-prefixed module, never collected as a test module itself (stated in its own docstring); `dev/docs/tests/` scope.
- **Nominated owner:** `dev/docs/tests/_http_serve_support.py`.

### _match / _oracle_rules | census | verified 11 consumers, not 7

- **Decorator form / scope / autouse:** N/A, plain functions.
- **Names:** `_oracle_rules() -> list[dict[str, object]]` (reads the ledger corpus's `ground-truth.manifest.json`); `_match(description, rules) -> dict[str, object] | None` (first rule whose `match` substring is in `description`).
- **Constraints:** the shared module also carries `_invoke`, `_import_corpus`, `_import_bbva`, `_list_payload`, `_find`, `_set_group`, `_active_repo`, `_xlsx_mirror_of_csv` — a broader shared-plumbing module than just the two named helpers, all real CLI invocations against a real ledger corpus fixture, no mocks.
- **Teardown:** none — stateless reads/CLI invocations.
- **Consumers:** grep for `_ledger_corpus_support import` under `entrypoints/cli/tests/` returns **11** files, not 7 (`test_ledger_classify_fixture.py`, `test_ledger_corpus_batch_transform.py`, `test_ledger_corpus_classification.py`, `test_ledger_corpus_import.py`, `test_ledger_corpus_import_export.py`, `test_ledger_corpus_journeys.py`, `test_ledger_corpus_review.py`, `test_ledger_identification_operator_input.py`, `test_ledger_persona_autonoma_close.py`, `test_ledger_persona_multicurrency.py`, `test_ledger_persona_yearend_m100.py`).
- **Visibility boundary:** module-private, `entrypoints/cli/tests/` only.
- **Nominated owner:** `src/cadrumo/entrypoints/cli/tests/_ledger_corpus_support.py`.

### _line_value | census | 4 sites, one canonical owner

- **Decorator form / scope / autouse:** N/A.
- **Name:** `_line_value(output: str, key: str) -> str`, raises `AssertionError` naming the missing key and full output on miss.
- **Constraints:** parses plain tab-separated CLI text output; no JSON, no envelope model involved.
- **Teardown:** none.
- **Consumers:** 4, matches the assignment list exactly (`test_catalogue_invoice_bulk_import.py`, `_lifecycle.py`, `_link_flow.py`, `_wizard.py`).
- **Visibility boundary:** module-private, `entrypoints/cli/tests/` only.
- **Nominated owner:** `src/cadrumo/entrypoints/cli/tests/_cli_text_output_support.py`.

### active_profile_isolated_backend_fixture | census | the one true pytest-fixture cluster in this list

- **Decorator form:** the shared function is a FIXTURE FACTORY — it returns a closure decorated `@pytest.fixture(name=name, autouse=autouse)`, not a bare fixture itself, precisely so each site keeps its own name/autouse/bucket-id as explicit per-caller axes rather than collapsing them.
- **Scope:** function-scope (the closure's default).
- **Autouse:** per-caller parameter, default `True`; not uniformly autouse across all sites.
- **Constraints:** documents FIVE independently-varying axes it preserves rather than collapses — `bucket_id`, `autouse`, `name`, `dispose_engine_around` (a second SQL-engine-disposal convention some sites need before AND after), `settings_overrides`, `profile_overrides`, `display_name` — each defaulted to the prior universal behaviour so no consolidated site changes silently.
- **Teardown:** `finally: dispose_engine()` when `dispose_engine_around=True`; otherwise the underlying `isolated_profile_storage_root` / `open_test_profile_session` context managers own teardown.
- **Visibility boundary:** `src/cadrumo/tests/` package-level, cross-package reach by design (a canonical shared-fixture home, not a narrow module-private helper).
- **Nominated owner:** `src/cadrumo/tests/active_profile_isolated_backend_fixture.py`.
- **Note:** this is architecturally different from every other cluster in this census — a fixture FACTORY preserving per-site axes as parameters is the correct shape when scope/autouse/lifecycle genuinely vary per site, versus the plain-function shape correct when the body is identical and only a data value varies. Worth citing as the worked precedent the ADR's "fixture equality is only a candidate signal" consideration describes.

### run_loopback_server / stop_loopback_server | census | 3 telemetry sites, shared start/stop plumbing only

- **Decorator form / scope / autouse:** N/A.
- **Names:** `run_loopback_server(handler_class) -> (server, thread, events)`; `stop_loopback_server(server, thread) -> None`.
- **Constraints:** binds ephemeral port `0` so parallel xdist workers cannot collide; each consuming suite keeps its OWN handler class (the module's own docstring states "the recorded event shape genuinely differs between them") — deliberately narrow consolidation of only the identical bind/serve/shutdown boilerplate, not the handler logic.
- **Teardown:** `stop_loopback_server` always called from the caller's `finally`, per its own docstring, bounded by a 3-second join timeout so a wedged handler surfaces as a failure rather than hanging the suite.
- **Nominated owner:** `src/cadrumo/tests/loopback_recording_server.py`.

### release_cohort | census | 4-source consolidation with wall-clock nondeterminism retired

- **Decorator form / scope / autouse:** N/A.
- **Name:** `release_cohort(root, *, version=..., commit=..., build_constraints_sha256=..., created_at=..., payload_suffix="") -> LoadedReleaseCohort`.
- **Constraints:** materialises a REAL on-disk cohort (every `REQUIRED_ARTIFACT_KINDS` artifact, a real manifest, a real `load_release_cohort` read-back) — no mock. `created_at` is now a fixed default (`datetime(2026, 1, 1, tzinfo=UTC)`) rather than `datetime.now(UTC)`, retiring the wall-clock nondeterminism two of the four source copies had already independently pinned. `payload_suffix` is the one genuinely meaningful kept parameter, needed by the mismatched-evidence gate to build two cohorts sharing a commit but carrying different artifact digests.
- **Consumers:** the module's own docstring names its 4 source sites: `dev/packaging/tests/test_evidence.py`, `test_distribution_evidence_emit.py`, `test_evidence_scrub.py`, and `dev/release/tests/test_distribution_readiness.py`'s `_cohort`.
- **Nominated owner:** `dev/packaging/tests/_release_cohort_support.py`, placed under `dev/packaging/tests/` (not `dev/release/tests/`) because `dev.packaging.cohort_manifest` is the owning production module — the cross-package test-helper import from `dev/release/tests/` follows an established precedent the docstring cites (`dev/release/tests/test_distribution_readiness.py` already imports production cohort/evidence code across that boundary).

### sha256_path | census | packaging-wide digest helper

- **Decorator form / scope / autouse:** N/A.
- **Name:** `sha256_path(path: Path) -> str`, streamed (1 MiB chunks), never buffers the file whole.
- **Nominated owner:** `dev/packaging/_hashing.py` — NOT under `tests/`, this is production packaging code, not a test-only helper, despite being the target of a test-helper consolidation batch.

### declared_live_write | census | INCOMPLETE — one of three sites still has its own local copy

- **Decorator form:** `@contextmanager`.
- **Name:** `declared_live_write(command_key: str) -> Iterator[None]` in the canonical home; a byte-identical `_declared_live_write` (leading underscore, otherwise identical including the docstring) still exists locally in `dev/agent_eval/tests/test_confirmation_gate_golden.py` at the time of this record.
- **Constraints:** declares `command_key` a live-write in `COMMAND_RISK` for the test body, restoring the prior entry (or popping it if there was none) in `finally` — real test-data mutation of the risk table, not a mocked behaviour, per its own docstring.
- **Consumers verified:** `src/cadrumo/entrypoints/mcp/tests/test_hitl_and_live_write.py` and `test_meta_tools.py` both correctly `from ._risk_table_support import declared_live_write`. `dev/agent_eval/tests/test_confirmation_gate_golden.py` does NOT import it — it still defines its own `_declared_live_write` at line 96, byte-identical body.
- **Nominated owner:** `src/cadrumo/entrypoints/mcp/tests/_risk_table_support.py`.
- **Finding, not fixed here (out of this session's assigned batches):** this is a genuine open gap, not a false positive — most plausibly because `dev/` and `src/cadrumo/` are different trees and a cross-tree private import from `dev/agent_eval/tests/` into `src/cadrumo/entrypoints/mcp/tests/_risk_table_support.py` may be structurally the wrong direction (dev-path isolation is itself a gated one-way boundary in this repo — see `src/cadrumo/tests/test_dev_path_isolation.py`). Recorded here rather than silently left for the next agent to "rediscover" as unconsolidated; the correct remedy (shared module relocated to a location both trees can reach, or accepted as a legitimate cross-boundary exception) is a decision for whoever owns that batch, not assumed here.

### write_concept_fragment | census | 3 sites, one canonical owner

- **Decorator form / scope / autouse:** N/A.
- **Name:** `write_concept_fragment(tmp_path, name, content) -> Path`, writes to `concepts/<name>` under `tmp_path` and returns the `concepts` dir.
- **Consumers (3, verified):** `test_loader.py`, `test_scaffold.py`, `test_validators.py`.
- **Nominated owner:** `dev/docs/terminology_handbook/tests/_support.py`.

### registered_objects | census | 4 sites consolidated; a DIFFERENT, similarly-named sibling deliberately left alone across an architecture boundary

- **Decorator form / scope / autouse:** N/A.
- **Name:** `registered_objects(profile_objects, namespace) -> SecureObjectRepository` in `application/operations/tests/_test_support.py`; takes `namespace` as a parameter.
- **Consumers (4, verified):** `test_executor_contract.py`, `test_supervisor.py`, `test_supervisor_lifecycle.py`, `test_supervisor_replay.py`, all under `application/operations/tests/`.
- **Deliberately NOT folded in:** `src/cadrumo/adapters/persistence/operations/tests/test_secure_refs.py` defines its own `_registered_objects(profile_objects) -> SecureObjectRepository` — same shape, same intent, but hardcodes its own module-level `_NAMESPACE` internally instead of taking `namespace` as a parameter, and lives under `adapters/`, not `application/`. Folding these together would cross the adapters/application hexagonal layer boundary this repo's architecture rules forbid crossing for test-owned helpers just as much as for production code. Recorded as a deliberate boundary case, not a missed consolidation — the correct outcome under "narrowest common owner" is two owners, one per layer.
- **Nominated owner (application layer only):** `src/cadrumo/application/operations/tests/_test_support.py`.

### operator_text / build_package_bytes | census | 3 sites each, confirmed against source

- **operator_text:** `operator_text(diagnostic: CalculationSourceDiagnostic) -> str`, `src/cadrumo/application/modelo/tests/_advisory_bucket_fixture.py`.
- **build_package_bytes:** `build_package_bytes(tmp_path, *, bucket_id, work_unit_factory, revision_factory, draft_bytes) -> bytes`, delegates to a sibling `build_package_path` in the same module, which itself is shared by a further 3-site cluster returning the path rather than the bytes (the module's own docstring: "six suites each build a fresh review package ... differing only in ... whether the caller wants the raw bytes back (three suites) or the package path itself (three more)"). `src/cadrumo/application/modelo/tests/_review_package_bytes_support.py`.

### modelo 131 clone-to-parametrize | census | parametrize decorators confirmed present; exact "66" count not independently re-verified

`src/cadrumo/domain/calculations/registry/tests/test_modelo_131_modulos_engine.py` carries `@pytest.mark.parametrize(("epigrafe", "table", "modulos", "expected_previo"), _FASE_1_CASES)` and a second parametrize over `_FASE_4_CASES`, confirming genuine data-driven consolidation exists at this location. This record does not independently re-derive the historical "66 clone tests" figure from git history (not accessible in a form this session could reliably diff against); it is passed through from the assigning report, unverified to that precision, and should be treated as directionally correct rather than exact until someone with the pre-consolidation history confirms the count.

### deliberate non-consolidations | census | partially verified, lower confidence than the clusters above

The AEAT live-write refusal guards, the standalone-runnable gate files, and the extractor tamper-detection tests were located via `vaultspec-rag` (queries in Scope) rather than exhaustively enumerated and counted against the assignment's stated tallies (9 guards across 5 adapter modules; 5 gate files; 4 extractor tests). Confirmed real and load-bearing: `src/cadrumo/adapters/outbound/aeat/auth/tests/test_gate.py::test_require_live_write_always_raises_permanent_refusal` (asserts `AeatAccessGate(settings).require_live_write()` unconditionally raises `LiveSubmitForbiddenError`, with its own comment "no env / Settings read"); `src/cadrumo/adapters/outbound/aeat/sede/tests/test_read_landing_guard.py`, whose own docstring states its reason for existing as written rather than as a shared copy: "This file exercises the real production helper rather than a mirrored copy of its rule. A copy would keep agreeing with itself after the rule changed shape, which is the failure mode that makes a no-write proof worthless." That sentence is the clearest first-party statement of why these guards are deliberately NOT consolidated into one shared assertion, and is recorded here verbatim as the standing rationale future readers should not need to rediscover. `src/cadrumo/tests/test_dev_path_isolation.py` and `test_deferred_cross_layer_imports.py` confirm the standalone-gate-file pattern exists and is intentional (each names its own reason for standing alone in its module docstring). The exact 9/5/4 tallies are NOT independently re-confirmed here to that precision and should not be read as verified counts.

## Recommendations

- Land plan step `W09.P30.S131` (rename `declared_manual_inputs` to something in the `oracle_declared_figures` family) before the next agent reads the name cold — the collision is confirmed real, not speculative.
- Assign an owner to close the `declared_live_write` / `dev/agent_eval/tests/test_confirmation_gate_golden.py` gap: either an accepted cross-tree import exception or a relocated shared home reachable from both `dev/` and `src/cadrumo/`. Do not let it stand as a silent "already consolidated" assumption — this record is the evidence it is not.
- Re-run the `application/calculations/tests/` and `domain/calculations/registry/tests/` failure-set diffs one more time from a fully quiesced tree (no concurrent peer writes) before this wave is declared closeable, given how many peer batches are landing on the same shared worktree concurrently with this record's own verification runs.
- Treat the consumer-count corrections above (`_repo_at`/`_ephemeral_secure_repo`: 10 not 8; `serve_directory`: 7 not 5; `_match`/`_oracle_rules`: 11 not 7) as the census superseding the original assignment tallies, not as errors in either — the assignment counts likely predate later call sites landing on the same shared clusters.
- The 9/5/4 non-consolidation tallies (AEAT write-refusal guards, standalone gate files, extractor tamper tests) need a dedicated enumeration pass by whoever owns that part of the campaign; this record establishes the pattern is real and load-bearing but does not certify the counts.
