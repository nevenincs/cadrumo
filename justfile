# ── Platform ─────────────────────────────────────────────────────────────────
set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

# List available recipes.
default:
    @just --list

# ── Bootstrap / install ──────────────────────────────────────────────────────

# Full bootstrap for a fresh clone or worktree:
# sync deps, install vaultspec, provision env/.env, then run the Desktop OAuth wrapper chain.
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
    uv run pytest src/aeat/adapters/outbound/aeat/export/_formats/test_integration_kent_e2e.py src/aeat/adapters/outbound/aeat/export/_formats/test_integration_kent_303_e2e.py -v

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
# Uses the env-managed GOOGLE_OAUTH_CLIENT_JSON path written by
# `aeat auth init` / `aeat oauth-client init`, because Google blocks Workspace scopes when
# requested against gcloud's built-in OAuth client. Browser flows fire here.
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
    CLIENT_JSON=$(uv run python -c "from aeat.core.config import Settings; print(Settings().google_oauth_client_json)")
    if [ -z "$CLIENT_JSON" ]; then
        echo "GOOGLE_OAUTH_CLIENT_JSON is empty in env/.env — run 'uv run aeat auth init --path desktop-oauth-local-dev' first." >&2
        exit 1
    fi
    if [ ! -f "$CLIENT_JSON" ]; then
        echo "OAuth client JSON not found at $CLIENT_JSON — run 'uv run aeat auth init --path desktop-oauth-local-dev' first." >&2
        echo "Drive/Sheets/Docs scopes cannot be requested against gcloud's built-in OAuth client." >&2
        exit 1
    fi
    PROJECT=$(uv run python -c "from aeat.core.config import Settings; print(Settings().google_cloud_project)")
    if [ -z "$PROJECT" ]; then
        echo "GOOGLE_CLOUD_PROJECT is empty in env/.env — set it before continuing." >&2
        exit 1
    fi
    SCOPES=$(uv run python -c "from aeat.adapters.outbound.aeat.auth import ADC_LOGIN_SCOPE_CSV; print(ADC_LOGIN_SCOPE_CSV)")
    echo "▶ gcloud auth login (browser will open)…"
    gcloud auth login --quiet
    echo "▶ gcloud config set project $PROJECT"
    gcloud config set project "$PROJECT" --quiet
    echo "▶ gcloud auth application-default login (with Drive/Sheets/Docs scopes via your OAuth client)…"
    gcloud auth application-default login \
        --client-id-file="$CLIENT_JSON" \
        --scopes="$SCOPES"
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
    $clientJson = (& uv run python -c "from aeat.core.config import Settings; print(Settings().google_oauth_client_json)" | Select-Object -Last 1).Trim()
    if (-not $clientJson) {
        Write-Error "GOOGLE_OAUTH_CLIENT_JSON is empty in env/.env - run 'uv run aeat auth init --path desktop-oauth-local-dev' first."
        exit 1
    }
    if (-not (Test-Path $clientJson)) {
        Write-Error "OAuth client JSON not found at $clientJson - run 'uv run aeat auth init --path desktop-oauth-local-dev' first. Drive/Sheets/Docs scopes cannot be requested against gcloud's built-in OAuth client."
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
    $project = (& uv run python -c "from aeat.core.config import Settings; print(Settings().google_cloud_project)" | Select-Object -Last 1).Trim()
    if (-not $project) {
        Write-Error "GOOGLE_CLOUD_PROJECT is empty in env/.env"
        exit 1
    }
    $scopes = (& uv run python -c "from aeat.adapters.outbound.aeat.auth import ADC_LOGIN_SCOPE_CSV; print(ADC_LOGIN_SCOPE_CSV)" | Select-Object -Last 1).Trim()
    Write-Host "▶ gcloud auth login (browser will open)…"
    & $gcloud.Source auth login --quiet
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "▶ gcloud config set project $project"
    & $gcloud.Source config set project $project --quiet
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "▶ gcloud auth application-default login (with Drive/Sheets/Docs scopes via your OAuth client)…"
    & $gcloud.Source auth application-default login `
        --client-id-file=$clientJson `
        --scopes=$scopes
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "✔ gcloud + ADC ready for project $project"

# Enable the Google APIs the bootstrap requires (no billing needed).
# Workspace surfaces (Drive/Sheets/Docs) plus IAM and Service Usage.
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
        iam.googleapis.com \
        serviceusage.googleapis.com
    echo "✔ Required APIs enabled."

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
        iam.googleapis.com `
        serviceusage.googleapis.com
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "✔ Required APIs enabled."

# Enable the billing-gated APIs (Cloud Functions, Cloud Run, Cloud Storage).
# Requires an active billing account linked to the project.
[unix]
gsuite-enable-apis-billing:
    #!/usr/bin/env bash
    set -euo pipefail
    gcloud services enable \
        cloudfunctions.googleapis.com \
        run.googleapis.com \
        storage.googleapis.com
    echo "✔ Billing-gated APIs enabled."

[windows]
gsuite-enable-apis-billing:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
    & $gcloud.Source services enable `
        cloudfunctions.googleapis.com `
        run.googleapis.com `
        storage.googleapis.com
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "✔ Billing-gated APIs enabled."

# Compose: install gcloud, authenticate, enable APIs, provision scratch, doctor.
# This is the OAuth Desktop client / ADC path. Requires the operator to
# create the OAuth client in Cloud Console first via `aeat auth init`.
gsuite-bootstrap:
    just gcloud-install
    just gcloud-auth
    just gsuite-enable-apis
    uv run aeat bootstrap
    uv run aeat doctor

# Autonomous service-account-driven bootstrap. Creates a service account
# in the active gcloud project, grants it editor, downloads a key into
# env/sa.json, sets GOOGLE_APPLICATION_CREDENTIALS in env/.env, enables
# the required APIs, provisions scratch resources, and runs doctor.
# Requires gcloud already authenticated as a user with IAM admin on the
# project. No browser flow.
[unix]
gsuite-bootstrap-sa:
    #!/usr/bin/env bash
    set -euo pipefail
    PROJECT=$(grep -E '^GOOGLE_CLOUD_PROJECT=' env/.env | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d '[:space:]')
    if [ -z "$PROJECT" ]; then
        echo "GOOGLE_CLOUD_PROJECT is empty in env/.env" >&2
        exit 1
    fi
    SA="aeat-bootstrap@${PROJECT}.iam.gserviceaccount.com"
    if ! gcloud iam service-accounts describe "$SA" --project="$PROJECT" >/dev/null 2>&1; then
        gcloud iam service-accounts create aeat-bootstrap --project="$PROJECT" --display-name="AEAT bootstrap automation"
    fi
    gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role="roles/editor" --quiet
    if [ ! -f env/sa.json ]; then
        gcloud iam service-accounts keys create env/sa.json --iam-account="$SA" --project="$PROJECT"
    fi
    uv run python -c "from pathlib import Path; from aeat.core.env_io import write_env_vars; write_env_vars(Path('env/.env'), {'GOOGLE_AUTH_PATH': 'service-account-automation', 'GOOGLE_APPLICATION_CREDENTIALS': 'env/sa.json'})"
    just gsuite-enable-apis
    uv run aeat bootstrap
    uv run aeat doctor

[windows]
gsuite-bootstrap-sa:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
    if (-not $gcloud) { Write-Error "gcloud not on PATH"; exit 1 }
    try {
        $bundled = (& $gcloud.Source components copy-bundled-python 2>$null | Select-Object -Last 1)
        if ($bundled) { $env:CLOUDSDK_PYTHON = $bundled.Trim() }
    } catch {}
    $line = (Get-Content env/.env | Where-Object { $_ -match '^GOOGLE_CLOUD_PROJECT=' })
    if (-not $line) { Write-Error "GOOGLE_CLOUD_PROJECT not in env/.env"; exit 1 }
    $project = ($line -replace '^GOOGLE_CLOUD_PROJECT=', '').Trim().Trim('"').Trim("'")
    if (-not $project) { Write-Error "GOOGLE_CLOUD_PROJECT empty"; exit 1 }
    $sa = "aeat-bootstrap@$project.iam.gserviceaccount.com"
    & $gcloud.Source iam service-accounts describe $sa --project=$project 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $gcloud.Source iam service-accounts create aeat-bootstrap --project=$project --display-name="AEAT bootstrap automation"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    & $gcloud.Source projects add-iam-policy-binding $project --member="serviceAccount:$sa" --role="roles/editor" --quiet
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (-not (Test-Path 'env/sa.json')) {
        & $gcloud.Source iam service-accounts keys create env/sa.json --iam-account=$sa --project=$project
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    & uv run python -c "from pathlib import Path; from aeat.core.env_io import write_env_vars; write_env_vars(Path('env/.env'), {'GOOGLE_AUTH_PATH': 'service-account-automation', 'GOOGLE_APPLICATION_CREDENTIALS': 'env/sa.json'})"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    just gsuite-enable-apis
    uv run aeat bootstrap
    uv run aeat doctor

# Run the doctor health check.
gsuite-doctor:
    uv run aeat doctor

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

# Walk through OAuth Desktop client provisioning.
gsuite-oauth-client:
    uv run aeat auth init --path desktop-oauth-local-dev --no-acquire-cli-token --no-prepare-mcp

# Fetch the AEAT PKCS#12 certificate from Google Drive into credentials/.
# Requires `just gcloud-auth` to have been run (Drive scope on ADC).
# Usage: `just aeat-cert-fetch WOOTSCH_GERGELY_DOMOKOS_Y4113523X.p12`.
# After it succeeds, edit env/.env to set:
#   AEAT_LIVE_TESTS_ENABLED=1
#   AEAT_CERTIFICATE_PATH=<absolute path printed by this recipe>
#   AEAT_CERTIFICATE_PASSWORD_SECRET=<your cert passphrase>
[unix]
aeat-cert-fetch NAME:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f env/.env ]; then
        echo "env/.env not found — run 'just env-setup' first." >&2
        exit 1
    fi
    mkdir -p credentials
    uv run aeat drive fetch "{{NAME}}" --out "credentials/{{NAME}}"
    echo ""
    echo "next steps:"
    echo "  1. Edit env/.env and set AEAT_CERTIFICATE_PATH=$(pwd)/credentials/{{NAME}}"
    echo "  2. Set AEAT_CERTIFICATE_PASSWORD_SECRET=<passphrase>"
    echo "  3. Set AEAT_LIVE_TESTS_ENABLED=1"
    echo "  4. Run 'just test-live-read' to verify the live AEAT read path."

[windows]
aeat-cert-fetch NAME:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    if (-not (Test-Path 'env/.env')) {
        Write-Error "env/.env not found - run 'just env-setup' first."
        exit 1
    }
    if (-not (Test-Path 'credentials')) {
        New-Item -ItemType Directory -Path 'credentials' | Out-Null
    }
    uv run aeat drive fetch "{{NAME}}" --out "credentials/{{NAME}}"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $abs = (Resolve-Path "credentials/{{NAME}}").Path
    Write-Host ""
    Write-Host "next steps:"
    Write-Host "  1. Edit env/.env and set AEAT_CERTIFICATE_PATH=$abs"
    Write-Host "  2. Set AEAT_CERTIFICATE_PASSWORD_SECRET=<passphrase>"
    Write-Host "  3. Set AEAT_LIVE_TESTS_ENABLED=1"
    Write-Host "  4. Run 'just test-live-read' to verify the live AEAT read path."

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

# ── Google Workspace test fixtures ──────────────────────────────────────────
#
# Idempotent provisioning and teardown of the Drive/Sheets/Docs fixtures
# consumed by `@pytest.mark.live_read` tests. See scripts/README.md and
# .vault/adr/2026-04-12-google-fixtures-adr.md.

# Provision (or discover) every fixture in scripts/_fixture_catalogue.py,
# seed freshly-created ones, and persist their IDs into env/.env.
[unix]
google-fixtures-provision:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python scripts/provision_google_fixtures.py

[windows]
google-fixtures-provision:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run python scripts/provision_google_fixtures.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Permanently delete the fixture folder tree and clear its env footprint.
[unix]
google-fixtures-teardown:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python scripts/teardown_google_fixtures.py

[windows]
google-fixtures-teardown:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run python scripts/teardown_google_fixtures.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
