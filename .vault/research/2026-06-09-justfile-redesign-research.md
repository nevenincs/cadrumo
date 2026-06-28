---
tags:
  - '#research'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-04-17-pytest-markers-adr]]'
---

# `justfile-redesign` research: Quality and Testing Harness

This research investigates the repository's testing taxonomy, hexagonal architecture enforcement, static quality tools, and recipe naming conventions to design a standardized, human-readable development and CI harness for the `justfile`.

---

## Findings

### 1. Pytest Testing Taxonomy (Markers, Flags, and Constraints)

The project's test suite uses a strict hexagonal marker system enforced statically by `src/aeat/tests/test_marker_integrity.py` and dynamically at collection time by `src/aeat/tests/_marker_hook.py`.

* **Active Marker Schema:**
  * **Execution Markers (exactly one required per test):** `unit` (deterministic, no external I/O), `integration` (deterministic, layer-crossing), and `aeat_live` (opt-in external service access).
  * **Hexagonal Layer Markers (exactly one required per test):** `hex_application`, `hex_core`, `hex_domain`, `hex_entrypoint`, `hex_inbound_adapter`, `hex_outbound_adapter`, and `hex_persistence_adapter`.
* **Configured pytest defaults (`pyproject.toml`):**
  * `addopts = "-v --tb=short -m 'unit' --strict-markers"`.
  * Running a bare `pytest` command defaults to executing only `unit`-marked tests.
  * Unregistered markers are blocked by the `--strict-markers` flag.
* **Bugs & Stale Declarations in Current `justfile`:**
  * **Stale Markers:** The current `justfile` test commands reference `live_read` and `live_write` markers (e.g. `pytest -m "unit or live_read"`). These markers were retired and are listed in `_FORBIDDEN_MARKERS` inside `src/aeat/tests/test_marker_integrity.py`.
  * **Silent Execution Drops:**
    * Running `just test-live` attempts to execute `unit or live_read`. Because no tests carry the forbidden `live_read` marker, this command silently executes only the unit tests, skipping the actual live tests (which are marked `aeat_live`).
    * Running `just test-live-read` uses `-m "live_read"`, selecting 0 tests.
    * Running `just test-live-write` uses `-m live_write`, which selects 0 tests and prints a warning.
  * **Unregistered Marker and Lane Bypass:**
    * The slow LibreOffice-based workbook parity tests in `src/aeat/domain/calculations/registry/tests/test_workbook_parity.py` are executed via `just test-workbook-parity` using `pytest -m workbook_parity`.
    * Because `workbook_parity` is listed in `_FORBIDDEN_MARKERS` in the integrity check, it cannot be registered in `pyproject.toml` or attached to tests.
    * The test file `test_workbook_parity.py` is marked with `pytest.mark.unit` to pass the integrity checks.
    * As a consequence, `just test-workbook-parity` runs 0 tests, while the slow LibreOffice tests (adding 60–90 seconds to runs) are executed by default in the standard `just test` unit suite.
* **Codebase Marker Mismatches and Integrity Contradictions (Discovered in Review):**
  * **The `"docs"` Marker Contradiction**: The `"docs"` marker was registered in `pyproject.toml` and actively used by 5 test files under `docs/tools/tests/` and `src/aeat/tests/test_docstring_core_struct_links.py`. However, it was mistakenly cataloged in `_FORBIDDEN_MARKERS` inside `test_marker_integrity.py`, causing test failures when running the AST checks. This is resolved by removing `"docs"` from `_FORBIDDEN_MARKERS` and adding it to `_EXPECTED_CONFIGURED_MARKERS`.
  * **`pytestmark` Placement Violation**: The file `src/aeat/tests/test_roundtrip_fixture_saturation.py` failed the AST-level placement check because a non-import variable assignment (`_TESTS_DIR = Path(__file__).parent`) appeared before the `pytestmark` list. This is resolved by moving `pytestmark` immediately after the imports.

---

### 2. Hexagonal Architecture and Boundary Enforcement

The codebase enforces strict decoupling between layers (`entrypoints`, `adapters`, `application`, `domain`, and `core`) using both static linter contracts and AST checkers.

* **Layer Dependency Order (Outer to Inner):**
  * `entrypoints` > `adapters` > `application` > `domain` > `core`.
  * Statically validated via `import-linter` (using `.importlinter`).
* **Domain Isolation (`domain-not-application` contract):**
  * Production domain modules are barred from importing from the `application` layer.
  * Dependency inversion is used for cross-layer references (e.g. `domain.contribuyente._keys` uses a `register_profile_keys()` injection point rather than importing wizard builders).
* **Core Layer Decoupling (`core-not-outer` contract):**
  * `core` is the innermost utility layer and must not import from `domain`, `application`, `adapters`, or `entrypoints`.
  * Interface contracts are defined as local Protocols (e.g. `SiteHealthStatusProtocol` inside `core/errors/__init__.py`) to break cycles with outer types.
* **Domain Peer Isolation (`no-renta-in-registry` contract):**
  * Peer packages under the `domain` namespace are decoupled. The registry calculations module (`aeat.domain.calculations`) must not import from the `renta` domain (`aeat.domain.renta`).
  * Inter-domain integration uses Protocol-based inversion: registry validation exposes a `CrossDomainSnapshotCheck` Protocol and a `register_cross_domain_snapshot_check()` hook; `renta` registers its concrete check at runtime.
* **Absolute Import Prohibition:**
  * Absolute imports of the package itself (`import aeat.*` or `from aeat.*`) are banned inside `src/aeat/`.
  * Statically audited by `scripts/check_relative_imports.py` using AST walks to prevent false positives.
  * Absolute imports are only allowed for `tests/` and tooling `scripts/` (outside the production package boundary).
* **Hexagonal Directory Test Parity:**
  * `test_marker_integrity.py` ensures that all test modules live under a parent `tests` directory and use the `test_` prefix (no underscore prefixes or suffix styles allowed).
  * `test_module_hex_marker_matches_owning_architecture_root` validates that test marker tags match their physical folder root (e.g. tests under `src/aeat/domain/` must carry `hex_domain`).

---

### 3. Verify-Only pre-commit hook policies (`prek.toml`)

Git pre-commit gates are configured to prevent local workspace mutations at commit time:
* **The "Verify-Only" Policy:**
  * No formatting or automatic fixers are run during the pre-commit stage.
  * **Rationale:** Automated refactoring during git pre-commit stashing frequently causes `git stash pop` conflicts in parallel workspaces.
  * Pre-commit checks are read-only (`ruff-check` and `ruff-format --check`).
* **Workstation pre-commit execution:**
  * The git hook is not installed globally (`prek install` is disabled).
  * Developers manually execute the validation suite via: `uv run --no-sync prek run --all-files`.
* **Manual Stages:**
  * Destructive or auto-mutating tasks (`vault-fix` executing `vault check all --fix` and `spec-check` running `spec doctor`) are relegated to the `manual` prek stage and must be called explicitly.

---

### 4. Naming Taxonomy & Readability Critique

The current `justfile` has a flat, ambiguous naming topology that hides command scope, side effects, and relationships:

* **The Ambiguity of Flat Verbs:**
  * `lint`: Confuses Python coding style checks with custom relative-import validation.
  * `fmt`: Ambiguous about which files or extensions are modified.
  * `typecheck`: Lacks indicators that it runs two separate tools (`ty` and `pyright`) on distinct packages.
  * `quality`: A generic name that does not convey that it acts as the primary local validation gate for Python code, imports, shims, and unit tests.
* **Lack of Read-Only vs. Mutation Separation:**
  * Developers cannot easily distinguish commands that check the code (read-only verification) from commands that actively modify files (such as formatting or linting auto-fixes).

#### Proposed Standardized Prefix Taxonomy
To improve readability and usability, the `justfile` will be refactored to use a prefix-based, self-documenting naming standard:

| Scope | Prefix | Description | Example Commands |
| :--- | :--- | :--- | :--- |
| **Verify (Read-only)** | `check-` | Runs static analyzers and linters in check mode. Never writes files. Failures exit non-zero. | `check-style`, `check-format`, `check-types`, `check-imports`, `check-dependencies`, `check-all` |
| **Fix (Mutate)** | `fix-` | Runs style formats and auto-fixers. Modifies files in place. | `fix-style`, `fix-format` |
| **Test Runners** | `test-` | Runs specific sub-suites of the test framework using markers or paths. | `test-unit`, `test-integration`, `test-live`, `test-smoke`, `test-coverage` |
| **Advisory Audits** | `audit-` | Runs informational debt detectors (complexity, duplication, dead-code) without blocking builds. | `audit-complexity`, `audit-dead-code`, `audit-duplication`, `audit-debt-dashboard` |
| **Environment Setup** | `env-` | Checks, verifies, and provisions the workstation toolchain and environment variables. | `env-setup`, `env-doctor`, `env-playwright` |
| **Database Migrations** | `db-` | Manages Alembic schema migrations and upgrades. | `db-migrate`, `db-upgrade` |

---

### 5. Semantic Search, RAG Ingestion, and Drift Discovery (vaultspec-rag)

The project leverages `vaultspec-rag` (a dense/sparse hybrid embedding vector database backed by Qdrant) as a core quality and architectural verification instrument:
* **Quality & Code Discovery Enforcement:**
  * Used to audit Axis 7 of the quality swarm: discovering semantic functionality-cluster overlap and enforcing canonical definition enrollment (as defined by `aeat-swarm-audit-cadence.md`).
  * Relies on loopback-bound daemon services to ensure fast semantic search responses without single-writer database lock conflicts.
  * **Programmatic Semantic Auditing**: In addition to manual searches, we can programmatically assert semantic invariants. A python script `scripts/audit_semantic.py` will define a set of canonical concept queries (e.g. `"round to two decimal places for currency"`, `"calculate IRPF retention base"`), target canonical/allowed paths, and prohibited paths. The script queries the RAG daemon on port 8766; if high-similarity codebase chunks (e.g. score > 0.75) are found in prohibited paths (e.g. domain logic duplicated inside adapters or entrypoints) or outside the declared canonical modules without an allowed exception, the script exits non-zero, failing the gate.
* **Vector Store & Indexing Lifecycle:**
  * Data lives under the gitignored path `.vault/data/search-data/`.
  * The HTTP RAG service (`vaultspec-rag server service start`) implements a filesystem watcher to incrementally re-index on modification, avoiding GPU/CPU-heavy manual full rebuilding during typical development loops.
* **Current Deficiencies:**
  * The current `justfile` lacks unified commands to inspect daemon status, trigger re-indexing when the watcher is disabled, run semantic queries, or manage the service lifecycle.
  * Only a single specialized command (`docs-changed-rag`) exists, leaving the RAG toolchain unintegrated with general quality audit dashboards.
* **Proposed Design:**
  * Introduce a dedicated RAG lifecycle and validation section in the `justfile`.
  * Define `check-rag` to verify daemon status and heartbeat.
  * Define `check-semantic` to run programmatic semantic invariant sweeps (`scripts/audit_semantic.py`) against the running daemon.
  * Define `fix-rag` (or `fix-rag-index`) to trigger a safe incremental re-index.
  * Define `env-rag-start` and `env-rag-stop` to manage daemon processes.
  * Define `audit-rag` to run semantic concept searches on-demand from the console.

---

### 6. Corpus, Modelo, and Calculation Engine Verification

The core calculations and models are validated by a large suite of registry tests:
* **Registry Test Base:** `src/aeat/domain/calculations/registry/tests/` contains `155` test files validating schemas, referential integrity, domain parameters, and formula runtimes.
* **Workbook Parity:** Parity scenario replays and conversions (`src/aeat/domain/calculations/registry/_workbook_parity.py`) run as slow integration/unit checks.
* **Tautology checks:** Evaluated by `test_tautology_gate.py` to prevent circular verification against synthetic expectations.
* **Proposed Design:** Group these under a dedicated section in the `justfile` (e.g. `── Registry and Correctness ──`).
  * Recipes should distinguish fast schema and integrity checks (`check-registry`) from slow workbook parity runs (`check-workbook-parity`).

---

### 7. Code Quality, Complexity, and Structure Audits

The codebase integrates several static analysis tools in the dev loop and advisory dashboards:
* **Formatting/Linting:** `ruff` (style, type hints, relative import mandates).
* **Type-Checking:** `ty` (primary) and `pyright` (strict on application/domain subpackages).
* **Dependency Auditing:** `deptry`.
* **Dead Code Scanning:** `vulture` (confidence threshold `80`).
* **Security Scanning:** `semgrep` (using auto rulesets).
* **Cognitive Complexity:** `radon` and `complexipy`.
* **Duplication:** Node-based `jscpd` (configured for python files).
* **Current Deficiencies:**
  * Complex Python heredocs for calculating complexity are embedded directly in the `justfile` recipes (e.g. `audit-complexity-production`).
  * No naming standard separates read-only quality checks (CI gates) from automatic repair tools.
* **Proposed Design:**
  * Group static checks under `── Code Quality ──`.
  * Establish a naming taxonomy: `check-` for read-only gates (e.g. `check-style`, `check-types`, `check-imports`, `check-security`) and `fix-` for formatting/repair tools (e.g. `fix-style`).
  * Prepare to relocate embedded Python heredoc scripts into standalone scripts (e.g. `scripts/audit_complexity.py`).
