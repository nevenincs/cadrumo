# ── Platform ─────────────────────────────────────────────────────────────────
set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

# List available recipes.
default:
    @just --list

# ── Bootstrap / Install ──────────────────────────────────────────────────────

# Full bootstrap for a fresh clone or worktree: additively install deps,
# install vaultspec, provision env/.env. Avoid `uv sync` here because shared
# Windows worktrees can hold long-lived executable locks under `.venv/Scripts`.
bootstrap:
    just install
    uv run --no-sync vaultspec-core install --upgrade
    just env-setup
    -just doctor

# Verify the workstation for the services the active profile opts into: external
# dependency availability (Ollama vision, provider CLIs, Playwright) + the profile's
# capability posture, with the exact fix for any gap. Exits non-zero when an
# opted-in capability has a missing dependency. This is the product-side
# "is my workstation ready" check (the dev-toolchain probe is `just env-doctor`).
doctor:
    uv run --no-sync aeat config check

# Provision the optional external dependencies a fresh workstation needs for the
# capability surfaces: the Playwright browser binary now; Ollama + the vision model
# are guided by `just doctor` (run `ollama pull <model>` per its remediation rows).
provision: env-playwright
    @echo "Playwright Chromium installed. For on-host LLM vision, run 'ollama serve' and 'ollama pull qwen2.5vl:3b' (see 'just doctor')."

# Additively install runtime, workbook, and dev dependencies into the current
# venv. This is intentionally not an exact sync: it repairs missing packages and
# editable metadata without removing locked executables from other agents.
[windows]
install:
    uv pip install --python .venv/Scripts/python.exe --editable ".[workbook-windows]" --group dev

[unix]
install:
    uv pip install --python .venv/bin/python --editable ".[workbook-windows]" --group dev

# Alias for `install` — explicit name for CI clarity without exact pruning.
sync:
    just install

# Workstation CLI prerequisites for non-Python audit recipes.
[windows]
workstation-tools:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
        Write-Error 'scoop is required for workstation tool provisioning.'
        exit 1
    }
    foreach ($tool in @(
        @{Command = 'uv'; Package = 'uv'},
        @{Command = 'just'; Package = 'just'},
        @{Command = 'node'; Package = 'nodejs-lts'},
        @{Command = 'npx'; Package = 'nodejs-lts'}
    )) {
        if (-not (Get-Command $tool.Command -ErrorAction SilentlyContinue)) {
            scoop install $tool.Package
        }
    }

[unix]
workstation-tools:
    #!/usr/bin/env bash
    set -euo pipefail
    for tool in uv just node npx; do
        command -v "$tool" >/dev/null 2>&1 || {
            echo "$tool is required; install it with the workstation package manager." >&2
            exit 1
        }
    done

# ── Environment Setup and Doctor ─────────────────────────────────────────────

# Copy env/.env.example → env/.env if the latter is missing. No-op otherwise.
[unix]
env-setup:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f env/.env.example ]; then
        echo "env/.env.example not found — cannot provision env/.env" >&2
        exit 1
    fi
    if [ -f env/.env ]; then
        echo "env/.env already exists — leaving it untouched."
    else
        cp env/.env.example env/.env
        echo "Created env/.env from env/.env.example."
    fi

[windows]
env-setup:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    if (-not (Test-Path 'env/.env.example')) {
        Write-Error 'env/.env.example not found - cannot provision env/.env'
        exit 1
    }
    if (Test-Path 'env/.env') {
        Write-Host 'env/.env already exists - leaving it untouched.'
    } else {
        Copy-Item 'env/.env.example' 'env/.env'
        Write-Host 'Created env/.env from env/.env.example.'
    }

# Verify the local venv and workstation provide the full audit toolchain and RAG status.
env-doctor: env-playwright
    uv run --no-sync python -c "import cadrumo; print(cadrumo.__file__)"
    uv run --no-sync ruff --version
    uv run --no-sync ty --version
    uv run --no-sync pyright --version
    uv run --no-sync lint-imports --version
    uv run --no-sync deptry --version
    uv run --no-sync vulture --version
    uv run --no-sync radon --version
    uv run --no-sync complexipy --help
    uvx --from semgrep==1.168.0 semgrep --version
    npx --yes jscpd@4.2.0 --version
    just env-pip-check
    -just check-rag

[windows]
env-pip-check:
    uv pip check --python .venv/Scripts/python.exe

[unix]
env-pip-check:
    uv pip check --python .venv/bin/python

# Provision the Playwright Chromium browser binary (the post-install step that
# `uv sync` does not perform; the AEAT sede live-capture paths need it).
env-playwright:
    uv run --no-sync playwright install chromium

# Start the background vaultspec-rag HTTP service daemon on loopback port 8766.
env-rag-start:
    uv run --no-sync vaultspec-rag server start --updates --port 8766

# Stop the background vaultspec-rag HTTP service daemon.
env-rag-stop:
    uv run --no-sync vaultspec-rag server stop

# ── Static checks (Verify, Read-only) ────────────────────────────────────────

# Verify code style using ruff check. Silent on success; lists violations on failure.
check-style:
    @uv run --no-sync python -m dev.quality.quiet ruff check .

# Verify code format using ruff format --check. Silent on success; lists drift on failure.
check-format:
    @uv run --no-sync python -m dev.quality.quiet ruff format --check .

# Verify type correctness with ty (full src) and pyright (strict domain + application).
# Wrapper emits a signal-only summary grouped by rule and file; silent on success.
check-types:
    @uv run --no-sync python -m dev.quality.types

# Verify import structure and hexagonal boundaries. Silent on success.
check-imports:
    @uv run --no-sync python -m dev.quality.quiet lint-imports

# Verify that all test modules only use relative imports. Silent on success.
check-relative-imports:
    @uv run --no-sync python -m dev.quality.relative_imports

# Verify dependency declarations for drift or unused packages. Silent on success.
check-dependencies:
    @uv run --no-sync python -m dev.quality.quiet deptry src/cadrumo --known-first-party cadrumo --extend-exclude ".*test_.*[.]py" --extend-exclude ".*_test_.*[.]py" --extend-exclude ".*[\\/]tests[\\/].*"

# Cheap dependency-surface preflight: verify pyproject, optional-extra registry,
# and frozen core/all-extras/all-groups exports before any artifact work.
packaging-smoke-dependencies:
    @uv run --no-sync python -m dev.packaging.dependency_surface

# Verify the lightweight packaging preflight command contracts.
packaging-smoke-preflight-tests:
    @uv run --no-sync pytest dev/packaging/tests -q

# Cheap source-data preflight: fail before wheel, venv, or Docker work if a
# git-tracked shipped data file has been deleted from the worktree.
packaging-smoke-source:
    @uv run --no-sync python -m dev.packaging.source_preflight

# Construct the temporary Python wheel cohort once for the current smoke campaign.
# The immutable release-cohort builder replaces this transitional constructor.
packaging-build-python-cohort: packaging-smoke-source
    @uv run --no-sync python -m dev.packaging.python_cohort build --output var/packaging-smoke-cohort/python

# Consume the supplied wheel cohort, validate dependency surfaces, install into
# a fresh venv, and run the installed grounded tax-work oracle.
packaging-smoke-core: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_core --cohort-dir var/packaging-smoke-cohort/python

# Build the wheel, create a stdlib venv, install with plain pip, and run the
# same installed core CLI/resource/attachment/LLM smoke checks.
packaging-smoke-pip-core: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_pip_core --cohort-dir var/packaging-smoke-cohort/python

# Build the source distribution, inspect bundled data, install it with plain
# pip in a stdlib venv, and run the same installed core smoke checks.
packaging-smoke-sdist-core: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_sdist_core --cohort-dir var/packaging-smoke-cohort/python

# Build the wheel, install cadrumo[all] with plain pip in a stdlib venv, and
# verify every capability-gated optional Python package imports.
packaging-smoke-extras: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_extras --cohort-dir var/packaging-smoke-cohort/python

# Create a fresh uv project environment from the frozen lock with all extras
# and all dependency groups, then verify developer tools and imports start.
packaging-smoke-dev: packaging-smoke-source
    @uv run --no-sync python -m dev.packaging.smoke_dev

# Build the command-bearing wheel plus both mandatory cadrumo-data-* wheels,
# install the exact three-wheel cohort, and prove byte-identical source verification.
packaging-smoke-split: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_split_install --cohort-dir var/packaging-smoke-cohort/python

# Build the wheel, install it with the browser extra, provision Chromium in an
# isolated Playwright cache, and run the no-secret browser health check.
packaging-smoke-browser: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_browser --cohort-dir var/packaging-smoke-cohort/python

# Linux/container browser smoke: also install host browser dependencies.
packaging-smoke-browser-linux: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_browser --cohort-dir var/packaging-smoke-cohort/python --with-deps

# Linux host release-artifact smoke gates.
packaging-smoke-linux: packaging-smoke-dependencies packaging-smoke-preflight-tests packaging-smoke-core packaging-smoke-pip-core packaging-smoke-sdist-core packaging-smoke-extras packaging-smoke-browser-linux

# Build the wheel, mount only the wheel/probe into python:3.13-slim, and run
# the installed core CLI/resource smoke with pip inside Linux.
packaging-smoke-docker-core: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_docker --cohort-dir var/packaging-smoke-cohort/python

# Build the wheel, install cadrumo[browser] in python:3.13-slim, provision
# Chromium with Linux system dependencies, and run browser health.
packaging-smoke-docker-browser: packaging-build-python-cohort
    @uv run --no-sync python -m dev.packaging.smoke_docker --cohort-dir var/packaging-smoke-cohort/python --browser

# Fresh Linux image release-artifact smoke gates.
packaging-smoke-docker: packaging-smoke-dependencies packaging-smoke-preflight-tests packaging-smoke-docker-core packaging-smoke-docker-browser

# Run both installed public transports against the exact built cohort.
packaging-smoke-installed-oracles: packaging-build-python-cohort
    @uv run --no-sync pytest -q -n0 -m "integration and serial" dev/packaging/tests/test_installed_oracles.py

# Local release-artifact smoke gates that do not need host package-manager access.
# The campaign driver builds the cohort once and runs the flavor lanes
# concurrently (bounded pool; lanes are disk-disjoint), then the serial
# installed-oracles pass — same proofs as the former serial aggregate at a
# fraction of the wall time (the Windows leg measured 26.3 min serial).
packaging-smoke:
    @uv run --no-sync python -m dev.packaging.campaign --profile portable

# One CI invocation keeps every artifact and oracle lane on the same cohort bytes.
packaging-smoke-ci:
    @uv run --no-sync python -m dev.packaging.campaign --profile ci

# Per-push quick probe: cohort built once plus the single installed core smoke.
# Deliberately minimal (ten-minute per-push budget); every other flavor lane is
# a release-campaign proof carried by `packaging-smoke` / `packaging-smoke-ci`.
packaging-quick:
    @uv run --no-sync python -m dev.packaging.campaign --profile quick --skip-preflight

# ── Devcontainer ─────────────────────────────────────────────────────────────

# Build the reproducible dev image (.devcontainer/devcontainer.json + Dockerfile).
devcontainer-build:
    docker build -t cadrumo-devcontainer -f Dockerfile .

# Verify the dev image installs cleanly and its pre-baked toolchain works:
# the editable install imports, the unit suite collects, and Playwright
# Chromium launches headless with no further provisioning.
devcontainer-test: devcontainer-build
    docker run --rm cadrumo-devcontainer bash -lc "python -c 'import cadrumo; print(cadrumo.__file__)' && python -m pytest --collect-only -q -m unit && python -m playwright install --dry-run chromium"

# Verify codebase security posture using semgrep scans.
[unix]
check-security:
    #!/usr/bin/env bash
    set -euo pipefail
    uvx --from semgrep==1.168.0 semgrep scan --quiet --config auto src/cadrumo

[windows]
check-security:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uvx --from semgrep==1.168.0 semgrep scan --quiet --config auto src/cadrumo

# Check if the RAG service daemon is running.
check-rag:
    @uv run --no-sync vaultspec-rag server status --port 8766

# Run programmatic semantic audit checks using the local RAG daemon. Silent on success.
check-semantic:
    @uv run --no-sync python -m dev.audit.semantic

# Run all pre-commit hooks via prek. Silent on success; replays hook output on failure.
check-pre-commit:
    @uv run --no-sync python -m dev.quality.quiet uv run --no-sync prek run --all-files

# Excludes check-pre-commit (re-runs ruff + ty) and the local-only RAG/semantic checks.
# Run every fast static gate to completion; report only failures; silent on full pass.
check-all:
    @uv run --no-sync python -m dev.quality.suite

# ── Code mutations (Write) ──────────────────────────────────────────────────

# Auto-repair every lint violation that carries a safe fix (ruff check --fix).
fix-style:
    @uv run --no-sync ruff check --fix .

# Auto-sort imports only (ruff I-rule safe fixes).
fix-imports:
    @uv run --no-sync ruff check --select I --fix .

# Auto-format all python source files (ruff format).
fix-format:
    @uv run --no-sync ruff format .

# Action every automatically-fixable issue in one pass: safe lint fixes then formatting.
fix-all: fix-style fix-format

# Trigger incremental vector re-indexing via the loopback service.
fix-rag:
    @uv run --no-sync vaultspec-rag index --type all --port 8766

# ── Testing ──────────────────────────────────────────────────────────────────

pytest_workers := env_var_or_default("CADRUMO_PYTEST_WORKERS", "auto")

# Run the fast test-framework ratchets for discovery, markers, skip/xfail, mock/test-double, monkeypatch, broad raises, bare except, and tautology drift.
test-ratchets:
    @uv run --no-sync pytest -q -p no:cacheprovider -rs src/cadrumo/tests/test_test_inventory.py src/cadrumo/tests/test_marker_integrity.py src/cadrumo/tests/test_relative_imports_only.py src/cadrumo/tests/test_no_skip_xfail.py src/cadrumo/tests/test_mock_inventory.py src/cadrumo/tests/test_monkeypatch_inventory.py src/cadrumo/tests/test_no_broad_exception_raises.py src/cadrumo/tests/test_no_bare_except.py src/cadrumo/tests/test_no_tautology.py --tb=short

# Run the unit test suite in parallel, ignoring workbook parity tests. Quiet progress; failures shown.
test-unit:
    @uv run --no-sync pytest -q -rs -n {{pytest_workers}} --dist=loadfile -m unit --ignore=src/cadrumo/domain/calculations/registry/tests/workbook_parity

# Run the unit test suite serially for reruns after a parallel failure.
test-unit-serial:
    @uv run --no-sync pytest -q -rs -n0 -m unit --ignore=src/cadrumo/domain/calculations/registry/tests/workbook_parity

# Run the integration test suite in two lanes: the bulk in parallel (xdist,
# excluding serial-marked tests), then the isolation-sensitive `serial`-marked
# tests alone with no workers (-n0). The serial lane exists because a handful of
# tests mutate process-global state (the master-key-provider singleton) and
# flake under `-n auto` interleaving while passing cleanly in isolation.
test-integration:
    @uv run --no-sync pytest -q -m "integration and not serial"
    @uv run --no-sync pytest -q -m "integration and serial" -n0

# Run only the serial (isolation-sensitive) integration lane, no xdist workers.
test-integration-serial:
    @uv run --no-sync pytest -q -m "integration and serial" -n0

# Run the live test suite. Quiet progress; failures shown.
test-live:
    @uv run --no-sync pytest -q -m aeat_live

# Run the produce, verify, and export end-to-end smoke tests.
test-smoke:
    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_file_flow_calculation.py src/cadrumo/application/modelo/tests/test_file_flow_verify.py src/cadrumo/application/modelo/tests/test_file_flow_filing.py src/cadrumo/application/modelo/tests/test_export.py -v

# Run the LibreOffice workbook parity tests.
test-workbook-parity:
    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/workbook_parity/test_workbook_parity.py

# Run the unit test suite with coverage report and fail-under check. Quiet progress.
[unix]
test-coverage:
    @uv run --no-sync pytest -q --cov=cadrumo --cov-report=term-missing --cov-fail-under=60

[windows]
test-coverage:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run --no-sync pytest -q --cov=cadrumo --cov-report=term-missing --cov-fail-under=60
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# ── Advisory audits ──────────────────────────────────────────────────────────

# List every ty + pyright diagnostic verbatim (advisory; always exits 0).
audit-types:
    @uv run --no-sync python -m dev.quality.types --full

# Run complexity audits for production code.
audit-complexity:
    @uv run --no-sync python -m dev.audit.complexity

# Scan for dead code. The whitelist clears individually-justified
# false positives (contract-fixed signature params); see its docstring.
# src/cadrumo is named explicitly because a positional whitelist path
# overrides (not merges with) the config `paths`.
audit-dead-code:
    @uv run --no-sync vulture --config pyproject.toml src/cadrumo dev/vulture_whitelist.py

# Scan for copy-paste code duplication. Aggregate line + capped clone list.
# The runner owns the jscpd invocation AND its parsing, so this recipe and the
# health report's duplication dimension cannot drift apart or disagree.
audit-duplication:
    @uv run --no-sync python -m dev.audit.duplication

# Perform an on-demand semantic search query delegating to the running RAG daemon.
audit-rag QUERY:
    @uv run --no-sync vaultspec-rag search "{{QUERY}}" --port 8766 --timeout 45.0

# Run all advisory audits with section headers; tolerant of individual findings.
# Advisory-audit sibling of `check-all` (the fast static gates).
audit-all:
    @echo "=== complexity ==="
    -@just audit-complexity
    @echo "=== dead code ==="
    -@just audit-dead-code
    @echo "=== duplication ==="
    -@just audit-duplication
    @echo "=== security ==="
    -@just check-security

# Monthly code-health report: shadowing, duplication, layering, complexity,
# each classified red/amber/green. Composes the scanners above (plus
# lint-imports) into one contributor-facing verdict. Exits 1 if any
# dimension is RED; AMBER dimensions are advisory debt, not a gate.
audit-health-report:
    @uv run --no-sync python -m dev.audit.report

# Same report, machine-readable.
audit-health-report-json:
    @uv run --no-sync python -m dev.audit.report --json

# ── Documentation ────────────────────────────────────────────────────────────

# Build changed narrative and API reference documents.
docs:
    uv run --no-sync python -m dev.docs.build docs/conf.py

# Build a single narrative page.
docs-page PAGE:
    uv run --no-sync python -m dev.docs.build --single-page {{PAGE}}

# Serve documentation with live reload on docs/ and src/cadrumo/ edits. Binds every
# interface on the docs' canonical port 8788, claimed strictly: attaches to a
# healthy running server, evicts an invalid squatter, and errors rather than
# drifting to another port. The first serve builds before opening the browser.
docs-serve PORT="":
    uv run --no-sync python -m dev.docs.serve {{ if PORT == "" { "" } else { "--port " + PORT } }} --open-browser

# Build documentation changed since a base commit.
docs-changed BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}}

# Build changed documentation with strict warnings-as-errors flags.
docs-changed-strict BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}} --strict

# Build changed documentation and update the vector index.
docs-changed-rag BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}} --rag-index

# Extract gettext POT templates and refresh the es/ca/hu doc catalogues.
docs-gettext:
    uv run --no-sync python -m dev.docs.i18n

# Build the user-scope documentation in one language (es/en/ca/hu).
docs-lang LANG:
    uv run --no-sync python -m dev.docs.build --scope user --language {{LANG}}

# Build the user-scope documentation for every translation language.
docs-langs:
    uv run --no-sync python -m dev.docs.build --scope user --language es
    uv run --no-sync python -m dev.docs.build --scope user --language ca
    uv run --no-sync python -m dev.docs.build --scope user --language hu

# Run docstring structure and Sphinx build checks. Quiet pytest progress.
docs-check:
    @uv run --no-sync pytest -q dev/docs/tests dev/docs/apidocs/tests src/cadrumo/tests/test_docstring_core_struct_links.py -m docs
    @uv run --no-sync doc8 docs
    @uv run --no-sync interrogate -c pyproject.toml src/cadrumo

# Create or update the private Cadrumo docs stack.
docs-stack-deploy:
    uv run --no-sync python -m dev.deploy.docs_static_site provision --confirm provision-cadrumo-docs

# Build and publish the complete Cadrumo docs site.
docs-deploy:
    uv run --no-sync python -m dev.deploy.docs_static_site publish --confirm publish-cadrumo-docs

# Build and publish the Cadrumo landing page to the site root.
frontend-deploy:
    uv run --no-sync python -m dev.deploy.frontend_static_site publish --confirm publish-cadrumo-frontend

# ── Database migrations ──────────────────────────────────────────────────────

# Generate a new Alembic database migration file.
[unix]
db-migrate message:
    uv run alembic revision --autogenerate -m "{{message}}"

[windows]
db-migrate message:
    uv run alembic revision --autogenerate -m "{{message}}"

# Upgrade the database schema to the latest version.
[unix]
db-upgrade:
    uv run alembic upgrade head

[windows]
db-upgrade:
    uv run alembic upgrade head

# ── Release ──────────────────────────────────────────────────────────────────

# Audit-state readiness gate: version-surface parity, changelog sanity, the
# most recent packaging-smoke evidence, and (best-effort, via `gh`) no open
# priority:P0-blocker issue. Read-only — no outward action, ever. Exits 1 on
# a blocking failure; advisory failures (e.g. no packaging-smoke run yet,
# `gh` unavailable) are reported but do not fail the gate. Run this before
# trusting `just release-apply`. See docs/_release_checklist.yaml.
release-readiness:
    uv run --no-sync python -m dev.release.readiness

# Same gate, machine-readable.
release-readiness-json:
    uv run --no-sync python -m dev.release.readiness --json

# Print the rollback procedure for a released version that must be pulled.
# Read-only — never runs a destructive action; every step below is printed
# for a human to run deliberately. See RELEASING.md#rollback-procedure.
[unix]
release-rollback version:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Rollback procedure for cadrumo v{{version}} (RELEASING.md#rollback-procedure):"
    echo ""
    echo "1. Confirm the rollback trigger (data loss/corruption, security disclosure,"
    echo "   widespread regression, or a compatibility mis-computation) — see"
    echo "   docs/_release_checklist.yaml 'rollback.triggers'."
    echo "2. Revert the release commit and tag on main (human-run, never automated):"
    echo "     git revert --no-commit <release-commit-sha>"
    echo "     git commit -m 'revert: roll back v{{version}}'"
    echo "     git tag -a v{{version}}-rollback -m 'marks the rollback of v{{version}}'"
    echo "     git push origin main"
    echo "     git push origin refs/tags/v{{version}}-rollback"
    echo "3. Yank the bad version from PyPI so pip/uv skip it by default (this does"
    echo "   NOT delete the artifact; it only stops new installs from resolving it):"
    echo "     https://pypi.org/manage/project/cadrumo/release/{{version}}/  -> Options -> Yank release"
    echo "     https://pypi.org/manage/project/cadrumo-data-manuals/release/{{version}}/  -> Options -> Yank release"
    echo "     https://pypi.org/manage/project/cadrumo-data-official/release/{{version}}/  -> Options -> Yank release"
    echo "4. Publish a corrected patch release following the emergency hotfix cycle"
    echo "   time for the trigger category (docs/_release_checklist.yaml 'hotfix')."
    echo "5. Update docs/updates.md per its critical-updates contract and note the"
    echo "   rollback + corrected version in the GitHub Release notes for v{{version}}."

[windows]
release-rollback version:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    Write-Host "Rollback procedure for cadrumo v{{version}} (RELEASING.md#rollback-procedure):"
    Write-Host ""
    Write-Host "1. Confirm the rollback trigger (data loss/corruption, security disclosure,"
    Write-Host "   widespread regression, or a compatibility mis-computation) - see"
    Write-Host "   docs/_release_checklist.yaml 'rollback.triggers'."
    Write-Host "2. Revert the release commit and tag on main (human-run, never automated):"
    Write-Host "     git revert --no-commit <release-commit-sha>"
    Write-Host "     git commit -m 'revert: roll back v{{version}}'"
    Write-Host "     git tag -a v{{version}}-rollback -m 'marks the rollback of v{{version}}'"
    Write-Host "     git push origin main"
    Write-Host "     git push origin refs/tags/v{{version}}-rollback"
    Write-Host "3. Yank the bad version from PyPI so pip/uv skip it by default (this does"
    Write-Host "   NOT delete the artifact; it only stops new installs from resolving it):"
    Write-Host "     https://pypi.org/manage/project/cadrumo/release/{{version}}/  -> Options -> Yank release"
    Write-Host "     https://pypi.org/manage/project/cadrumo-data-manuals/release/{{version}}/  -> Options -> Yank release"
    Write-Host "     https://pypi.org/manage/project/cadrumo-data-official/release/{{version}}/  -> Options -> Yank release"
    Write-Host "4. Publish a corrected patch release following the emergency hotfix cycle"
    Write-Host "   time for the trigger category (docs/_release_checklist.yaml 'hotfix')."
    Write-Host "5. Update docs/updates.md per its critical-updates contract and note the"
    Write-Host "   rollback + corrected version in the GitHub Release notes for v{{version}}."

# Preview the next version release via dry-run.
[unix]
release:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v node >/dev/null 2>&1; then
        echo "node not on PATH — install Node.js to use release-please (npx)." >&2
        exit 1
    fi
    if ! command -v gh >/dev/null 2>&1; then
        echo "gh not on PATH — install the GitHub CLI and run 'gh auth login'." >&2
        exit 1
    fi
    if ! TOKEN=$(gh auth token 2>/dev/null); then
        echo "gh auth token failed — run 'gh auth login' first." >&2
        exit 1
    fi
    mkdir -p var/release
    LOG=var/release/release-please.log
    echo "▶ release-please release-pr --dry-run --debug (output → $LOG)"
    npx --yes release-please@16 release-pr \
        --token "$TOKEN" \
        --repo-url nevenincs/cadrumo \
        --target-branch main \
        --config-file release-please-config.json \
        --manifest-file .release-please-manifest.json \
        --dry-run \
        --debug \
        2>&1 | tee "$LOG"
    echo "✔ dry-run complete — review $LOG, then run 'just release-apply' if the proposal is correct."

[windows]
release:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Write-Error "node not on PATH - install Node.js to use release-please (npx)."
        exit 1
    }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Write-Error "gh not on PATH - install the GitHub CLI and run 'gh auth login'."
        exit 1
    }
    $token = & gh auth token 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $token) {
        Write-Error "gh auth token failed - run 'gh auth login' first."
        exit 1
    }
    New-Item -ItemType Directory -Force -Path var/release | Out-Null
    $log = 'var/release/release-please.log'
    Write-Host "▶ release-please release-pr --dry-run --debug (output → $log)"
    & npx --yes release-please@16 release-pr `
        --token $token `
        --repo-url nevenincs/cadrumo `
        --target-branch main `
        --config-file release-please-config.json `
        --manifest-file .release-please-manifest.json `
        --dry-run `
        --debug 2>&1 | Tee-Object -FilePath $log
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "✔ dry-run complete - review $log, then run 'just release-apply' if the proposal is correct."

# Apply the release changes locally.
[unix]
release-apply:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! uv run --no-sync python -m dev.release.readiness; then
        echo "audit-state gate blocked — resolve the failures above before 'just release-apply'." >&2
        exit 1
    fi
    if [ ! -f var/release/release-please.log ]; then
        echo "var/release/release-please.log missing — run 'just release' first." >&2
        exit 1
    fi
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [ "$BRANCH" != "main" ]; then
        echo "release-apply must run on main (current: $BRANCH)." >&2
        exit 1
    fi
    if [ -n "$(git status --porcelain)" ]; then
        echo "working tree is not clean — commit or stash first." >&2
        exit 1
    fi
    echo "Review var/release/release-please.log for the proposed next version."
    echo "Then, in this order:"
    echo "  1. Update .release-please-manifest.json to the new version."
    echo "  2. Update pyproject.toml [project].version to the new version."
    echo "  3. Update packaging/cadrumo_data_manuals/pyproject.toml [project].version."
    echo "  4. Update packaging/cadrumo_data_official/pyproject.toml [project].version."
    echo "  5. Update src/cadrumo/__init__.py __version__ to the new version."
    echo "  5b. Update packaging/mcpb/manifest.json \"version\" to the new version."
    echo "  6. Update both mandatory base dependency pins in pyproject.toml:"
    echo "       cadrumo-data-manuals==X.Y.Z"
    echo "       cadrumo-data-official==X.Y.Z"
    echo "  7. Prepend the release block to CHANGELOG.md (use the dry-run log as source)."
    echo "  8. Regenerate and verify the lock, then rerun the fail-closed version gate:"
    echo "       uv lock"
    echo "       uv lock --check"
    echo "       just release-readiness"
    echo "  9. Stage all eight release authorities:"
    echo "       git add .release-please-manifest.json pyproject.toml packaging/cadrumo_data_manuals/pyproject.toml packaging/cadrumo_data_official/pyproject.toml src/cadrumo/__init__.py packaging/mcpb/manifest.json CHANGELOG.md uv.lock"
    echo "  10. Commit:"
    echo '       git commit -m "chore(release): vX.Y.Z"'
    echo "  11. Tag:"
    echo '       git tag -a vX.Y.Z -m "Cadrumo vX.Y.Z"'
    echo "When ready (human decision only), push with:"
    echo "  git push origin main"
    echo "  git push origin refs/tags/vX.Y.Z"

[windows]
release-apply:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    & uv run --no-sync python -m dev.release.readiness
    if ($LASTEXITCODE -ne 0) {
        Write-Error "audit-state gate blocked - resolve the failures above before 'just release-apply'."
        exit 1
    }
    if (-not (Test-Path 'var/release/release-please.log')) {
        Write-Error "var/release/release-please.log missing - run 'just release' first."
        exit 1
    }
    $branch = (& git rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -ne 'main') {
        Write-Error "release-apply must run on main (current: $branch)."
        exit 1
    }
    $dirty = & git status --porcelain
    if ($dirty) {
        Write-Error "working tree is not clean - commit or stash first."
        exit 1
    }
    Write-Host "Review var/release/release-please.log for the proposed next version."
    Write-Host "Then, in this order:"
    Write-Host "  1. Update .release-please-manifest.json to the new version."
    Write-Host "  2. Update pyproject.toml [project].version to the new version."
    Write-Host "  3. Update packaging/cadrumo_data_manuals/pyproject.toml [project].version."
    Write-Host "  4. Update packaging/cadrumo_data_official/pyproject.toml [project].version."
    Write-Host "  5. Update src/cadrumo/__init__.py __version__ to the new version."
    Write-Host "  5b. Update packaging/mcpb/manifest.json 'version' to the new version."
    Write-Host "  6. Update both mandatory base dependency pins in pyproject.toml:"
    Write-Host "       cadrumo-data-manuals==X.Y.Z"
    Write-Host "       cadrumo-data-official==X.Y.Z"
    Write-Host "  7. Prepend the release block to CHANGELOG.md (use the dry-run log as source)."
    Write-Host "  8. Regenerate and verify the lock, then rerun the fail-closed version gate:"
    Write-Host "       uv lock"
    Write-Host "       uv lock --check"
    Write-Host "       just release-readiness"
    Write-Host "  9. Stage all eight release authorities:"
    Write-Host "       git add .release-please-manifest.json pyproject.toml packaging/cadrumo_data_manuals/pyproject.toml packaging/cadrumo_data_official/pyproject.toml src/cadrumo/__init__.py packaging/mcpb/manifest.json CHANGELOG.md uv.lock"
    Write-Host "  10. Commit:"
    Write-Host '       git commit -m "chore(release): vX.Y.Z"'
    Write-Host "  11. Tag:"
    Write-Host '       git tag -a vX.Y.Z -m "Cadrumo vX.Y.Z"'
    Write-Host "When ready (human decision only), push with:"
    Write-Host "  git push origin main"
    Write-Host "  git push origin refs/tags/vX.Y.Z"

# Aggregate every distribution-evidence row from the given CI run(s)' evidence
# drafts into var/distribution-install-readiness/ so `just release-readiness`
# can reach 12/12. Pass the packaging-smoke run id (mints python-<os> rows +
# the release cohort) plus any acquisition run ids (Scoop, Homebrew) - every
# run publishes its rows as assets on a draft release tagged
# evidence-<lane>-<run_id> (release-asset transport; Actions artifacts are
# retired). The four real client rows (claude-*) are minted locally by
# `python -m dev.packaging.emit_real_client_evidence ...` and already live in
# the dest.
[unix]
release-collect-evidence *run_ids:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "{{run_ids}}" ]; then
        echo "usage: just release-collect-evidence SMOKE_RUN_ID [SCOOP_RUN_ID HOMEBREW_RUN_ID ...]" >&2
        exit 1
    fi
    dest="var/distribution-install-readiness"
    mkdir -p "$dest"
    tmp="$(mktemp -d)"
    for run_id in {{run_ids}}; do
        tag=""
        for lane in smoke scoop homebrew claude; do
            candidate="evidence-$lane-$run_id"
            if gh release view "$candidate" --json tagName >/dev/null 2>&1; then
                tag="$candidate"
                break
            fi
        done
        if [ -z "$tag" ]; then
            echo "no evidence draft found for run $run_id (expected evidence-<lane>-$run_id)" >&2
            exit 1
        fi
        echo "collecting evidence rows from draft $tag"
        gh release download "$tag" --pattern '*.json' --dir "$tmp/$run_id" --clobber
    done
    n=0
    while IFS= read -r -d '' f; do cp "$f" "$dest/"; n=$((n + 1)); done \
        < <(find "$tmp" -name '*.json' ! -name 'evidence-manifest.json' -print0)
    rm -rf "$tmp"
    echo "collected $n record(s) into $dest (client-row records from emit_real_client_evidence are already local there)"

[windows]
release-collect-evidence *run_ids:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $ids = "{{run_ids}}".Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
    if ($ids.Count -eq 0) {
        Write-Error "usage: just release-collect-evidence SMOKE_RUN_ID [SCOOP_RUN_ID HOMEBREW_RUN_ID ...]"
        exit 1
    }
    $dest = "var/distribution-install-readiness"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $tmp = (New-Item -ItemType Directory -Path (Join-Path $env:TEMP ("collect-" + [Guid]::NewGuid().ToString("N")))).FullName
    foreach ($id in $ids) {
        $tag = $null
        foreach ($lane in @("smoke", "scoop", "homebrew", "claude")) {
            $candidate = "evidence-$lane-$id"
            & gh release view $candidate --json tagName *> $null
            if ($LASTEXITCODE -eq 0) { $tag = $candidate; break }
        }
        if (-not $tag) {
            Write-Error "no evidence draft found for run $id (expected evidence-<lane>-$id)"
            exit 1
        }
        Write-Host "collecting evidence rows from draft $tag"
        & gh release download $tag --pattern '*.json' --dir (Join-Path $tmp $id) --clobber
        if ($LASTEXITCODE -ne 0) { Write-Error "download failed for $tag"; exit 1 }
    }
    $n = 0
    Get-ChildItem -Path $tmp -Recurse -Filter *.json |
        Where-Object { $_.Name -ne "evidence-manifest.json" } |
        ForEach-Object { Copy-Item $_.FullName -Destination $dest -Force; $n++ }
    Remove-Item -Recurse -Force $tmp
    Write-Host "collected $n record(s) into $dest (client-row records from emit_real_client_evidence are already local there)"
