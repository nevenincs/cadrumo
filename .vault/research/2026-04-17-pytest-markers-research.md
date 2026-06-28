---
tags:
  - "#research"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-16-live-write-test-audit-research]]"
  - "[[2026-04-16-live-write-test-audit]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-13-filing-complementaria-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
issue: "#163"
charter: "#116"
---

# pytest-markers research

Grounds the ADR for issue `#163` - granular pytest markers that (a) classify every test by the `aeat.*` subpackage domain it exercises, and (b) split the legacy `@pytest.mark.live` marker into `live_read` (permitted in opt-in suites) and `live_write` (structurally blocked from automated execution). The live-write ban mechanism is the primary safety lever of this feature and ties directly to the `#116` live-AEAT-write safety charter (rules **R1**, **R3**, **R5**).

## 1. problem statement

Two shortcomings are observable on the current `main`:

1. The marker vocabulary is a boolean `unit | live` pair. That gives no way to scope a run to "all financial-input tests", "everything touching the AEAT remote", or "everything below the storage boundary". As the test count grows past ~900 collected items, scoped runs matter both for developer inner-loop ergonomics and for CI sharding.
2. The single `@pytest.mark.live` marker conflates **reads** (status, inbox, justificante CSV round-trip) with **writes** (submission engine, filing amendment, any modelo submit path). Rule `R1` of the safety charter #116 categorically forbids any programmatically reachable live write; the current marker shape does not express that distinction, and the guard is carried entirely by runtime checks inside `SubmissionEngine` plus the human-operator discipline of never setting `AEAT_LIVE_SUBMIT_ENABLED`.

The goal is to promote the live-read / live-write distinction to a first-class pytest marker and to bolt a collection-time hook on top that refuses to collect or execute `live_write` tests unless an explicit, interactive, hard-to-type bypass is present.

## 2. current state survey

### 2.1 marker registration

`pyproject.toml` `[tool.pytest.ini_options]` (lines 157-165) today registers only two markers:

```toml
addopts = "-v --tb=short -m 'not live'"
markers = [
    "unit: deterministic tests with no external I/O",
    "live: tests that hit real Google APIs against scratch resources",
]
```

The description on `live` is stale - it references "Google APIs" but the marker is now also used against AEAT Sede Electronica, the Anthropic LLM endpoint, and Playwright-driven browser probes.

### 2.2 conftest inventory

- `tests/conftest.py` - docstring only, no hooks, no fixtures.
- No other `conftest.py` exists anywhere under `src/aeat/` or `tests/`.
- Confirmed by `.vault/audit/2026-04-16-live-write-test-audit.md` ("Procedure 4: fixture and conftest audit").

That means there is currently zero collection-time enforcement: the entire safety story relies on `-m 'not live'` in the default `addopts` plus runtime refusal inside `SubmissionEngine.__init__`.

### 2.3 test file inventory

Enumerated below by proposed domain. "Current" is `module` if `pytestmark = ...` is module-level, `per-function` if individual `@pytest.mark.unit` / `@pytest.mark.live` decorators are used. "Access" is the proposed `unit | live_read | live_write` classification. No file today exercises a live-write path - every `live`-marked module in the tree is either a read probe, a dry-run-only submission probe, or a dependency-gated placeholder.

#### 2.3.1 domain_aeat_remote - AEAT Sede Electronica read-facing

| file | current | access | notes |
| --- | --- | --- | --- |
| `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py` | per-function `unit` | `unit` | cert-loader happy paths |
| `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py` | per-function `live` | `live_read` | mTLS handshake probe |
| `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_health.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_evasion.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py` | per-function `live` | `live_read` | bot-detection probe |
| `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_profile.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py` | per-function `unit` | `unit` |  |
| `src/aeat/inbox/test_classifier.py` | per-function `unit` | `unit` |  |
| `src/aeat/inbox/test_deadline.py` | per-function `unit` | `unit` |  |
| `src/aeat/inbox/test_fetcher.py` | per-function `unit` | `unit` |  |
| `src/aeat/inbox/test_live_inbox.py` | per-function `live` | `live_read` | fetch+ack; skipped until #8 |
| `src/aeat/inbox/test_models.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/justificante/test_parser.py` | module `unit` | `unit` |  |
| `src/aeat/domain/justificante/test_verify_live.py` | module `live` | `live_read` | CSV verification round-trip |
| `src/aeat/status/test_cache.py` | module `unit` | `unit` |  |
| `src/aeat/status/test_cache_key.py` | module `unit` | `unit` |  |
| `src/aeat/status/test_errors.py` | module `unit` | `unit` |  |
| `src/aeat/status/test_live.py` | module `live` | `live_read` | Sede landing read probe (placeholder) |
| `src/aeat/status/test_models.py` | module `unit` | `unit` |  |
| `src/aeat/status/test_reader.py` | module `unit` | `unit` |  |
| `src/aeat/status/test_site_health.py` | per-function `unit` | `unit` |  |
| `src/aeat/status/_parsers/test_expedientes.py` | module `unit` | `unit` |  |
| `src/aeat/domain/casillas/test_live_cli.py` | per-function `live` | `live_read` | skip until #21 |
| `src/aeat/domain/casillas/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/casillas/_test_catalogue.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/casillas/_test_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/sync/test_bounded_policy.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/sync/test_classifier.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/sync/test_live_sync.py` | per-function `live` | `live_read` | dependency-gated fetch read |
| `src/aeat/application/sync/test_repository.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/sync/test_runner.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/sync/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/sync/test_strategies.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/sync/test_wire.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/portals/test_smoke.py` | per-function `unit` | `unit` |  |

#### 2.3.2 domain_submission - AEAT write-capable boundary

Every test in this domain must be reviewed against charter rule `R5`. None execute a live write today; the live-marked ones exercise dry-run-only paths. The domain marker is distinct from `domain_aeat_remote` because these are the code paths a future live write would go through, and charter-driven audits need a precise lens.

| file | current | access | notes |
| --- | --- | --- | --- |
| `src/aeat/application/filing/test_complementaria.py` | module `unit` | `unit` |  |
| `src/aeat/application/filing/test_filing.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/filing/test_live_complementaria.py` | module `live` | `live_read` | explicit `dry_run=True` |
| `src/aeat/application/filing/test_modelo_303_390.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/export/test_engine.py` | module `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/export/test_errors.py` | module `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` | module `live` | `live_read` | dry-run-only per module docstring |
| `src/aeat/adapters/outbound/aeat/export/test_models.py` | module `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/export/test_preflight.py` | module `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py` | module `unit` | `unit` |  |
| `src/aeat/adapters/outbound/aeat/export/_submitters/test_modelo130.py` | module `unit` | `unit` |  |

**No `live_write` test exists today.** The plan that follows this research will introduce the marker, document it, and install the ban hook. Any future test that truly exercises `dry_run=False` against a real AEAT endpoint (which the charter forbids) would carry `live_write`; collection-time refusal ensures the ban is structural rather than procedural.

#### 2.3.3 domain_financial_input - financial ingest

| file | current | access | notes |
| --- | --- | --- | --- |
| `src/aeat/domain/financial/categories/test_profile.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/categories/test_proportionality.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/categories/test_registry.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/categories/test_spending_category.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/invoices/test_catalogue.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/invoices/test_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/invoices/test_models.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/invoices/test_reconciliation.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/invoices/test_validators.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/providers/test_base.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/providers/test_csv.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/providers/test_ofx.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/providers/test_xlsx.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/transactions/test_catalogue.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/transactions/test_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/transactions/test_models.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/vat/test_categories.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/vat/test_corpus.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/vat/test_rates.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/vat/test_rules.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/financial/vat/test_verify.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/financial/test_cli.py` | per-function `unit` | `unit` |  |

#### 2.3.4 domain_local_state - on-disk catalogues and local SQLite mirror

| file | current | access | notes |
| --- | --- | --- | --- |
| `src/aeat/adapters/persistence/storage/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/persistence/storage/_test_constraints.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/persistence/storage/_test_engine.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/persistence/storage/_test_migrations.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/persistence/storage/_test_records.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/persistence/storage/_test_repository.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/persistence/storage/_test_session.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/modelos/test_applicability.py` | module `unit` | `unit` |  |
| `src/aeat/domain/modelos/test_casilla_cross_reference.py` | module `unit` | `unit` |  |
| `src/aeat/domain/modelos/test_citations.py` | module `unit` | `unit` |  |
| `src/aeat/domain/modelos/test_cli.py` | module `unit` | `unit` |  |
| `src/aeat/domain/modelos/test_codes.py` | module `unit` | `unit` |  |
| `src/aeat/domain/modelos/test_metadata.py` | module `unit` | `unit` |  |
| `src/aeat/domain/modelos/test_registry.py` | module `unit` | `unit` |  |
| `src/aeat/domain/modelos/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/normatives/test_loader.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/normatives/test_lookup_and_cite.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/normatives/test_schema.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/normatives/test_verify.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/manuals/test_fetch.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/manuals/test_loader.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/manuals/test_schema.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/manuals/test_verify.py` | per-function `unit` | `unit` |  |
| `src/aeat/corpus/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/schema/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/deadlines/test_applies.py` | module `unit` | `unit` |  |
| `src/aeat/domain/deadlines/test_calendar.py` | module `unit` | `unit` |  |
| `src/aeat/domain/deadlines/test_engine.py` | module `unit` | `unit` |  |
| `src/aeat/domain/deadlines/test_models.py` | module `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/deadlines/test_cli.py` | module `unit` | `unit` |  |

#### 2.3.5 domain_mediation - workflow, LLM, i18n, testing

| file | current | access | notes |
| --- | --- | --- | --- |
| `src/aeat/application/workflow/test_engine.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/workflow/test_live.py` | per-function `live` | `live_read` | no writes per module docstring |
| `src/aeat/application/workflow/test_models.py` | per-function `unit` | `unit` |  |
| `src/aeat/application/workflow/test_persistence.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/llm/test_live_anthropic.py` | per-function `live` | `live_read` | Anthropic round-trip |
| `src/aeat/adapters/outbound/llm/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/llm/_test_cache.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/llm/_test_client.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/llm/_test_models.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/llm/_test_prompts.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/llm/_test_translation.py` | per-function `unit` | `unit` |  |
| `src/aeat/adapters/outbound/llm/_test_usage.py` | per-function `unit` | `unit` |  |
| `src/aeat/core/i18n/test_i18n.py` | per-function `unit` | `unit` |  |
| `src/aeat/domain/testing/test_testing.py` | per-function `unit` | `unit` |  |

#### 2.3.6 domain_infra - project plumbing, CLI, setup, release-meta

| file | current | access | notes |
| --- | --- | --- | --- |
| `src/aeat/_test_auth.py` | per-function `unit` | `unit` |  |
| `src/aeat/_test_env_io.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/test_categories_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/test_manual_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/test_vat_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/browser/test_health.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/filing/test_filing_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/inbox/test_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/llm/test_smoke.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/submission/test_cli.py` | module `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/sync/test_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/workflow/test_cli.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/_test_bootstrap.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/_test_cloud.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/_test_cloud_live.py` | per-function `live` | `live_read` | Google Cloud read-only smoke |
| `src/aeat/entrypoints/cli/_test_docs_helpers.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/_test_docs_live.py` | per-function `live` | `live_read` | scratch-doc round-trip (net-neutral) |
| `src/aeat/entrypoints/cli/_test_doctor.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/_test_drive_helpers.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/_test_drive_live.py` | per-function `live` | `live_read` | scratch-folder round-trip |
| `src/aeat/entrypoints/cli/_test_oauth.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/_test_sheets_helpers.py` | per-function `unit` | `unit` |  |
| `src/aeat/entrypoints/cli/_test_sheets_live.py` | per-function `live` | `live_read` | scratch-sheet round-trip |
| `src/aeat/application/setup/test_cli.py` | module `unit` | `unit` |  |
| `src/aeat/application/setup/test_env_writer.py` | module `unit` | `unit` |  |
| `src/aeat/application/setup/test_models.py` | module `unit` | `unit` |  |
| `src/aeat/application/setup/test_verifier.py` | module `unit` | `unit` |  |
| `src/aeat/application/setup/test_wizard.py` | module `unit` | `unit` |  |
| `tests/test_config.py` | module `unit` | `unit` |  |
| `tests/test_docs.py` | per-function `unit` | `unit` |  |
| `tests/test_release_config.py` | per-function `unit` | `unit` |  |
| `tests/live/test_google_fixtures_smoke.py` | module list `[live, skipif]` | `live_read` | dual-opt-in Google fixture smoke |

Subtotal: ~140 test modules, of which 14 are currently `live`-marked and 0 are live-write under the proposed taxonomy.

### 2.4 subpackages under src/aeat/

`auth`, `browser`, `casillas`, `cli`, `corpus`, `deadlines`, `filing`, `financial`, `i18n`, `inbox`, `justificante`, `llm`, `manuals`, `models`, `normatives`, `portals`, `schema`, `setup`, `status`, `storage`, `submission`, `sync`, `testing`, `workflow`. Plus root modules: `config.py`, `env_io.py`, `errors.py`, `logging.py`.

## 3. proposed marker taxonomy

### 3.1 axis A - access level (mutually exclusive)

Every test carries exactly one of these three:

- `unit` - deterministic, no external I/O. Mocks/stubs allowed per `CLAUDE.md`. Selected by `just test` via `-m 'unit'`.
- `live_read` - talks to a real external service and performs only read-shaped operations. Opt-in via `AEAT_LIVE_TESTS_ENABLED=1`. Google-specific live_read additionally requires `AEAT_LIVE_TESTS_GOOGLE=1`. Selected by `just test-live` via `-m 'live_read'`.
- `live_write` - talks to a real external service and performs a write-shaped operation (HTTP POST, form submission, signed envelope, modelo filing, amendment submission). **Collection-banned by default.** See section 5.

Invariant: a test must carry exactly one of `{unit, live_read, live_write}`. Collection-time hook in `tests/conftest.py` fails if zero or more than one is present.

### 3.2 axis B - domain (one or more required)

The domain axis maps cleanly to `aeat.*` subpackages. Issue #163 proposes four domain markers; surveying the actual subpackage graph yields a recommended **six**:

| marker | covers subpackages |
| --- | --- |
| `domain_aeat_remote` | `auth`, `browser`, `casillas`, `inbox`, `justificante`, `portals`, `status`, `sync` |
| `domain_submission` | `filing`, `submission` |
| `domain_financial_input` | `financial`, `cli/financial` |
| `domain_local_state` | `storage`, `models`, `normatives`, `manuals`, `corpus`, `schema`, `deadlines`, `cli/deadlines` |
| `domain_mediation` | `workflow`, `llm`, `i18n`, `testing`, `cli/workflow`, `cli/llm` |
| `domain_infra` | root modules, `cli` (non-domain-specific), `setup`, top-level `tests/*.py` |

**Deviation from the issue proposal:** the issue lists five markers. I recommend adding `domain_submission` as a dedicated carve-out. Rationale: charter R1 makes the write-capable boundary a uniquely sensitive target for scoped runs, audits, and future `live_write` experiments. Collapsing it into `domain_aeat_remote` would dilute that lens.

**Also considered, rejected:** separate `domain_models`, `domain_identity` (auth/cert), `domain_config`. These do not survive the "is it a useful scoping axis for CI shards or audits?" test - they are subfolders of already-covered domains.

### 3.3 module-level application (MANDATED)

All markers are applied module-level via `pytestmark = [...]`:

```python
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]
```

This replaces per-function `@pytest.mark.unit` scattering (currently used in ~80% of `src/aeat/` test files). Enforcement: a new `tests/test_marker_integrity.py` parses every test module with `ast` and fails if any module lacks a module-level `pytestmark` assignment that includes exactly one access marker AND at least one domain marker.

**Override pattern.** If a module is mostly `unit` but contains a single `live_read` or vice versa, split the module. Do NOT rely on per-function overrides - function-level markers are additive, not replacing; a function inside a live-marked module still inherits `live`. The plan should explicitly prohibit mixed-access modules.

Mixed-domain modules are rare but legal. In that case the module-level `pytestmark` carries both domain markers.

## 4. live-marker split - per-test classification

From section 2.3 the 14 currently `live`-marked modules all fall into `live_read` under the proposed taxonomy. Citations (module path then docstring evidence):

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py` - "mTLS handshake smoke test" (read)
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py` - bot-evasion probe (read)
- `src/aeat/domain/casillas/test_live_cli.py` - skipped until #21 (would be read)
- `src/aeat/entrypoints/cli/_test_cloud_live.py` - "Read-only round-trips against Cloud Functions, Cloud Run, and Cloud Storage"
- `src/aeat/entrypoints/cli/_test_docs_live.py` - scratch-doc round-trip, self-cleaning
- `src/aeat/entrypoints/cli/_test_drive_live.py` - scratch-folder round-trip
- `src/aeat/entrypoints/cli/_test_sheets_live.py` - scratch-sheet round-trip
- `src/aeat/application/filing/test_live_complementaria.py` - "exercises only the dry-run/read-only amendment submission path"
- `src/aeat/inbox/test_live_inbox.py` - fetch+ack read
- `src/aeat/domain/justificante/test_verify_live.py` - CSV verification round-trip (read)
- `src/aeat/adapters/outbound/llm/test_live_anthropic.py` - Anthropic API round-trip (read)
- `src/aeat/status/test_live.py` - Sede landing page read (placeholder)
- `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` - "performs a DRY-RUN-ONLY engine invocation. It never enters live submission mode."
- `src/aeat/application/sync/test_live_sync.py` - "fetch then validate then classify" read cycle
- `src/aeat/application/workflow/test_live.py` - asserts rejection-on-missing-adapters (no writes)
- `tests/live/test_google_fixtures_smoke.py` - Drive+Sheets+Docs read probes

**Subtle case - scratch-resource round-trips.** The Google scratch tests (`_test_docs_live.py`, `_test_drive_live.py`, `_test_sheets_live.py`, `tests/live/test_google_fixtures_smoke.py`) do perform writes against Google-owned, project-provisioned scratch resources. Under the charter's letter-of-the-law, those are writes. Under the charter's intent, `R1` forbids writes to the **AEAT Sede Electronica** specifically - AEAT has no sandbox, every write is legally binding. Google Workspace writes against scratch-only documents are out of scope of R1.

**Recommendation:** the `live_write` marker is reserved for writes that produce legally binding state on AEAT. Google scratch round-trips stay `live_read` (with an explanatory comment in the marker registration). If the project later decides to audit Google scratch writes separately, a `live_scratch_write` marker could be introduced, but that is out of scope for this feature.

## 5. live_write ban mechanism

### 5.1 defence in depth

The ban stacks on top of, not instead of, the existing charter guards:

- Charter `R1` - no automated test may ever produce a live write.
- Charter `R3` - `AEAT_LIVE_SUBMIT_ENABLED=1` must never be set in any pytest context.
- Charter `R5` - `SubmissionEngine.__init__` detects `PYTEST_CURRENT_TEST` and refuses `dry_run=False` at runtime.

`#163` adds a fourth layer: the test never even gets collected.

### 5.2 hook shape

In `tests/conftest.py`:

```python
from __future__ import annotations

import os
import sys

import pytest


_LIVE_WRITE_BYPASS_ENV = "AEAT_LIVE_WRITE_UNSAFE_BYPASS"
_LIVE_WRITE_CONFIRM_ENV = "AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM"
_LIVE_WRITE_CONFIRM_PHRASE = "I ACCEPT THE RISK OF FILING A LIVE TAX RETURN"


def _live_write_bypass_active() -> bool:
    if os.environ.get(_LIVE_WRITE_BYPASS_ENV) != "1":
        return False
    if os.environ.get(_LIVE_WRITE_CONFIRM_ENV) != _LIVE_WRITE_CONFIRM_PHRASE:
        return False
    if not sys.stdin.isatty():
        return False
    return True


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    access_markers = {"unit", "live_read", "live_write"}
    remaining: list[pytest.Item] = []
    for item in items:
        owned = {m.name for m in item.iter_markers()}
        access = owned & access_markers
        if len(access) != 1:
            raise pytest.UsageError(
                f"{item.nodeid}: must carry exactly one of {access_markers}, "
                f"found {access or 'none'}"
            )
        if not any(name.startswith("domain_") for name in owned):
            raise pytest.UsageError(
                f"{item.nodeid}: must carry at least one domain_* marker"
            )
        if "live_write" in access and not _live_write_bypass_active():
            continue
        remaining.append(item)
    items[:] = remaining
```

Design notes:

- **Drop, don't skip.** A skip would flash through CI and could be flipped by a single env-var change. Dropping the item from `items[:]` means the items simply do not exist from pytest's point of view in the default run.
- **Three-factor bypass.** Env-var set, confirmation phrase typed exactly, interactive TTY. All three AND-gated. Matches charter R4 philosophy (operator types the exact phrase `CONFIRMO FILING {modelo} {period}`).
- **No pytest marker flag can override the ban.** `pytest -m live_write` without the bypass collects zero items.
- **UsageError on missing markers.** Strict at collection. `tests/test_marker_integrity.py` remains as a separate unit test so CI reports show "marker integrity failure" rather than "pytest usage error".
- **UNSAFE in env names** makes the intent legible in shell history and audit logs.

### 5.3 cross-reference with charter

- **R1 to collection ban.** Implementing this hook is the structural enforcement of R1 on the pytest layer. R1 is now enforced three ways: collection-drop (#163), runtime refusal (R5), env gating (R3).
- **R3 to bypass env var is DISTINCT from `AEAT_LIVE_SUBMIT_ENABLED`.** Under no circumstance does setting the bypass env var unlock a live submission; `AEAT_LIVE_SUBMIT_ENABLED` remains the only thing that allows `dry_run=False`, and the bypass only controls whether `live_write` items are collected. A collected test still has to survive R5.
- **R5 untouched.** The runtime refusal in `SubmissionEngine.__init__` remains verbatim. The pytest hook is additive.

## 6. just test / just test-live integration

Current `justfile`:

```
test:
    uv run pytest

test-live:
    uv run pytest -m live
```

`test` relies on `addopts = "-v --tb=short -m 'not live'"` in pyproject. That default `-m 'not live'` cannot survive the split because `live` no longer exists as a marker.

Proposed:

```toml
# pyproject.toml
addopts = "-v --tb=short -m 'unit'"
markers = [
    "unit: deterministic tests with no external I/O",
    "live_read: opt-in tests that READ from a real external service",
    "live_write: opt-in tests that WRITE to a real external service - collection-banned",
    "domain_aeat_remote: exercises AEAT Sede Electronica read paths",
    "domain_submission: exercises the AEAT-write-capable submission boundary",
    "domain_financial_input: exercises financial ingest",
    "domain_local_state: exercises on-disk catalogues and local SQLite mirror",
    "domain_mediation: exercises workflow orchestration, LLM, i18n",
    "domain_infra: exercises project plumbing",
]
```

```justfile
test:
    uv run pytest

test-live:
    uv run pytest -m "unit or live_read"

test-live-read:
    uv run pytest -m "live_read"

test-domain DOMAIN:
    uv run pytest -m "unit and domain_{{DOMAIN}}"
```

**Invariant:** neither `just test` nor `just test-live` selects `live_write`. The only path that touches `live_write` is a direct interactive `pytest -m live_write` with all three bypass factors active, and even then the collected items still have to survive `SubmissionEngine`'s R5 refusal.

## 7. documentation impact

Files that require edits in the implementation PR:

- `pyproject.toml` - update `[tool.pytest.ini_options].addopts` and `markers` per section 6.
- `tests/conftest.py` - add the hook in section 5.2.
- `tests/test_marker_integrity.py` (new) - AST-based audit.
- `tests/README.md` (new) - canonical reference of the taxonomy plus the bypass incantation. Cross-link `#116` charter.
- `CLAUDE.md` - lines 1-4 describe the `unit` / `live` binary. Rewrite to describe the new taxonomy and reference `tests/README.md` + charter.
- `env/.env.example` - new entries for `AEAT_LIVE_WRITE_UNSAFE_BYPASS` and `AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM` with loud warnings. Must be mirrored in `src/aeat/config.py` `Settings` per repo-wide env-alignment invariant enforced by `tests/test_config.py`.
- `src/aeat/config.py` - add `aeat_live_write_unsafe_bypass: bool = False` and `aeat_live_write_unsafe_bypass_confirm: str = ""` with explicit warning descriptions.
- `justfile` - update `test`, `test-live`, add `test-live-read` and `test-domain`.
- `.claude/rules/*.md` - no direct updates required.
- `.vault/adr/2026-04-12-base-module-structure-adr.md` - may want a marginal update during the plan phase.

## 8. risks, gotchas, open questions

1. **Module-level pytestmark is additive.** A module that sets `pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]` and contains a function with `@pytest.mark.live_read` produces an item with BOTH `unit` and `live_read`. The hook raises `UsageError` because `{'unit', 'live_read'}` is two access markers. This is the desired behaviour - the plan must explicitly ban mixed-access modules and the enforcement falls out naturally.

2. **PytestUnknownMarkWarning.** Every new marker must be registered in `pyproject.toml [tool.pytest.ini_options].markers`, otherwise the suite emits warnings. The `markers` list in section 6 covers all nine markers.

3. **ruff / ty lint on pytestmark.** No known issue - `pytest` is already a dev dep. `ty` rules config does not flag `pytest.mark.*` attribute access.

4. **Per-function @pytest.mark.unit retained vs. module-level.** `#163` mandates module-level. The migration touches ~130 test files. The plan should do this as a single mechanical refactor PR: insert `pytestmark = [...]` at the top, delete per-function `@pytest.mark.unit` decorators. Parametrized tests (e.g. `src/aeat/domain/casillas/test_live_cli.py`) show that `@pytest.mark.parametrize` does not conflict with module-level `pytestmark`.

5. **Mixed-domain modules.** Rare but legal. `workflow/test_live.py` touches both workflow and submission; `sync/test_live_sync.py` touches sync + browser + auth. Plan should permit a list of domain markers and forbid zero-or-missing.

6. **Under-src conftest.** The project has no `src/aeat/conftest.py`. The hook in section 5.2 lives in `tests/conftest.py`. `pyproject.toml` has `testpaths = ["src", "tests"]`, and pytest walks upward from each test file looking for conftest files. A conftest at the repo root OR at `tests/` applies globally - BUT pytest only picks up `tests/conftest.py` because collected items under `src/aeat/...` share the rootdir. This needs verification; if broken, add a `src/aeat/conftest.py` that re-exports the hook, or promote the hook to a root-level `conftest.py`. **Verification step:** run `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/test_live_submission.py -m live_write` after tagging that file temporarily with `live_write` and confirm zero collection.

7. **Existing tests/test_config.py env-alignment.** Adding two new env vars to `Settings` without corresponding lines in `env/.env.example` fails `tests/test_config.py`. Plan must stage the three changes together.

8. **CI interaction.** `.github/workflows/ci.yml` runs `just test` (GHA is active on PRs despite historical notes). `just test` becomes `pytest -m unit` - effectively identical to today's `-m 'not live'` for inner-loop and CI runs. No CI infrastructure changes required.

9. **The live marker becomes undefined.** Any branch / WIP work that still references `@pytest.mark.live` warns. Plan should grep the tree and migrate in one shot; the pyproject migration removes the `live` marker registration in the same commit. Prose mentions (docstrings, ADRs) can stay but should get a trailing "(historical - now live_read)".

10. **Selective-domain runs have a subtle trap.** `pytest -m domain_aeat_remote` selects BOTH `unit` and `live_read` items in that domain because the access axis is orthogonal. Operators who want "unit tests of domain X" need `-m "unit and domain_x"`; the `test-domain` recipe wires that correctly.

## 9. out of scope

- Enabling a `live_write` test path. Charter R1 forbids it; this feature ships infrastructure that remains dormant.
- Splitting `domain_mediation` further (e.g. carving out a `domain_llm`). Revisit if/when LLM testing grows.
- Removing runtime `SubmissionEngine` R5 refusal. It remains mandatory.
- Retiring the bespoke `AEAT_LIVE_TESTS_GOOGLE` dual-opt-in on `tests/live/test_google_fixtures_smoke.py`. That gate is narrower than `live_read` and layered on top; it is orthogonal.

## 10. recommended next step

Advance to ADR (`vaultspec-adr`) bound to this research. The ADR must decide on:

- The exact six-entry domain taxonomy in section 3.2 (vs. the five in the issue).
- The collection-ban hook shape in section 5.2.
- Module-level `pytestmark` mandate + enforcement via `tests/test_marker_integrity.py`.
- Justfile recipe names (`test`, `test-live`, `test-live-read`, `test-domain`).
- Whether Google scratch round-trips stay `live_read` or get a separate marker.

After the ADR, a single-phase implementation plan with four tasks: migrate markers, install hook + integrity test, update docs/env, switch justfile recipes.
