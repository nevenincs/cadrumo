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
    uv run --no-sync python -c "import aeat; print(aeat.__file__)"
    uv run --no-sync ruff --version
    uv run --no-sync ty --version
    uv run --no-sync pyright --version
    uv run --no-sync lint-imports --version
    uv run --no-sync deptry --version
    uv run --no-sync vulture --version
    uv run --no-sync radon --version
    uv run --no-sync complexipy --help
    uvx --from semgrep semgrep --version
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
    @uv run --no-sync python -m dev.quality.quiet deptry src/aeat --known-first-party aeat --extend-exclude ".*test_.*[.]py" --extend-exclude ".*_test_.*[.]py" --extend-exclude ".*[\\/]tests[\\/].*"

# Verify codebase security posture using semgrep scans.
[unix]
check-security:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v semgrep >/dev/null 2>&1; then
        semgrep scan --quiet --config auto src/aeat
    else
        uvx --from semgrep semgrep scan --quiet --config auto src/aeat
    fi

[windows]
check-security:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    if (Get-Command semgrep -ErrorAction SilentlyContinue) {
        semgrep scan --quiet --config auto src/aeat
    } else {
        uvx --from semgrep semgrep scan --quiet --config auto src/aeat
    }

# Check if the RAG service daemon is running.
check-rag:
    @uv run --no-sync vaultspec-rag server status

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

# Run the unit test suite in parallel, ignoring workbook parity tests. Quiet progress; failures shown.
test-unit:
    @uv run pytest -q -n auto -m unit --ignore=src/aeat/domain/calculations/registry/tests/workbook_parity

# Run the unit test suite serially for reruns after a parallel failure.
test-unit-serial:
    @uv run pytest -q -m unit --ignore=src/aeat/domain/calculations/registry/tests/workbook_parity

# Run the integration test suite. Quiet progress; failures shown.
test-integration:
    @uv run pytest -q -m integration

# Run the live test suite. Quiet progress; failures shown.
test-live:
    @uv run pytest -q -m aeat_live

# Run the produce, verify, and export end-to-end smoke tests.
test-smoke:
    uv run pytest src/aeat/application/modelo/tests/test_file_flow_calculation.py src/aeat/application/modelo/tests/test_file_flow_verify.py src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_export.py -v

# Run the LibreOffice workbook parity tests.
test-workbook-parity:
    uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/workbook_parity/test_workbook_parity.py

# Run the unit test suite with coverage report and fail-under check. Quiet progress.
[unix]
test-coverage:
    @uv run pytest -q --cov=aeat --cov-report=term-missing --cov-fail-under=60

[windows]
test-coverage:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run pytest -q --cov=aeat --cov-report=term-missing --cov-fail-under=60
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
# src/aeat is named explicitly because a positional whitelist path
# overrides (not merges with) the config `paths`.
audit-dead-code:
    @uv run --no-sync vulture --config pyproject.toml src/aeat dev/vulture_whitelist.py

# Scan for copy-paste code duplication. Aggregate line + capped clone list.
audit-duplication:
    @npx --yes jscpd@4.2.0 src/aeat --format python --min-lines 6 --min-tokens 80 --max-size 250kb --ignore "**/test_*.py,**/_test_*.py,**/tests/**,**/_data/**" --gitignore --reporters console --noTips | uv run --no-sync python -m dev.audit.duplication

# Perform an on-demand semantic search query delegating to the running RAG daemon.
audit-rag QUERY:
    @uv run --no-sync vaultspec-rag search "{{QUERY}}" --port 8766 --timeout 45.0

# Run all advisory audits with section headers; tolerant of individual findings.
audit-debt-dashboard:
    @echo "=== complexity ==="
    -@just audit-complexity
    @echo "=== dead code ==="
    -@just audit-dead-code
    @echo "=== duplication ==="
    -@just audit-duplication
    @echo "=== security ==="
    -@just check-security

# ── Documentation ────────────────────────────────────────────────────────────

# Build changed narrative and API reference documents.
docs:
    uv run --no-sync python -m dev.docs.build docs/conf.py

# Build a single narrative page.
docs-page PAGE:
    uv run --no-sync python -m dev.docs.build --single-page {{PAGE}}

# Serve documentation on localhost with live reload on docs/ and src/aeat/ edits.
docs-serve PORT="8000":
    uv run --no-sync python -m dev.docs.serve --port {{PORT}} --open-browser

# Build documentation changed since a base commit.
docs-changed BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}}

# Build changed documentation with strict warnings-as-errors flags.
docs-changed-strict BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}} --strict

# Build changed documentation and update the vector index.
docs-changed-rag BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}} --rag-index

# Run docstring structure and Sphinx build checks. Quiet pytest progress.
docs-check:
    @uv run --no-sync pytest -q dev/docs/tests dev/docs/apidocs/tests src/aeat/tests/test_docstring_core_struct_links.py -m docs
    @uv run --no-sync doc8 docs
    @uv run --no-sync interrogate -c pyproject.toml src/aeat

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
        --repo-url wgergely/aeat \
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
        --repo-url wgergely/aeat `
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
    echo "  3. Update src/aeat/__init__.py __version__ to the new version."
    echo "  4. Prepend the release block to CHANGELOG.md (use the dry-run log as source)."
    echo "  5. Stage the four files:"
    echo "       git add .release-please-manifest.json pyproject.toml src/aeat/__init__.py CHANGELOG.md"
    echo "  6. Commit:"
    echo '       git commit -m "chore(release): vX.Y.Z"'
    echo "  7. Tag:"
    echo '       git tag -a vX.Y.Z -m "aeat vX.Y.Z"'
    echo "When ready (human decision only), push with:"
    echo "  git push origin main --tags"

[windows]
release-apply:
    #!pwsh
    $ErrorActionPreference = 'Stop'
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
    Write-Host "  3. Update src/aeat/__init__.py __version__ to the new version."
    Write-Host "  4. Prepend the release block to CHANGELOG.md (use the dry-run log as source)."
    Write-Host "  5. Stage the four files:"
    Write-Host "       git add .release-please-manifest.json pyproject.toml src/aeat/__init__.py CHANGELOG.md"
    Write-Host "  6. Commit:"
    Write-Host '       git commit -m "chore(release): vX.Y.Z"'
    Write-Host "  7. Tag:"
    Write-Host '       git tag -a vX.Y.Z -m "aeat vX.Y.Z"'
    Write-Host "When ready (human decision only), push with:"
    Write-Host "  git push origin main --tags"
