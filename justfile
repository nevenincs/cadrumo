# ── Platform ─────────────────────────────────────────────────────────────────
# Requires just >= 1.38 (`set working-directory`, native modules, `[doc]`/`[group]`).
#
# This repository is the fleet's ONE pwsh exception, and the reason is quoting.
# Unlike its siblings, several recipe bodies here carry real shell syntax - the
# single-quoted pytest `-m 'unit and not perf'` selectors, `$( )` substitution,
# `bash -c '...'` payloads handed to docker. `cmd.exe` does not treat `'` as a
# quote character at all, so it would split `-m 'unit and not perf'` into five
# argv entries and hand pytest a marker expression it never wrote - selecting a
# different test population, silently, while still reporting green. Everywhere
# a body IS a single bare command the fleet uses `cmd` instead, because it
# forwards native exit codes verbatim where pwsh does not; `propagate` below is
# what buys that fidelity back here.
#
# `-NoProfile` is load bearing: without it every recipe loads the operator's
# personal PowerShell profile, so aliases shadowing `ls`/`curl`, a customised
# `$ErrorActionPreference`, or an altered `PSModulePath` silently change what a
# recipe does from one machine to the next.
set windows-shell := ["pwsh.exe", "-NoLogo", "-NoProfile", "-Command"]

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

# PowerShell's `-Command` host exits 1 for ANY failing native command rather
# than forwarding that command's own status, which would collapse every
# `init` exit code onto 1 and destroy the distinction between "a host tool is
# missing", "the lockfile drifted", and "an editor is holding .venv open".
# Appending an explicit propagation is the whole remedy; it is empty on unix,
# where `sh` already forwards the status, so no recipe needs a platform pair.
propagate := if os_family() == "windows" { "; exit $LASTEXITCODE" } else { "" }

# `init` is the one command a fresh worktree needs, and the command git
# tooling and the worktree provisioner call after creating one. It runs on an
# ephemeral interpreter because it must work before `.venv` exists, and every
# step it runs delegates to `dev/env`, which already owns this repository's
# venv provisioning, its exclusive install lock, and `env/.env`.
#
# `uv sync --locked` is the sole project-environment operation. It creates
# `.venv` when absent and converges it exactly to the committed lockfile; the
# initializer refuses first when a live process holds the environment.
#
# Idempotent: a second run costs a stamp comparison and touches nothing.
# `just init-check` verifies without mutating, exiting 3 when the worktree is
# not initialized. Set VAULTSPEC_INIT_JSON=1 for an NDJSON event stream,
# VAULTSPEC_INIT_FORCE=1 to ignore the stamp. Every run writes
# `.venv/init-report.json`; an environment held open by a live session exits 6.

[doc('Initialize a fresh clone or worktree: Python, dev dependencies, vaultspec, and env/.env.')]
[group('bootstrap')]
init:
    uv run --no-project --python 3.13.11 -- python -m dev.init all{{propagate}}

[doc('Synchronize the pinned environment exactly from uv.lock.')]
[group('bootstrap')]
init-python:
    uv run --no-project --python 3.13.11 -- python -m dev.init python{{propagate}}

[doc('Install the Vaultspec tooling and report the resulting configuration.')]
[group('bootstrap')]
init-tools:
    uv run --no-project --python 3.13.11 -- python -m dev.init tools{{propagate}}

[doc('Report whether this worktree is initialized. Mutates nothing; exits 3 if not.')]
[group('bootstrap')]
init-check:
    uv run --no-project --python 3.13.11 -- python -m dev.init check{{propagate}}

# Verify the workstation for the services the active profile opts into: external
# dependency availability (Ollama vision, provider CLIs, Playwright) + the profile's
# capability posture, with the exact fix for any gap. Exits non-zero when an
# opted-in capability has a missing dependency. This is the product-side
# "is my workstation ready" check (the dev-toolchain probe is `just doctor-env`).
[doc('Verify the workstation is ready: external dependency availability plus the active profile capability posture.')]
[group('doctor')]
doctor-check:
    uv run --no-sync aeat config check

# Synchronize runtime, workbook, and dev dependencies exactly from uv.lock.
# The live-process guard refuses before uv mutates an environment in active use.
[doc('Synchronize the project environment exactly from uv.lock.')]
[group('setup')]
setup-install:
    uv run --no-sync python -m dev.env install

# Workstation CLI prerequisites for non-Python audit recipes.
[doc('Workstation CLI prerequisites for non-Python audit recipes.')]
[group('setup')]
setup-workstation-tools:
    uv run --no-sync python -m dev.env workstation-tools

# ── Environment Setup and Doctor ─────────────────────────────────────────────

# Copy env/.env.example → env/.env if the latter is missing. No-op otherwise.
[doc('Copy env/.env.example to env/.env if the latter is missing; no-op otherwise.')]
[group('setup')]
setup-env:
    uv run --no-sync python -m dev.env setup

# Verify the local venv and workstation provide the full audit toolchain and RAG status.
[group('doctor')]
doctor-env:
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
    just doctor-pip
    just doctor-playwright
    -just rag-service-status

[doc('Verify installed packages satisfy their declared dependency constraints.')]
[group('doctor')]
[windows]
doctor-pip:
    uv pip check --python .venv/Scripts/python.exe

[doc('Verify installed packages satisfy their declared dependency constraints.')]
[group('doctor')]
[unix]
doctor-pip:
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
# recipe with elevation. Verify the result with `just doctor-playwright`.
[doc('Provision both Playwright browser channels the codebase needs (Chromium and the chrome channel).')]
[group('setup')]
setup-playwright:
    uv run --no-sync playwright install chromium
    uv run --no-sync playwright install chrome

# Verify the local environment is correctly provisioned with the CONFIGURED
# Playwright browser channel (per `cadrumo_browser_channel`, default `chrome`)
# and its dependencies, per ADR 2026-04-12-playwright-anti-bot-adr. Performs a
# real headless launch-and-close of that channel (never hardcodes "chrome" —
# reads the live setting) and prints the exact remediation command on failure.
# Exits non-zero when the environment cannot satisfy the configured channel.
[doc('Verify the local environment is provisioned with the configured Playwright browser channel and its dependencies.')]
[group('doctor')]
doctor-playwright:
    uv run --no-sync python -m dev.env.playwright_doctor

# Start the background vaultspec-rag HTTP service daemon on loopback port 8766.
[group('service')]
rag-service-start:
    uv run --no-sync vaultspec-rag server start --updates --port 8766

# Stop the background vaultspec-rag HTTP service daemon.
[group('service')]
rag-service-stop:
    uv run --no-sync vaultspec-rag server stop

# Report what the temp directory is holding, and which sessions still own it. Deletes nothing.
[group('maintenance')]
dev-temp-report:
    uv run --no-sync python -m dev.env.temp_reaper

# Reclaim the session scratchpads the report judged abandoned. Read the report first.
[group('maintenance')]
dev-temp-reap:
    uv run --no-sync python -m dev.env.temp_reaper --apply

# ── Static checks (Verify, Read-only) ────────────────────────────────────────

# Verify code style using ruff check. Silent on success; lists violations on failure.
[group('check')]
check-style:
    @uv run --no-sync python -m dev.quality.quiet ruff check .

# Verify code format using ruff format --check. Silent on success; lists drift on failure.
[group('check')]
check-format:
    @uv run --no-sync python -m dev.quality.quiet ruff format --check .

# Verify type correctness with ty (full src) and pyrefly (strict domain + application).
# Wrapper emits a signal-only summary grouped by rule and file; silent on success.
[doc('Verify type correctness with ty, pyrefly, and basedpyright. Silent on success.')]
[group('check')]
check-types:
    @uv run --no-sync python -m dev.quality.types

# Verify import structure and hexagonal boundaries. Silent on success.
[group('check')]
check-imports:
    @uv run --no-sync python -m dev.quality.quiet lint-imports

# Refuse tracked identity canaries while retaining the value-free advisory report.
[doc('Verify that tracked content contains no configured identity canary.')]
[group('check')]
check-identity:
    @uv run --no-sync python -m dev.identity

# Verify every locale catalogue against the live code and registry surface.
[doc('Audit locale keys, values, placeholders, and codebase enrolment.')]
[group('check')]
check-locales:
    @uv run --no-sync python -m dev.locales audit

# Verify the committed API-reference stub tree without rewriting it.
[doc('Verify that generated API documentation stubs match the source module tree.')]
[group('check')]
check-docs-api:
    @uv run --no-sync python -m dev.docs.apidocs scaffold --check

# Verify that synonym ratification decisions agree with the shipped vocabulary.
[doc('Verify the terminology synonym ratification queue.')]
[group('check')]
check-docs-synonyms:
    @uv run --no-sync python -m dev.docs.terminology.synonyms validate

# Verify the core facade, import-edge, and no-shim architecture invariants.
[group('check')]
check-architecture:
    @uv run --no-sync pytest -v -n0 dev/tests/test_cross_package_private_imports.py dev/tests/test_import_edge_integrity_gate.py

# Verify the production registry compiler and the bundled parity-oracle bindings.
# The two commands are dependent: a failed production verification invalidates
# any downstream parity claim, so this health gate stops before the audit.
[doc('Verify the production registry and audit every bundled parity-oracle binding.')]
[group('check')]
check-registry:
    @uv run --no-sync aeat app registry verify
    @uv run --no-sync python -m dev.registry.parity.maintenance_cli audit-oracles

# Refuse numeric product policy embedded beside modelo-routing branches.
[group('check')]
check-modelo-regulatory-literals:
    @uv run --no-sync python -m dev.quality.modelo_regulatory_literals

[doc('Refuse regulatory literals embedded in modelo-specific registry modules.')]
[group('check')]
check-modelo-regulatory-embeds:
    @uv run --no-sync python -m dev.quality.modelo_regulatory_embeds

# Report every shipped module no declared product command reaches.
[group('check')]
check-unreachable-module-coverage:
    @uv run --no-sync python -m dev.quality.unreachable_module_coverage

# Report every exact unused symbol and orphaned test module in the live tree.
[group('check')]
check-unused-symbol-coverage:
    @uv run --no-sync python -m dev.quality.unused_symbol_coverage

# A store nothing fills reads as empty rather than as absent, so a count
# rendered from it reports zero forever and an aggregation contributes a zero
# where the source is missing. Known gaps are declared with their kind and
# rationale in dev/quality/secure_store_write_path.toml; a new one fails.
# Verify every encrypted store the application reads has a production writer.
[group('check')]
check-secure-store-write-path:
    @uv run --no-sync python -m dev.quality.secure_store_write_path

# Verify every Sphinx cross-reference in a docstring names a symbol that
# still exists; a dangling target fails the build.
[doc('Verify every docstring cross-reference resolves to a real symbol.')]
[group('check')]
check-docstring-references:
    @uv run --no-sync python -m dev.quality.docstring_reference_targets

# Report every name in __all__ that no non-test module imports and the live
# reachability audit also reports unused.
[doc('Refuse every exported name no non-test module consumes.')]
[group('check')]
check-unconsumed-export-coverage:
    @uv run --no-sync python -m dev.quality.unconsumed_export_coverage

# Refuse every production-readable persistence surface with no production writer.
[group('check')]
check-write-path-coverage:
    @uv run --no-sync python -m dev.quality.write_path_coverage

# Verify dependency declarations for drift or unused packages. Silent on success.
[group('check')]
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
[group('check')]
check-changed BASE="HEAD":
    @uv run --no-sync python -m dev.quality.changed_paths {{BASE}}

# Cheap dependency-surface preflight: verify pyproject, optional-extra registry,
# and frozen core/all-extras/all-groups exports before any artifact work.
[doc('Cheap dependency-surface preflight: verify pyproject, optional-extra registry, and frozen exports.')]
[group('test')]
test-packaging-smoke-dependencies:
    @uv run --no-sync python -m dev.packaging.dependency_surface

# Verify the packaging preflight command contracts. The marker expression is
# stated explicitly and kept equal to the campaign driver's parallel preflight
# pass (`dev.packaging.campaign`), so this local gate and a release leg select
# the same set. `dev/packaging/tests` is mixed-marker: inheriting the default
# `-m 'unit and ...'` expression from pyproject silently deselected every
# integration contract in it -- including the modules named for the
# packaging-smoke, Scoop, Homebrew, and Docker workflows the campaign runs this
# preflight ahead of -- and still exited zero.
# The excluded `serial` tests are not dropped silently: every one of them is
# owned by `test-packaging-smoke-serial`, and the installed-oracle cohort
# additionally by the narrower `test-packaging-smoke-installed-oracles`.
# `serial` is excluded by MARKER rather than left to the scheduler: an item
# selected here would be held out of the run by the collection hook behind a
# warning, which is a green summary over a test that never executed. `perf` is
# excluded by its registered policy, which holds it out of every per-push lane.
# Guarded by `dev/packaging/tests/test_preflight_recipe_selection.py`.
[doc('Verify the packaging preflight command contracts (dependency surface, source data, Docker/Scoop/Homebrew workflows).')]
[group('test')]
test-packaging-smoke-preflight:
    @uv run --no-sync pytest -v -m "(unit or integration) and not serial and not perf" dev/packaging/tests

# Cheap source-data preflight: fail before wheel, venv, or Docker work if a
# git-tracked shipped data file has been deleted from the worktree.
[doc('Cheap source-data preflight: fail before wheel, venv, or Docker work if a shipped data file was deleted.')]
[group('test')]
test-packaging-smoke-source:
    @uv run --no-sync python -m dev.packaging.source_preflight

# Operator-run: regenerate the committed AEAT manual PDF corpus-text sidecars
# after a corpus PDF changes. The sidecars are load-bearing for registry
# evidence validation, so re-run this and commit the regenerated JSON.
[doc('Operator-run: regenerate the committed AEAT manual PDF corpus-text sidecars after a corpus PDF changes.')]
[group('fix')]
fix-corpus-text:
    @uv run --no-sync python -m dev.corpus.extract_manual_corpus_text

# Freshness gate: fail (without writing) when any committed corpus-text sidecar
# is stale or missing against its source PDF.
[doc('Freshness gate: fail when any committed corpus-text sidecar is stale or missing against its source PDF.')]
[group('check')]
check-corpus-text:
    @uv run --no-sync python -m dev.corpus.extract_manual_corpus_text --check

# Build every distribution the release publishes, then refuse any file the index
# would reject on size. Same two operations the publish workflow performs, in the
# same order, so the local run and the hosted one can disagree only about the host.

#: The artifacts a plain checkout can produce. `build-devcontainer` and
#: `build-runner-image` are deliberately absent: both need a working Docker
#: daemon, so an aggregate that included them would fail on a machine that is
#: perfectly able to build every artifact this repository ships.
full_build_lanes := "build-distributions build-python-cohort"

# AGGREGATES RUN EVERY STEP and exit non-zero when any step failed; they do not
# stop at the first failure. An aggregate is asked for a complete picture, and
# fail-fast costs a round-trip per defect. That is why this dispatches into
# `dev/` rather than listing its members as just dependencies: a dependency
# chain cannot express run-all-then-report.
[doc('Build every artifact a plain checkout can produce; continue after failures and report per-lane timings.')]
[group('build')]
build-all:
    uv run --no-sync python -m dev.test_runs lanes {{full_build_lanes}}

[doc('Build every published distribution and refuse any file over the index cap.')]
[group('build')]
build-distributions:
    @uv build --out-dir var/distributions .
    @uv build --out-dir var/distributions packaging/cadrumo_data_manuals
    @uv build --out-dir var/distributions packaging/cadrumo_data_official
    @uv run --no-sync python -m dev.packaging.distribution_cap --directory var/distributions

# Run source and binary compatibility probes for every row in the checked-in
# runtime inventory. The release cohort is built once; binary rows consume its
# sealed bytes and never rebuild per runtime. Stable failures are blocking,
# while the inventory's prerelease canary remains visible as advisory evidence.
[doc('Run inventory-driven source and binary compatibility probes for every declared Python runtime.')]
[group('test')]
test-python-compatibility:
    uv run --no-sync python -m dev.ci.python_runtime_sweep

[doc('Construct the temporary Python wheel cohort once for the current smoke campaign.')]
[group('build')]
build-python-cohort: test-packaging-smoke-source
    @uv run --no-sync python -m dev.packaging.python_cohort build --output var/packaging-smoke-cohort/python

# Run both installed public transports against the exact built cohort.
[group('test')]
test-packaging-smoke-installed-oracles: build-python-cohort
    @uv run --no-sync pytest -v -n0 -m "integration and serial" dev/packaging/tests/test_installed_oracles.py

# Own the rest of the serial contracts in this directory. The preflight lane
# selects `not serial` because these must not run concurrently, and the oracle
# lane above names one module, so without this recipe the remaining serial
# tests here have no packaging-scoped owner: reaching them means running the
# tree-wide `test-integration-serial`, and someone verifying packaging alone
# gets a green result that never touched them. Depends on the cohort because
# several of these install the built wheels; the ones that do not are
# unaffected by having it.
# The expression keys on `serial` alone rather than on `integration and serial`:
# two serial contracts here carry `unit`, and the narrower expression left them
# owned by nothing that runs them -- selected by the preflight lane, held out
# of it by the scheduler, and outside this one. `perf` is deliberately NOT
# excluded: this recipe is the serving-path benchmark's only owner, and
# narrowing it away from that cohort makes those tests unreachable. Guarded by
# `dev/packaging/tests/test_preflight_recipe_selection.py`.
[doc('Run the serial packaging contracts the preflight lane excludes.')]
[group('test')]
test-packaging-smoke-serial: build-python-cohort
    @uv run --no-sync pytest -v -n0 -m "serial" dev/packaging/tests

# Local release-artifact smoke gates that do not need host package-manager access.
# The campaign driver builds the cohort once and runs the flavor lanes
# concurrently (bounded pool; lanes are disk-disjoint), then the serial
# installed-oracles pass — same proofs as the former serial aggregate at a
# fraction of the wall time (the Windows leg measured 26.3 min serial).
[doc('Local release-artifact smoke gates that do not need host package-manager access (portable profile).')]
[group('test')]
test-packaging-smoke:
    @uv run --no-sync python -m dev.packaging.campaign --profile portable

# One CI invocation keeps every artifact and oracle lane on the same cohort bytes.
[group('test')]
test-packaging-smoke-ci:
    @uv run --no-sync python -m dev.packaging.campaign --profile ci

# Per-push quick probe: cohort built once plus the single installed core smoke.
# Deliberately minimal (ten-minute per-push budget); every other flavor lane is
# a release-campaign proof carried by `test-packaging-smoke` / `test-packaging-smoke-ci`.
[doc('Per-push quick probe: cohort built once plus the single installed core smoke check.')]
[group('test')]
test-packaging-quick:
    @uv run --no-sync python -m dev.packaging.campaign --profile quick --skip-preflight

# ── Devcontainer ─────────────────────────────────────────────────────────────

# Build the reproducible dev image (.devcontainer/devcontainer.json + Dockerfile).
# `--target dev` matches devcontainer.json's `build.target`, so the recipe and
# the editor build the same stage of the one shared Dockerfile.
[doc('Build the reproducible dev image (.devcontainer/devcontainer.json + Dockerfile, `dev` stage).')]
[group('build')]
build-devcontainer:
    docker build --target dev -t cadrumo-devcontainer -f Dockerfile .

# Verify the dev image installs cleanly and its pre-baked toolchain works.
# The checks live in `dev/containers/devcontainer_smoke.py`, not inline here:
# `just` runs plain recipes through PowerShell on Windows, which parses `<` as
# a reserved operator, so an inline probe containing HTML failed at PARSE time
# before docker was invoked — reporting a recipe error that said nothing about
# the image. `bash -lc` is deliberate: it reproduces the LOGIN shell the VS Code
# integrated terminal uses, which is where the venv once fell off PATH.
[doc('Verify the dev image installs cleanly and its pre-baked toolchain (imports, unit collection, just, headless Chromium launch) works.')]
[group('test')]
test-devcontainer: build-devcontainer
    docker run --rm cadrumo-devcontainer bash -lc "python dev/containers/devcontainer_smoke.py"

# ── Self-hosted runner image ─────────────────────────────────────────────────

# Build the Linux self-hosted runner image (`runner` stage of the same
# Dockerfile). Declarative replacement for the hand-provisioned stock
# container described in dev/runners/README.md.
[doc('Build the self-hosted Linux runner image (`runner` stage of the shared Dockerfile).')]
[group('build')]
build-runner-image:
    docker build --target runner -t cadrumo-runner-linux -f Dockerfile .

# Verify the runner image carries every capability the fleet assumes present.
# Each check below maps to a documented outage: `gh` absent broke a release
# mid-cohort-seal, `brew` absent broke the acquisition lane's first step, and a
# `brew` reached through a symlinked prefix breaks `brew link` only at the very
# end of an install.
[doc('Verify the runner image carries gh, just, a canonical-prefix brew, and a runnable entrypoint.')]
[group('test')]
test-runner-image: build-runner-image
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
[doc('Audit codebase security posture using semgrep scans; advisory and always non-blocking.')]
[group('audit')]
audit-security:
    @uv run --no-sync python -m dev.audit.security

# Check if the RAG service daemon is running.
[group('service')]
rag-service-status:
    @uv run --no-sync vaultspec-rag server status --port 8766

# Run programmatic semantic audit checks using the local RAG daemon. Silent on success.
[group('check')]
check-semantic:
    @uv run --no-sync python -m dev.audit.semantic

# Two questions about the same artifacts. actionlint asks whether the YAML is
# well-formed and its expressions resolve; the CI contract asks whether a `run:`
# step is calling a recipe or re-implementing one. A workflow can be perfectly
# valid YAML and still install `just` with an unpinned `scoop install`, which
# is what two Windows legs here did.

# Lint the workflows, then hold them to the CI/justfile contract.
[group('check')]
check-workflow:
    @uv run --no-sync python -m dev.actionlint
    @uv run --no-sync python -m dev.ci_contract

[doc('Mutation-prove each merge-check contract fails and passes in isolation.')]
[group('check')]
prove-check-set:
    @uv run --no-sync python dev/ci/prove_check_set_guards.py

# Run all pre-commit hooks via prek. Silent on success; replays hook output on failure.
[group('check')]
check-pre-commit:
    @uv run --no-sync python -m dev.quality.quiet uv run --no-sync prek run --all-files

# Excludes check-pre-commit (re-runs ruff + ty + architecture) and the local-only RAG/semantic checks.
# Run every fast static gate to completion; report only failures; silent on full pass.
[group('check')]
check-all:
    @uv run --no-sync python -m dev.quality.suite

# ── Code mutations (Write) ──────────────────────────────────────────────────

# Auto-repair every lint violation that carries a safe fix (ruff check --fix).
[group('fix')]
fix-style:
    @uv run --no-sync ruff check --fix .

# Auto-sort imports only (ruff I-rule safe fixes).
[group('fix')]
fix-imports:
    @uv run --no-sync ruff check --select I --fix .

# Auto-format all python source files (ruff format).
[group('fix')]
fix-format:
    @uv run --no-sync ruff format .

# Action every automatically-fixable issue in one pass: safe lint fixes then formatting.
[group('fix')]
fix-all:
    @uv run --no-sync python -m dev.quality.fixes

# Trigger incremental vector re-indexing via the loopback service.
[group('service')]
rag-index:
    @uv run --no-sync vaultspec-rag index --type all --port 8766

# Reconcile the committed API-reference stubs with the source module tree.
[doc('Regenerate API documentation stubs; pass CLI options through unchanged.')]
[group('docs')]
docs-api-scaffold *ARGS:
    @uv run --no-sync python -m dev.docs.apidocs scaffold {{ARGS}}

# Refresh committed CLI-sequence goldens. Scope with the underlying CLI options.
[doc('Refresh committed documentation CLI-sequence goldens.')]
[group('docs')]
docs-sequences-refresh *ARGS:
    @uv run --no-sync python -m dev.docs.sequences refresh {{ARGS}}

# Run Terminology Handbook curation commands such as scaffold, set, and relate.
[doc('Run a Terminology Handbook mutation command.')]
[group('docs')]
docs-terminology *ARGS:
    @uv run --no-sync python -m dev.docs.terminology_handbook {{ARGS}}

# Regenerate the committed terminology coverage report.
[doc('Regenerate the terminology coverage report.')]
[group('docs')]
docs-terminology-coverage *ARGS:
    @uv run --no-sync python -m dev.docs.terminology.coverage report {{ARGS}}

# Run the resident-RAG terminology sweep and optionally write its reviewed map.
[doc('Run the terminology relevance sweep against the resident RAG service.')]
[group('docs')]
docs-terminology-sweep *ARGS:
    @uv run --no-sync python -m dev.docs.terminology.sweep {{ARGS}}

# Mine or otherwise maintain the synonym ratification queue.
[doc('Run a terminology synonym maintenance command.')]
[group('docs')]
docs-terminology-synonyms *ARGS:
    @uv run --no-sync python -m dev.docs.terminology.synonyms {{ARGS}}

# Route locale catalogue changes through their canonical maintenance CLI.
[doc('Run a locale catalogue maintenance command.')]
[group('maintenance')]
dev-locales *ARGS:
    @uv run --no-sync python -m dev.locales {{ARGS}}

# Scaffold a modelo or render its contributor checklist through the owning CLI.
[doc('Run a new-modelo scaffolding or checklist command.')]
[group('maintenance')]
dev-newmodelo *ARGS:
    @uv run --no-sync python -m dev.registry.newmodelo {{ARGS}}

# Check, publish, or republish a generated registry target through the owning CLI.
[doc('Run a generated registry pipeline command.')]
[group('maintenance')]
dev-registry-pipeline *ARGS:
    @uv run --no-sync python -m dev.registry.pipeline {{ARGS}}

# Generate and maintain TUI visual-review artifacts.
[doc('Run a TUI visual-review command.')]
[group('maintenance')]
dev-tui-review *ARGS:
    @uv run --no-sync python -m dev.tui {{ARGS}}

# Drive the persistent interactive TUI harness session.
[doc('Run an interactive TUI harness command.')]
[group('maintenance')]
dev-tui-harness *ARGS:
    @uv run --no-sync python -m dev.tui.harness {{ARGS}}

# ── Testing ──────────────────────────────────────────────────────────────────

pytest_workers := env_var_or_default("CADRUMO_PYTEST_WORKERS", "auto")

# The dedicated harness verdict's members: the ONE declaration of which proofs
# reach their subject by spawning a real child pytest. Each path is written
# exactly once in this file. The enrolling recipe below runs exactly these, and
# every corpus-walking lane excludes exactly these -- derived with `prepend`,
# never restated, because a member list repeated at five call sites is five
# chances to drift into a lane that silently nests a worker pool inside a pool.
#
# The worker hook sits among hundreds of ordinary unit modules in
# `src/cadrumo/tests`, so naming its directory would drag that whole corpus into
# an outer-serial lane and out of every parallel one; only the file is named.
harness_worker_hook := "src/cadrumo/tests/test_worker_count_hook_harness.py"
harness_members := harness_worker_hook
harness_exclusions := prepend("--ignore=", harness_members)

# Run the fast test-framework ratchets for discovery, markers, skip/xfail, mock/test-double, monkeypatch, broad raises, bare except, tautology drift, and the exit-code contract.
[group('test')]
test-ratchets:
    @uv run --no-sync pytest -v -p no:cacheprovider dev/tests/test_test_inventory.py dev/tests/test_no_skip_xfail.py dev/tests/test_no_broad_exception_raises.py dev/tests/test_no_bare_except.py dev/tests/test_exit_code_contract.py

# Run the worker-count hook verdict outer-serially so it can inspect the
# installed pytest hook without nesting another worker pool.
[doc('Run the dedicated outer-serial worker-count hook verdict.')]
[group('test')]
test-harness:
    @uv run --no-sync pytest -q -m integration --collect-only -n0 {{harness_worker_hook}}
    @uv run --no-sync pytest -v -m integration -n0 --timeout=900 {{harness_members}}

# Run the unit test suite in parallel, ignoring workbook parity tests. Per-test
# verdicts stream while the lane is running. `durations` is optional and prints
# pytest's slowest-N-tests profile (CI passes a value to keep a rolling
# public log of the suite's heaviest tests; local runs leave it unset).
#
# The reporting flags now live in `[tool.pytest.ini_options]` addopts rather
# than on every lane below, which restated `-rsf --tb=short` thirty-five times.
# `-ra` there supersedes `-rsf`: pytest's default `-r` value is `fE`, so a bare
# `-rs` REPLACES it and the short-summary `FAILED path::test` lines disappear,
# and every triage path this repository documents -- see the background-capture
# rule -- greps the log for `^FAILED`. `a` reports every non-passing outcome, so
# nothing has to be re-added flag by flag. `--tb=short` is there for the same
# reason it always was: a lane with thousands of failures writing a FULL
# traceback each produced a TEN MILLION line log, slower to write than the tests
# were to run and unreadable by any tool.
#
# `-v` stays on the lanes, and is the one reporting flag that does: under `-q` pytest withholds every failure IDENTITY until the
# run completes, so an hour-long lane that is killed, wedged, or simply still
# running tells you nothing at all -- only a growing wall of dots. `-rsf` was
# added earlier for the same class of problem but only helps at the END. Under
# `-v` each worker prints `[gwN] [ NN%] FAILED <nodeid>` the moment the test
# finishes, so `grep -E '^\[gw.*FAILED' suite.log` yields a live fail list
# while the lane is still running. The console is noisier; the capture rule
# already says to redirect to a file, and a greppable file is the point.
[doc('Run the unit test suite in parallel. Streams failure identities as they happen.')]
[group('test')]
test-unit durations="":
    @uv run --no-sync pytest -v -n {{pytest_workers}} --dist=loadfile -m 'unit and not external_tool and not os_keychain and not windows_only and not tui_render' {{ if durations == "" { "" } else { "--durations=" + durations } }}

# Focused subsystem selectors use the same explicit offline-capability boundary
# as the full lanes. Each runs ordinary tests under xdist and isolation-sensitive
# tests separately at -n0; a focused green therefore cannot hide serial tests.
[doc('Run all offline CLI tests, splitting parallel and isolation-sensitive serial passes.')]
[group('test')]
test-cli:
    @uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/entrypoints/cli
    @uv run --no-sync pytest -v -n0 -m "(unit or integration) and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/entrypoints/cli

# The TUI currently has no serial-marked case. Keep an explicit serial pass so a
# future one cannot fall out of the focused selector; pytest exit 5 is accepted
# only for that visible empty selection, never for a collected failure.
[doc('Run all offline TUI tests and boundary guards, splitting parallel and serial passes.')]
[group('test')]
[unix]
test-tui:
    #!/usr/bin/env bash
    set -uo pipefail
    failed=0
    uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/entrypoints/tui dev/tui/tests src/cadrumo/entrypoints/cli/tests/test_tui_launcher.py dev/quality/tests/test_cli_tui_entrypoint_boundary.py dev/tests/test_importlinter_tui_boundaries.py || failed=1
    uv run --no-sync pytest -v -n0 -m "(unit or integration) and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/entrypoints/tui dev/tui/tests src/cadrumo/entrypoints/cli/tests/test_tui_launcher.py dev/quality/tests/test_cli_tui_entrypoint_boundary.py dev/tests/test_importlinter_tui_boundaries.py
    serial_status=$?
    if [[ "$serial_status" -eq 5 ]]; then
        echo "No serial TUI tests are currently declared."
    elif [[ "$serial_status" -ne 0 ]]; then
        failed=1
    fi
    exit "$failed"

[doc('Run all offline TUI tests and boundary guards, splitting parallel and serial passes.')]
[group('test')]
[windows]
test-tui:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $failed = $false
    uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/entrypoints/tui dev/tui/tests src/cadrumo/entrypoints/cli/tests/test_tui_launcher.py dev/quality/tests/test_cli_tui_entrypoint_boundary.py dev/tests/test_importlinter_tui_boundaries.py
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    uv run --no-sync pytest -v -n0 -m "(unit or integration) and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/entrypoints/tui dev/tui/tests src/cadrumo/entrypoints/cli/tests/test_tui_launcher.py dev/quality/tests/test_cli_tui_entrypoint_boundary.py dev/tests/test_importlinter_tui_boundaries.py
    $serialStatus = $LASTEXITCODE
    if ($serialStatus -eq 5) {
        Write-Host 'No serial TUI tests are currently declared.'
    }
    elseif ($serialStatus -ne 0) {
        $failed = $true
    }
    if ($failed) { exit 1 }

# Calculation coverage is deliberately broader than the application package:
# registry compilation/runtime tests are co-owners of executable tax behavior.
# As with TUI, keep an explicit currently-empty serial pass for future changes.
[doc('Run application calculations plus registry calculation/runtime tests, splitting parallel and serial passes.')]
[group('test')]
[unix]
test-calculations:
    #!/usr/bin/env bash
    set -uo pipefail
    failed=0
    uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests src/cadrumo/application/registry/tests || failed=1
    uv run --no-sync pytest -v -n0 -m "(unit or integration) and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests src/cadrumo/application/registry/tests
    serial_status=$?
    if [[ "$serial_status" -eq 5 ]]; then
        echo "No serial calculation tests are currently declared."
    elif [[ "$serial_status" -ne 0 ]]; then
        failed=1
    fi
    exit "$failed"

[doc('Run application calculations plus registry calculation/runtime tests, splitting parallel and serial passes.')]
[group('test')]
[windows]
test-calculations:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    $failed = $false
    uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests src/cadrumo/application/registry/tests
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    uv run --no-sync pytest -v -n0 -m "(unit or integration) and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests src/cadrumo/application/registry/tests
    $serialStatus = $LASTEXITCODE
    if ($serialStatus -eq 5) {
        Write-Host 'No serial calculation tests are currently declared.'
    }
    elseif ($serialStatus -ne 0) {
        $failed = $true
    }
    if ($failed) { exit 1 }

# Run the integration test suite in two lanes: the bulk in parallel (xdist,
# excluding serial-marked tests), then the isolation-sensitive `serial`-marked
# tests alone with no workers (-n0). The serial lane exists because a handful of
# tests mutate process-global state (the master-key-provider singleton) and
# flake under `-n auto` interleaving while passing cleanly in isolation.
[doc('Run the integration suite in two lanes: parallel xdist, then the isolation-sensitive serial tests alone.')]
[group('test')]
test-integration:
    @just test-integration-parallel
    @just test-integration-serial

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
# the reason `test-packaging-smoke-preflight` states it: these directories are
# mixed-marker, so inheriting the default `-m 'unit and ...'` would silently
# deselect the integration contracts and still exit zero.
#
[doc('Run the dev/ tooling gates that no other lane reaches (audit, deploy, env, identity, locales, sanitizer, registry, docs, agent-eval, ingest-harness, and TUI-harness subsystems).')]
[group('test')]
test-dev-tooling:
    @uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not resident_service and not external_tool" dev/audit/tests dev/corpus/tests dev/deploy/tests dev/docs/tests dev/env/tests dev/identity/tests dev/locales/tests dev/readme/tests dev/tests dev/test_runs/tests dev/sanitizer/tests dev/registry/tests dev/registry/newmodelo/tests dev/registry/aeip/tests dev/docs/preprocess/tests dev/docs/sequences/tests dev/docs/terminology/tests dev/docs/terminology_handbook/tests dev/agent_eval/tests dev/ingest_harness/tests dev/containers/tests dev/smoke/tests dev/tui/tests dev/tui/harness/tests dev/registry/parity/tests

# Run the registry conformance suite. It sits in its own lane rather than in
# `test-dev-tooling` because of cost, not category: a sequential local run
# measured roughly two minutes per test across 32 tests, where that whole
# lane's other 24 directories finish in well under a minute. The composer
# walks every revision in the bundled registry, which is the same reason
# `dev/tests/test_registry_conformance_gate.py` records the real run as being
# beyond the per-push budget.
#
# It is named here so the directory sits inside a lane at all. Left unnamed it
# was one of six directories `dev/tests/test_lane_reachability.py` reported as
# swept by nothing -- a suite that looks like coverage and reports to no one.
[doc('Run the registry conformance suite (slow: walks every bundled revision).')]
[group('test')]
test-registry-conformance:
    @uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not resident_service and not external_tool" --timeout=300 dev/registry/conformance/tests

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
# way -- `unit`, `hex_core`, `docs-build` -- and it needs no browser or server, so it
# costs the lane a directory walk.
[doc('Run the dev-tree workflow/tooling conformance gates that CI runs per-push.')]
[group('test')]
test-dev-ci:
    @uv run --no-sync pytest -v -n 8 --timeout=900 -m "unit or (integration and not serial)" dev/ci/tests dev/packaging/tests dev/quality/tests dev/release/tests dev/docs/apidocs/tests dev/docs/tests/test_api_stubs.py
    @uv run --no-sync pytest -v -n0 --timeout=900 -m "integration and serial" dev/ci/tests dev/quality/tests dev/release/tests dev/docs/apidocs/tests

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
[group('test')]
test-per-push-integration-gates:
    @uv run --no-sync pytest -v -n {{pytest_workers}} -m "integration and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo_harness/tests/test_rule_surface_conformance.py src/cadrumo/application/user_profile/tests/test_status_projection.py src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py dev/tests/test_suggestion_command_conformance.py

# Enrol the tests that query the resident vaultspec-rag search service. Held out
# of every other lane by the `resident_service` marker, because the service is a
# separate product this project does not install and its own isolation guard
# refuses the HTTP call under pytest -- so from a plain invocation these fail on
# the harness before the corpus is ever consulted.
#
# READ BEFORE TRUSTING A GREEN RESULT. This recipe assumes a started AND fully
# indexed service. A truncated index answers confidently rather than refusing,
# so these gates can pass thinly against a partial corpus. Confirm the index is
# whole before reading a pass as evidence; `just rag-service-status` reports status, and a
# section count far below the tracked file count means the answers are worthless
# even though nothing errored.
[doc('Enrol the tests that query the resident vaultspec-rag search service (held out of every other lane).')]
[group('test')]
test-resident-service:
    @uv run --no-sync pytest -v -n0 -m "resident_service" dev/docs/preprocess/tests dev/docs/terminology/tests

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
[group('test')]
test-both-lanes:
    @just test-harness
    @just test-unit
    @just test-integration

# Execute every distinct test population through its owning recipe. Lanes run
# sequentially because several share caches, generated artifacts, credential
# stores, or services. A lane failure is recorded without suppressing its live
# output, and independent later lanes still run; the final non-zero exit reports
# the complete failure set. Capability-gated lanes deliberately remain in the
# list: their owning recipes must report an unmet LibreOffice, desktop-keychain,
# resident-service, or live-read precondition instead of the aggregate silently
# claiming those tests ran. This composes tests only; it performs no environment
# setup and no Vaultspec administration.
full_test_lanes := "test-harness check-registry test-unit test-integration-parallel test-integration-serial test-dev-ci test-dev-tooling test-registry-conformance docs-check test-packaging-smoke-serial test-channel-artifacts test-workbook-parity test-os-keychain test-resident-service test-live"

[doc('Run every test population sequentially; stream output, continue independent lanes after failures, and report per-lane timings.')]
[group('test')]
test-all:
    uv run --no-sync python -m dev.test_runs lanes {{full_test_lanes}}

[doc('Run only the parallel integration lane, holding the isolation-sensitive serial tests out.')]
[group('test')]
test-integration-parallel:
    @uv run --no-sync pytest -v -n {{pytest_workers}} {{harness_exclusions}} -m "integration and not serial and not os_keychain and not windows_only and not tui_render"

# Run only the serial (isolation-sensitive) integration lane, no xdist workers.
[group('test')]
test-integration-serial:
    @uv run --no-sync pytest -v {{harness_exclusions}} -m "integration and serial and not perf and not os_keychain and not windows_only and not tui_render" -n0

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
# Enrol the Windows-only surface. Every lane excludes `windows_only`, because on
# a POSIX checkout the console-launcher stubs these tests read do not exist at
# all -- there is nothing to assert about. On Windows they are ordinary tests.
[doc('Run the tests whose subject exists only on Windows (console launcher stubs).')]
[group('test')]
test-windows-only:
    uv run --no-sync pytest -v -n0 -m windows_only dev/packaging/tests

# Render the visual inventory, then assert on it. The render is the point: these
# tests read real Textual exports, and a measured full render takes over ten
# minutes, which is why `tui_render` is excluded from every ordinary lane rather
# than folded into one.
[doc('Render the TUI visual inventory and run the tests that read real exports.')]
[group('test')]
test-tui-render:
    uv run --no-sync python -m dev.tui render
    uv run --no-sync pytest -v -n0 -m tui_render dev/tui/tests


[doc('Run the OS-credential-store custody tests (interactive desktop session only).')]
[group('test')]
test-os-keychain:
    uv run --no-sync pytest -v -n0 -m os_keychain src/cadrumo/application/user_profile/tests src/cadrumo/entrypoints/cli/tests src/cadrumo/tests/test_secure_sql.py src/cadrumo/adapters/persistence/storage/custody/tests src/cadrumo/adapters/persistence/storage/master_key/tests src/cadrumo/adapters/persistence/storage/tests

# Run live-read tests serially: they observe shared external state and the test
# guide explicitly forbids xdist for live tests. Failure identities stream as
# they occur; the shared prerequisite gate fails when live access is not opted in.
[doc('Run the opt-in live-read test suite serially. Streams failure identities as they happen.')]
[group('test')]
test-live:
    @uv run --no-sync pytest -v -n0 -m aeat_live

# Run the produce, verify, and export end-to-end smoke tests.
[group('test')]
test-smoke:
    uv run --no-sync pytest -v src/cadrumo/application/modelo/tests/test_file_flow_calculation.py src/cadrumo/application/modelo/tests/test_file_flow_verify.py src/cadrumo/application/modelo/tests/test_file_flow_filing.py src/cadrumo/application/modelo/tests/test_export.py

# Run the LibreOffice workbook parity tests. These carry `external_tool` rather
# than `unit`, so the default `-m 'unit'` in addopts must be overridden here or
# this lane selects nothing; the explicit path also overrides the addopts
# --ignore that keeps the directory out of the default lane.
[doc('Run the LibreOffice workbook parity tests (external_tool marker, outside the default unit lane).')]
[group('test')]
test-workbook-parity:
    uv run --no-sync pytest -v -n0 -m external_tool dev/registry/tests/test_workbook_parity.py

# Run the Homebrew/Scoop channel-artifact conformance tests. These bind
# the generated formula and manifest to a real built cohort. Explicit paths
# and -n0, never marker selection alone: a marker-filtered xdist run holds
# serial tests out while still reporting a clean pass. Dispatch-only
# (ci-full.yml) rather than per-push: these tests build real sdists and
# wheels, costing minutes the per-push budget cannot absorb.
[doc('Run the Homebrew/Scoop channel-artifact conformance tests (serial, builds real sdists and wheels).')]
[group('test')]
test-channel-artifacts:
    @uv run --no-sync pytest -v -n0 --timeout=900 -m serial packaging/homebrew/tests packaging/scoop/tests

# Run the unit suite with live per-test verdicts, coverage, and fail-under check.
[doc('Run the unit test suite with a coverage report and a fail-under check.')]
[group('test')]
[unix]
test-coverage:
    @uv run --no-sync pytest -v --cov=cadrumo --cov-report=term-missing --cov-fail-under=60

[doc('Run the unit test suite with a coverage report and a fail-under check.')]
[group('test')]
[windows]
test-coverage:
    #!pwsh
    $ErrorActionPreference = 'Stop'
    uv run --no-sync pytest -v --cov=cadrumo --cov-report=term-missing --cov-fail-under=60
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# ── Advisory audits ──────────────────────────────────────────────────────────

# List every ty + pyrefly diagnostic verbatim (advisory; always exits 0).
[group('audit')]
audit-types:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-types -- uv run --no-sync python -m dev.quality.types --full

# Gate on published vulnerability advisories against the pinned dependency
# tree. This repository had NO dependency vulnerability audit of any kind -- no
# uv audit, no pip-audit, no osv-scanner -- while shipping binaries; every
# audit-* recipe below is a code-quality dimension.
#
# This is the ONE audit that GATES: a published advisory against a pinned
# version is a verdict, not a lead, so it is deliberately NOT part of
# `audit-all`, which is advisory and always exits 0. It is not built on
# `uv audit` either -- that preview tool exits 0 even when it prints
# advisories, which is exactly how three sibling repositories ended up with a
# gate that could not fail. The runner reads the committed lockfiles itself,
# queries OSV, and derives the verdict from the finding set.
#
# Exits 1 on an unaccepted advisory or an expired suppression, 7 if the audit
# could not complete (a gate that cannot run is never a pass). Accepted
# advisories live in dependency-audit-allowlist.toml, each with a reason and an
# expiry date; binaries no lockfile pins are declared in
# dependency-audit-binaries.toml. `--json` emits the machine report; nothing is
# written to disk unless VAULTSPEC_CI_REPORTS names a directory, so the
# zero-Actions-artifact posture is preserved.
[doc('Gate on published vulnerability advisories against every pinned dependency; the one audit that fails the build.')]
[group('audit')]
audit-deps *ARGS:
    @uv run --no-sync python -m dev.audit.dependency_audit {{ARGS}}

# Run complexity audits for production code.
[group('audit')]
audit-complexity:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-complexity -- uv run --no-sync python -m dev.audit.complexity

# Scan for dead code. The whitelist clears individually-justified
# false positives (contract-fixed signature params); see its docstring.
# The runner (dev.audit.dead_code) owns the vulture invocation AND its
# parsing, so this recipe and audit-all's dead-code dimension cannot drift
# apart or disagree. Pass --full for the uncapped finding list.
[doc('Scan for dead code, clearing individually-justified false positives via the whitelist.')]
[group('audit')]
audit-dead-code:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-dead-code -- uv run --no-sync python -m dev.audit.dead_code

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
[group('audit')]
audit-unreachable-code *ARGS:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-unreachable-code -- uv run --no-sync python -m dev.audit.unreachable_code {{ARGS}}

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
[group('audit')]
audit-write-paths *ARGS:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-write-paths -- uv run --no-sync python -m dev.audit.write_path_coverage {{ARGS}}

# Scan for copy-paste code duplication. Aggregate line + capped clone list.
# The runner owns the jscpd invocation AND its parsing, so this recipe and the
# health report's duplication dimension cannot drift apart or disagree.
[doc('Scan for copy-paste code duplication; aggregate line count plus a capped clone list.')]
[group('audit')]
audit-duplication:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-duplication -- uv run --no-sync python -m dev.audit.duplication

# Perform an on-demand semantic search query delegating to the running RAG daemon.
[group('service')]
rag-search QUERY:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-rag -- uv run --no-sync vaultspec-rag search "{{QUERY}}" --port 8766 --timeout 45.0

# Run all retained advisory audits (complexity, dead code, duplication,
# security) as one composed red/amber/green dashboard; tolerant of
# individual findings (always exits 0). The runner (dev.audit.advisory) owns
# the composition, so this recipe cannot drift from what it reports. Full,
# uncapped results are persisted to a unique date-partitioned directory below
# .logs/audit-runs/ every run (summary.json for machine parsing, summary.md for
# the human-readable uncapped text); both identify the producing command.
# Advisory-audit sibling of `check-all` (the fast static gates).
[doc('Run all advisory audits; full command-identified results persist below .logs/audit-runs/.')]
[group('audit')]
audit-all *ARGS:
    @uv run --no-sync python -m dev.audit.advisory {{ARGS}}

# Monthly code-health report: shadowing, duplication, layering, complexity,
# each classified red/amber/green. Composes the scanners above (plus
# lint-imports) into one contributor-facing verdict. Exits 1 if any
# dimension is RED; AMBER dimensions are advisory debt, not a gate.
[doc('Monthly code-health report: shadowing, duplication, layering, and complexity, each classified red/amber/green.')]
[group('audit')]
audit-health-report *ARGS:
    @uv run --no-sync python -m dev.audit.report {{ARGS}}

# Show conformance status across all modelo revisions and the derived release
# closure. Both verbs exit 0 always (screen posture): ``report`` renders every
# axis, ``closure`` renders the temporal, source, and filing release predicate.
# To gate on the completeness claim use ``closure --check`` directly.
[doc('Show conformance status across all modelo revisions and the derived release closure.')]
[group('audit')]
audit-registry-conformance:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-registry-report -- uv run --no-sync python -m dev.registry.conformance report
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-registry-closure -- uv run --no-sync python -m dev.registry.conformance closure

# Inspect AEIP continuity events, open adjudications, or the proposed plan.
[doc('Run an AEIP continuity audit command.')]
[group('audit')]
audit-aeip *ARGS:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-aeip -- uv run --no-sync python -m dev.registry.aeip {{ARGS}}

# ── Documentation ────────────────────────────────────────────────────────────

# Build changed narrative and API reference documents.
[group('docs')]
docs-build:
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

# Re-execute committed CLI sequences and report divergence without rewriting.
[doc('Verify committed documentation CLI-sequence goldens.')]
[group('docs')]
docs-sequences-check *ARGS:
    uv run --no-sync python -m dev.docs.sequences check {{ARGS}}

# Report the health of the curated Terminology Handbook.
[doc('Audit the curated Terminology Handbook.')]
[group('docs')]
docs-terminology-audit:
    uv run --no-sync python -m dev.test_runs.command --family audit-runs --label docs-terminology-audit -- uv run --no-sync python -m dev.docs.terminology_handbook audit

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
    just docs-lang es
    just docs-lang ca
    just docs-lang hu

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

# Run docstring structure and Sphinx build checks with live per-test verdicts.
# `workers` bounds the pytest-xdist lane: CI passes 8 (machine-aware sizing,
# .github/ci-control-plane.md — the 24-core box is shared with other
# repositories' runners, and 8 is a working pin, not a derivation); local
# development keeps the `auto` default per the same control plane.
[doc('Run docstring structure and Sphinx build checks. Streams failure identities as they happen.')]
[group('docs')]
docs-check workers="auto":
    @uv run --no-sync pytest -v -n {{workers}} dev/docs/tests dev/docs/apidocs/tests src/cadrumo/tests/test_docstring_core_struct_links.py -m "docs or unit or (integration and not serial)"
    @uv run --no-sync doc8 docs
    @uv run --no-sync interrogate -c pyproject.toml src/cadrumo

# ── Database migrations ──────────────────────────────────────────────────────

# Generate a new Alembic database migration file. Identical body across
# platforms — a single plain `uv run` invocation needs no shell preamble.
[doc('Generate a new Alembic database migration file.')]
[group('maintenance')]
dev-db-migrate message:
    uv run alembic revision --autogenerate -m "{{message}}"

# Upgrade the database schema to the latest version. Identical body across
# platforms — a single plain `uv run` invocation needs no shell preamble.
[doc('Upgrade the database schema to the latest version.')]
[group('maintenance')]
dev-db-upgrade:
    uv run alembic upgrade head

# ── Deployment ───────────────────────────────────────────────────────────────
#
# Its own lane, deliberately. Building documentation is a local
# check-and-balance verification with no bearing on deployment; publishing
# writes bytes to a live public destination. The `docs-build` group therefore holds
# only build and check verbs, and the three recipes below are the only ones in
# this file that reach outward at all.
#
# The `release-publish` group is adjacent but disjoint, and nothing here re-declares
# any of it: every release recipe is read-only (`release-publish` is a dry-run preview,
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
release-readiness *ARGS:
    uv run --no-sync python -m dev.release.readiness {{ARGS}}

# Print the rollback procedure for a released version that must be pulled.
# Read-only — never runs a destructive action; every step below is printed
# for a human to run deliberately. See RELEASING.md#diagnose-and-recover.
[doc('Print the rollback procedure for a released version that must be pulled (read-only, human-run).')]
[group('release')]
release-rollback version:
    uv run --no-sync python -m dev.release rollback {{version}}

# Preview the next version release via dry-run.
[doc('Preview the next version release via dry-run (release-please).')]
[group('release')]
release-publish:
    uv run --no-sync python -m dev.release preview

# ===========================================================================
#  meta
# ===========================================================================

# The composed pipeline, in the order CI runs it, so a green local run means
# what a green CI run means. The composition is the fleet's, and the two
# rulings inside it are worth stating where they are made:
#
#   `audit-deps` and NOTHING else from the audit group. Every other audit
#   dimension is advisory by construction - each finding is a lead to confirm,
#   and a pipeline that fails on a lead teaches people to stop reading it. A
#   published advisory against a pinned version is not a lead, it is a verdict.
#
#   BUILD IS PART OF IT. A break on the release path otherwise surfaces at
#   release, when the tag is already cut and the only remedies are a revert or
#   a hotfix. The gates before it prove the source is well-formed and the tests
#   pass; only this one proves the artifact a user receives can still be
#   produced from it.

# Run the full local gate: static analysis, dependency audit, tests, build.
[group('meta')]
ci:
    @just check-all
    @just audit-deps
    @just test-unit
    @just build-all
