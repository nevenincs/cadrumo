# ── Platform ─────────────────────────────────────────────────────────────────
set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

# List available recipes.
default:
    @just --list

# ── Bootstrap / install ──────────────────────────────────────────────────────

# Full bootstrap for a fresh clone or worktree: additively install deps,
# install vaultspec, provision env/.env. Avoid `uv sync` here because shared
# Windows worktrees can hold long-lived executable locks under `.venv/Scripts`.
bootstrap:
    just install
    uv run --no-sync vaultspec-core install --upgrade
    just env-setup

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

# Verify the local venv and workstation provide the full audit toolchain.
tooling-doctor:
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
    just tooling-pip-check

[windows]
tooling-pip-check:
    uv pip check --python .venv/Scripts/python.exe

[unix]
tooling-pip-check:
    uv pip check --python .venv/bin/python

# ── Env-file provisioning ────────────────────────────────────────────────────

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

# ── Dev loop ─────────────────────────────────────────────────────────────────

# Lint with ruff and enforce the relative-imports mandate.
lint:
    uv run ruff check .
    uv run python scripts/check_relative_imports.py

# Format with ruff.
fmt:
    uv run ruff format .

# Type-check with ty (primary) and pyright (cross-checker on
# src/aeat/domain and src/aeat/application). Both must pass.
# Pyright config in pyrightconfig.json sets standard mode globally
# with selected strict rules on the two listed packages; the
# Unknown-family rules are deferred to a tracked ratchet workstream.
typecheck:
    uv run --no-sync ty check src
    uv run --no-sync pyright src/aeat/domain src/aeat/application

# Full-tree type audit. Advisory: use for ratchet discovery and type debt
# triage, not as the default daily hard gate until the baseline is clean.
typecheck-audit:
    uv run --no-sync ty check src --output-format concise
    uv run --no-sync pyright src/aeat --level warning --warnings

# Run the pytest suite (unit-only by default via pyproject addopts).
test:
    uv run pytest

# Run the produce → verify → export end-to-end smoke tests (Modelo 130 + 303).
# Used as the behavioural CI gate for the restructure (#476) per ADR
# Acceptance criterion 13: structural import-resolution alone is not
# sufficient proof of restructure correctness.
test-smoke-produce-verify-export:
    uv run pytest src/aeat/adapters/outbound/aeat/export/_formats/test_integration_operator_e2e.py src/aeat/adapters/outbound/aeat/export/_formats/test_integration_operator_303_e2e.py -v

# Verify every documented re-export shim still resolves its symbols
# (Step 8 acceptance precondition for the deterministic semver-bump rule).
verify-shims:
    uv run --no-sync python scripts/verify_shims.py

# Run the import-linter contract against the current layout.
# Pre-Step-7 reports "no matches" warnings for the future paths;
# post-Step-7 enforces the layered + independence + forbidden contracts.
lint-imports:
    uv run --no-sync lint-imports

# Hard local quality gate. Keeps required daily checks separate from the
# advisory quality-audit dashboard below.
quality:
    just lint
    just typecheck
    just lint-imports
    just verify-shims
    just test

# Structural hard checks that do not need the full unit suite.
audit-structure:
    just lint-imports
    just verify-shims
    uv run --no-sync python scripts/check_relative_imports.py

# Dependency declaration drift: missing, unused, transitive, and misplaced deps.
audit-deps:
    uv run --no-sync deptry src/aeat --known-first-party aeat --extend-exclude ".*test_.*[.]py" --extend-exclude ".*_test_.*[.]py" --extend-exclude ".*[\\/]tests[\\/].*"

# Dead-code discovery. Configuration lives in pyproject.toml.
audit-dead-code:
    uv run --no-sync vulture --config pyproject.toml

# Deprecation, private-usage, unused-function, and type-opportunity report.
audit-deprecation:
    uv run --no-sync pyright src/aeat/domain src/aeat/application --level warning --warnings

# Cyclomatic, maintainability, and cognitive-complexity report for production
# refactor planning. Thresholds are advisory until ratcheted by ADR.
audit-complexity:
    just audit-complexity-production

# Production-only complexity lane. Test ratchets are tracked separately so the
# production hotspot list is not crowded out by inventory-test maintenance debt.
[windows]
audit-complexity-production:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $exclude = 'src/aeat/test_*.py,src/aeat/**/test_*.py,src/aeat/**/_test_*.py,src/aeat/tests/*,src/aeat/_data/*'
    uv run --no-sync radon cc src/aeat -n C -s -a -e $exclude
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    uv run --no-sync radon mi src/aeat -s -e $exclude
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    @'
    from pathlib import Path

    from complexipy import file_complexity

    ROOT = Path("src/aeat")
    THRESHOLD = 20

    def is_production(path: Path) -> bool:
        parts = path.parts
        name = path.name
        if "_data" in parts or "tests" in parts:
            return False
        return not (name.startswith("test_") or name.startswith("_test_") or "_test_" in name)

    findings: list[tuple[int, str, str]] = []
    files = sorted(path for path in ROOT.rglob("*.py") if is_production(path))
    for path in files:
        result = file_complexity(str(path))
        for function in result.functions:
            if function.complexity > THRESHOLD:
                findings.append((function.complexity, str(path), function.name))

    findings.sort(reverse=True)
    print(f"complexipy production cognitive complexity: {len(files)} files analyzed")
    if findings:
        print(f"functions above {THRESHOLD}:")
        for complexity, path, function_name in findings[:80]:
            print(f"{complexity:>4}  {path}::{function_name}")
        raise SystemExit(1)
    print(f"no production functions exceed {THRESHOLD}")
    '@ | uv run --no-sync python -
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

[unix]
audit-complexity-production:
    #!/usr/bin/env bash
    set -euo pipefail
    exclude='src/aeat/test_*.py,src/aeat/**/test_*.py,src/aeat/**/_test_*.py,src/aeat/tests/*,src/aeat/_data/*'
    uv run --no-sync radon cc src/aeat -n C -s -a -e "$exclude"
    uv run --no-sync radon mi src/aeat -s -e "$exclude"
    uv run --no-sync python - <<'PY'
    from pathlib import Path

    from complexipy import file_complexity

    ROOT = Path("src/aeat")
    THRESHOLD = 20

    def is_production(path: Path) -> bool:
        parts = path.parts
        name = path.name
        if "_data" in parts or "tests" in parts:
            return False
        return not (name.startswith("test_") or name.startswith("_test_") or "_test_" in name)

    findings: list[tuple[int, str, str]] = []
    files = sorted(path for path in ROOT.rglob("*.py") if is_production(path))
    for path in files:
        result = file_complexity(str(path))
        for function in result.functions:
            if function.complexity > THRESHOLD:
                findings.append((function.complexity, str(path), function.name))

    findings.sort(reverse=True)
    print(f"complexipy production cognitive complexity: {len(files)} files analyzed")
    if findings:
        print(f"functions above {THRESHOLD}:")
        for complexity, path, function_name in findings[:80]:
            print(f"{complexity:>4}  {path}::{function_name}")
        raise SystemExit(1)
    print(f"no production functions exceed {THRESHOLD}")
    PY

# Top-level package ratchet-test complexity lane. This keeps inventory-test
# cognitive debt visible without mixing it into the production refactor queue.
[windows]
audit-complexity-tests:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    @'
    from pathlib import Path

    from complexipy import file_complexity

    ROOT = Path("src/aeat")
    THRESHOLD = 20

    findings: list[tuple[int, str, str]] = []
    files = sorted(ROOT.glob("test_*.py"))
    for path in files:
        result = file_complexity(str(path))
        for function in result.functions:
            if function.complexity > THRESHOLD:
                findings.append((function.complexity, str(path), function.name))

    findings.sort(reverse=True)
    print(f"complexipy top-level test cognitive complexity: {len(files)} files analyzed")
    if findings:
        print(f"functions above {THRESHOLD}:")
        for complexity, path, function_name in findings[:80]:
            print(f"{complexity:>4}  {path}::{function_name}")
        raise SystemExit(1)
    print(f"no top-level test functions exceed {THRESHOLD}")
    '@ | uv run --no-sync python -
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

[unix]
audit-complexity-tests:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run --no-sync python - <<'PY'
    from pathlib import Path

    from complexipy import file_complexity

    ROOT = Path("src/aeat")
    THRESHOLD = 20

    findings: list[tuple[int, str, str]] = []
    files = sorted(ROOT.glob("test_*.py"))
    for path in files:
        result = file_complexity(str(path))
        for function in result.functions:
            if function.complexity > THRESHOLD:
                findings.append((function.complexity, str(path), function.name))

    findings.sort(reverse=True)
    print(f"complexipy top-level test cognitive complexity: {len(files)} files analyzed")
    if findings:
        print(f"functions above {THRESHOLD}:")
        for complexity, path, function_name in findings[:80]:
            print(f"{complexity:>4}  {path}::{function_name}")
        raise SystemExit(1)
    print(f"no top-level test functions exceed {THRESHOLD}")
    PY

# Copy/paste duplication discovery. Uses the workstation Node toolchain so the
# Python uv bootstrap does not inherit a Node package dependency.
audit-duplication:
    npx --yes jscpd@4.2.0 src/aeat --format python --min-lines 6 --min-tokens 80 --max-size 250kb --ignore "**/test_*.py,**/_test_*.py,**/tests/**,**/_data/**" --gitignore --reporters console --noTips

# Semgrep security scan. Prefer a workstation executable, then fall back to uvx
# so a fresh worktree still has an authoritative just endpoint.
[unix]
audit-security:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v semgrep >/dev/null 2>&1; then
        semgrep scan --config auto src/aeat
    else
        uvx --from semgrep semgrep scan --config auto src/aeat
    fi

[windows]
audit-security:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    if (Get-Command semgrep -ErrorAction SilentlyContinue) {
        semgrep scan --config auto src/aeat
    } else {
        uvx --from semgrep semgrep scan --config auto src/aeat
    }

# Advisory dashboard for refactor planning. Each line is intentionally
# error-tolerant so all reports run even when one audit finds existing debt.
quality-audit:
    -just typecheck-audit
    -just audit-structure
    -just audit-deps
    -just audit-dead-code
    -just audit-deprecation
    -just audit-complexity
    -just audit-duplication
    -just audit-security

# Build the HTML documentation (furo) from Google-style docstrings plus
# the narrative pages under docs/. Output to docs/_build/html (gitignored).
docs:
    uv run --no-sync python docs/tools/build_changed_docs.py docs/conf.py

# Build one non-API documentation source file into the canonical HTML output
# without rebuilding generated API/autodoc pages.
docs-page PAGE:
    uv run --no-sync python docs/tools/build_changed_docs.py --single-page {{PAGE}}

# Build only documentation pages affected by local changes since BASE.
docs-changed BASE="HEAD":
    uv run --no-sync python docs/tools/build_changed_docs.py --base {{BASE}}

# Build explicit repository-relative docs/source paths in a noisy worktree.
docs-path +PATHS:
    uv run --no-sync python docs/tools/build_changed_docs.py {{PATHS}}

# Strict changed-page build: nitpicky warnings-as-errors, offline inventories.
docs-changed-strict BASE="HEAD":
    uv run --no-sync python docs/tools/build_changed_docs.py --base {{BASE}} --strict

# Build changed docs and refresh the resident vaultspec-rag service index.
docs-changed-rag BASE="HEAD":
    uv run --no-sync python docs/tools/build_changed_docs.py --base {{BASE}} --rag-index

# Documentation conformance gate: the docs-marked tests (nitpicky
# warnings-as-errors Sphinx build, module-to-stub correspondence, and CLI
# reference drift/conformance), doc8 reStructuredText formatting, and
# interrogate docstring coverage.
docs-check:
    uv run --no-sync pytest docs/tools/tests src/aeat/tests/test_docstring_core_struct_links.py -m docs
    uv run --no-sync doc8 docs
    uv run --no-sync interrogate -c pyproject.toml src/aeat

# Run the LibreOffice workbook-parity tests. Excluded from the default unit
# lane (adds 60-90s wallclock per soffice subprocess call). Requires
# LibreOffice / soffice on PATH.
test-workbook-parity:
    uv run --no-sync pytest -m workbook_parity

# Run unit plus live_read tests (requires AEAT_LIVE_TESTS_ENABLED=1 for live_read items).
test-live:
    uv run pytest -m "unit or live_read"

# Run only live_read tests.
test-live-read:
    uv run pytest -m "live_read"

# Run unit tests in a single domain, e.g. `just test-domain financial_input`.
test-domain DOMAIN:
    uv run pytest -m "unit and domain_{{DOMAIN}}"

# Documentation surface for @pytest.mark.live_write tests. Live AEAT writes
# are permanently forbidden and collection-dropped with no bypass.
[unix]
test-live-write:
    #!/usr/bin/env bash
    echo "WARNING: @pytest.mark.live_write tests are permanently collection-dropped; there is no bypass."
    uv run pytest -m live_write

[windows]
test-live-write:
    #!pwsh
    Write-Host "WARNING: @pytest.mark.live_write tests are permanently collection-dropped; there is no bypass."
    uv run pytest -m live_write

# Run the unit suite with coverage and enforce the fail-under floor.
[unix]
test-cov:
    uv run pytest --cov=aeat --cov-report=term-missing --cov-fail-under=60

[windows]
test-cov:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run pytest --cov=aeat --cov-report=term-missing --cov-fail-under=60
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Run the unit suite in parallel via pytest-xdist. Opt-in; never on live tests.
[unix]
test-parallel:
    uv run pytest -n auto

[windows]
test-parallel:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run pytest -n auto
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Run all pre-commit hooks via prek.
hooks:
    uv run prek run --all-files

# ── Database migrations (aeat#10) ────────────────────────────────────────────

# Generate a new Alembic revision from the current model metadata.
# Usage: just db-migrate message="add foo column"
[unix]
db-migrate message:
    uv run alembic revision --autogenerate -m "{{message}}"

[windows]
db-migrate message:
    uv run alembic revision --autogenerate -m "{{message}}"

# Apply every pending migration up to head.
[unix]
db-upgrade:
    uv run alembic upgrade head

[windows]
db-upgrade:
    uv run alembic upgrade head

# Run the Playwright doctor health check.
[unix]
playwright-doctor:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python -m aeat.entrypoints.cli.browser.health

[windows]
playwright-doctor:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run python -m aeat.entrypoints.cli.browser.health

# ── Release (local-only; see RELEASING.md + aeat#60) ────────────────────────
#
# release-please runs LOCALLY, never in GitHub Actions (Actions is
# permanently disabled on this repo). `just release` previews the next
# release in --dry-run mode. `just release-apply` guides the human
# operator through applying the bump + tagging, never pushing.

# Preview the next release. Dry-run only; never writes to the tree.
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

# Apply the previewed release locally. Human-gated; never pushes.
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
