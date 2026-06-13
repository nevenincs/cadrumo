---
tags:
  - '#audit'
  - '#pytest'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-04-17-pytest-markers-adr]]'
  - '[[2026-04-17-pytest-only-testing-adr]]'
  - '[[2026-04-16-live-write-test-audit-adr]]'
  - '[[2026-04-21-integration-tests-ci-adr]]'
---

# Pytest Runtime and Marker Conformance Audit

## Scope

Topic: package-local pytest runtime and marker conformance.

Audit surface: `src/aeat` tests, `pyproject.toml` pytest marker configuration, `src/aeat/tests/test_marker_integrity.py`, and the test marker ADR trail under `.vault`.

Rewrite scope: create one audit record with timing evidence, marker inventory, ADR conformance findings, suspected runtime culprits, and next actions. Repo-root `tests/` and README checks are intentionally out of scope.

The workspace was shared during this audit. Existing modified and untracked files were left untouched. Commands were run with package-local paths and direct `.venv\Scripts\pytest.exe` where possible because `uv run` was observed to hit a locked `.venv\Scripts\aeat.exe` in this workspace.

## Executive Finding

The current package-local suite does not show a single confirmed deadlock. The strongest early "hang" signals are genuine long-running slices:

- `src/aeat/adapters/inbound` completes when given a larger timeout: 472 passed in 391.49s, wall 393.4s.
- `src/aeat/adapters/inbound/sanitizer` spends about 180s in one setup path that parses fixtures through the justificante parser.
- `src/aeat/adapters/inbound/justificante/test_parser.py` spends about 180s on real corpus PDF parsing.
- `src/aeat/domain/calculations/registry/test_workbook_parity.py` is slow but bounded: 17 passed in 51.28s, wall 54.2s.

The suite also has real regressions and collection blockers. A bounded default run failed during collection because `AmendmentVerificationRefusedError` is missing an `ErrorCode` registry entry. Several bounded package slices fail independently.

Marker coverage is strong at the module level: no markerless package-local test modules were found, every checked module has a top-level `pytestmark`, and access/domain marker counts are coherent. The marker system still drifts from ADR history and configuration hygiene: duplicated `pyproject.toml` marker declarations, current taxonomy names that differ from the accepted 2026-04-17 ADR, unused registered markers, and leftover per-function access/domain decorators.

## Marker Timing Summary

These are collection timings by access marker from `src/aeat`:

| Marker | Command | Result | Wall/pytest time |
| --- | --- | --- | --- |
| `unit` | `.venv\Scripts\pytest.exe src/aeat --collect-only -q -m unit` | 5232 selected / 5268 collected / 36 deselected | 22.33s pytest |
| `live_read` | `.venv\Scripts\pytest.exe src/aeat --collect-only -q -m live_read` | 36 selected / 5268 collected / 5232 deselected | 22.29s pytest |
| `live_write` | `.venv\Scripts\pytest.exe src/aeat --collect-only -q -m live_write` | 0 selected / 5268 deselected; pytest exits non-zero because no tests were collected | 22.26s pytest |

The access-marker counts are consistent with the marker inventory: no package-local `live_write` modules are currently active.

## Package Timing Evidence

| Slice | Command shape | Result | Wall/pytest time | Finding |
| --- | --- | --- | --- | --- |
| Full package via `uv` | `uv run pytest src/aeat -q` | Could not start in one run because `.venv\Scripts\aeat.exe` was locked | N/A | Use direct pytest while workspace has console-script locks. |
| Full package direct | `.venv\Scripts\pytest.exe src/aeat -q` | Timed out and was stopped | 15m timeout | Not representative until narrower blockers are fixed. |
| Default collect | `.venv\Scripts\pytest.exe src/aeat --collect-only -q -m unit` | 5232 selected / 5268 collected | 22.33s pytest | Collection itself is bounded. |
| Broad app/CLI/core/locales/tests | `src/aeat/application src/aeat/entrypoints/cli src/aeat/core src/aeat/locales src/aeat/tests -m unit` | Exit 1; visible failures in application/auth, filing, modelo_303_390, wizard translations | 490.1s wall | Large and failing, but not confirmed deadlocked. |
| Inbound | `src/aeat/adapters/inbound -m unit` | 472 passed, 22 warnings | 391.49s pytest / 393.4s wall | Long but bounded. |
| Persistence | `src/aeat/adapters/persistence -m unit` | 1 failed, 298 passed, 2 skipped | 9.43s pytest / 11.2s wall | Fast slice with one write-surface failure. |
| Outbound | `src/aeat/adapters/outbound -m unit` | 33 failed, 511 passed, 35 deselected | 88.71s pytest / 91.6s wall | Failing and moderately slow. |
| Domain broad | `src/aeat/domain -m unit` | Timed out | 184s timeout | Split required. |
| Domain calculations registry | `src/aeat/domain/calculations/registry -m unit` | Timed out | 244s timeout | Split required. |
| Domain VAT | `src/aeat/domain/vat -m unit` | 180 passed | 4.12s pytest / 6.1s wall | Clean. |
| Domain excluding registry and VAT | domain reduced slice | 759 passed, 6 failed | 14.13s pytest / 16.5s wall | Failures are in normatives. |
| Registry collect-only | registry collect-only | 1034 tests | 2.9s pytest | Collection is fast. |
| Registry workbook parity | `test_workbook_parity.py -m unit` | 17 passed | 51.28s pytest / 54.2s wall | Slow bounded LibreOffice/binary workbook work. |

## Inbound Culprit Detail

The earlier 124s inbound timeout was too low. With a larger timeout, inbound passes:

| Slice | Result | Wall/pytest time | Slowest evidence |
| --- | --- | --- | --- |
| `src/aeat/adapters/inbound/borrador` | 11 passed | 2.68s pytest / 4.4s wall | No material slow test. |
| `src/aeat/adapters/inbound/declaracion` | 16 passed | 8.27s pytest / 10.3s wall | 3.64s and 2.73s PDF parser boundary tests. |
| `src/aeat/adapters/inbound/financial` | 48 passed, 22 warnings | 3.50s pytest / 5.0s wall | N26 fixture parsing below 1s per top test. |
| `src/aeat/adapters/inbound/justificante/test_extract_helpers.py` | 21 passed | 0.66s pytest / 1.8s wall | Clean. |
| `src/aeat/adapters/inbound/justificante/test_extract_modelos.py` | 9 passed | 0.69s pytest / 1.8s wall | Clean. |
| `src/aeat/adapters/inbound/justificante/test_parser.py` | 54 passed | 178.54s pytest / 179.9s wall | Real corpus PDF parser cases dominate. |
| `src/aeat/adapters/inbound/pdf` | 50 passed | 0.72s pytest / 1.9s wall | Clean. |
| `src/aeat/adapters/inbound/sanitizer` | 263 passed | 180.62s pytest / 182.1s wall | 178.37s setup in `test_round_trip.py::test_fixture_parses_through_justificante_parser[2021-0A.pdf0]`. |
| Full inbound | 472 passed, 22 warnings | 391.49s pytest / 393.4s wall | Same sanitizer setup plus corpus PDF parser calls. |

Top inbound durations from the confirmed full inbound run:

- 180.52s setup: `src/aeat/adapters/inbound/sanitizer/test_round_trip.py::test_fixture_parses_through_justificante_parser[2021-0A.pdf0]`
- 13.36s call: `src/aeat/adapters/inbound/justificante/test_parser.py::TestRealCorpusParses::test_corpus_pdf_parses[390/2023-0A]`
- 11.47s call: `src/aeat/adapters/inbound/justificante/test_parser.py::TestRealCorpusParses::test_corpus_pdf_parses[390/2022-0A]`
- 8.39s call: `src/aeat/adapters/inbound/justificante/test_parser.py::TestRealCorpusParses::test_corpus_pdf_parses[303/2024-3T]`
- 8.26s call: `src/aeat/adapters/inbound/justificante/test_parser.py::TestRealCorpusParses::test_corpus_pdf_parses[303/2024-4T]`

## Other Confirmed Failure Groups

Collection/import blocker:

- `src/aeat/application/modelo/_actions.py` declares `AmendmentVerificationRefusedError`, but the error registry check reports it has no declared `ErrorCode` registry entry. The enforcement path includes `src/aeat/core/errors/_registry.py` and `src/aeat/entrypoints/cli/__init__.py`.

Persistence:

- `src/aeat/adapters/persistence` fails the sensitive write-surface inventory because `src/aeat/application/ledger/_actions.py` writes through `command.output_path.write_bytes`.

Outbound:

- `Settings` rejects uppercase `AEAT_CERTIFICATE_BACKEND=HTTPX_FALLBACK`.
- Browser stage regex expectations mismatch current behavior.
- Modelo 100 relation tests expect an observed filing that is missing.
- Top outbound duration: 20.27s in a submitted-file observation test for Modelo 123.

Domain:

- `src/aeat/domain/vat` is clean and fast.
- Domain excluding calculations/registry and VAT fails six normatives tests.
- Registry collect-only is fast, but registry execution remains too broad to classify from the timed-out slice. `test_workbook_parity.py` is confirmed slow and bounded.

Application/CLI/core/locales/tests broad slice:

- The large slice completed only after 490.1s with exit 1.
- Visible failures included `application/auth/test_catalogue.py`, `application/filing/test_complementaria.py`, `application/filing/test_modelo_303_390.py`, and `application/wizard/test_wizard_translations_resolve.py`.

## Marker Inventory

Static marker audit over package-local tests found:

- Total package-local test modules including fixture-generator tests: 403.
- Modules covered by `src/aeat/tests/test_marker_integrity.py` after fixture exclusion: 402.
- Markerless modules: 0.
- Modules with bad access marker counts: 0.
- Modules missing domain markers: 0.
- Unknown custom marker uses: 0.
- Modules with exactly one top-level list-form `pytestmark`: all 403.

Access marker module counts:

| Marker | Count | Reason |
| --- | ---: | --- |
| `unit` | 388 | Default hermetic test class for package-local behavior. This is the configured default selection in `pyproject.toml`. |
| `live_read` | 15 | Tests that may read external/live resources but should not mutate remote state. |
| `live_write` | 0 | Live mutation tests are currently absent from package-local modules and are also dropped by the marker hook. |

Domain marker module counts:

| Marker | Count | Reason |
| --- | ---: | --- |
| `domain_model` | 166 | Pure domain/model behavior and calculation logic. |
| `domain_application` | 116 | Application orchestration, workflows, commands, and use-case services. |
| `domain_outbound` | 57 | Outbound adapters and remote-facing integration boundaries. |
| `domain_core` | 25 | Core shared infrastructure and cross-cutting policies. |
| `domain_persistence` | 23 | Storage, repositories, persistence adapters, and write-surface policy. |
| `domain_inbound` | 16 | Inbound parsing/import/sanitization adapters and file ingestion. |
| `domain_export` | 9 | Export surfaces and generated artifact behavior. |
| `domain_submission` | 0 | Registered but unused; likely stale after live-write/live-submission excision. |

Fixture tier marker counts:

| Marker | Count | Reason |
| --- | ---: | --- |
| `fixture_tier_l1` | 0 | Registered but unused. Intended fixture-size/tier classification is not active in package-local modules. |
| `fixture_tier_l2` | 0 | Registered but unused. Intended fixture-size/tier classification is not active in package-local modules. |
| `fixture_tier_l3` | 1 | Used once for large/heavy fixture coverage. |

Other marker notes:

- No active obsolete `@pytest.mark.live` code usage was found.
- Stale prose references to old live-marker language still exist, for example in `src/aeat/entrypoints/cli/_live.py`.

## Marker Conformance vs ADR History

Confirmed conformance:

- Package-local tests have complete module-level access/domain marker coverage.
- No markerless package-local test module was found.
- No module was missing an access marker or domain marker under the current integrity test.
- No obsolete active `@pytest.mark.live` decorator usage was found.
- Current collection behavior honors the default unit selection.

Confirmed drift:

- `pyproject.toml` contains duplicate marker descriptions for `domain_inbound`, `domain_outbound`, `domain_persistence`, `domain_application`, and `domain_core`.
- The accepted 2026-04-17 marker ADR used taxonomy names such as `domain_aeat_remote`, `domain_financial_input`, `domain_local_state`, `domain_mediation`, and `domain_infra`. Current code uses `domain_outbound`, `domain_inbound`, `domain_persistence`, `domain_application`, `domain_core`, plus `domain_model` and `domain_export`.
- `domain_submission` remains registered but unused.
- `fixture_tier_l1` and `fixture_tier_l2` remain registered but unused.
- `src/aeat/tests/_marker_hook.py` permanently drops `live_write`, while the original live-write ADR expected a three-factor bypass.
- Per-function access/domain decorators still exist despite the module-level marker policy.

Per-function access/domain decorator leftovers:

- `src/aeat/adapters/outbound/aeat/browser/test_session.py:268` uses `@pytest.mark.unit`.
- `src/aeat/adapters/persistence/storage/sql/_test_engine.py:62` uses `@pytest.mark.unit`.
- `src/aeat/domain/manuals/test_fetch.py:114` has nested `@pytest.mark.unit`.
- `src/aeat/locales/test_parity.py:31` has function-level `unit` plus `domain_application`.
- `src/aeat/tests/test_adr_layout_import_smoke.py:94` has function-level `unit` plus `domain_core`.

Modules with nonstandard `pytestmark` placement:

- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py:19`
- `src/aeat/adapters/inbound/sanitizer/test_pipeline.py:51`
- `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py:57`
- `src/aeat/tests/test_config.py:25`

## Culprit Ranking

1. `src/aeat/adapters/inbound/sanitizer/test_round_trip.py` fixture setup is the largest confirmed single runtime cost. It spends about 180s before the first parameter case when parsing fixtures through the justificante parser.

2. `src/aeat/adapters/inbound/justificante/test_parser.py` is the largest confirmed file-level runtime cost. It passes, but takes about 180s because real corpus PDF parser cases cost up to 13.36s each.

3. `src/aeat/domain/calculations/registry/test_workbook_parity.py` is slow but bounded at about 54s. The rest of registry still needs narrower partitioning because the broader registry slice timed out.

4. `AmendmentVerificationRefusedError` missing from the error-code registry is a hard collection blocker for default package runs. Fix this before interpreting full-suite results.

5. Outbound has broad real regressions: 33 failing tests in a 91.6s slice.

6. The broad application/CLI/core/locales/tests slice is both slow and failing. It completed in 490.1s, so it is not proven hung, but it is too coarse to diagnose without further partitioning.

## Recommended Actions

1. Fix the missing `ErrorCode` registry entry for `AmendmentVerificationRefusedError` before the next full package run.

2. Split the two inbound heavy paths:
   - Keep real corpus parser coverage, but consider a smaller default `unit` representative set and move exhaustive corpus sweeps behind a heavier marker only if that conforms to the marker ADR.
   - Investigate why sanitizer round-trip setup pays about 180s once, especially whether it duplicates the justificante corpus parse work.

3. Partition `src/aeat/domain/calculations/registry` beyond `test_workbook_parity.py` with per-file timings.

4. Triage failing slices before another 15-minute full run:
   - Persistence write-surface inventory.
   - Outbound settings/backend casing, browser stage expectations, and Modelo 100 relation observation.
   - Domain normatives failures.
   - Application/auth, filing, modelo_303_390, and wizard translation failures.

5. Normalize marker configuration:
   - Deduplicate marker declarations in `pyproject.toml`.
   - Decide whether the current taxonomy supersedes `2026-04-17-pytest-markers-adr` or whether code should be renamed back to the ADR terms.
   - Remove or justify `domain_submission`, `fixture_tier_l1`, and `fixture_tier_l2`.
   - Reconcile permanent `live_write` dropping with the live-write ADR.

6. Clean residual marker drift:
   - Remove per-function access/domain decorators unless a documented exception is added.
   - Move the four nonstandard module-level `pytestmark` declarations to the expected top position.

7. Add a repeatable package-local timing harness that records marker counts, selected counts, per-slice wall time, and `--durations` output to an artifact. The harness should avoid repo-root `tests/` and should not depend on `uv run` while the Windows console script lock persists.
