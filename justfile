# ── Platform ─────────────────────────────────────────────────────────────────
set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

# Install or upgrade Google Cloud CLI
[unix]
gcloud-setup:
    #!/usr/bin/env bash
    set -euo pipefail
    if command -v gcloud &>/dev/null; then
        echo "gcloud found: $(gcloud version 2>/dev/null | head -1)"
        gcloud components update --quiet
    elif [ "$(uname)" = "Darwin" ]; then
        brew install google-cloud-cli
    else
        curl -fsSL https://sdk.cloud.google.com | bash -s -- --disable-prompts
        echo "Restart your shell or run: exec -l \$SHELL"
    fi

[windows]
gcloud-setup:
    #!pwsh
    if (Get-Command gcloud -ErrorAction SilentlyContinue) {
        Write-Host "gcloud found: $((gcloud version 2>$null)[0])"
        gcloud components update --quiet
    } else {
        winget install Google.CloudSDK --accept-source-agreements --accept-package-agreements
        Write-Host "Restart your shell to use gcloud"
    }
