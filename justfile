# ── Platform ─────────────────────────────────────────────────────────────────
set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

# List available recipes.
default:
    @just --list

# ── Bootstrap / install ──────────────────────────────────────────────────────

# Full bootstrap for a fresh clone or worktree: sync deps + install vaultspec.
bootstrap:
    uv sync
    uv run vaultspec-core install

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

# Lint with ruff.
lint:
    uv run ruff check .

# Format with ruff.
fmt:
    uv run ruff format .

# Type-check with ty.
typecheck:
    uv run ty check src tests

# Run the pytest suite.
test:
    uv run pytest

# Run all pre-commit hooks via prek.
hooks:
    uv run prek run --all-files

# ── Google Cloud CLI ─────────────────────────────────────────────────────────

# Install or update the Google Cloud CLI.
[unix]
gcloud-setup:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v gcloud >/dev/null 2>&1; then
        echo "gcloud found: $(gcloud version 2>/dev/null | head -1)"
        gcloud components update --quiet || echo "gcloud update failed — continue manually if needed."
        exit 0
    fi
    if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
        brew install --cask google-cloud-sdk
        echo "Restart your shell to use gcloud."
        exit 0
    fi
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL https://sdk.cloud.google.com | bash -s -- --disable-prompts
        echo "Restart your shell or run: exec -l \$SHELL"
        exit 0
    fi
    echo "No supported installer (brew/curl) found." >&2
    echo "Install manually from https://cloud.google.com/sdk/docs/install" >&2
    exit 1

[windows]
gcloud-setup:
    #!pwsh
    $ErrorActionPreference = 'Continue'
    $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
    if ($gcloud) {
        $version = (& gcloud version 2>$null | Select-Object -First 1)
        Write-Host "gcloud found: $version"
        try {
            & gcloud components update --quiet
        } catch {
            Write-Host "gcloud update failed - continue manually if needed."
        }
        exit 0
    }
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & winget install --id Google.CloudSDK --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) {
            Write-Host "winget install returned $LASTEXITCODE - see https://cloud.google.com/sdk/docs/install-sdk#windows"
        } else {
            Write-Host "Restart your shell to use gcloud."
        }
        exit 0
    }
    Write-Host "winget not available. Install Google Cloud CLI manually:"
    Write-Host "  https://cloud.google.com/sdk/docs/install-sdk#windows"
    exit 1
