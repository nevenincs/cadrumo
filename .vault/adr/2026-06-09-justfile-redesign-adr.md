---
tags:
  - '#adr'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-06-09-justfile-redesign-research]]'
---

# `justfile-redesign` adr: Quality and Testing Harness Redesign | (**status:** `accepted`)

## Problem Statement

The repository's root `justfile` serves as the primary developer and CI/CD interface but suffers from structural disorder, naming ambiguity, and comments that violate source hygiene standards:
1. **Ambiguous Naming:** Flat, arbitrary verbs (such as `lint`, `fmt`, `typecheck`, and `quality`) conflate read-only style verification checks with active code format mutations and aggregated quality gates, confusing both human and agentic developers.
2. **Source Hygiene Violations:** Comments inside the `justfile` violate the `aeat-source-hygiene` project rule by hardcoding transient project-management metadata (such as issue IDs like `#476` or `aeat#10` and plan step numbers like `Step 7` or `Step 8`).
3. **Stale Testing Targets:** Test execution recipes refer to retired markers (`live_read` and `live_write`), resulting in silent test execution drops (e.g. `just test-live` runs only standard unit tests, skipping the actual live tests marked `aeat_live`).
4. **Lane Bypass:** Slow LibreOffice workbook parity tests run by default in the fast `unit` test suite because the `workbook_parity` marker is forbidden by `test_marker_integrity.py`. The `justfile`'s separate `test-workbook-parity` command runs 0 tests.
5. **Complex Inline Scripts:** Large Python complexity calculation scripts are embedded directly inside the `justfile` as heredocs rather than stored as clean, versioned scripts.

This ADR is persisted to define the standardized, self-documenting prefix taxonomy, clean comment hygiene rules, and pre-commit verify-only constraints for the redesigned harness.

---

## Considerations

* **Developer Usability:** Standardizing recipe names so their actions (read-only verification vs. file-writing modifications) and scopes (style, types, imports, dependencies) are immediately obvious.
* **Pre-commit Data Safety:** Preventing local git stash data-loss in `prek` pre-commit hooks by ensuring no file-writing auto-fixers are executed at commit time.
* **Registry Correctness Loop:** Separating fast semantic registry schema validations from slow LibreOffice workbook-parity runs to speed up the unit testing loop.
* **Cross-Platform Parity:** Abstracting Windows and Unix CLI differences cleanly using recipe attributes (`[windows]`, `[unix]`).

---

## Constraints

* **AST Integrity Checks:** The AST-based test marker verification gate `src/aeat/tests/test_marker_integrity.py` is the authority for allowed markers and is immutable. We must not attempt to register retired markers (such as `workbook_parity` or `live_read`) in `pyproject.toml` or attach them to tests.
* **Hexagonal Layering:** Production code boundaries and layer hierarchies defined in `.importlinter` must be fully respected and validated by the redesigned harness.
* **No Git Stashing at Commit Time:** The pre-commit workflow in `prek.toml` must remain strictly verify-only.

---

## Implementation

The root `justfile` will be refactored to implement a standardized prefix-based recipe taxonomy:

### 1. Recipe Prefix Taxonomy
* **`check-` (Verify, Read-Only):**
  * `check-style`: Runs `ruff check` on Python code.
  * `check-format`: Runs `ruff format --check` to verify code layout without modifying files.
  * `check-types`: Runs `ty check` (project custom wrapper) and `pyright` to type-check.
  * `check-imports`: Runs `lint-imports` to verify hexagonal boundary coupling.
  * `check-relative-imports`: Runs `scripts/check_relative_imports.py` to assert relative imports in package files.
  * `check-dependencies`: Runs `deptry` to inspect package declaration drift.
  * `check-security`: Runs `semgrep` vulnerability scans.
  * `check-rag`: Runs `vaultspec-rag server service status` (local workstation only; excluded from CI gates).
  * `check-semantic`: Runs `scripts/audit_semantic.py` to assert programmatic semantic invariants against the local RAG daemon (local workstation only; excluded from CI gates).
  * `check-pre-commit` (previously `hooks`): Runs prek verify-only hooks against all files.
  * `check-all`: Aggregates all fast static quality gates (excluding local-only RAG daemon and semantic checks).
* **`fix-` (Mutate, Write):**
  * `fix-style`: Runs `ruff check --fix` to auto-repair lint issues.
  * `fix-format`: Runs `ruff format` to format files.
  * `fix-rag`: Runs `vaultspec-rag index --type all --port 8766` to trigger an incremental vector re-indexing of code and vault files.
* **`test-` (Test Runner):**
  * `test-unit`: Runs only unit-marked tests (`pytest -m unit`), excluding the slow workbook parity tests via path ignores.
  * `test-integration`: Runs only integration-marked tests (`pytest -m integration`).
  * `test-live`: Runs only live-marked tests (`pytest -m aeat_live`).
  * `test-smoke`: Runs end-to-end integration flows (e.g. Model 130/303 flow tests).
  * `test-workbook-parity`: Runs only the workbook parity tests by targetting their path directly.
  * `test-coverage`: Runs unit tests with coverage reporting.
* **`audit-` (Advisory Debt Dashboard):**
  * `audit-complexity`: Evaluates code complexity.
  * `audit-dead-code`: Scans for dead code via `vulture`.
  * `audit-duplication`: Scans for duplication via `jscpd`.
  * `audit-rag QUERY`: Performs an on-demand semantic search query delegating to the running daemon via `--port 8766`.
  * `audit-debt-dashboard`: Aggregates all advisory audits in error-tolerant mode.
* **`env-` (Environment Setup):**
  * `env-setup`: Copies environment configuration templates.
  * `env-doctor`: Verifies active workstation toolchains.
  * `env-playwright`: Verifies browser automation drivers.
  * `env-rag-start`: Starts the background `vaultspec-rag` HTTP service daemon on loopback port 8766 with the filesystem watcher enabled.
  * `env-rag-stop`: Stops the background `vaultspec-rag` HTTP service daemon.
* **`db-` (Database Migrations):**
  * `db-migrate`: Generates Alembic schema files.
  * `db-upgrade`: Applies migrations.

### 2. Path-Based Isolation of Parity Tests
To prevent slow LibreOffice workbook tests from running during the default unit suite without violating `test_marker_integrity.py` restrictions, isolation will be achieved using pytest path exclusion:
* The `test-unit` command will explicitly ignore the workbook-parity test file:
  `pytest -m unit --ignore=src/aeat/domain/calculations/registry/tests/test_workbook_parity.py`
* The `test-workbook-parity` command will target the file directly by path:
  `pytest src/aeat/domain/calculations/registry/tests/test_workbook_parity.py`

### 3. Deprecations and Removals
* **Stale Commands:** `test-domain`, `test-live-read`, and `test-live-write` are retired and removed from the active command list.
* **Verification Hook Rename:** The `hooks` command is renamed to `check-pre-commit` to align with the read-only taxonomy.

### 4. Testing Framework and Marker Integrity Remediation
To ensure local and CI harness execution reliability, pre-existing taxonomy contradictions in the test framework are resolved:
* **`docs` Marker Conflict**: The `"docs"` marker is removed from `_FORBIDDEN_MARKERS` and added to `_EXPECTED_CONFIGURED_MARKERS` in `src/aeat/tests/test_marker_integrity.py` to reconcile it with its active use in 5 documentation-sweep files.
* **Statement-Order Repair**: The file `src/aeat/tests/test_roundtrip_fixture_saturation.py` is corrected by moving its `pytestmark` assignment immediately after imports to pass the AST ordering gate.

### 5. Comment Wording Standards
* **Removal of Cruft:** Delete all issue IDs (e.g. `#476`), PR links, and plan-specific step labels (e.g. `Step 7`, `Step 8`) from the comments.
* **Standardized Descriptions:** Recipes must have concise, imperative-mood comments explaining the command's prerequisites, dependencies, and side effects.

### 6. Script Extraction
* The inline Python heredocs inside the complexity audit recipes will be extracted into a dedicated Python script `scripts/audit_complexity.py` to keep the build wrapper readable.

### 7. Semantic Vector Index Lifecycle (vaultspec-rag)
* The vector index daemon is integrated into the build wrapper as a built-in quality control:
  * Running `check-rag` and `check-semantic` are included in environment diagnostics (e.g. `env-doctor` warning if offline) and optional local workstation checks, but are strictly excluded from general CI verification sweeps (`check-all`) to avoid failures where the daemon is unavailable.
  * Programmatic semantic assertions (`check-semantic` running `scripts/audit_semantic.py`) query the running daemon on port 8766. This script checks that core concepts (e.g., currency rounding, specific tax base calculations) only occur in their designated canonical paths and have not leaked into adapters or entrypoints.
  * Querying and indexing commands (`audit-rag`, `fix-rag`) explicitly pass `--port 8766` to delegate to the loopback-bound daemon, preserving database lock boundaries and avoiding competing lock contention on the local Qdrant instance.
  * Process management commands (`env-rag-start`, `env-rag-stop`) delegate to the loopback-bound daemon to prevent concurrent write-locks on the Qdrant database, ensuring the filesystem watcher is the single authoritative compiler of file modifications.

---

## Rationale

* **Clean Mental Model:** Placing the verb before the subject (e.g., `check-style` vs `fix-style`) tells the developer immediately if a command is read-only, mutating, or testing-oriented.
* **Active Marker Parity:** Aligning pytest executions with the active taxonomy (`unit`, `integration`, `aeat_live`) prevents silent drops and ensures live tests are executed when requested.
* **Isolation of slow tests:** Removing slow LibreOffice test modules from default unit sweeps by ignoring them in default unit runs and isolating them in a specific `test-workbook-parity` recipe.
* **Integrated Semantic Ingestion:** Exposing unified RAG daemon commands prevents port-conflict crashes and locks, making the semantic code/vault search engine a first-class citizen of developer workstation checks and quality swarm audits (Axis 7).

---

## Consequences

* **Gains:** Standardized development interface; eliminates silent test execution drops; speeds up the local unit testing loop; ensures vector index is kept warm and accessible for semantic audits.
* **Difficulties:** Requires updating pre-commit configurations, CI workflows, and developer documentation to match the new prefix-based command list.

---

## Codification candidates

* **Rule slug:** `justfile-recipe-taxonomy`
  **Rule:** Root justfile recipes must follow a standardized prefix taxonomy (`check-`, `fix-`, `test-`, `audit-`, `env-`, `db-`) and remain free of transient project-management metadata (such as issue IDs, PR numbers, or plan steps) in comments.
* **Rule slug:** `pre-commit-verify-only`
  **Rule:** Git pre-commit hooks configured in prek.toml must be verify-only and are barred from running file-mutating auto-fixers at commit time.
* **Rule slug:** `vaultspec-rag-daemon-control`
  **Rule:** Vector index mutations and queries must route through the running loopback service (port 8766) via the designated RAG harness recipes rather than triggering competing database lock holders.
