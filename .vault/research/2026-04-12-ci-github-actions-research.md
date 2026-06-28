---
tags:
  - "#research"
  - "#ci-github-actions"
date: 2026-04-12
modified: '2026-04-12'
related: []
---
# CI GitHub Actions Research

## Survey of Actions

- **`astral-sh/setup-uv`**: Recommended. Official, fast, supports caching.
  - Latest version: `v5` (or `v5.3.1`).
  - Cache: `enable-cache: true` caches the uv environment based on `uv.lock`.
- **`taiki-e/install-action`**: Recommended for `just`.
  - Latest version: `v2`.
  - Usage: `uses: taiki-e/install-action@just`.
- **`actions/checkout`**: `v4`.
- **`actions/setup-python`**: Not strictly needed if `setup-uv` is used, but can be used to ensure a specific version. However, `uv` handles Python versions well. `setup-uv` can install Python too.
- **`actions/cache`**: Needed for `prek` if it doesn't have a dedicated action.
  - `prek` cache location:
    - Linux: `~/.cache/prek`
    - Windows: `~\AppData\Local\prek` (or use `env: LOCALAPPDATA\prek`)
  - Cache key: `prek-${{ runner.os }}-${{ hashFiles('prek.toml', '.pre-commit-config.yaml') }}`.

## Caching Strategy

- **uv**: Use `enable-cache: true` in `astral-sh/setup-uv`. It caches `~/.cache/uv`.
- **prek**: Use `actions/cache` on the `prek` cache directory.
  - Key: `prek-${{ runner.os }}-${{ hashFiles('prek.toml', '.pre-commit-config.yaml') }}`.
  - Paths:
    - Ubuntu: `~/.cache/prek`
    - Windows: `~\AppData\Local\prek`

## Cross-Platform Execution

- **Matrix**: `[ubuntu-latest, windows-latest]`.
- **Shell**:
  - Ubuntu: `bash`.
  - Windows: `pwsh`.
- **Just on Windows**: `justfile` sets `windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]`. This ensures `just` recipes run in PowerShell on Windows.

## Bootstrap Sequence

- **Direct vs Expanded**:
  - `just bootstrap` is NOT suitable for CI because it includes `gcloud-install`, `gcloud-auth`, etc., which are interactive or require secrets.
  - **CI Bootstrap**:
    1. `uv sync`
    2. `uv run vaultspec-core install --upgrade`
    3. `just env-setup` (to create `env/.env` from example)

## Gating and Permissions

- **Permissions**: `contents: read` is sufficient.
- **Concurrency**: `group: ${{ github.workflow }}-${{ github.ref }}`, `cancel-in-progress: true`.

## Unit Tests vs Live Tests

- **Policy**: `AEAT_LIVE_TESTS` must be UNSET.
- `just test` already excludes `@pytest.mark.live` by default (`addopts = "-v --tb=short -m 'not live'"` in `pyproject.toml`).
- Verified that `just test` runs unit tests only.

## Artifacts

- **JUnit report**: `pytest --junitxml=report.xml`.
- Use `actions/upload-artifact@v4` to save the report.

## Verification

- Need to verify `just lint`, `just typecheck`, `just test`, `just hooks` run cleanly locally.
- Current status: `just hooks` passed.
