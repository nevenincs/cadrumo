# ── Platform ─────────────────────────────────────────────────────────────────
set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

# List available recipes.
default:
    @just --list

# ── Bootstrap / install ──────────────────────────────────────────────────────

# Full bootstrap for a fresh clone or worktree:
# sync deps, install vaultspec, provision env/.env, then run gsuite-bootstrap.
bootstrap:
    uv sync
    uv run vaultspec-core install --upgrade
    just env-setup
    just gsuite-bootstrap

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

# Run the pytest suite (excludes @pytest.mark.live by default).
test:
    uv run pytest

# Run only the live smoke tests against real Google APIs.
test-live:
    uv run pytest -m live

# Run all pre-commit hooks via prek.
hooks:
    uv run prek run --all-files

# ── Google Cloud CLI ─────────────────────────────────────────────────────────

# Install or update the Google Cloud CLI.
[unix]
gcloud-install:
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
gcloud-install:
    #!pwsh
    $ErrorActionPreference = 'Continue'
    $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
    if ($gcloud) {
        $version = (& gcloud version 2>$null | Select-Object -First 1)
        Write-Host "gcloud found: $version"
        # The Windows installer ships a bundled Python that refuses to
        # self-update in non-interactive mode. Point CLOUDSDK_PYTHON at
        # the copied bundled interpreter before invoking `components update`.
        try {
            $bundled = (& $gcloud.Source components copy-bundled-python 2>$null | Select-Object -Last 1)
            if ($bundled) { $env:CLOUDSDK_PYTHON = $bundled.Trim() }
        } catch {
            Write-Host "copy-bundled-python failed - attempting update without override."
        }
        & $gcloud.Source components update --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Host "gcloud update failed (exit $LASTEXITCODE) - continue manually if needed."
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

# Deprecated alias for `gcloud-install` — kept so existing muscle memory works.
gcloud-setup: gcloud-install

# Authenticate gcloud and acquire ADC with the full Workspace scope set.
# Requires env/oauth-client.json (provisioned by `just gsuite-oauth-client`)
# because Google blocks Workspace scopes when requested against gcloud's
# built-in OAuth client. Reads GOOGLE_CLOUD_PROJECT from env/.env.
# Browser flows fire here.
[unix]
gcloud-auth:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v gcloud >/dev/null 2>&1; then
        echo "gcloud not on PATH — run 'just gcloud-install' first." >&2
        exit 1
    fi
    if [ ! -f env/.env ]; then
        echo "env/.env not found — run 'just env-setup' first." >&2
        exit 1
    fi
    if [ ! -f env/oauth-client.json ]; then
        echo "env/oauth-client.json not found — run 'just gsuite-oauth-client' first." >&2
        echo "Drive/Sheets/Docs scopes cannot be requested against gcloud's built-in OAuth client." >&2
        exit 1
    fi
    PROJECT=$(grep -E '^GOOGLE_CLOUD_PROJECT=' env/.env | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d '[:space:]')
    if [ -z "$PROJECT" ]; then
        echo "GOOGLE_CLOUD_PROJECT is empty in env/.env — set it before continuing." >&2
        exit 1
    fi
    echo "▶ gcloud auth login (browser will open)…"
    gcloud auth login --quiet
    echo "▶ gcloud config set project $PROJECT"
    gcloud config set project "$PROJECT" --quiet
    echo "▶ gcloud auth application-default login (with Drive/Sheets/Docs scopes via your OAuth client)…"
    gcloud auth application-default login \
        --client-id-file=env/oauth-client.json \
        --scopes=openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/documents
    echo "✔ gcloud + ADC ready for project $PROJECT"

[windows]
gcloud-auth:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
    if (-not $gcloud) {
        Write-Error "gcloud not on PATH - run 'just gcloud-install' first."
        exit 1
    }
    if (-not (Test-Path 'env/.env')) {
        Write-Error "env/.env not found - run 'just env-setup' first."
        exit 1
    }
    if (-not (Test-Path 'env/oauth-client.json')) {
        Write-Error "env/oauth-client.json not found - run 'just gsuite-oauth-client' first. Drive/Sheets/Docs scopes cannot be requested against gcloud's built-in OAuth client."
        exit 1
    }
    # Pre-set CLOUDSDK_PYTHON once so every gcloud subcommand uses the
    # bundled interpreter without prompting in non-interactive mode.
    try {
        $bundled = (& $gcloud.Source components copy-bundled-python 2>$null | Select-Object -Last 1)
        if ($bundled) { $env:CLOUDSDK_PYTHON = $bundled.Trim() }
    } catch {
        Write-Host "copy-bundled-python failed - continuing without override."
    }
    $line = (Get-Content env/.env | Where-Object { $_ -match '^GOOGLE_CLOUD_PROJECT=' })
    if (-not $line) {
        Write-Error "GOOGLE_CLOUD_PROJECT not present in env/.env"
        exit 1
    }
    $project = ($line -replace '^GOOGLE_CLOUD_PROJECT=', '').Trim().Trim('"').Trim("'")
    if (-not $project) {
        Write-Error "GOOGLE_CLOUD_PROJECT is empty in env/.env"
        exit 1
    }
    Write-Host "▶ gcloud auth login (browser will open)…"
    & $gcloud.Source auth login --quiet
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "▶ gcloud config set project $project"
    & $gcloud.Source config set project $project --quiet
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "▶ gcloud auth application-default login (with Drive/Sheets/Docs scopes via your OAuth client)…"
    & $gcloud.Source auth application-default login `
        --client-id-file=env/oauth-client.json `
        --scopes='openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/documents'
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "✔ gcloud + ADC ready for project $project"

# Enable every Google API the gsuite-bootstrap ADR commits to.
[unix]
gsuite-enable-apis:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v gcloud >/dev/null 2>&1; then
        echo "gcloud not on PATH — run 'just gcloud-install' first." >&2
        exit 1
    fi
    gcloud services enable \
        drive.googleapis.com \
        sheets.googleapis.com \
        docs.googleapis.com \
        cloudfunctions.googleapis.com \
        run.googleapis.com \
        storage.googleapis.com \
        iam.googleapis.com \
        serviceusage.googleapis.com
    echo "✔ APIs enabled."

[windows]
gsuite-enable-apis:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
    if (-not $gcloud) {
        Write-Error "gcloud not on PATH - run 'just gcloud-install' first."
        exit 1
    }
    try {
        $bundled = (& $gcloud.Source components copy-bundled-python 2>$null | Select-Object -Last 1)
        if ($bundled) { $env:CLOUDSDK_PYTHON = $bundled.Trim() }
    } catch {
        Write-Host "copy-bundled-python failed - continuing without override."
    }
    & $gcloud.Source services enable `
        drive.googleapis.com `
        sheets.googleapis.com `
        docs.googleapis.com `
        cloudfunctions.googleapis.com `
        run.googleapis.com `
        storage.googleapis.com `
        iam.googleapis.com `
        serviceusage.googleapis.com
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "✔ APIs enabled."

# Compose: install gcloud, authenticate, enable APIs, provision scratch, doctor.
gsuite-bootstrap:
    just gcloud-install
    just gcloud-auth
    just gsuite-enable-apis
    uv run aeat bootstrap
    uv run aeat doctor

# Run the doctor health check.
gsuite-doctor:
    uv run aeat doctor

# Walk through OAuth Desktop client provisioning.
gsuite-oauth-client:
    uv run aeat oauth-client init
