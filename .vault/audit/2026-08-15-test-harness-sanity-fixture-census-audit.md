---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-15'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e083b7577c5a76a50b5e2ed97383e4bc0fbce0da2a9fbacdf01fe7565d2efba9'
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

`domain/calculations/registry/tests/` (covers `declared_manual_inputs`, `modelo_validation_failures`): baseline 1388 failed / 3062 passed / 14 warnings / 204 errors; post-edit 1430 failed / 3015 passed / 12 warnings / 209 errors. The raw failure-set diff is NOT empty — 47 new FAILED/ERROR ids, 5 resolved — and this record does not claim it is. Every changed line was checked against the 6 edited test files (`test_m100_{2021,2022,2024}_cuotas_integras_escala_aragon_manual_worked_example.py`, `test_referential_integrity_part{1,2,4}.py`) and the 2 touched support modules (`_manual_oracle_support.py`, `_referential_integrity_support.py`): zero matches. Every new and every resolved line belongs to an unrelated registry surface — `test_classification_coherence.py`, `test_cross_revision_drift.py`, `test_governance_stamp.py`, `test_iva_ledger_observation_role_cutover_static.py`, `test_loader_cache_isolation.py`, `test_loader_directory_mode.py`, `test_m303_orden_anual_authority.py`, `test_modelo_714_registry.py`, `test_orden_aplicabilidad.py` (new), `test_modelo_347_registry_bindings.py`, `test_record_design.py`, `test_record_design_intermediate_source_boundary.py` (resolved). This directory took 13-14 minutes per run and this is an actively-written shared worktree with multiple peer agents landing concurrent commits (confirmed elsewhere in this campaign's own coordination — see the peer note about a broad commit sweeping uncommitted work into the tree); the changed set reads as concurrent peer writes landing on unrelated registry surfaces during the run window, not as an effect of this consolidation, but this record deliberately does not claim a "clean" verdict the way the `application/calculations/tests/` diff earned one — a fully quiesced re-run is the way to earn that here, and is recommended below rather than asserted.

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

**Third construction settled (`W09.P30.S133`/adjacent triage).** `_bound_repo_with_engine(tmp_path) -> tuple[_RoundtripRepository, Engine]` in `src/cadrumo/adapters/persistence/storage/envelope/tests/test_secure_bound_repository.py:67` is a THIRD construction of an encrypted repository, flagged by a peer as possibly skipping the real key provider. Checked all 7 call sites (`test_secure_bound_repository.py:85,116,153,193,229,257,303`): every one wraps the call in `with EphemeralMasterKeyProvider(): ...`, the same caller-side-key convention `_repo_at` uses (as opposed to `_ephemeral_secure_repo`'s self-contained key lifecycle). **Correctness cleared — no fake/skip anywhere in any of the three.** Duplication verdict: the 2-line engine-bootstrap snippet (`create_engine_from_settings(Settings(cadrumo_database_url=...)); Base.metadata.create_all(engine)`) is repeated verbatim across all three, but the wrapping contracts are genuinely different — contextmanager vs plain function, self-key vs external-key, return shape, and `_bound_repo_with_engine` wraps a different class (`SecureBoundRepository`, not bare `SecureObjectRepository`) because `test_secure_bound_repository.py` exists specifically to test that higher base-class layer. **JUSTIFIED-DIVERGENCE at the function level; not consolidated.** A cheap future follow-up, not done here: extract only the 2-line bootstrap snippet into a shared `_bootstrap_sqlite_engine(db_path) -> Engine` micro-helper next time any of the three is touched.

**Superseded later in the same session — the follow-up above WAS done.** `src/cadrumo/adapters/persistence/storage/tests/engine_bootstrap.py::bootstrap_sqlite_engine` exists and is imported by both `_secure_objects_support.py` and `envelope/tests/test_secure_bound_repository.py`. The "not done here" wording above is retained rather than rewritten so the sequence stays legible, but read it as closed. The function-level JUSTIFIED-DIVERGENCE verdict still stands unchanged: the three wrapping contracts remain separate: only the shared 2-line bootstrap moved.

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

### declared_live_write | census | CLOSED (W09.P30.S136) — relocated to `cadrumo.tests`, all 3 sites now import one definition

- **Decorator form:** `@contextmanager`.
- **Name:** `declared_live_write(command_key: str) -> Iterator[None]`.
- **Constraints:** declares `command_key` a live-write in `COMMAND_RISK` for the test body, restoring the prior entry (or popping it if there was none) in `finally` — real test-data mutation of the risk table, not a mocked behaviour, per its own docstring.
- **Teardown:** the `finally` restore above.
- **Consumers (3, all verified importing the one definition after this step):** `src/cadrumo/entrypoints/mcp/tests/test_hitl_and_live_write.py`, `src/cadrumo/entrypoints/mcp/tests/test_meta_tools.py`, `dev/agent_eval/tests/test_confirmation_gate_golden.py`.
- **Visibility boundary:** module-level export reached by cross-package/cross-tree consumers through its own submodule path (`from cadrumo.tests.declared_command_risk import declared_live_write` / `from ....tests.declared_command_risk import declared_live_write`), per the same `cadrumo/tests/__init__.py` submodule-direct-reach convention `scoped_attribute` and `active_profile_isolated_backend_fixture` already use.
- **Nominated owner:** `src/cadrumo/tests/declared_command_risk.py` (new module; `src/cadrumo/entrypoints/mcp/tests/_risk_table_support.py` deleted, it held nothing else).
- **Adjudication (per operator direction, the hypothesis in this record's earlier draft was tested and found wrong):** the original hypothesis was that a `dev/` -> `entrypoints/mcp/tests/` import might be the structurally forbidden direction. It is not — `test_dev_path_isolation.py`'s own docstring states the gate it enforces governs only SHIPPED (non-test) `src/cadrumo` modules importing `dev.*`; test trees on both sides are explicitly excluded from that gate (`_TEST_TREE_EXCLUDES` matches `src/cadrumo/**/tests/**`), and a peer agent independently confirmed roughly 40 existing precedent files of `dev/` importing `cadrumo.tests.<submodule>` (`dev/env/temp_reaper.py`, `dev/identity/hex64_acceptance_probe.py`, `dev/agent_eval/tests/test_exit_code_verdict_golden.py`, among them). The real defect was narrower: `entrypoints/mcp/tests/` was never a valid narrowest-common-owner for three consumers, only two of which lived under `entrypoints/mcp` — the moment a third, unrelated consumer existed, the narrowest common owner became the package's own cross-cutting `cadrumo.tests`, which is exactly the reach point the already-precedented pattern and this file's own pre-existing `from cadrumo.tests import connected_server_and_client_session as connect` import already used. Chose relocation (option 1 of the three offered) over recording a permanent boundary (option 2), because the boundary that would have been recorded does not exist — recording a false boundary as "permanent" would have been worse than the open gap it replaced.
- **Verification:** `ast.parse` and `ruff check` clean on all 4 touched files (`declared_command_risk.py`, `test_hitl_and_live_write.py`, `test_meta_tools.py`, `test_confirmation_gate_golden.py`; ruff auto-fixed import ordering in the two mcp files). `entrypoints/mcp/tests/test_hitl_and_live_write.py` + `test_meta_tools.py`: 25/25 pass (`-m integration`). `dev/agent_eval/tests/test_confirmation_gate_golden.py`: 2 passed / 4 failed (`-m integration`) — every failure traced by hand to the identical origin, `run_golden_scenario` -> `_resolve_revision` -> the registry authority's whole-tree validation (`RegistryValidationError`: missing legal-corpus sidecars, missing export layouts across several unrelated modelos) — the same pre-existing, unrelated registry redness this whole campaign has been told to expect and never judge by absolute count. `test_hypothetical_live_write_leaf_blocks_unconditionally`, the one test in this file that exercises `declared_live_write` WITHOUT going through the golden-scenario registry-authority path, passed; `test_confirmation_gate_wired_into_golden_scenario_passes_when_tiers_match` (the other `declared_live_write` caller) failed at the identical registry-load line as the two callers that never touch `declared_live_write` at all — proving the failure is unrelated to this move, not merely asserting it.
- **Dead imports removed as part of this step:** `dev/agent_eval/tests/test_confirmation_gate_golden.py` had `COMMAND_RISK`, `CommandRiskDeclaration`, `contextlib`, and `Iterator` become dead once its local `_declared_live_write` was deleted; all four removed rather than left orphaned.

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

### grounding-saves | census | three cases where reading the governing decision or the real consumer changed the answer

The reusable lesson from this wave is not only that grounding stopped a wrong move — in the case that matters most here, it CLEARED one. Recorded as three cases, in ascending order of how surprising the correction was:

1. **`declared_manual_inputs` / manual-input-allowlist collision (this session).** Same words ("manual input"), opposite register: one names an AEAT-published paper document's printed figures, the other names a registry binding source-kind escape hatch that can silence a refusal and leave a casilla silently blank. A name-only judgement would have read the collision as a reason to HESITATE on an otherwise safe, purely mechanical, three-site consolidation. Reading `2026-06-10-calculation-aggregation-taxonomy-adr` and the `ManualWorkedExamplePayload` docstring FIRST is what let the consolidation proceed with confidence instead of stalling on a false alarm. This is the sharper case for the rag-first mandate than the usual framing: grounding is not only a brake, it is also what lets you move on something that looks dangerous but is not.
2. **The live-write refusal ADR justifying the `declared_live_write` merge.** `src/cadrumo/entrypoints/mcp/tests/_risk_table_support.py`'s own docstring states the governing fact directly: "no real command declares live_write (never-submit is enforced as 'no such tool exists'), so a test that exercises the defensive BLOCK branch must supply a declared live-write row." That is a uniform, tree-wide rail — one risk-table shape, one refusal path — rather than a per-surface convention that could plausibly vary by adapter. Reading that rail is what justified folding two independently-authored copies (`test_hitl_and_live_write.py`, `test_meta_tools.py`) into one shared context manager rather than treating each surface's copy as legitimately independent.
3. **The `sancion_pdf_bytes` docstring, corrected once the real consumer was traced.** `_notification_document_support.py`'s current docstring states it "self-verifies through pypdfium2 that the produced bytes really carry the text layer" — deliberately NOT claiming pypdfium2 is the same engine production uses. Tracing the real consumer confirms why that phrasing matters: `NotificationDocumentReader.read()` calls `extract_pages_text_from_bytes` in `adapters/inbound/pdf/_pdfplumber.py` — the production extraction path is pdfplumber, not pdfium. An earlier version of this docstring reportedly claimed pypdfium2 was "the same engine as production," which was factually wrong; the test fixture's self-verification is a genuine second-opinion oracle (a different library confirming the text layer exists), not a claim of engine parity. The corrected docstring is the artifact; this record traces WHY the correction was necessary, so the false claim does not get re-authored by a future editor who has not read the production call chain.

### deliberate non-consolidations, expanded | census | first-class entries with the specific cost of merging

Each entry states what consolidating it would have cost, per operator direction, so it reads as a decision record rather than an unexamined gap:

- **9 AEAT live-write refusal guards across 5 adapter modules and 2 architectural layers.** `src/cadrumo/adapters/outbound/aeat/auth/tests/test_gate.py::test_require_live_write_always_raises_permanent_refusal` and `src/cadrumo/adapters/outbound/aeat/sede/tests/test_read_landing_guard.py` are two of the nine; the sede file's own docstring states the cost of merging explicitly: "This file exercises the real production helper rather than a mirrored copy of its rule. A copy would keep agreeing with itself after the rule changed shape, which is the failure mode that makes a no-write proof worthless." Consolidating these into one shared assertion would trade nine independent proofs against nine independent production refusal paths for one proof against one path, silently losing coverage of the other eight the moment any one of them changed shape without the shared copy noticing.
- **5 standalone-runnable gate files, each with its own module-scoped fixture.** `src/cadrumo/tests/test_deferred_cross_layer_imports.py` and `test_dev_path_isolation.py` are two of the five; each names its own reason for standing alone in its module docstring. Pytest fixture scope does not share across files — collapsing a module-scoped setup fixture into a shared location would mean a gate run in isolation (`pytest path/to/one_gate.py`, the way a CI job or a bisect actually invokes it) would silently lose the fixture unless every caller also imported the shared conftest layer, defeating the entire point of a gate that must be independently invocable and unprotected-when-run-alone-safe.
- **4 per-extractor sidecar tamper-detection tests.** Each proves a different extractor's own tamper/fingerprint-mismatch surface (confirmed via `application/aggregation/tests/test_ledger_filing_snapshot.py::test_anti_tautology_tampered_fingerprint_surfaces_mismatch` as one concrete example of the pattern, alongside sidecar-freshness proofs under `src/cadrumo/_data/corpus/tests/`). Merging them would require asserting on a shared tamper-detection interface no such interface currently exists to name, and would lose the per-extractor coupling that lets each test catch its own extractor's specific corruption mode rather than a generic one.
- **`_seed_corpus` — genuinely differing return-type contract, confirmed by direct read.** `src/cadrumo/core/corpus_manifest/tests/test_bundle.py:40` and `test_manifest.py:44` both declare `def _seed_corpus(corpus_root: Path) -> dict[str, bytes]`, returning the seeded content for later assertion. `test_bundle_signing.py:67` declares `def _seed_corpus(corpus_root: Path) -> None` — it seeds and returns nothing, because that suite never needs the bytes back. Forcing one signature would mean either the signing suite silently starts building and discarding a mapping its own tests never read (dead cost, every run), or the two content-returning suites lose the return value they assert against (an actual behaviour loss, not a refactor).
- **`test_evidence_draft.py::_scan_only_pdf_bytes` and its 3 sibling PDF helpers — different concepts, confirmed by direct read.** `_scan_only_pdf_bytes()` builds a raster-only PDF via `PIL.Image(...).save(format="PDF")` — no text layer, mirroring a scanned-document vision-fallback fixture. `_png_bytes()` in the same file is a plain raster image, not a PDF at all. Both are structurally unrelated to `sancion_pdf_bytes()` in `_notification_document_support.py`, which builds a real EXTRACTABLE text-layer PDF via reportlab and self-verifies the text layer through pypdfium2. "PDF-shaped test fixture" is not one concept; folding these together would require branching internally on text-layer-present-vs-absent, which is exactly the axis each test exists to keep apart — a scan-only-PDF vision-fallback test whose fixture accidentally grew a text layer via a bad merge would silently stop testing the fallback path it was written for.

### storage_path_settings_field_authority | proven-negative | `W09.P30.S133` — the `_isolated_user_cli` financial-txs/invoices directory-name drift is SELF-CONSISTENT-ONLY, not a live defect

Raised by the `_isolated_user_cli` vs `isolated_cli_backend` semantic-mirror finding (`test_workflow_surface.py:66-110`): the mirror reproduces, byte-for-byte in intent, a directory-naming drift (`cadrumo_financial_txs_dir=tmp_path/"txs"` vs the taxonomy's declared `"financial/transactions"`) that the canonical `isolated_cli_runtime_profile`'s own docstring (`src/cadrumo/tests/secure_sql.py:635-636`) records as a previously-fixed historical bug. Before treating the convergence (`W09.P30.S132`) as a correctness fix rather than tidy-up, traced every production consumer.

- **Sole production consumer, by taxonomy declaration:** `core/_storage_taxonomy_locations.py:450-461` names `consumer_module="adapters/persistence/storage/_rotation.py"` for both `StorageCategory.FINANCIAL_TRANSACTIONS` and `StorageCategory.INVOICES`. Grepped all of `src/cadrumo` and `dev/` for both enum members outside test files — zero other production references. No archive, export, reconcile, ledger-import or invoice-catalogue path touches either category.
- **That consumer reads the resolved settings field, not the taxonomy default:** `_rotation.py:434,438` reads `settings.cadrumo_financial_txs_dir` / `settings.cadrumo_invoices_dir` directly. It is a defensive re-encryption sweep on master-key rotation ("a sweep, not a writer", per the docstring `test_transactions_repository_roundtrip.py:177` documents), not the actual data path — `TransactionCatalogueRepository`'s own docstring states "no plaintext transaction row, JSON catalogue, or envelope file lands on disk"; real data lives in the encrypted SQL `secure_objects` table.
- **The one general-purpose resolver honors the field first:** `storage_path()` (`core/_storage_taxonomy_locations.py:794-827`) checks the settings field FIRST and only falls back to `local_storage_root / relative_path()` when the field is `None`.
- **ADR grounding:** `2026-08-03-canonical-storage-management-adr` R10 ("Unify the names in core; federate the policy on the member") rules the settings field is the declared override authority, not the taxonomy default — consistent with all of the above.

**Verdict: SELF-CONSISTENT-ONLY.** The `_isolated_user_cli` override is honored end-to-end by every real consumer; no production path currently reads the wrong directory. `W09.P30.S132`'s convergence onto `isolated_cli_backend` is drift-prevention against a defect class that already recurred once (this mirror is proof it recurs), not a data-location bug fix. Recording this so the question is not re-escalated: it was checked against evidence, not inferred.

Grounding queries used: `uvx vaultspec-rag search "resolve the on-disk directory for financial transactions from storage taxonomy" --type code`; `uvx vaultspec-rag search "canonical storage path resolution authority" --type vault --doc-type adr`.

### isolated_backend_family | census-reconciliation | `W09.P30.S140` — the "37-file cluster" figure conflated at least 7 distinct owning implementations sharing one local fixture NAME; true outstanding duplication is much smaller

**This entry supersedes the 37-file figure previously cited for the `_isolated_backend` cluster — conclusion stands, mechanism corrected below.** `grep -rln "_isolated_backend"` returns 117 files today. The name is NOT bound by import-aliasing (`rg -c "import .* as _isolated_backend"` returns zero files, verified before writing this correction) — it is bound four ways: a direct `def _isolated_backend(...)` (9 sites), a module-level assignment from a factory CALL such as `_isolated_backend = active_profile_isolated_backend_fixture(profile_overrides={...})` or `_isolated_backend = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=True, name="_isolated_backend")`, an `__all__ = ["_isolated_backend"]` re-export sitting beside that assignment, and the factory's own parameter default (`active_profile_isolated_backend_fixture`'s `name: str = "_isolated_backend"`, matched 10 times by `name="_isolated_backend"` across the tree). The dominant mechanism is the module-level factory-call assignment — and that is the CONVERGED shape, the thing a successful consolidation produces, not evidence of duplication.

**The reusable lesson is narrower and sharper than "the count was wrong": a name-keyed count of a parameterized-factory cluster is meaningless before AND after consolidation.** The factory's `name=` parameter defaults to `"_isolated_backend"` specifically so every call site binds a locally-recognisable pytest fixture name; consolidating N independently-written bodies into N calls to one factory leaves the name bound at all N sites BY CONSTRUCTION. Per the operator's own report: 37 sites before another agent's sweep, and after that sweep converged roughly 30 of them onto two factories, `def _isolated_backend` occurrences today still stand at 9 with 117 total references to the name. The count did not shrink to track convergence, because it was never counting the thing convergence changes — it counts adoption of a fixture NAME, not persistence of a duplicate BODY. This is a fifth miscount mechanism for this campaign, and the first that INFLATES rather than undercounts: the four before it (functions-only missing inline copies; `def`-name-only missing differently-named siblings; a stale snapshot missing a file created afterward; name-keying missing factories bound via `pytest.fixture(name=...)`) all searched the wrong CONTAINER and came up short. This one searches the right container (the bound name) but that container is an INTERFACE shared by design, not a duplication signal, so more hits after consolidation reads exactly like more hits before it.

**Method:** rag by behaviour (`uvx vaultspec-rag search "isolate CLI runtime storage and neutralize ambient auth provider configuration for a test only:tests" --type code`) surfaced the first outstanding site by meaning, not name. Grepped the snippet body (`cadrumo_clave_movil_dni_nie=None`, the least generic field in the auth-nulling block) across `src/cadrumo` — 10 files matched; 4 were false positives (single-field ad hoc overrides in `application/auth/tests/*` and `application/tests/test_preflight.py`, unrelated to the composed cluster — verified by reading each, not by the grep alone). Then read every remaining owning module in full before classifying.

**Two distinct concepts share the `_isolated_backend` NAME; only one is this cluster's actual subject:**

- **Concept A — "isolate storage, auto-seed a profile" (no auth nulling).** Already CONVERGED, deliberately, as a parameterized factory: `active_profile_isolated_backend_fixture` (`src/cadrumo/tests/active_profile_isolated_backend_fixture.py:27`) returns a fixture closure over `bucket_id` / `autouse` / `name` / `dispose_engine_around` / `settings_overrides` / `profile_overrides` / `display_name`. Its own docstring states it already replaced several independently-written sites, naming the exact per-site axes that varied. Consumers: `_ledger_seeded_profile_fixture.py`, most of `_isolated_profile_storage_fixtures.py`, `_profile_backend_fixtures.py` (module-level `_isolated_backend = active_profile_isolated_backend_fixture(profile_overrides={...})` plus `__all__` re-export), `test_custody_restore_atomicity.py` (a sibling factory, `bucket_scoped_runtime_profile_fixture`, called the same way), and ~20 direct importers — all calling the SAME factory with different kwargs. **CONVERGED, not duplication** — a factory called many times with different arguments, each binding the name the factory itself defaults to, is the intended single-home shape and is name-keyed-count-invariant by design, not the pattern this campaign hunts. A sibling factory, `isolated_profile_storage_fixture` (`src/cadrumo/tests/profile_storage_root_fixture.py`), covers the same shape for the "empty storage root, no profile" variant and is consumed the same way (e.g. `_modelo_empty_profile_fixture.py`). Also CONVERGED.
- **Concept B — "isolate storage, null ambient auth-provider configuration" (the actual subject of this reconciliation).** This is the concept `test_workflow_surface.py::_isolated_user_cli` belongs to (`W09.P30.S132`), and where the true outstanding duplication lives.

**Concept B sites, individually read and classified:**

1. **`isolated_cli_surface_backend`** — `src/cadrumo/entrypoints/cli/tests/_cli_surface_support.py:16`. The base composition: `isolated_profile_storage_root(tmp_path)` + `override_settings(cadrumo_auth_provider=None, cadrumo_certificate_path=None, cadrumo_certificate_password_secret=None, cadrumo_clave_movil_dni_nie=None, cadrumo_clave_movil_dni_fecha=None, cadrumo_clave_movil_nie_soporte=None)`. **CANONICAL** for Concept B.
2. **`_cli_surface_profile_fixture.py::_isolated_backend`** — wraps #1 + `create_cli_surface_profile()` (the credential-first `register_cli_profile` door). **CONVERGED**, calls #1 directly. Only **2** direct importers (`grep -rl "from \._cli_surface_profile_fixture import"` — not 37; see the mechanism correction above for why the raw name-count read so much higher).
3. **`_strict_cli_fixture_support.py::cli_surface_isolated_backend`** — thin wrapper delegating to #1 (`with isolated_cli_surface_backend(tmp_path): yield`). **CONVERGED**, calls #1 directly. (This same file's `diagnostics_isolated_backend` / `binding_isolated_backend` / `inventory_isolated_backend` are Concept A shapes composed inline rather than via the Concept A factory — noted below, OUTSTANDING but low-priority.)
4. **`test_ledger_lucia_persona_feedback.py::_isolated_backend`** (line 20) — body is byte-identical to #1 minus nothing (same six fields, same order). **TRUE-MIRROR.** Should import #1 instead of re-declaring. Canonical candidate: #1.
5. **`test_cli_workflow_verification.py::_isolated_cli_backend`** (line 54, local name collides with the separately-imported canonical `isolated_cli_backend` — worth a rename on its own, not a duplication issue) — same six-field shape but `cadrumo_certificate_path=tmp_path / "certificate.p12"` instead of `None`, load-bearing: the test's own comment explains the round-trip helper writes its synthetic certificate to that exact path and the health-summary assertion depends on the override naming the same file. **JUSTIFIED-DIVERGENCE.**
6. **`test_workflow_surface.py::_isolated_user_cli`** (`W09.P30.S132`, this session) — composes `isolated_profile_storage_root` + the same six-field auth-null block **plus** `cadrumo_allow_unencrypted=""`, and does NOT auto-seed a profile (this file's tests each seed their own facts via a local `_seed_profile` helper, or invoke the wizard-create flow directly — see `W09.P30.S139`). **Borderline, recording honestly:** close enough to #1 that it could converge onto `isolated_cli_surface_backend` plus a separate one-line `cadrumo_allow_unencrypted` override, but the no-auto-seed contract is real and distinguishes it from every Concept-B-with-seeding sibling. Left as its own composition in `W09.P30.S132` because that step's authorized scope was the storage-path drift, not a second consolidation pass; flagging here as **OUTSTANDING** for a follow-up decision rather than converging unilaterally.
7. **`test_manager_screen.py`** (TUI, `adapters/inbound/tui/tests/test_manager_screen.py:464`) — inline block inside one test function, NOT a reusable fixture: `isolated_profile_storage_root` + `override_settings(cadrumo_output_language="en", cadrumo_clave_prefer_non_qr=False, cadrumo_clave_movil_dni_nie=None, cadrumo_clave_movil_nie_soporte=None, cadrumo_clave_movil_dni_fecha=None, cadrumo_clave_permanente_dni_nie=None)`. Different field set (no `cadrumo_auth_provider`/`cadrumo_certificate_*`, adds `cadrumo_clave_permanente_dni_nie` and locale/QR fields), different domain (TUI manager-screen auth-choice action, not a CLI invocation). **JUSTIFIED-DIVERGENCE.**
8. **`_isolated_storage_fixture.py::config_check_backend`** (`entrypoints/cli/_config/tests/_isolated_storage_fixture.py:13`) — related but narrower: storage + locale only, no auth-nulling at all. **Correctness note, not a duplication finding:** its `override_settings(cadrumo_local_storage_root=tmp_path / "storage", cadrumo_output_language="en")` is entered BEFORE `isolated_profile_storage_root(tmp_path=tmp_path)` in the same `with` tuple; `isolated_profile_storage_root` also sets `cadrumo_local_storage_root` (to `tmp_path / "cadrumo-storage"`) and is entered second, so per `override_settings`'s own merge-over-`load_settings()` semantics (`core/config.py:1517-1533`) the inner call's value wins and the outer `cadrumo_local_storage_root=tmp_path / "storage"` is dead on arrival — harmless today (the effective root is still correct, just via the OTHER override), but exactly the "fixture that only round-trips its own value" shape S133 warns about: if the tuple order were ever reversed, this would silently start pointing `config check` tests at the wrong root. Recommend deleting the dead `cadrumo_local_storage_root=tmp_path / "storage"` clause; keep `cadrumo_output_language="en"`.

**Also OUTSTANDING, lower priority:** `_isolated_profile_storage_fixtures.py::llm_profile_isolated_backend` and `::live_fx_isolated_backend` (`entrypoints/cli/tests/_isolated_profile_storage_fixtures.py:28,39`) compose `isolated_profile_storage_root` + `register_minimal_profile` inline — the Concept A shape — rather than calling the canonical `active_profile_isolated_backend_fixture()` factory the rest of that same file already imports and uses two lines above them. Not read in full detail (parameter-level diff against the factory not verified); flagging for whoever picks up Concept A convergence to check factory-substitutability before merging.

**Reconciled count for Concept B (the actual cluster):** 1 canonical (#1) + 2 already-converged wrappers (#2, #3) + 1 true mirror to fix (#4) + 2 justified divergences (#5, #7) + 1 borderline/outstanding (#6) + 1 correctness-adjacent dead-code note (#8, different sub-concept). **Not 37 — 8 sites total, of which exactly one (#4) is a plain duplicate worth a one-line fix (replace its body with an import of #1).** The 37 figure was never wrong because it missed sites; it was wrong because a name shared by design across a converged factory's call sites is not a debt signal, in either direction.

### helper_body_census reconciliation | census-reconciliation | `W09.P30.S141` — 309 groups became 225; delegating wrappers were being reported as duplication, and the `_invoke` cluster was ruled real-but-unswept debt

**This entry supersedes the 309-group figure this record's own worklist cited earlier in the session — conclusion narrows, mechanism corrected below, same discipline as the `isolated_backend_family` 37-vs-8 correction above.** `dev/quality/helper_body_census.py`'s S125/S141 first pass reported 309-310 aliased-behaviour groups. A body whose SOLE executable statement is a `return`/bare-expression wrapping exactly one `Call` to a plain name resolved through an import (`_delegating_wrapper_target`) is not a second implementation of anything — it already routes through the one shared callee — so counting it as duplication reports the solution as the problem. Excluding every record matching that shape (1,672 of 7,990 total helper records, roughly 27% of the reported backlog) drops the figure to **225 groups**.

**Concrete case that forced the correction:** `_write_modelo` / `_load_revision` in `src/cadrumo/domain/calculations/registry/tests/` (`test_governance_stamp.py`, `test_revision_authority_grade.py`, `test_revision_manifest_only_placement.py`, `test_schema_family_coverage.py`) were reported CONSTANT-DEPENDENT duplication — closing over `_CASILLA_FRAGMENT` / `_REVISION_ID` — until this correction. Each is in fact a per-file wrapper forwarding its own closed-over constant into ONE call on the canonical `_loader_directory_mode_support.py::_write_modelo` / `::_load_revision`. The constant-dependence label was correct (the shape genuinely closes over a per-file constant); the duplication verdict under it was not.

**Method:** reused the same `_module_symbol_origins` resolution the constant-dependence detector already computes, rather than a second import-resolution pass — one shared axis, not a parallel mechanism. Classification is per-RECORD, not per-group, and deliberately conservative: a call reached through attribute access (`_RUNNER.invoke(...)`) or an unresolved callee stays in the duplicate bucket rather than being guessed at, matching the same no-guessing discipline the constant-dependence detector already commits to. Proven both ways by two new synthetic tests: a delegating wrapper closing over a constant is excluded from the count; a body that CONSTRUCTS rather than forwards (still closing over a constant) stays counted and stays labelled CONSTANT-DEPENDENT.

**Operator ruling on `_invoke` (51 sites, `src/cadrumo/entrypoints/cli/tests/`) — recorded, not swept.** Structurally a delegating wrapper (`return invoke_cached_cli(args)`, some with `env=` forwarded), so it is now correctly excluded from the 225 figure same as `_write_modelo`. Unlike `_write_modelo`, though, most sites inject no per-file argument the canonical `cadrumo.tests.cli_runner.invoke_cached_cli` lacks — a pure signature-preserving local rename, not composition adding value. Read as real but low-value debt, and deliberately left unswept. The standing principle, stated for reuse: **duplication matters when it can diverge.** A copy that can be fixed in one place and silently survive unfixed in another is the failure this census exists to catch; a delegating wrapper cannot do that, since every site already routes through the one canonical callee and a fix there reaches all of them. Against that: a 51-file sweep on a tree three teams are actively committing to trades real collision risk for a purely cosmetic gain. If this pattern is worth preventing going forward, the correct tool is a lint rule blocking NEW value-free wrappers over an already-canonical callee, not a retrospective sweep of the existing ones — not attempted here.

**Verification:** `uv run --no-sync ruff check dev/quality/helper_body_census.py dev/quality/tests/test_helper_body_census.py` clean. `uv run --no-sync pytest dev/quality/tests/test_helper_body_census.py -p no:randomly -q` — 16/16 passed (13 pre-existing plus 3 new: delegating-wrapper-excluded, real-work-still-counted, attribute-access-not-guessed), the S125 canonical-home regression pin still green with its allowlist still empty. Live-tree figures: `helper_count=7990`, `delegating_wrapper_count=1672`, `aliased_behaviour_count=225` (down from 309-310), reproducible via `python -m dev.quality.helper_body_census --json`.

## Recommendations

- ~~Land plan step `W09.P30.S131` (rename `declared_manual_inputs` to something in the `oracle_declared_figures` family) before the next agent reads the name cold — the collision is confirmed real, not speculative.~~ **CLOSED.** The rename landed and went further than recommended: `declared_manual_inputs` returns zero hits across the registry tests tree, and `oracle_declared_figures` is defined in `_manual_oracle_support.py` and adopted by **9** test files, not the 3 the original recommendation named.
- Assign an owner to close the `declared_live_write` / `dev/agent_eval/tests/test_confirmation_gate_golden.py` gap: either an accepted cross-tree import exception or a relocated shared home reachable from both `dev/` and `src/cadrumo/`. Do not let it stand as a silent "already consolidated" assumption — this record is the evidence it is not.
- Re-run the `application/calculations/tests/` and `domain/calculations/registry/tests/` failure-set diffs one more time from a fully quiesced tree (no concurrent peer writes) before this wave is declared closeable, given how many peer batches are landing on the same shared worktree concurrently with this record's own verification runs.
- Treat the consumer-count corrections above (`_repo_at`/`_ephemeral_secure_repo`: 10 not 8; `serve_directory`: 7 not 5; `_match`/`_oracle_rules`: 11 not 7) as the census superseding the original assignment tallies, not as errors in either — the assignment counts likely predate later call sites landing on the same shared clusters.
- The 9/5/4 non-consolidation tallies (AEAT write-refusal guards, standalone gate files, extractor tamper tests) need a dedicated enumeration pass by whoever owns that part of the campaign; this record establishes the pattern is real and load-bearing but does not certify the counts.

### `_period` / `_p` | census | CLOSED — 3 aggregation sites converged, 1 documented delegating wrapper, 1 deliberate non-consolidation

The census reported a `_period` alias recurring across `application/aggregation/tests/` and `application/workflow/tests/`. Every body was the same one-line delegation to the public canonical constructor `Period.from_year_and_code(year, code)`, so the cluster is real but the correct remedy differs by side.

**Aggregation (closed):** `_renta_income_aggregation_support.py:19` is the canonical home; `test_renta_ledger_aggregation.py` and `test_renta_ledger_helpers.py` now import it. `test_aggregation_period_for_modelo.py:64` keeps a local `_period(code, *, year=2025)` that delegates to the canonical builder under an explicit docstring reason — the argument ORDER is the payload there (that module is code-first throughout), so collapsing it would rewrite every call site to gain nothing. Recorded as a sanctioned delegating wrapper, consistent with the `helper_body_census` delegating-wrapper ruling above.

**Workflow (closed, and NOT by the route originally approved):** the pre-approved scope was a new `application/workflow/tests/` support module with `test_resume.py` canonical and `test_models.py` keeping its defaults in a thin wrapper. Reading both files whole changed the answer, and no support module was created:

- `test_resume.py` already called `Period.from_year_and_code(...)` DIRECTLY at five sites (529, 545, 561, 576, 596) while routing eight others through its own `_period` alias — the alias earned nothing even inside its own file. The alias is deleted and all eight sites inlined; the file is now internally consistent on one spelling.
- `test_models.py:61` `_period(year=2026, code="1T")` is **deliberately left alone**. Its DEFAULTS are the payload — nine of its ten call sites are the bare `_period()` — so it is a defaulted local factory, not a copy of a helper that exists elsewhere. It shares only a name with the deleted alias, which is the `isolated_backend_family` name-collision shape this record already documents at length.

**The standing principle this reinforces:** a one-line alias over an *already public canonical constructor* does not need a shared home — it needs deleting. Inventing a support module to host an alias of `Period.from_year_and_code` would have added an indirection layer carrying zero behaviour, which is the same reporting-the-solution-as-the-problem error the delegating-wrapper correction fixed in the census itself.

**Verification:** `uv run --no-sync ruff check src/cadrumo/application/workflow/tests/test_resume.py` clean; no `_period` reference survives in that file. `src/cadrumo/application/workflow/tests/test_resume.py` currently reports 22 setup ERRORs, **all pre-existing and unrelated** — they raise `ProfileCustodyRecordError: profile capsule destination already exists` inside the autouse `_patch_secure_backend` fixture (line 117), which executes before any test body and therefore cannot reach `_period` at all. Cause is recorded separately below.

### custody inventory regression | live-defect | an uncommitted peer edit makes the Windows capsule inventory under-report committed capsules

Surfaced while verifying the `_period` change; **not caused by it, and deliberately not fixed here** — the owning file is another agent's in-flight uncommitted work.

`src/cadrumo/adapters/persistence/storage/custody/_inventory.py:189` (uncommitted) swaps `path.iterdir()` for `iter_directory(path, require_root=True)` inside `_inventory_windows_directory`. Downstream, `seed_test_profile_record` (`src/cadrumo/tests/profile_capsule.py:283`) guards capsule creation on `if identity not in list_current_profile_custody_capsule_ids(...)`. With the new walk the listing no longer reports a capsule that `isolated_runtime_profile` has already published, so the guard passes, a second create is attempted, and the directory rename fails closed with `profile capsule destination already exists` (`custody/_filesystem.py:1227`).

**Why this matters beyond a red test:** the failing surface is the inventory of committed profile custody capsules — the listing that tells a writer what already exists. An inventory that under-reports is the precondition for a create path clobbering real encrypted data; here it fails closed, which is the correct direction, but the underlying disagreement between "what the inventory lists" and "what the destination path resolves to" is the defect, not the refusal.

**Blast radius observed:** `src/cadrumo/adapters/persistence/storage/tests` is broadly red (33 failed / 238 passed), including `test_storage_path_directory_agreement_gate.py` and `test_schema_lineage.py`. Sibling workflow files that use `isolated_runtime_profile` WITHOUT nesting `seed_test_profile_record` inside it (`test_run_persistence_roundtrip.py`, `test_per_bucket_engine_isolation.py`) pass — 14/14 — which localises the fault to the listing-versus-destination disagreement rather than to `isolated_runtime_profile` generally.

**Action:** owner of the `_inventory.py` change to confirm `iter_directory(..., require_root=True)` reproduces `path.iterdir()` semantics under the anchored-handle walk before landing it, and to add a regression pinning that a capsule published by `isolated_runtime_profile` is visible to `list_current_profile_custody_capsule_ids` in the same process.

### W09 close-phase honesty review | close-gate | independent read-only re-derivation, no regressions, two corrections landed

Run as an independent fresh-context pass against the live tree, briefed to believe none of the wave's checked claims and to treat every checked step as a claim to verify. Read-only; it fixed nothing.

**The check that mattered most — safety non-consolidations — came back clean.** The deliberately-unmerged duplications are all still standing as independent code: the AEAT live-write refusal guards (`test_gate.py`, `test_clave_permanente_live.py`, `test_errors.py`, `test_no_write_surface.py`, `test_read_landing_guard.py` — five distinct files across the auth, export and sede adapter modules, each still asserting independently, no shared helper introduced), and `_seed_corpus` (still three independently-signed functions — `test_bundle.py:41` and `test_manifest.py:44` returning `dict[str, bytes]`, `test_bundle_signing.py:68` returning `None`; genuinely different contracts, not merged). No REGRESSION, no STALE, no HALF-DONE. `S145` is correctly left unchecked with no false-complete claim.

**Independently re-derived counts, all matching:** observation-lookup 13, `scoped_attribute` 10, convenio rate 12, `serve_directory` 7, isolated-backend family 8 (not 37), `_seed_corpus` 3 signatures, AEAT guard files 5.

**Two corrections landed from this review:**

1. `W09.P29.S114`'s step PROSE said "the eight convenio rate resolvers" while the real figure — recorded correctly in this census and re-derived live — is twelve. A wording drift in the Step text, not a work defect. The step action has been corrected to "twelve" so the plan and the census agree.
2. The `aliased_behaviour_count` recorded above as **225** now reads **224** live. Re-run independently and confirmed: `helper_count=7987` (was 7990), `delegating_wrapper_count=1676` (was 1672), `aliased_behaviour_count=224` (was 225). This is concurrent-worktree drift from peer commits landing between the census write and the re-run, not an error in either figure — the census's own notes flag this tree as heavily contended. **The 309 → 225 correction is confirmed real and live; only its last digit has moved since.** Treat 225 as "as-of the census write" rather than a standing invariant, and re-derive before quoting.

**Explicitly still unverified, carried forward rather than assumed:** the exact tallies "9 AEAT live-write refusal guards" and "4 extractor tamper tests" were not exhaustively enumerated by this review either — the review confirmed the qualitative safety property (all separate, none merged) but not the precise counts, which is the same limitation this record already declares for those two figures. The historical "66 modelo-131 clone tests" figure likewise remains unconfirmed from git history; the `@pytest.mark.parametrize` decorators over `_FASE_1_CASES` and `_FASE_4_CASES` are confirmed present, the pre-consolidation count is not.

### no-monkeypatch gate | REGRESSION FOUND AND FIXED | the wave declared a gate clean against a state that no longer held

**This is the finding the close-phase honesty review exists to produce, and it was missed by a second, count-focused reviewer run in parallel — recorded here because the contrast is the lesson.**

`src/cadrumo/tests/test_monkeypatch_inventory.py::test_no_monkeypatch_fixture_or_context_usage` was FAILING on the live tree, contradicting the plan's own Verification bullet ("The no-monkeypatch inventory and its discriminating controls pass with no allowlist, suppression, or renamed equivalent") and the checked status of `S79` (restore the gate to green) and `S89` (run it and confirm).

**Violation:** `src/cadrumo/domain/calculations/registry/tests/test_read_parameter_authority_invalidation.py` used the pytest `monkeypatch` fixture — `monkeypatch.setattr(core_resources, "bundled_path", _redirected)` at line 138, plus the `monkeypatch: pytest.MonkeyPatch` fixture parameter at line 115 — inside a real fixture in a deterministic production test file.

**Not live churn, and that was checked before acting.** The file was committed clean on 2026-08-14 (`6d80634e6b`, an unrelated registry-campaign commit bounding `read_parameter`'s authority on the tree fingerprint) with zero uncommitted changes. The gate went red when that commit landed, AFTER `W07.P23` last verified it green, and nothing re-ran it in between. **A wave declared a gate clean on the strength of a past run, and the tree moved underneath the claim.**

**Fix:** the fixture now uses the campaign's own canonical `cadrumo.tests.attribute_scope.scoped_attribute` context manager — the helper created earlier in this very campaign for exactly this case, already carrying 10-11 consumers. The fixture wraps its `yield` in `with scoped_attribute(core_resources, "bundled_path", _redirected):` and drops the `monkeypatch` parameter entirely. This is a vocabulary change, not a behaviour change: a save/restore performs the identical mutation `monkeypatch.setattr` would, so the test still exercises the real default-root branch with the real loader, authority and verdict store, exactly as its module docstring promises. **No allowlist, no suppression, no renamed equivalent** — the mechanism the gate bans is gone, not hidden from the matcher.

**Verification, with the revert-to-red proof obtained for free:** the gate was RED (1 failed / 8 passed) before the edit and is GREEN (9 passed) after, on the same sequential `-n0` invocation — so the gate is proven to bite on exactly this violation without needing a deliberate breakage window. The subject file's own three tests pass (3 passed), and `ruff check` is clean on it.

**Standing lesson for the campaign:** a checked gate step records that the gate passed *once*. On a worktree three teams commit to concurrently, that is a perishable claim. The close-phase honesty review must RE-RUN the gates a wave claims green, not re-read the checkmarks — a reviewer that verifies counts and file existence will confirm every structural claim in this record and still miss a red gate entirely, which is precisely what happened here.

### find_observation | census | 13 sites, one canonical owner

`W09.P29.S112` landed in `c7b3206ecc`: the thirteen application-calculation
test consumers route through `_observation_lookup_support.find_observation`,
whose narrow return annotation replaces the unannotated local lookup bodies.
Commit `0c0b3079745` later moved the M036 caller onto that same owner rather
than creating a sibling helper. Current-tree inspection still finds thirteen
consumers and no substitutable local implementation.

### ephemeral_secure_repo | census | postdated S119 delivery reconciled

The earlier per-step pass correctly reported that its 2026-08-15 snapshot
could not locate the ephemeral-repository clause of `W09.P29.S119`. That gap
was subsequently delivered in `e8475e8289d` on 2026-08-25:
`_ephemeral_secure_repo` and `_ephemeral_secure_repo_at` became the shared
definitions, the write-batching and part-two local bodies were deleted, and
the mutation-sensitive canonical-home test proves direct consumers and one
shared definition. This census entry supersedes only the historical
"no locatable evidence" observation; it does not rewrite the as-of record.

### W09 per-step evidence map | close-gate | the formal carry-forward record, and two steps returned to open

The governing constraint is that no plan step is marked complete without a matching execution record **or a close audit recording the deferred carry-forward** — otherwise delivered-as-specified, delivered-narrower and recorded-but-not-implemented all wear the same checkbox. `.vault/exec/2026-08-14-test-harness-sanity/` covers `S47`-`S98` (waves W06-W08) and holds **nothing** for `S111`-`S145`. W09's Phase description asserts this census substitutes for per-step records. **This section is what makes that substitution legitimate where it is, and refuses it where it is not.**

Every checked step S111-S144 was classified by an independent read-only pass as COVERED (a named census section addresses it), TREE-EVIDENT (no prose section, but the claim is directly verifiable in the tree now, with a locator) or EVIDENCE-THIN (neither).

**Result: COVERED 18, TREE-EVIDENT 9, EVIDENCE-THIN 7.** The 27 COVERED and TREE-EVIDENT steps are hereby recorded as carried forward under this audit in lieu of individual exec records, each with a locator in the map. The 7 thin ones are dealt with individually below — not waved through.

**Two steps have been RETURNED TO OPEN (unchecked), because their claims do not hold:**

- **`S138`** (re-run the registry-tests failure-set diff from a quiesced tree) — this record's own Recommendations section still *asks* for that re-run "before this wave is declared closeable". The ask being open is evidence the step is open. It also cannot be satisfied right now: the tree is actively torn by peers mid-relocation (`cadrumo.agent`, `_app_agent_workspace_payloads`, `_lazy_command_tree`, `_run_loopback_server`), measured at 67 collection errors falling to 4 across two runs an hour apart. A step whose precondition is a quiesced tree cannot be complete while the tree is demonstrably not quiesced.
- **`S137`** (sweep key providers and encrypted sessions for guaranteed teardown) — no locatable record mentions key providers or encrypted sessions at all. A direct probe found **15 `EphemeralMasterKeyProvider` constructions assigned to a name that is never context-managed anywhere in its file** (against 30 that are), across `application/auth`, `storage/tests`, `storage/sql/tests`, `master_key`, `envelope`, `blob_store`. Some are likely passed into a helper that manages them (`_rotation_key_fixtures.py` forwards `old_key=`/`new_key=`), so this is an adjudication list rather than 15 confirmed leaks — but that adjudication is exactly the sweep the step claims to have done. The step text now carries the count so the next owner starts from evidence.

**One step's TEXT was factually wrong and has been corrected:** `S115` said "the five secure-object repository builders". The tree carries **two** canonical builders plus a third justified-divergence construction, as this record's own `_repo_at + _ephemeral_secure_repo` entry documents. Not a work defect — a numeric claim in the step that contradicted the census sitting beside it.

**Remaining EVIDENCE-THIN steps, left checked with the gap stated rather than silently accepted:**

- `S111` (union-find partition into file-disjoint batches) and `S121` (score name-grouped clusters by structural similarity over normalised AST node sequences) and `S122` (adjudicate every drifted cluster above the threshold) — **the work was really done, but only in ephemeral scratchpad tooling, so no persisted artefact traces back to the step.** The similarity mechanism was a Jaccard comparison over normalised AST node-type sequences with names, constants and argument names erased, splitting clusters at a median-similarity threshold of 0.75 into genuine drift versus name collision. Its adjudicated outputs are visible in this record's downstream entries (the `isolated_backend_family` 37→8 reconciliation and the modelo-131 clone triage are both products of it), but the mechanism itself was never persisted. Recorded here so the reasoning survives the scratchpad. **The shipped gate `dev/quality/helper_body_census.py` does exact-hash grouping, not graded similarity** — anyone expecting to find the similarity scorer in the repository will not, and that is the honest state.
- `S119` — three of its four named helper classes are covered (`sha256_path`, `declared_live_write`, `write_concept_fragment`). The **ephemeral-repository clause has no locatable evidence** in either the census or the tree.
- `S115` — see the correction above.

**Method note:** this map was produced by an independent agent that had not done the work, briefed to disbelieve the checkmarks, and it contradicted a prior reviewer on `S138` — which had previously been reasoned closed on causation (an identified unrelated cause plus a zero import path) rather than on a clean diff. **The re-run was the specified evidence and reasoning was substituted for it.** That substitution is the exact failure the carry-forward rule names, and it was caught only because a second reviewer was asked for locators instead of conclusions.

### `S145` regime normalisation | determination | the step's own premise was false, and the answer is still useful

`W09.P30.S145` asked whether any current door can still write an unnormalised `iva.regime` value, "since the retired wizard may have been the only path that exercised read-time normalisation".

**PREMISE FALSE.** The wizard is not retired. `src/cadrumo/application/wizard/` carries 16 live non-test modules (`_catalogue.py`, `_commands.py`, `_persistence.py`, `_status.py` and siblings), all actively referencing `iva.regime` / `IVARegime`, and `apply_wizard_fact_changes` / `persist_answers` / `persist_patch` in `application/wizard/_persistence.py` are a live write path today. **A step premised on a retirement that did not happen would have produced a confident wrong answer if the premise had been taken on trust.**

**NORMALISER:** `src/cadrumo/domain/deadlines/_profiles.py:174-175`, inside `_canonicalize_and_pad`, reached from `taxpayer_profile_from_mapping` and so from every `TaxpayerProfile` projection including `application/user_profile/_projections.py:280`. It strips, uppercases and maps `-` to `_`.

**WRITE DOORS — enumerated, not sampled:**

| Door | Pre-persist posture |
|---|---|
| Wizard interactive SELECT (`application/wizard/_widgets.py:validate_select`) | typed — exact-case membership against the uppercase `IVARegime` tokens |
| `--iva-regime` CLI flag (`application/wizard/_commands.py:339-344`) | typed — `click.Choice(case_sensitive=False)` returns the canonically-cased declared choice, so `general` arrives as `GENERAL` |
| `aeat config profile set` (`entrypoints/cli/_config/_manager_frontend.py`) | not normalised, but gated — routes through `reject_invalid_profile_facts` → `domain/user_profile/_schema.py:enum_value_refusal`, exact-case only against `schema.toml:1154` |
| Registration initial record (`application/user_profile/_registration.py:184`) | typed — same refusal gate before persist |
| Cotejo censal adoption (`application/user_profile/_cotejo_apply.py`) | does not write `iva.regime` at all, and is gated regardless |
| First-run workspace init (`application/setup/_contracts.py`) | normalises explicitly, then coerces to the `IVARegime` enum via `Annotated[..., BeforeValidator(...)]` |
| Test seeding (`seed_test_profile_record`) | bypasses the judge, but is not a production door and every fixture found writes canonical tokens |

**VERDICT: DEAD DEFENSIVE CODE.** No enumerated live production door can persist an unnormalised `iva.regime`: each either normalises explicitly before persisting or is refused outright by an exact-case enum gate rather than storing a raw token.

**Do NOT delete the normaliser on the strength of this verdict, and this is the load-bearing caveat.** `ProfileRecordRepository.apply_fact_changes` does **not** self-enforce validation — the refusal gate is *caller discipline*, and the determination rests on all in-tree callers currently honouring it (two direct production callers found: `_cotejo_apply.py` and `wizard/_persistence.py`, both gated, plus registration's separate validated create-path). The normaliser is therefore the last backstop behind a discipline convention, not behind a structural guarantee. **The correct follow-up is to make `apply_fact_changes` enforce the enum itself, at which point the normaliser becomes genuinely removable.** Deleting the backstop first would convert a convention into a silent data-integrity risk — and `iva.regime` selects the IVA regime a filing is computed under.

**EVIDENCE GAPS, carried forward:** no empirical check of on-disk records written before the enum gate existed (the no-legacy posture argues none should exist, but that was not verified against real storage), and no check for out-of-tree tooling calling `apply_fact_changes` directly. The determination is a static code reading, which is what the step asked for, and it did not require the test suite — so the torn tree did not affect it.

### two half-landed relocations | live-defect FIXED | both were committed broken on main, not in-flight edits

Found while testing whether the tree had quiesced enough to satisfy `S138`. Tree-wide collection was failing, and the first instinct — "peers are mid-edit, wait" — was **wrong on inspection**: `git status` showed both owning files committed and clean, and their mtimes were 100 minutes and 3 hours old. Nobody was editing them. They were abandoned broken. **A torn tree is not self-evidently someone's live work; check before deferring to it.**

Both are the same defect class — a relocation that moved a symbol and updated some consumers but not all, against the standing requirement that a relocation lands in ONE commit with every consumer.

**1. Telemetry loopback plumbing.** `run_loopback_server` / `stop_loopback_server` had correctly moved to their canonical home `src/cadrumo/tests/loopback_recording_server.py`, and `core/telemetry/tests/test_http_sink.py` plus `application/tests/test_diagnostics_telemetry.py` were migrated. `core/telemetry/tests/test_producers.py` was left importing the OLD private names from `test_http_sink` — a test module reaching into a sibling test module's privates, which is what made the breakage possible at all.

Fixed by pointing `test_producers.py` at the canonical home. That exposed the real coupling: it called `_run_loopback_server()` with no argument, because the old private wrapper defaulted to `test_http_sink`'s own handler class, while the canonical takes the handler explicitly. **The handler could not simply be imported across, because that would reinstate the exact test-module-to-test-module import that broke.** Checked whether the shipped design allows a shared handler: `loopback_recording_server.py`'s docstring deliberately declines to own handler classes because "the recorded event shape genuinely differs between suites" — and that claim is **true**, verified by reading all four: the two diagnostics suites record `{path, body}`, while both suites in the telemetry package assert on `content_type` and record `{path, content_type, body}`.

So the two suites that share a shape got one definition, in a package-local home: **`src/cadrumo/core/telemetry/tests/_telemetry_endpoint_support.py::RecordingTelemetryEndpoint`**, imported by both. No fourth copy of the handler, no cross-suite private import, and the shipped module's per-suite-handler rationale left intact because it is correct for the suites it describes. Verified: `ruff` clean, `core/telemetry/tests` 42 passed.

**2. `_json_object` in the LLM-vision evidence support.** `src/cadrumo/application/ledger/tests/_llm_vision_evidence_support.py` had `_json_object` deleted while keeping its sibling `_json_array`, breaking `llm/tests/test_llm_vision_classifier.py` and `llm/tests/test_evidence_draft_vision.py`, which both import it. **Confirmed committed, not in-flight:** `git status` clean on all three, and HEAD's consumer already imports a name HEAD's support module already does not define — so the broken pair is what landed.

Restored beside `_json_array`, implemented to match the canonical `entrypoints/cli/tests/_cli_json_support.py::_json_object` exactly — `STR_KEYED_MAPPING_ADAPTER.validate_python(value)`, the core type-narrowing primitive — rather than the looser `assert isinstance` shape `_json_array` uses, so the two `_json_object` definitions in the tree cannot diverge in behaviour. **Deliberately NOT consolidated onto the canonical:** `cadrumo.llm.tests` importing `cadrumo.entrypoints.cli.tests._cli_json_support` would be a cross-package private reach, which the architecture boundary forbids. The pre-existing cross-package import from `llm/tests` into `application/ledger/tests` is left as found — not this change's to fix, and noted here so it is not mistaken for something this change introduced.

**`S138` remains blocked, and the reason is now measured rather than asserted.** Collection errors across four runs this session: 67 → 4 → 3 → (after these two fixes) 7. The rise at the end is not a regression from these fixes — both symbols cleared the error list — but a peer landing an in-flight relocation of `cadrumo.entrypoints.mcp`, which took out seven suites across `command_search`, `modelo`, `operator_surface` and `cli`. The tree has not been collectable once this session. **`S138` asks for a failure-set diff from a quiesced tree, and there has been no quiesced tree to take one from.**

### `S137` key-provider and session teardown | proven-negative | 15 suspects, zero leaks, and the sweep deliberately stops short of a 30-site hygiene churn

This step had been marked complete with no locatable evidence, was returned to open, and has now been done properly. **The result is a clean negative, which is a real result and is recorded as one rather than being padded into a fix.**

**The whole verdict rests on one fact, so it was verified directly rather than taken from the report:** in `src/cadrumo/tests/master_key.py`, `EphemeralMasterKeyProvider.get_master_key()` returns `self._key` and touches nothing else, while `__enter__` is the SOLE place a `BucketSession` is opened (`BucketSession.open` + `activate_session`). A provider that is constructed but never entered therefore opens no session, registers nothing, and holds no OS handle: **there is nothing to tear down.** `__init__` only mints bytes.

**All 15 suspects adjudicated:**

- **HELPER-MANAGED (5):** `test_secure_objects_part1.py:608,723,772` and `test_secure_objects_part2.py:317,343` all forward into `sql/tests/_secure_objects_support.py::_seed_under_key`, which does `with provider: ... finally: engine.dispose()`. My original probe could not see these because it was a regex over the same file only — exactly the limitation it was flagged with.
- **SELF-CLOSING (10):** every remaining site's provider reaches only `.get_master_key()`, directly or through `EncryptedBlobStore` / `SecretStore` / `rotate_blob_stores` / `save_encrypted_envelope` / `load_encrypted_envelope` — each confirmed to call `.get_master_key()` directly and never the ContextVar-based `get_active_master_key()`.

**Widened beyond the probe's scope**, since the step also names encrypted sessions: `FileFallbackMasterKeyProvider`, `UnsecuredMasterKeyProvider` and `KeyringMasterKeyProvider` share the identical `__enter__`-only-opens-a-session shape, and ~28 further bare constructions across `master_key/tests/` are all `.get_master_key()`-only. No new leaks.

**`ProfileRecordSession` is NOT this resource class, and the ~20 test files that never close one are DELIBERATELY left alone.** It is a plain `@dataclass(slots=True)` with no `__enter__`/`__exit__`, no live-session registration, no SQL engine, no lock and no ContextVar binding; `.close()` only zeroises its own `bytearray` DEK in place. **The question worth asking was about production, not tests, and production is clean:** all four construction sites are accounted for — `_registration.py:179` closes at `:206`, `_login_session.py:1101` closes at `:1103`, `_login_session.py:753` and `_profile_record_repository.py:141` both hand the session straight to `activate_profile_record_session`, whose owner `close_active_profile_record_session` zeroises it. Every path either closes in a `finally` or transfers ownership to the activator.

So the test-side gap is a best-effort memory-hygiene nicety over test key material, with no OS handle, no registered global outliving the test, and a GC-reclaimed buffer. **Adding `.close()` to ~30 call sites would be churn on a tree three teams are committing to, in exchange for nothing observable.** Recorded as a deliberate non-fix. The principle generalises the census's own "duplication matters when it can diverge": **a leak matters when it can outlive the test.** One that cannot is a style preference, and this campaign does not spend collision risk on style.

**Verification:** the 9 affected files run sequentially give 154 passed, 1 failed — `test_materialisation.py::test_get_secret_store_writes_a_real_blob_at_the_declared_taxonomy_path`, failing inside `open_test_profile_session` on `UUID("materialisation-wiring-test")` with `ValueError: badly formed hexadecimal UUID string`. That fails before any master-key-provider code runs, and **no code was changed in this step, so the before and after sets are the same set** — there is no diff to claim. That failure is separate pre-existing tree noise and is not attributed to this sweep.

### `S138` | BLOCKED, with the blocker finally measured | "collection succeeds" is the WRONG quiescence criterion

The first collectable tree of the session appeared and the diff was taken immediately: `domain/calculations/registry/tests` plus `application/calculations/tests`, sequential `-n0`, full output to disk. It ran 1 hour 9 minutes and produced **1722 failed, 3429 passed, 221 errors**.

**That is not a baseline, and it must not be recorded as one.** Grouping the failures by cause shows a single systemic refusal, not a distribution:

| Cause | Count |
|---|---|
| `RegistryValidationError` | 1704 |
| `AssertionError` | 93 |
| `RegistryLoadError` | 50 |
| `ProfileCustodyRecordError` | 43 |
| `TomlParsingError` | 41 |
| everything else | <30 each |

Every one of the 1704 carries the same message: modelos 036 and 038 declare no export layout, modelo 100 revision 2020 claims `filing` authority grade while four families "remain blocked pending evidence", and so on. Alongside them, `_rtoml.TomlParsingError: duplicate key: 'segmento' for key 'revisions.2022.completeness_manifest.casillas' at line 113`. **The registry itself does not currently validate**, so every test that loads an authority fails identically regardless of anything this campaign did.

**Committed, not in-flight, and not ours to fix:** `git status` shows zero uncommitted registry changes, and `git log` shows `registry: continue authority-grade sweep (round 41)`. The registry is in a knowingly intermediate state between rounds of another campaign's long-running sweep. Waiting it out is not a strategy measured in loop ticks.

**The correction this produces is the valuable part.** `S138` and this record's own recommendation both said "re-run from a quiesced tree", and the working definition of quiesced had silently become *"`pytest --collect-only` succeeds"*. It does not follow: collection only proves every module imports. Registry validity is a **runtime** property evaluated when a test loads an authority, and the two are independent. This session watched collection errors go 67 → 4 → 3 → 7 → 0 and treated the 0 as the green light — while the registry underneath had been invalid the whole time.

**The quiescence criterion for `S138` is therefore restated:** the tree is ready when the registry VALIDATES, not when collection succeeds. The cheap precondition check is a single authority-loading test — if it raises `RegistryValidationError`, the tree is not ready and a full 70-minute run is wasted before it starts. **Run that check first next time.** This run cost 70 minutes to learn something a single test would have said in seconds.

**Also confirmed still live:** 43 `ProfileCustodyRecordError` failures, the same uncommitted `custody/_inventory.py` regression recorded above. Unchanged and still unowned.

**`S138` stays OPEN.** It is the only open step in the wave, it is blocked on another campaign completing its authority-grade sweep, and no amount of re-running changes that. It is not deferred silently: the blocker, its cause, its owner and the corrected precondition are all recorded here.
