# ── Platform ─────────────────────────────────────────────────────────────────
set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

# List available recipes.
default:
    @just --list

# ── Bootstrap / install ──────────────────────────────────────────────────────

# Full bootstrap for a fresh clone or worktree: sync deps, install
# vaultspec, provision env/.env.
bootstrap:
    uv sync
    uv run vaultspec-core install --upgrade
    just env-setup

# Install / sync all runtime and dev dependencies via uv.
install:
    uv sync

# Alias for `install` — explicit name for CI clarity.
sync:
    uv sync

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

# Lint with ruff and enforce the #162 relative-imports mandate.
lint:
    uv run ruff check .
    uv run python scripts/check_relative_imports.py

# Format with ruff.
fmt:
    uv run ruff format .

# Type-check with ty.
typecheck:
    uv run ty check src tests

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
# See .vault/adr/2026-04-17-pytest-only-testing-adr.md (#15).
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

