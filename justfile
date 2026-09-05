# ── Platform ─────────────────────────────────────────────────────────────────
set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

# ── Dev-loop storage root ────────────────────────────────────────────────────
# Keep a developer's state inside the checkout instead of the platform
# user-data directory. This is DEV CONFIGURATION, not product behaviour: the
# application always defaults to the platform directory and never inspects the
# filesystem for a `pyproject.toml` or `.git` marker to decide otherwise. A
# tax-filing product does not classify its own installation, so the dev loop
# opts in through the ordinary override channel like any operator would.
export CADRUMO_LOCAL_STORAGE_ROOT := env_var_or_default(
    "CADRUMO_LOCAL_STORAGE_ROOT",
    justfile_directory() / "var" / "storage",
)

# List available recipes.
[group('meta')]
default:
    @just --list

# ── Bootstrap / Install ──────────────────────────────────────────────────────

# Full bootstrap for a fresh clone or worktree: additively install deps,
# install vaultspec, provision env/.env. Avoid `uv sync` here because shared
# Windows worktrees can hold long-lived executable locks under `.venv/Scripts`.
[doc('Full bootstrap for a fresh clone or worktree: install deps, install vaultspec, provision env/.env.')]
[group('bootstrap')]
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
[doc('Verify the workstation is ready: external dependency availability plus the active profile capability posture.')]
[group('bootstrap')]
doctor:
    uv run --no-sync aeat config check

# Provision the optional external dependencies a fresh workstation needs for the
# capability surfaces: the Playwright browser binary now; Ollama + the vision model
# are guided by `just doctor` (run `ollama pull <model>` per its remediation rows).
[doc('Provision the optional external dependencies a fresh workstation needs: the Playwright browser binary now.')]
[group('bootstrap')]
provision: env-playwright
    @echo "Playwright Chromium + chrome channel provisioned (verify with 'just playwright-doctor'). For on-host LLM vision, run 'ollama serve' and 'ollama pull qwen2.5vl:3b' (see 'just doctor')."

# Additively install runtime, workbook, and dev dependencies into the current
# venv. This is intentionally not an exact sync: it repairs missing packages and
# editable metadata without removing locked executables from other agents.
[doc('Additively install runtime, workbook, and dev dependencies into the current venv.')]
[group('bootstrap')]
[windows]
install:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $venv = (Resolve-Path '.venv').Path.TrimEnd('\')
    $mutexName = 'Local\cadrumo-install-' + [Convert]::ToHexString(
        [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($venv))
    )
    $mutex = [Threading.Mutex]::new($false, $mutexName)
    if (-not $mutex.WaitOne(0)) {
        Write-Error "Another dependency install already owns $venv."
        exit 1
    }
    try {
        $users = @(Get-CimInstance Win32_Process | Where-Object {
            ($_.ExecutablePath -and $_.ExecutablePath.StartsWith("$venv\", [StringComparison]::OrdinalIgnoreCase)) -or
            ($_.CommandLine -and $_.CommandLine.Contains("$venv\", [StringComparison]::OrdinalIgnoreCase))
        })
        if ($users) {
            $details = $users | ForEach-Object { "PID $($_.ProcessId): $($_.CommandLine)" }
            Write-Error ("Refusing to mutate a virtualenv used by live processes. Stop the owning sessions first:`n" + ($details -join "`n"))
            exit 1
        }
        uv pip install --python .venv/Scripts/python.exe --editable ".[workbook-windows]" --group dev
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        $mutex.ReleaseMutex()
        $mutex.Dispose()
    }

[doc('Additively install runtime, workbook, and dev dependencies into the current venv.')]
[group('bootstrap')]
[unix]
install:
    uv pip install --python .venv/bin/python --editable ".[workbook-windows]" --group dev

# Alias for `install` — explicit name for CI clarity without exact pruning.
[group('bootstrap')]
sync:
    just install

# Workstation CLI prerequisites for non-Python audit recipes.
[doc('Workstation CLI prerequisites for non-Python audit recipes.')]
[group('bootstrap')]
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

[doc('Workstation CLI prerequisites for non-Python audit recipes.')]
[group('bootstrap')]
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
[doc('Copy env/.env.example to env/.env if the latter is missing; no-op otherwise.')]
[group('environment')]
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

[doc('Copy env/.env.example to env/.env if the latter is missing; no-op otherwise.')]
[group('environment')]
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
[group('environment')]
env-doctor: env-playwright
    uv run --no-sync python -c "import cadrumo; print(cadrumo.__file__)"
    uv run --no-sync ruff --version
    uv run --no-sync ty --version
    uv run --no-sync pyrefly --version
    uv run --no-sync lint-imports --version
    uv run --no-sync deptry --version
    uv run --no-sync vulture --version
    uv run --no-sync radon --version
    uv run --no-sync complexipy --help
    uvx --from semgrep==1.168.0 semgrep --version
    npx --yes $(uv run --no-sync python -c "from dev.audit.duplication import _JSCPD_SPEC; print(_JSCPD_SPEC)") --version
    just env-pip-check
    -just check-rag

[doc('Verify installed packages satisfy their declared dependency constraints.')]
[group('environment')]
[windows]
env-pip-check:
    uv pip check --python .venv/Scripts/python.exe

[doc('Verify installed packages satisfy their declared dependency constraints.')]
[group('environment')]
[unix]
env-pip-check:
    uv pip check --python .venv/bin/python

# Provision both browser channels the codebase needs (the post-install step
# `uv sync` does not perform). Bundled Chromium: some tests launch it directly
# regardless of the configured channel. The `chrome` channel: AEAT browser
# automation is pinned to `channel: "chrome"` by ADR 2026-04-12-playwright-anti-
# bot-adr (anti-bot fingerprint reasons; bundled Chromium is the explicit
# fallback only if system Chrome breaks). Playwright does NOT download a private
# copy of Chrome for the `chrome` channel — it installs/detects the SYSTEM
# Google Chrome. On Linux this shells out to the OS package manager and
# typically needs root/apt access; a non-root Linux box may need
# `google-chrome-stable` pre-installed by an administrator, or rerun this
# recipe with elevation. Verify the result with `just playwright-doctor`.
[doc('Provision both Playwright browser channels the codebase needs (Chromium and the chrome channel).')]
[group('environment')]
env-playwright:
    uv run --no-sync playwright install chromium
    uv run --no-sync playwright install chrome

# Verify the local environment is correctly provisioned with the CONFIGURED
# Playwright browser channel (per `cadrumo_browser_channel`, default `chrome`)
# and its dependencies, per ADR 2026-04-12-playwright-anti-bot-adr. Performs a
# real headless launch-and-close of that channel (never hardcodes "chrome" —
# reads the live setting) and prints the exact remediation command on failure.
# Exits non-zero when the environment cannot satisfy the configured channel.
[doc('Verify the local environment is provisioned with the configured Playwright browser channel and its dependencies.')]
[group('environment')]
playwright-doctor:
    uv run --no-sync python -m dev.env.playwright_doctor

# Start the background vaultspec-rag HTTP service daemon on loopback port 8766.
[group('environment')]
env-rag-start:
    uv run --no-sync vaultspec-rag server start --updates --port 8766

# Stop the background vaultspec-rag HTTP service daemon.
[group('environment')]
env-rag-stop:
    uv run --no-sync vaultspec-rag server stop

# Report what the temp directory is holding, and which sessions still own it. Deletes nothing.
[group('environment')]
env-temp-report:
    uv run --no-sync python -m dev.env.temp_reaper

# Reclaim the session scratchpads the report judged abandoned. Read the report first.
[group('environment')]
env-temp-reap:
    uv run --no-sync python -m dev.env.temp_reaper --apply

# ── Static checks (Verify, Read-only) ────────────────────────────────────────

# Verify code style using ruff check. Silent on success; lists violations on failure.
[group('static-checks')]
check-style:
    @uv run --no-sync python -m dev.quality.quiet ruff check .

# Verify code format using ruff format --check. Silent on success; lists drift on failure.
[group('static-checks')]
check-format:
    @uv run --no-sync python -m dev.quality.quiet ruff format --check .

# Verify type correctness with ty (full src) and pyrefly (strict domain + application).
# Wrapper emits a signal-only summary grouped by rule and file; silent on success.
[doc('Verify type correctness with ty, pyrefly, and basedpyright. Silent on success.')]
[group('static-checks')]
check-types:
    @uv run --no-sync python -m dev.quality.types

# Verify import structure and hexagonal boundaries. Silent on success.
[group('static-checks')]
check-imports:
    @uv run --no-sync python -m dev.quality.quiet lint-imports

# Verify that all test modules only use relative imports. Silent on success.
[group('static-checks')]
check-relative-imports:
    @uv run --no-sync python -m dev.quality.relative_imports

# Verify the core facade, import-edge, and no-shim architecture invariants.
[group('static-checks')]
check-architecture:
    @uv run --no-sync pytest -q -n0 dev/tests/test_cross_package_private_imports.py dev/tests/test_closed_vocabulary_canonicalization.py dev/tests/test_import_edge_integrity_gate.py dev/tests/test_facade_export_gate.py

# Verify no shipped module has become unreachable from the declared entrypoints.
# The baseline in dev/quality/unreachable_module_ratchet.toml may only shrink;
# a new unreachable module fails rather than being absorbed into it.
[group('static-checks')]
check-unreachable-ratchet:
    @uv run --no-sync python -m dev.quality.unreachable_module_ratchet

# Verify no reachable module started carrying unused symbols, and no orphaned
# test module appeared. The baseline in dev/quality/unused_symbol_ratchet.toml
# may only shrink; a module that grows, or one absent from the file, fails
# rather than being absorbed. Covers the population the module ratchet cannot
# see: a symbol inside a module that is itself reachable.
[group('static-checks')]
check-unused-symbol-ratchet:
    @uv run --no-sync python -m dev.quality.unused_symbol_ratchet

# Verify no shipped module gained a citation of a Vaultspec rule slug. The
# vault is removable scaffolding, so a docstring naming a rule reads as a
# reference to nothing once the harness is absent. The baseline in
# dev/quality/vault_citation_ratchet.toml may only shrink; retiring the
# existing citations needs an explicit repository-wide migration, but a NEW
# one fails here.
[group('static-checks')]
check-vault-citation-ratchet:
    @uv run --no-sync python -m dev.quality.vault_citation_ratchet

# Verify no shipped module gained a docstring reference that names nothing.
# A Sphinx role claims the named symbol exists; nothing checked that, so the
# claim outlived the symbol 87 times. The baseline in
# dev/quality/docstring_reference_ratchet.toml holds the four that are
# CORRECT because they name something absent -- sentences about what a module
# consolidated, naming code that is properly gone.
[group('static-checks')]
check-docstring-reference-ratchet:
    @uv run --no-sync python -m dev.quality.docstring_reference_ratchet

# Verify every persistence surface a product command READS still has a
# production writer. The baseline in dev/quality/write_path_backlog.toml may
# only shrink; a newly writerless store fails rather than being absorbed.
[group('static-checks')]
check-write-path-backlog:
    @uv run --no-sync python -m dev.quality.write_path_backlog

# Verify dependency declarations for drift or unused packages. Silent on success.
[group('static-checks')]
check-dependencies:
    @uv run --no-sync python -m dev.quality.quiet deptry src/cadrumo src/cadrumo_harness dev/registry --known-first-party cadrumo --known-first-party cadrumo_harness --known-first-party dev --non-dev-dependency-groups registry --extend-exclude ".*test_.*[.]py" --extend-exclude ".*_test_.*[.]py" --extend-exclude ".*[\\/]tests[\\/].*"

# Verify format, style and relative-import shape over ONLY the paths a change
# touches. A seconds-long preflight to run before committing, where the whole-tree
# gates are too slow to run between batches and report drift owned by other writers.
#
# Reads `git diff --name-only` and nothing else: it manipulates no git state and
# rewrites no file, so it is safe to run at any time in a shared worktree. It is
# deliberately NOT installed as a commit hook -- see the policy at the top of
# `prek.toml`. Repair stays a separate explicit step (`just fix-all`).
#
# Partial by design: check-dependencies is a whole-tree usage-versus-declaration
# predicate that does not decompose to changed paths, and stays with check-all.
[doc('Verify format, style and relative imports over only the paths changed since BASE.')]
[group('static-checks')]
check-changed BASE="HEAD":
    @uv run --no-sync python -m dev.quality.changed_paths {{BASE}}

# Cheap dependency-surface preflight: verify pyproject, optional-extra registry,
# and frozen core/all-extras/all-groups exports before any artifact work.
[doc('Cheap dependency-surface preflight: verify pyproject, optional-extra registry, and frozen exports.')]
[group('packaging')]
packaging-smoke-dependencies:
    @uv run --no-sync python -m dev.packaging.dependency_surface

# Verify the packaging preflight command contracts. The marker expression is
# stated explicitly and kept byte-identical to the static lane in
# `.github/workflows/ci.yml`, so this local gate and CI select the same set.
# `dev/packaging/tests` is mixed-marker: inheriting the default `-m 'unit and
# ...'` expression from pyproject silently deselected every integration
# contract in it -- including the modules named for the packaging-smoke, Scoop,
# Homebrew, and Docker workflows the campaign driver (`dev.packaging.campaign`)
# runs this preflight ahead of -- and still exited zero.
# The excluded `serial` tests are not dropped silently: every one of them is
# owned by `packaging-smoke-serial`, the installed-oracle cohort additionally by
# the narrower `packaging-smoke-installed-oracles`, and the serving-path
# benchmark by the `-m perf` lane in `.github/workflows/ci-full.yml`. Guarded by
# `dev/packaging/tests/test_preflight_recipe_selection.py`.
[doc('Verify the packaging preflight command contracts (dependency surface, source data, Docker/Scoop/Homebrew workflows).')]
[group('packaging')]
packaging-smoke-preflight-tests:
    @uv run --no-sync pytest -q -m "unit or (integration and not serial)" dev/packaging/tests

# Cheap source-data preflight: fail before wheel, venv, or Docker work if a
# git-tracked shipped data file has been deleted from the worktree.
[doc('Cheap source-data preflight: fail before wheel, venv, or Docker work if a shipped data file was deleted.')]
[group('packaging')]
packaging-smoke-source:
    @uv run --no-sync python -m dev.packaging.source_preflight

# Operator-run: regenerate the committed AEAT manual PDF corpus-text sidecars
# after a corpus PDF changes. The sidecars are load-bearing for registry
# evidence validation, so re-run this and commit the regenerated JSON.
[doc('Operator-run: regenerate the committed AEAT manual PDF corpus-text sidecars after a corpus PDF changes.')]
[group('mutations')]
regenerate-corpus-text:
    @uv run --no-sync python -m dev.corpus.extract_manual_corpus_text

# Freshness gate: fail (without writing) when any committed corpus-text sidecar
# is stale or missing against its source PDF.
[doc('Freshness gate: fail when any committed corpus-text sidecar is stale or missing against its source PDF.')]
[group('static-checks')]
check-corpus-text:
    @uv run --no-sync python -m dev.corpus.extract_manual_corpus_text --check

# Build every distribution the release publishes, then refuse any file the index
# would reject on size. Same two operations the publish workflow performs, in the
# same order, so the local run and the hosted one can disagree only about the host.
[doc('Build every published distribution and refuse any file over the index cap.')]
[group('packaging')]
packaging-distributions:
    @uv build --out-dir var/distributions .
    @uv build --out-dir var/distributions packaging/cadrumo_data_manuals
    @uv build --out-dir var/distributions packaging/cadrumo_data_official
    @uv run --no-sync python -m dev.packaging.distribution_cap --directory var/distributions

# Run source and binary compatibility probes for every row in the checked-in
# runtime inventory. The release cohort is built once; binary rows consume its
# sealed bytes and never rebuild per runtime. Stable failures are blocking,
# while the inventory's prerelease canary remains visible as advisory evidence.
[doc('Run inventory-driven source and binary compatibility probes for every declared Python runtime.')]
[group('packaging')]
[unix]
python-compatibility:
    #!/usr/bin/env bash
    set -euo pipefail
    run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
    run_root="var/python-runtime-compatibility/runs/$run_id"
    cohort="$run_root/cohort"
    mkdir -p "$run_root"
    commit="$(git rev-parse HEAD)"
    uv run --no-sync python -m dev.packaging.release_cohort build \
      --output "$cohort" \
      --expected-commit "$commit"
    failed=0
    rows="$(uv run --no-sync python -c 'from dev.ci.python_runtime_matrix import load_runtime_inventory; inventory=load_runtime_inventory(); print("\n".join("\t".join((row.identifier, row.selector, row.phase.value, str(row.blocking).lower())) for row in inventory.rows))')"
    test -n "$rows"
    while IFS=$'\t' read -r runtime_id selector stability blocking; do
      for mode in source binary; do
        evidence_dir="$run_root/$runtime_id/$mode"
        evidence="$evidence_dir/compatibility-evidence.json"
        mkdir -p "$evidence_dir"
        args=(
          --mode "$mode"
          --python "$selector"
          --runtime-id "$runtime_id"
          --stability "$stability"
          --repo-root "$(pwd)"
          --work-dir "$evidence_dir"
          --evidence "$evidence"
        )
        if [[ "$mode" == binary ]]; then
          args+=(--cohort-dir "$cohort")
        fi
        set +e
        uv run --no-sync python -m dev.ci.python_runtime_compatibility "${args[@]}"
        probe_status=$?
        set -e
        if [[ "$probe_status" -ne 0 ]]; then
          if [[ "$blocking" == true ]]; then
            echo "::error::blocking $mode compatibility probe failed for $runtime_id" >&2
            failed=1
          else
            echo "::warning::advisory $mode compatibility probe failed for $runtime_id" >&2
          fi
        fi
      done
    done <<< "$rows"
    exit "$failed"

[doc('Run inventory-driven source and binary compatibility probes for every declared Python runtime.')]
[group('packaging')]
[windows]
python-compatibility:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $runId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + "-$PID"
    $runRoot = Join-Path (Join-Path (Get-Location) 'var/python-runtime-compatibility/runs') $runId
    $cohort = Join-Path $runRoot 'cohort'
    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    $commit = (git rev-parse HEAD).Trim()
    uv run --no-sync python -m dev.packaging.release_cohort build --output $cohort --expected-commit $commit
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $rows = @(uv run --no-sync python -c "import json; from dev.ci.python_runtime_matrix import load_runtime_inventory; inventory=load_runtime_inventory(); print(json.dumps([{'runtime_id':row.identifier,'selector':row.selector,'stability':row.phase.value,'blocking':row.blocking} for row in inventory.rows]))" | ConvertFrom-Json)
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if ($rows.Count -eq 0) { throw 'runtime inventory produced no rows' }
    $failed = $false
    foreach ($row in $rows) {
        foreach ($mode in @('source', 'binary')) {
            $evidenceDir = Join-Path (Join-Path $runRoot $row.runtime_id) $mode
            $evidence = Join-Path $evidenceDir 'compatibility-evidence.json'
            New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null
            $args = @('-m', 'dev.ci.python_runtime_compatibility', '--mode', $mode, '--python', $row.selector, '--runtime-id', $row.runtime_id, '--stability', $row.stability, '--repo-root', (Get-Location).Path, '--work-dir', $evidenceDir, '--evidence', $evidence)
            if ($mode -eq 'binary') { $args += @('--cohort-dir', $cohort) }
            uv run --no-sync python @args
            $probeStatus = $LASTEXITCODE
            if ($probeStatus -ne 0) {
                if ($row.blocking) {
                    Write-Host "::error::blocking $mode compatibility probe failed for $($row.runtime_id)"
                    $failed = $true
                } else {
                    Write-Warning "advisory $mode compatibility probe failed for $($row.runtime_id)"
                }
            }
        }
    }
    if ($failed) { exit 1 }

# Construct the temporary Python wheel cohort once for the current smoke campaign.
# The immutable release-cohort builder replaces this transitional constructor.
[doc('Construct the temporary Python wheel cohort once for the current smoke campaign.')]
[group('packaging')]
packaging-build-python-cohort: packaging-smoke-source
    @uv run --no-sync python -m dev.packaging.python_cohort build --output var/packaging-smoke-cohort/python

# Run both installed public transports against the exact built cohort.
[group('packaging')]
packaging-smoke-installed-oracles: packaging-build-python-cohort
    @uv run --no-sync pytest -q -n0 -m "integration and serial" dev/packaging/tests/test_installed_oracles.py

# Own the rest of the serial contracts in this directory. The preflight lane
# selects `not serial` because these must not run concurrently, and the oracle
# lane above names one module, so without this recipe the remaining serial
# tests here have no packaging-scoped owner: reaching them means running the
# tree-wide `test-integration-serial`, and someone verifying packaging alone
# gets a green result that never touched them. Depends on the cohort because
# several of these install the built wheels; the ones that do not are
# unaffected by having it. Guarded by
# `dev/packaging/tests/test_preflight_recipe_selection.py`.
[doc('Run the serial packaging contracts the preflight lane excludes.')]
[group('packaging')]
packaging-smoke-serial: packaging-build-python-cohort
    @uv run --no-sync pytest -q -n0 -m "integration and serial" dev/packaging/tests

# Local release-artifact smoke gates that do not need host package-manager access.
# The campaign driver builds the cohort once and runs the flavor lanes
# concurrently (bounded pool; lanes are disk-disjoint), then the serial
# installed-oracles pass — same proofs as the former serial aggregate at a
# fraction of the wall time (the Windows leg measured 26.3 min serial).
[doc('Local release-artifact smoke gates that do not need host package-manager access (portable profile).')]
[group('packaging')]
packaging-smoke:
    @uv run --no-sync python -m dev.packaging.campaign --profile portable

# One CI invocation keeps every artifact and oracle lane on the same cohort bytes.
[group('packaging')]
packaging-smoke-ci:
    @uv run --no-sync python -m dev.packaging.campaign --profile ci

# Per-push quick probe: cohort built once plus the single installed core smoke.
# Deliberately minimal (ten-minute per-push budget); every other flavor lane is
# a release-campaign proof carried by `packaging-smoke` / `packaging-smoke-ci`.
[doc('Per-push quick probe: cohort built once plus the single installed core smoke check.')]
[group('packaging')]
packaging-quick:
    @uv run --no-sync python -m dev.packaging.campaign --profile quick --skip-preflight

# ── Devcontainer ─────────────────────────────────────────────────────────────

# Build the reproducible dev image (.devcontainer/devcontainer.json + Dockerfile).
# `--target dev` matches devcontainer.json's `build.target`, so the recipe and
# the editor build the same stage of the one shared Dockerfile.
[doc('Build the reproducible dev image (.devcontainer/devcontainer.json + Dockerfile, `dev` stage).')]
[group('devcontainer')]
devcontainer-build:
    docker build --target dev -t cadrumo-devcontainer -f Dockerfile .

# Verify the dev image installs cleanly and its pre-baked toolchain works.
# The checks live in `dev/containers/devcontainer_smoke.py`, not inline here:
# `just` runs plain recipes through PowerShell on Windows, which parses `<` as
# a reserved operator, so an inline probe containing HTML failed at PARSE time
# before docker was invoked — reporting a recipe error that said nothing about
# the image. `bash -lc` is deliberate: it reproduces the LOGIN shell the VS Code
# integrated terminal uses, which is where the venv once fell off PATH.
[doc('Verify the dev image installs cleanly and its pre-baked toolchain (imports, unit collection, just, headless Chromium launch) works.')]
[group('devcontainer')]
devcontainer-test: devcontainer-build
    docker run --rm cadrumo-devcontainer bash -lc "python dev/containers/devcontainer_smoke.py"

# ── Self-hosted runner image ─────────────────────────────────────────────────

# Build the Linux self-hosted runner image (`runner` stage of the same
# Dockerfile). Declarative replacement for the hand-provisioned stock
# container described in dev/runners/README.md.
[doc('Build the self-hosted Linux runner image (`runner` stage of the shared Dockerfile).')]
[group('devcontainer')]
runner-image-build:
    docker build --target runner -t cadrumo-runner-linux -f Dockerfile .

# Verify the runner image carries every capability the fleet assumes present.
# Each check below maps to a documented outage: `gh` absent broke a release
# mid-cohort-seal, `brew` absent broke the acquisition lane's first step, and a
# `brew` reached through a symlinked prefix breaks `brew link` only at the very
# end of an install.
[doc('Verify the runner image carries gh, just, a canonical-prefix brew, and a runnable entrypoint.')]
[group('devcontainer')]
runner-image-test: runner-image-build
    # SINGLE-quoted payload: a double-quoted one lets the HOST shell expand
    # `$(command -v brew)` before docker ever runs, so the canonical-prefix
    # check silently compared two empty strings on the host instead of
    # resolving brew in the container.
    docker run --rm --entrypoint bash cadrumo-runner-linux -c 'set -e; gh --version | head -1; just --version; brew --version | head -1; resolved=$(readlink -f "$(command -v brew)"); case "$resolved" in /home/linuxbrew/.linuxbrew/*) echo "brew canonical prefix OK (no symlink indirection): $resolved" ;; *) echo "FAIL: brew resolves outside the canonical prefix: $resolved" >&2; exit 1 ;; esac; case "$(brew --cache)" in /home/runner/*) echo "FAIL: HOMEBREW_CACHE is inside the volume-shadowed /home/runner" >&2; exit 1 ;; *) echo "brew cache outside the volume: $(brew --cache)" ;; esac; test -d /home/linuxbrew/.linuxbrew/Homebrew/Library/Homebrew/vendor/portable-ruby && echo "portable-ruby pre-warmed (first job does not download it)"; test -x /usr/local/bin/cadrumo-runner-entry.sh && echo "entrypoint present outside the volume-shadowed /home/runner"; test -x /usr/local/bin/cadrumo-cleanup-linux.sh && echo "disk-hygiene hook present outside the volume-shadowed /home/runner"; test -x /home/runner/run.sh && echo "runner agent present"'

    # The volume-shadowing guarantee is the load-bearing design claim, so prove
    # it rather than assert it: tmpfs (unlike a named volume) does NOT seed from
    # the image, so this is the worst case a real state volume can present.
    docker run --rm --mount type=tmpfs,destination=/home/runner --entrypoint bash cadrumo-runner-linux -c 'set -e; test "$(ls -A /home/runner | wc -l)" = "0"; gh --version > /dev/null; just --version > /dev/null; brew --version > /dev/null; test -x /usr/local/bin/cadrumo-runner-entry.sh; test -x /usr/local/bin/cadrumo-cleanup-linux.sh; echo "tools, entrypoint and hygiene hook survive a volume mounted over /home/runner"'

# Verify codebase security posture using semgrep scans. The runner
# (dev.audit.security) owns the semgrep invocation AND its parsing (JSON,
# not the text report, which renders matched code plus surrounding context --
# 55,378 lines for 365 findings on this tree), so this recipe and audit-all's
# security dimension cannot drift apart or disagree. Pass --full for the
# uncapped finding list.
[doc('Verify codebase security posture using semgrep scans; capped console report, --full for everything.')]
[group('static-checks')]
check-security:
    @uv run --no-sync python -m dev.audit.security

# Check if the RAG service daemon is running.
[group('static-checks')]
check-rag:
    @uv run --no-sync vaultspec-rag server status --port 8766

# Run programmatic semantic audit checks using the local RAG daemon. Silent on success.
[group('static-checks')]
check-semantic:
    @uv run --no-sync python -m dev.audit.semantic

# Run all pre-commit hooks via prek. Silent on success; replays hook output on failure.
[group('static-checks')]
check-pre-commit:
    @uv run --no-sync python -m dev.quality.quiet uv run --no-sync prek run --all-files

# Excludes check-pre-commit (re-runs ruff + ty + architecture) and the local-only RAG/semantic checks.
# Run every fast static gate to completion; report only failures; silent on full pass.
[group('static-checks')]
check-all:
    @uv run --no-sync python -m dev.quality.suite

# ── Code mutations (Write) ──────────────────────────────────────────────────

# Auto-repair every lint violation that carries a safe fix (ruff check --fix).
[group('mutations')]
fix-style:
    @uv run --no-sync ruff check --fix .

# Auto-sort imports only (ruff I-rule safe fixes).
[group('mutations')]
fix-imports:
    @uv run --no-sync ruff check --select I --fix .

# Auto-format all python source files (ruff format).
[group('mutations')]
fix-format:
    @uv run --no-sync ruff format .

# Action every automatically-fixable issue in one pass: safe lint fixes then formatting.
[group('mutations')]
fix-all: fix-style fix-format

# Rehearse a reviewed object-name component by default; live application requires explicit arguments.
[script('pwsh.exe', '-NoLogo', '-NoProfile', '-File')]
[positional-arguments]
[group('mutations')]
fix-object-names *ARGS:
    & uv run --no-sync python -m dev.quality.object_name_declustering @args
    exit $LASTEXITCODE

# Trigger incremental vector re-indexing via the loopback service.
[group('mutations')]
fix-rag:
    @uv run --no-sync vaultspec-rag index --type all --port 8766

# ── Testing ──────────────────────────────────────────────────────────────────

pytest_workers := env_var_or_default("CADRUMO_PYTEST_WORKERS", "auto")

# The dedicated harness verdict's members: the ONE declaration of which proofs
# reach their subject by spawning a real child pytest. Each path is written
# exactly once in this file. The enrolling recipe below runs exactly these, and
# every corpus-walking lane excludes exactly these -- derived with `prepend`,
# never restated, because a member list repeated at five call sites is five
# chances to drift into a lane that silently nests a worker pool inside a pool.
#
# One member is a FILE and one is a DIRECTORY, and the asymmetry is deliberate.
# The worker hook sits among hundreds of ordinary unit modules in
# `src/cadrumo/tests`, so naming its directory would drag that whole corpus into
# an outer-serial lane and out of every parallel one; only the file can be named.
# `dev/harness` is the opposite: the package exists solely to hold outer-serial
# members, nothing else may live there, and naming the file left the DIRECTORY
# inside no lane's scope at all -- so a second proof added beside the first would
# have been collected by nothing, silently. Naming the directory makes membership
# a property of where a module lives rather than of remembering to edit this line.
harness_worker_hook := "src/cadrumo/tests/test_worker_count_hook_harness.py"
harness_package := "dev/harness/tests"
harness_members := harness_worker_hook + " " + harness_package
harness_exclusions := prepend("--ignore=", harness_members)

# Run the fast test-framework ratchets for discovery, markers, skip/xfail, mock/test-double, monkeypatch, broad raises, bare except, and tautology drift.
[group('testing')]
test-ratchets:
    @uv run --no-sync pytest -q -p no:cacheprovider -rsf dev/tests/test_test_inventory.py src/cadrumo/tests/test_relative_imports_only.py dev/tests/test_no_skip_xfail.py dev/tests/test_mock_inventory.py dev/tests/test_monkeypatch_inventory.py dev/tests/test_no_broad_exception_raises.py dev/tests/test_no_bare_except.py dev/tests/test_no_tautology.py --tb=short

# The real-proof pass raises the per-test wall ceiling above the product suite's
# 300 s ini default, for the reason `test-dev-ci` already states: this lane's
# subject is a real child pytest, and one member recursively collects the whole
# first-party corpus. That legitimately runs minutes -- measured at 75 s on a
# quiet tree and 272 s on a loaded one -- so the default ceiling kills a healthy
# proof under load and reports it as a harness failure. Only this lane is
# raised; 900 s still kills a genuine wedge in minutes.
# Run the dedicated harness verdict outer-serially. Each explicit owned member
# collects separately before the combined real-proof run, so pytest exit 5
# exposes either collapsed proof without inventing another marker. Every call
# is direct, preserving the meaningful failing pytest exit status.
[doc('Run the dedicated outer-serial test-harness verdict (installed hook and full-corpus collection proofs).')]
[group('testing')]
test-harness:
    @uv run --no-sync pytest -q -m integration --collect-only -n0 {{harness_worker_hook}}
    @uv run --no-sync pytest -q -m integration --collect-only -n0 {{harness_package}}
    @uv run --no-sync pytest -q -m integration -rsf -n0 --timeout=900 {{harness_members}}

# Run the unit test suite in parallel, ignoring workbook parity tests. Quiet
# progress; failures shown. `durations` is optional and, when set, prints
# pytest's slowest-N-tests profile (CI passes a value to keep a rolling
# public log of the suite's heaviest tests; local runs leave it unset).
#
# `-rsf`, not `-rs`: pytest's default `-r` value is `fE`, so passing `-rs`
# REPLACES it rather than adding to it, and the short-summary `FAILED
# path::test` lines disappear. The tracebacks still print, but every triage
# path this repository documents -- see the background-capture rule -- greps
# the log for `^FAILED` to get the fail list, so a 24-minute run yielded a
# count with no identities and the whole suite had to be re-run to learn what
# broke. Adding `f` back keeps the skip report the flag was added for.
# `-v`, not `-q`: under `-q` pytest withholds every failure IDENTITY until the
# run completes, so an hour-long lane that is killed, wedged, or simply still
# running tells you nothing at all -- only a growing wall of dots. `-rsf` was
# added earlier for the same class of problem but only helps at the END. Under
# `-v` each worker prints `[gwN] [ NN%] FAILED <nodeid>` the moment the test
# finishes, so `grep -E '^\[gw.*FAILED' suite.log` yields a live fail list
# while the lane is still running. The console is noisier; the capture rule
# already says to redirect to a file, and a greppable file is the point.
# `--tb=short`, not pytest's default: a lane with thousands of failures writes
# a FULL traceback for each, and the measured cost of that is not academic --
# one unit run produced a TEN MILLION line log, which is slower to write than
# the tests are to run and unreadable by any tool. The short form keeps the
# failing line and the assertion, which is what triage reads; the identity
# comes from `-v` above.
[doc('Run the unit test suite in parallel. Streams failure identities as they happen.')]
[group('testing')]
test-unit durations="":
    @uv run --no-sync pytest -v -rsf --tb=short -n {{pytest_workers}} --dist=loadfile -m 'unit and not external_tool and not os_keychain' {{ if durations == "" { "" } else { "--durations=" + durations } }}

# Run the unit test suite serially for reruns after a parallel failure.
[group('testing')]
test-unit-serial:
    @uv run --no-sync pytest -q -rsf -n0 -m 'unit and not external_tool and not os_keychain'

# Run the integration test suite in two lanes: the bulk in parallel (xdist,
# excluding serial-marked tests), then the isolation-sensitive `serial`-marked
# tests alone with no workers (-n0). The serial lane exists because a handful of
# tests mutate process-global state (the master-key-provider singleton) and
# flake under `-n auto` interleaving while passing cleanly in isolation.
[doc('Run the integration suite in two lanes: parallel xdist, then the isolation-sensitive serial tests alone.')]
[group('testing')]
test-integration:
    @uv run --no-sync pytest -v --tb=short -n {{pytest_workers}} {{harness_exclusions}} -m "integration and not serial and not os_keychain"
    @uv run --no-sync pytest -v --tb=short {{harness_exclusions}} -m "integration and serial and not perf and not os_keychain" -n0

# THIS FILE IS THE SOLE DECLARATION SITE FOR EVERY `dev/` TEST LANE.
#
# The list used to be declared three times -- ci.yml named four directories,
# `test-dev-tooling` named nine, `docs-check` named two -- and the workflow's
# set overlapped the justfile's by NOTHING. No single place answered "what runs
# under dev/", so fifteen of sixteen directories were covered only by the
# accident of three independently maintained lists. The workflow now invokes
# `test-dev-ci` instead of restating paths, so a `dev/` lane is declared here or
# nowhere. Declare a new one in a recipe below; never inline paths into a
# workflow, which puts the answer back in two places.
#
# `dev/tests/test_lane_reachability.py` proves the union of these
# recipes covers every tracked `dev/**/test_*.py` -- both that a lane NAMES the
# path and that its marker expression SELECTS the tests -- and fails when a new
# test lands that no lane reaches.

# Run the dev/ tooling gates that no other lane reaches. `testpaths` in
# pyproject names only `src/cadrumo` plus one packaging file, so these
# directories were collected by NOTHING and 19 of their tests had been failing
# unobserved, including the duplication-disposition gate and the whole shipped
# documentation-search corpus. The marker expression is stated explicitly for
# the reason `packaging-smoke-preflight-tests` states it: these directories are
# mixed-marker, so inheriting the default `-m 'unit and ...'` would silently
# deselect the integration contracts and still exit zero.
#
# `dev/benchmarks/cli/tests` holds no test module yet, and that is exactly why
# it is named: an empty `tests` package is the emptiest form of the hole this
# lane list keeps producing. Nothing collects from it today, so the cost is one
# directory walk; the first proof written into it runs on the push that adds it
# rather than waiting for someone to remember this line.
[doc('Run the dev/ tooling gates that no other lane reaches (audit, benchmarks, deploy, env, identity, locales, sanitizer, registry, docs, agent-eval, ingest-harness subsystems).')]
[group('testing')]
test-dev-tooling:
    @uv run --no-sync pytest -q -n {{pytest_workers}} -m "(unit or integration) and not resident_service and not external_tool" dev/audit/tests dev/benchmarks/cli/tests dev/corpus/tests dev/deploy/tests dev/docs/tests dev/env/tests dev/identity/tests dev/locales/tests dev/readme/tests dev/tests dev/sanitizer/tests dev/registry/tests dev/registry/newmodelo/tests dev/registry/aeip/tests dev/docs/preprocess/tests dev/docs/sequences/tests dev/docs/terminology/tests dev/docs/terminology_handbook/tests dev/agent_eval/tests dev/ingest_harness/tests

# Run the dev-tree workflow/tooling conformance gates that CI runs per-push
# (workflow structural pins, evidence-transport conformance, shard-plugin
# partition proof). ci.yml calls THIS recipe, so the paths and the marker
# expression live in one place and the lane is reproducible locally -- it was
# previously inline in the workflow and could not be run by hand at all.
#
# The marker expression is explicit for the same reason as `test-dev-tooling`:
# the default addopts' `-m unit` deselects the integration-marked workflow pins
# and still exits zero. `not serial` leaves the installed-oracles pass to the
# packaging campaign that builds its cohort.
#
# -n 8, never -n auto: the workstation's 24 logical CPUs are shared with
# co-resident runners from other repositories, so 8 is a working pin rather
# than a derivation (machine-aware sizing, .github/ci-control-plane.md). The dev tree
# carries real install/harness tests that legitimately run 300-900 s, so this
# raises the per-test ceiling above the product suite's 300 s ini default
# (slowest product test: 58.7 s measured); 900 s still kills a wedge in minutes.
#
# `dev/docs/apidocs/tests` is here because it is the ONLY gate whose subject is
# the production MODULE TREE, and the module tree is changed by exactly the
# pushes that could not reach it. It was previously selected only by
# `docs-check`, which runs in docs.yml -- path-scoped to docs/, dev/docs/ and the
# terminology data, so NO `src/cadrumo/**/*.py` change fires it -- and in the
# dispatch-only full lane. So a module add, rename or delete, the only thing that
# drifts the autodoc stubs, produced no verdict on any push.
#
# Both of its failure modes land on someone else. A deleted or renamed module
# leaves an orphan stub whose autodoc import hard-crashes the next nitpicky
# build, surfacing on an unrelated docs-path push in a file that author never
# touched. An added module has no stub and SILENTLY drops out of the published
# documentation -- no error anywhere, and that is the more common half.
#
# Deliberately this recipe and not a widened docs.yml trigger: this lane already
# fires on `src/**` per-push, while widening docs.yml would pay a Playwright
# provision and a full Sphinx build on every Python push (the ten-minute wall,
# operator directive 2026-07-20) and would duplicate the docstring cross-link
# gate the unit lane already runs. The path is also still named by `docs-check`;
# that overlap is intended, because the two lanes answer to different triggers.
# Its tests are `unit`-marked, so the marker expression below selects them --
# checked rather than assumed, since a `docs`-only marker would have been
# deselected here and still exited zero.
#
# `dev/docs/tests/test_api_stubs.py` is named too, and the pair is not
# redundant. `dev/docs/apidocs/tests` scaffolds the real module tree into a
# `tmp_path` and checks THAT for drift, so it proves the manager's round-trip
# and is clean by construction -- it cannot see the committed `docs/api/` tree
# at all. The gate whose subject is the COMMITTED tree is `test_api_stubs.py`,
# and it ran only in `test-dev-tooling` (ci-full) and `docs-check` (path-scoped
# to docs/, so no `src/**` push fires it). So the verdict this block argues for
# was still not produced on a push: a module added under `src/cadrumo/` reached
# main with no stub and silently dropped out of the published docs, which is
# exactly the failure mode described above. Its marker was checked the same
# way -- `unit`, `hex_core`, `docs` -- and it needs no browser or server, so it
# costs the lane a directory walk.
[doc('Run the dev-tree workflow/tooling conformance gates that CI runs per-push.')]
[group('testing')]
test-dev-ci:
    @uv run --no-sync pytest -q -n 8 --timeout=900 -m "unit or (integration and not serial)" dev/ci/tests dev/packaging/tests dev/quality/tests dev/release/tests dev/docs/apidocs/tests dev/docs/tests/test_api_stubs.py
    @uv run --no-sync pytest -q -n0 --timeout=900 -m "integration and serial" dev/ci/tests dev/quality/tests dev/release/tests dev/docs/apidocs/tests

# Run the four conformance gates that are correctly `integration`-marked
# (each genuinely crosses architectural layers) but were reached by no
# automatically-triggered workflow: the per-push lane pins `unit`, and the
# only `integration` invocation lived in the dispatch-only full lane, so none
# of the four had ever run on a push at any revision. ci.yml calls THIS
# recipe so the path set and the marker expression have one declaration
# site, same convention `test-dev-ci` established above. The marker
# expression excludes every marker this repository ever pairs with
# `integration` so a future addition to this path set cannot silently pull
# in a test this lane cannot satisfy.
[doc('Run the four cross-layer conformance gates the per-push lane needs (rule-surface, status-frontend, self-referential-string, suggestion-command).')]
[group('testing')]
test-per-push-integration-gates:
    @uv run --no-sync pytest -q -n {{pytest_workers}} -m "integration and not serial and not perf and not external_tool and not os_keychain and not resident_service" src/cadrumo_harness/tests/test_rule_surface_conformance.py src/cadrumo/application/user_profile/tests/test_status_projection.py src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py dev/tests/test_suggestion_command_conformance.py

# Enrol the tests that query the resident vaultspec-rag search service. Held out
# of every other lane by the `resident_service` marker, because the service is a
# separate product this project does not install and its own isolation guard
# refuses the HTTP call under pytest -- so from a plain invocation these fail on
# the harness before the corpus is ever consulted.
#
# READ BEFORE TRUSTING A GREEN RESULT. This recipe assumes a started AND fully
# indexed service. A truncated index answers confidently rather than refusing,
# so these gates can pass thinly against a partial corpus. Confirm the index is
# whole before reading a pass as evidence; `just check-rag` reports status, and a
# section count far below the tracked file count means the answers are worthless
# even though nothing errored.
[doc('Enrol the tests that query the resident vaultspec-rag search service (held out of every other lane).')]
[group('testing')]
test-resident-service:
    @uv run --no-sync pytest -q -n0 -m "resident_service" dev/docs/preprocess/tests dev/docs/terminology/tests

# Run BOTH lanes in sequence and report them separately. The default pytest
# invocation is pinned to the unit lane by addopts, so `just test-unit` green
# says nothing about the ~3k integration tests; this is the recipe to reach for
# before claiming a suite is clean.
#
# The harness verdict runs FIRST, and this is the only local composition that
# reaches it. Every corpus-walking lane `--ignore`s the harness members by
# design -- a member spawns a real child pytest, so a lane that collected one
# would nest a worker pool inside a pool -- which left the full-corpus
# collectability proof enrolled nowhere a routine local run could see it. A
# module that cannot IMPORT is silently absent from a lane's summary, so both
# lane verdicts below are claims about whatever happened to be collectable, and
# neither can report the modules that were not. That is the whole reason this
# runs before them rather than after: an uncollectable corpus invalidates the
# green they produce, and `just` stops at the first failing line, so a trailing
# position would never report on a tree whose lanes are already red.
#
# It is a separate `just` invocation, never folded into either lane's pytest
# command line, so the outer-serial `-n0` contract and the per-member collect
# preflight the harness recipe owns stay intact.
#
# Collectable is not passing, and this composition does not make it so: the
# proof establishes that every discovered first-party test module IMPORTS. A
# construction that breaks inside a deferred function-local import is invisible
# to it, as it is to `--collect-only` generally, because no test body runs.
[doc('Run the full-corpus harness verdict, then both lanes in sequence, reporting each separately.')]
[group('testing')]
test-both-lanes:
    @just test-harness
    @just test-unit
    @just test-integration

# Run only the PARALLEL integration lane, holding the serial tests out.
#
# Exists so CI can carry a separate verdict per pass. The two are not equally
# trustworthy: this pass is deterministic, while the serial pass includes
# wall-clock budgets that flake on a machine CI shares with the dev box and the
# agent fleet (measured: P95 4.098s against a 3.0s budget, samples mostly
# 1.1-1.5s with load-driven outliers). Wiring one CI step to both means the
# deterministic half can never go blocking without the load-sensitive half
# dragging the release-verdict lane down with it.
[doc('Run only the parallel integration lane, holding the isolation-sensitive serial tests out.')]
[group('testing')]
test-integration-parallel:
    @uv run --no-sync pytest -v --tb=short -n {{pytest_workers}} {{harness_exclusions}} -m "integration and not serial and not os_keychain"

# Run only the serial (isolation-sensitive) integration lane, no xdist workers.
[group('testing')]
test-integration-serial:
    @uv run --no-sync pytest -v --tb=short {{harness_exclusions}} -m "integration and serial and not perf and not os_keychain" -n0

# Run the OS-credential-store custody tests. These carry `os_keychain` alongside
# their execution marker, and EVERY lane above excludes it, so this recipe is the
# only way to select them. The capability is a property of the logon session: run
# this from an INTERACTIVE DESKTOP SESSION. A headless CI runner, or an agent
# reaching the host over SSH, holds a network logon that carries no credentials,
# so the store refuses every call and these cases fail at an explicit precondition
# naming the missing custody -- which is a true report of the host, not a defect.
#
# Runs with -n0 deliberately. The OS credential store is MACHINE-global, and these
# cases mint and remove session keys under fixed bucket ids, so xdist workers delete
# each other's keys: under -n auto the logout case fails at its own precondition,
# having had its key removed by a peer worker mid-test. That reads as a custody
# failure and is really a collision. Serial is not a speed compromise here, it is
# the only correct way to exercise a shared external store.
#
# The CLI path names the DIRECTORY, not one module. It named
# `test_profile_session_root_resume.py` alone, and three `os_keychain` custody
# cases in two sibling files were therefore selected by no lane at all -- among
# them "registered profile custody survives logout and reopens on login", which
# is the cross-process resumption contract this lane exists for. The marker
# expression is what scopes the directory, so a future `os_keychain` case added
# beside them is selected the moment it lands rather than silently reading as
# coverage.
[doc('Run the OS-credential-store custody tests (interactive desktop session only).')]
[group('testing')]
test-os-keychain:
    uv run --no-sync pytest -q -rsf -n0 -m os_keychain src/cadrumo/application/user_profile/tests src/cadrumo/entrypoints/cli/tests src/cadrumo/tests/test_secure_sql.py src/cadrumo/adapters/persistence/storage/custody/tests src/cadrumo/adapters/persistence/storage/master_key/tests src/cadrumo/adapters/persistence/storage/tests

# Run the live test suite. Quiet progress; failures shown.
[group('testing')]
test-live:
    @uv run --no-sync pytest -q -m aeat_live

# Run the produce, verify, and export end-to-end smoke tests.
[group('testing')]
test-smoke:
    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_file_flow_calculation.py src/cadrumo/application/modelo/tests/test_file_flow_verify.py src/cadrumo/application/modelo/tests/test_file_flow_filing.py src/cadrumo/application/modelo/tests/test_export.py -v

# Run the LibreOffice workbook parity tests. These carry `external_tool` rather
# than `unit`, so the default `-m 'unit'` in addopts must be overridden here or
# this lane selects nothing; the explicit path also overrides the addopts
# --ignore that keeps the directory out of the default lane.
[doc('Run the LibreOffice workbook parity tests (external_tool marker, outside the default unit lane).')]
[group('testing')]
test-workbook-parity:
    uv run --no-sync pytest -m external_tool dev/registry/tests/test_workbook_parity.py

# Run the Homebrew/Scoop channel-artifact conformance tests. These bind
# the generated formula and manifest to a real built cohort. Explicit paths
# and -n0, never marker selection alone: a marker-filtered xdist run holds
# serial tests out while still reporting a clean pass. Dispatch-only
# (ci-full.yml) rather than per-push: these tests build real sdists and
# wheels, costing minutes the per-push budget cannot absorb.
[doc('Run the Homebrew/Scoop channel-artifact conformance tests (serial, builds real sdists and wheels).')]
[group('testing')]
test-channel-artifacts:
    @uv run --no-sync pytest -q -n0 --timeout=900 -m serial packaging/homebrew/tests packaging/scoop/tests

# Run the unit test suite with coverage report and fail-under check. Quiet progress.
[doc('Run the unit test suite with a coverage report and a fail-under check.')]
[group('testing')]
[unix]
test-coverage:
    @uv run --no-sync pytest -q --cov=cadrumo --cov-report=term-missing --cov-fail-under=60

[doc('Run the unit test suite with a coverage report and a fail-under check.')]
[group('testing')]
[windows]
test-coverage:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run --no-sync pytest -q --cov=cadrumo --cov-report=term-missing --cov-fail-under=60
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# ── Advisory audits ──────────────────────────────────────────────────────────

# List every ty + pyrefly diagnostic verbatim (advisory; always exits 0).
[group('audits')]
audit-types:
    @uv run --no-sync python -m dev.quality.types --full

# Run complexity audits for production code.
[group('audits')]
audit-complexity:
    @uv run --no-sync python -m dev.audit.complexity

# Scan for dead code. The whitelist clears individually-justified
# false positives (contract-fixed signature params); see its docstring.
# The runner (dev.audit.dead_code) owns the vulture invocation AND its
# parsing, so this recipe and audit-all's dead-code dimension cannot drift
# apart or disagree. Pass --full for the uncapped finding list.
[doc('Scan for dead code, clearing individually-justified false positives via the whitelist.')]
[group('audits')]
audit-dead-code:
    @uv run --no-sync python -m dev.audit.dead_code

# Audit shipped code no console-script entrypoint can reach. Unlike
# `audit-dead-code` (vulture's name heuristics), this walks the import graph
# from `[project.scripts]` and counts only `src/cadrumo` non-test modules as
# use: a module or symbol that only tests or `dev/` touch is reported, with
# that outside use shown as a label so "kept alive by its tests" reads
# differently from "orphaned". A test whose every shipped subject is itself a
# finding is reported too, so dead code and the tests propping it up retire
# together.
#
# Every finding carries the tier it was derived at. `exact` is resolved
# through the import graph (unreachable modules, and top-level symbols whose
# every way in was checked); `name-match` and `name-match-data` are members
# reached by attribute access the scan cannot bind to a type. Start a cleanup
# from `--confidence exact`.
#
# Exits 3 on findings. `--full` uncaps the list, `--json` emits machine
# output with a stable id per finding, and `--root MODULE:ATTR` admits a
# surface the packaging does not declare (a `python -m` entry, say).
[doc('Audit shipped code unreachable from the console-script entrypoints; test-only and dev-only use is labelled, not credited.')]
[group('audits')]
audit-unreachable-code *ARGS:
    @uv run --no-sync python -m dev.audit.unreachable_code {{ARGS}}

# Audit the DATA path the reachability audit cannot see: a snapshot service
# whose list/show/latest side a console script reaches, while its capture side
# has no production caller anywhere. The store still imports and still tests;
# it is simply never filled again, so the product ships a view onto nothing.
#
# Surfaces are found structurally, through the subclass closure of the live
# snapshot lifecycle bases, and a caller counts only when it both imports the
# service and spells one of its verbs outside a docstring.
#
# Exits 3 on findings. `--json` emits machine output with a stable id per
# finding.
[doc('Audit persistence surfaces a product command reads but no production code writes.')]
[group('audits')]
audit-write-paths *ARGS:
    @uv run --no-sync python -m dev.audit.write_path_coverage {{ARGS}}

# Scan for copy-paste code duplication. Aggregate line + capped clone list.
# The runner owns the jscpd invocation AND its parsing, so this recipe and the
# health report's duplication dimension cannot drift apart or disagree.
[doc('Scan for copy-paste code duplication; aggregate line count plus a capped clone list.')]
[group('audits')]
audit-duplication:
    @uv run --no-sync python -m dev.audit.duplication

# Terminators rewritten after checkout are invisible to `git diff` and to every
# text-mode reader. This is a screen and always exits 0; apply the shrink-only
# ceiling with `python -m dev.audit.checkout_drift --check`.
# Count tracked files whose on-disk bytes differ from their committed bytes.
[group('audits')]
audit-checkout-drift:
    @uv run --no-sync python -m dev.audit.checkout_drift

# Perform an on-demand semantic search query delegating to the running RAG daemon.
[group('audits')]
audit-rag QUERY:
    @uv run --no-sync vaultspec-rag search "{{QUERY}}" --port 8766 --timeout 45.0

# Run all advisory audits (complexity, dead code, duplication, checkout
# drift, security) as one composed red/amber/green dashboard; tolerant of
# individual findings (always exits 0). The runner (dev.audit.advisory) owns
# the composition, so this recipe cannot drift from what it reports. Full,
# uncapped results are persisted to dev/audit/.runs/ every run (summary.json
# for machine parsing, summary.md for the human-readable uncapped text).
# Advisory-audit sibling of `check-all` (the fast static gates).
[doc('Run all advisory audits as one composed red/amber/green dashboard; full results persisted to dev/audit/.runs/.')]
[group('audits')]
audit-all:
    @uv run --no-sync python -m dev.audit.advisory

# Same composed advisory-audit dashboard, machine-readable.
[group('audits')]
audit-all-json:
    @uv run --no-sync python -m dev.audit.advisory --json

# Monthly code-health report: shadowing, duplication, layering, complexity,
# each classified red/amber/green. Composes the scanners above (plus
# lint-imports) into one contributor-facing verdict. Exits 1 if any
# dimension is RED; AMBER dimensions are advisory debt, not a gate.
[doc('Monthly code-health report: shadowing, duplication, layering, and complexity, each classified red/amber/green.')]
[group('audits')]
audit-health-report:
    @uv run --no-sync python -m dev.audit.report

# Same report, machine-readable.
[group('audits')]
audit-health-report-json:
    @uv run --no-sync python -m dev.audit.report --json

# Audit module, class, enum, and function names across src/ and dev/.
# Public production declarations must be singular and globally unique; private
# and test collisions remain visible as advisory findings.
[doc('Audit module, class, enum, and function names across src/ and dev/ for singularity and uniqueness.')]
[group('audits')]
audit-object-names *ARGS:
    @uv run --no-sync python -m dev.audit.object_names {{ARGS}}

# Show conformance status across all modelo revisions and the derived release
# closure. Both verbs exit 0 always (screen posture): ``report`` renders every
# axis, ``closure`` renders the temporal, source, and filing release predicate.
# To gate on the completeness claim use ``closure --check`` directly.
[doc('Show conformance status across all modelo revisions and the derived release closure.')]
[group('audits')]
audit-registry-conformance:
    @uv run --no-sync python -m dev.registry.conformance report
    @uv run --no-sync python -m dev.registry.conformance closure

# ── Documentation ────────────────────────────────────────────────────────────

# Build changed narrative and API reference documents.
[group('docs')]
docs:
    uv run --no-sync python -m dev.docs.build docs/conf.py

# Build a single narrative page.
[group('docs')]
docs-page PAGE:
    uv run --no-sync python -m dev.docs.build --single-page {{PAGE}}

# Serve documentation with live reload on docs/ and src/cadrumo/ edits. Binds every
# interface on the docs' canonical port 8788, claimed strictly: attaches to a
# healthy running server, evicts an invalid squatter, and errors rather than
# drifting to another port. The first serve builds before opening the browser.
[doc('Serve documentation with live reload on docs/ and src/cadrumo/ edits.')]
[group('docs')]
docs-serve PORT="":
    uv run --no-sync python -m dev.docs.serve {{ if PORT == "" { "" } else { "--port " + PORT } }} --open-browser

# Build documentation changed since a base commit.
[group('docs')]
docs-changed BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}}

# Build changed documentation with strict warnings-as-errors flags.
[group('docs')]
docs-changed-strict BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}} --strict

# Build changed documentation and update the vector index.
[group('docs')]
docs-changed-rag BASE="HEAD":
    uv run --no-sync python -m dev.docs.build --base {{BASE}} --rag-index

# Extract gettext POT templates and refresh the es/ca/hu doc catalogues.
[group('docs')]
docs-gettext:
    uv run --no-sync python -m dev.docs.i18n

# Build the user-scope documentation in one language (es/en/ca/hu) into that
# language's own root. `--out-dir` is what puts a build in a per-language
# subdirectory; `--language` alone only selects the catalogue, so without it the
# localized pages render into the canonical English root itself, leaving no
# language root at all and an English root full of translated pages.
[doc('Build the user-scope documentation in one language into that language own root.')]
[group('docs')]
docs-lang LANG:
    uv run --no-sync python -m dev.docs.build --scope user --language {{LANG}} --out-dir docs/_build/html/{{LANG}}

# Build the user-scope documentation for every translation language, each into
# its own root beside the English one. These are plain local builds: for the
# deploy-faithful multi-root artefact (strict, record-injected index, per-root
# canonical URLs) use `docs-site-dry-run`.
[doc('Build the user-scope documentation for every translation language, each into its own root.')]
[group('docs')]
docs-langs:
    uv run --no-sync python -m dev.docs.build --scope user --language es --out-dir docs/_build/html/es
    uv run --no-sync python -m dev.docs.build --scope user --language ca --out-dir docs/_build/html/ca
    uv run --no-sync python -m dev.docs.build --scope user --language hu --out-dir docs/_build/html/hu

# Build every published site root exactly as a publish builds it and run every
# pre-upload validation against the result. It belongs in this group and not in
# `deploy`: it needs no AWS session, writes nothing outward, and its entire
# subject is the built tree. Its value is that the per-root artifact, sitemap
# and record-index checks used to be reachable only through the publish itself,
# so a root that would land incomplete could not be caught before bytes went to
# the live destination.
[doc('Build every published site root and run every pre-upload validation, uploading nothing.')]
[group('docs')]
docs-site-dry-run:
    uv run --no-sync python -m dev.deploy.docs_static_site dry-run

# Run docstring structure and Sphinx build checks. Quiet pytest progress.
# `workers` bounds the pytest-xdist lane: CI passes 8 (machine-aware sizing,
# .github/ci-control-plane.md — the 24-core box is shared with other
# repositories' runners, and 8 is a working pin, not a derivation); local
# development keeps the `auto` default per the same control plane.
[doc('Run docstring structure and Sphinx build checks. Quiet pytest progress.')]
[group('docs')]
docs-check workers="auto":
    @uv run --no-sync pytest -q -n {{workers}} dev/docs/tests dev/docs/apidocs/tests src/cadrumo/tests/test_docstring_core_struct_links.py -m "docs or unit or (integration and not serial)"
    @uv run --no-sync doc8 docs
    @uv run --no-sync interrogate -c pyproject.toml src/cadrumo

# ── Database migrations ──────────────────────────────────────────────────────

# Generate a new Alembic database migration file. Identical body across
# platforms — a single plain `uv run` invocation needs no shell preamble.
[doc('Generate a new Alembic database migration file.')]
[group('database')]
db-migrate message:
    uv run alembic revision --autogenerate -m "{{message}}"

# Upgrade the database schema to the latest version. Identical body across
# platforms — a single plain `uv run` invocation needs no shell preamble.
[doc('Upgrade the database schema to the latest version.')]
[group('database')]
db-upgrade:
    uv run alembic upgrade head

# ── Deployment ───────────────────────────────────────────────────────────────
#
# Its own lane, deliberately. Building documentation is a local
# check-and-balance verification with no bearing on deployment; publishing
# writes bytes to a live public destination. The `docs` group therefore holds
# only build and check verbs, and the three recipes below are the only ones in
# this file that reach outward at all.
#
# The `release` group is adjacent but disjoint, and nothing here re-declares
# any of it: every release recipe is read-only (`release` is a dry-run preview,
# `release-rollback` prints a procedure, `release-readiness` audits), and
# release publication itself lives in CI behind the `pypi` environment
# (`publish.yml`). The release lane deliberately publishes nothing.
#
# These three verbs do NOT share an automation posture, and this group must
# not be read as granting one. Each states its own authority below.

# Create or update the private Cadrumo docs stack. Infrastructure provisioning,
# not publication: a one-time stack create/update that no workflow performs and
# no release step calls. Operator-only.
[doc('Create or update the private Cadrumo docs stack (infrastructure provisioning, operator-only).')]
[group('deploy')]
docs-stack-deploy:
    uv run --no-sync python -m dev.deploy.docs_static_site provision --confirm provision-cadrumo-docs

# Build and publish the complete Cadrumo docs site. The human half of a
# two-authority verb: the publisher accepts a provisioned automated authority,
# and `docs-publish.yml` runs the same publish on `release: published` once the
# deploy-role variable is set (operator decision OP-3). Until then this recipe
# is the release runbook's distribution-complete tripwire — see RELEASING.md
# phase 4, the one post-publication step still held by a human.
[doc('Build and publish the complete Cadrumo docs site (human half; docs-publish.yml is the automated peer).')]
[group('deploy')]
docs-deploy:
    uv run --no-sync python -m dev.deploy.docs_static_site publish --confirm publish-cadrumo-docs

# ── Release ──────────────────────────────────────────────────────────────────

# Audit-state readiness gate: version-surface parity, changelog sanity, the
# most recent packaging-smoke evidence, and (best-effort, via `gh`) no open
# priority:P0-blocker issue. Read-only — no outward action, ever. Exits 1 on
# a blocking failure; advisory failures (e.g. no packaging-smoke run yet,
# `gh` unavailable) are reported but do not fail the gate. Run it before
# merging a release pull request; nothing in CI runs it for you. See
# docs/_release_checklist.yaml and RELEASING.md.
[doc('Audit-state readiness gate: version-surface parity, changelog sanity, and packaging-smoke evidence.')]
[group('release')]
release-readiness:
    uv run --no-sync python -m dev.release.readiness

# Same gate, machine-readable.
[group('release')]
release-readiness-json:
    uv run --no-sync python -m dev.release.readiness --json

# Print the rollback procedure for a released version that must be pulled.
# Read-only — never runs a destructive action; every step below is printed
# for a human to run deliberately. See RELEASING.md#diagnose-and-recover.
[doc('Print the rollback procedure for a released version that must be pulled (read-only, human-run).')]
[group('release')]
[unix]
release-rollback version:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Rollback procedure for cadrumo v{{version}} (RELEASING.md#diagnose-and-recover):"
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

[doc('Print the rollback procedure for a released version that must be pulled (read-only, human-run).')]
[group('release')]
[windows]
release-rollback version:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    Write-Host "Rollback procedure for cadrumo v{{version}} (RELEASING.md#diagnose-and-recover):"
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
[doc('Preview the next version release via dry-run (release-please).')]
[group('release')]
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
    echo "✔ dry-run complete — review $LOG. Merging the release pull request applies the bump; this recipe is preview-only and mutates nothing."

[doc('Preview the next version release via dry-run (release-please).')]
[group('release')]
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
    Write-Host "✔ dry-run complete - review $log. Merging the release pull request applies the bump; this recipe is preview-only and mutates nothing."

