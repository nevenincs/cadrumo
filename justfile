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
# `setup` exit code onto 1 and destroy the distinction between "a host tool is
# missing", "the lockfile drifted", and "an editor is holding .venv open".
# Appending an explicit propagation is the whole remedy; it is empty on unix,
# where `sh` already forwards the status, so no recipe needs a platform pair.
propagate := if os_family() == "windows" { "; exit $LASTEXITCODE" } else { "" }

# Canonical checkout setup. This is the minimal convergence facade: it creates
# the pinned Python environment, installs repository tooling, and materializes
# local environment configuration. Workstation tools and browser binaries are
# optional capabilities and therefore have separate commands below.
[doc('Converge a checkout with Python, repository tooling, and local environment configuration.')]
[group('setup')]
setup:
    uv run --no-project --python 3.13.11 -- python -m dev.init all{{propagate}}

[doc('Synchronize the pinned Python environment from uv.lock.')]
[group('setup')]
setup-python:
    uv run --no-project --python 3.13.11 -- python -m dev.init python{{propagate}}

[doc('Install repository tooling, including pinned actionlint, after the Python environment is available.')]
[group('setup')]
setup-repository-tools:
    uv run --no-project --python 3.13.11 -- python -m dev.init tools{{propagate}}

[doc('Check checkout setup state without writing a report or changing files.')]
[group('setup')]
setup-check:
    uv run --no-project --python 3.13.11 -- python -m dev.init check{{propagate}}

# Optional workstation CLI prerequisites for non-Python audit recipes. This is
# deliberately outside the minimal checkout setup.
[doc('Provision optional workstation CLI prerequisites for non-Python audits; mutates workstation tooling only.')]
[group('setup')]
setup-workstation-tools:
    uv run --no-sync python -m dev.env workstation-tools{{propagate}}

# ── Environment Setup and Doctor ─────────────────────────────────────────────

# Copy env/.env.example → env/.env if the latter is missing. No-op otherwise.
[doc('Copy env/.env.example to env/.env if the latter is missing; no-op otherwise.')]
[group('setup')]
setup-env:
    uv run --no-sync python -m dev.env setup{{propagate}}

[doc('Diagnose the developer toolchain by PATH inspection; does not install or write anything.')]
[group('doctor')]
doctor-dev:
    uv run --no-sync python -m dev.env doctor{{propagate}}

[doc('Verify the product capability configuration without changing it.')]
[group('doctor')]
doctor-product:
    uv run --no-sync aeat config check{{propagate}}

[doc('Verify Python package consistency without modifying the environment.')]
[windows]
doctor-python:
    uv pip check --python .venv/Scripts/python.exe{{propagate}}

[doc('Verify Python package consistency without modifying the environment.')]
[unix]
doctor-python:
    uv pip check --python .venv/bin/python{{propagate}}

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
# recipe with elevation. Verify the result with `just doctor-browser`.

[doc('Provision optional Playwright Chromium and system Chrome browser channels.')]
[group('setup')]
setup-browser:
    uv run --no-sync playwright install chromium{{propagate}}
    uv run --no-sync playwright install chrome{{propagate}}

# Verify the local environment is correctly provisioned with the CONFIGURED
# Playwright browser channel (per `cadrumo_browser_channel`, default `chrome`)
# and its dependencies, per ADR 2026-04-12-playwright-anti-bot-adr. Performs a
# real headless launch-and-close of that channel (never hardcodes "chrome" —
# reads the live setting) and prints the exact remediation command on failure.
[doc('Probe the configured browser channel with a real read-only launch.')]
[group('doctor')]
doctor-browser:
    uv run --no-sync python -m dev.env.playwright_doctor{{propagate}}

# One reclamation surface over three families that used to be three commands:
# ignored worktree output, release-build scratch under `var/`, and the temp
# directory's pytest/session/test-run storage. They were split by which module
# happened to own the rules, which is not a split an operator can act on -- the
# largest accrual moves between `var/` and `.logs/` depending on what has been
# run, so a report covering one at a time never showed where the space went.
#
# ── Blast radius, for whoever or whatever is about to run `clean-apply` ──────
#
# NOT AT RISK, under any flag. Tracked files, staged changes, and untracked
# files that are not gitignored are never enumerated, never sized and never
# removed. So are `.env` and `env/`, every `vault*` tree, `.venv`, `secrets/`,
# `cadrumo-storage/`, and anything named like key material (`*.key`, `*.kdf`,
# `*.pem`, `*.db`). In-flight work is safe; that is the one guarantee here that
# is structural rather than a judgement call.
#
# AT RISK, and the reason this is not a routine command. `clean-apply` deletes
# irreversibly -- no trash, no undo -- and it REACHES OUTSIDE THIS WORKTREE:
#   * the OS temp directory, including the scratchpads of OTHER Claude Code
#     sessions on this machine. Those carry no owner on disk, so abandonment is
#     INFERRED from 72h of silence on two activity signals, not observed. A
#     colleague or agent whose session has been idle over a long weekend is
#     indistinguishable from an abandoned one, and this command will take it.
#   * `.logs/test-runs/`, which is failure evidence from earlier runs. Runs
#     still inside the retention window are kept; interrupted ones whose owner
#     is gone are not.
#   * `var/`, where the sweep removes only names matching a REGISTERED scratch
#     family. A name carrying its owner is removed when that process is
#     OBSERVED gone; a name carrying no readable owner is removed on 24h of
#     mtime silence, which is an inference the automatic callers never make and
#     `clean-apply` does. Everything else under `var/` -- the probe and cohort
#     trees kept by hand, tens of gigabytes of them -- is reported as unclaimed
#     and left alone, so this section frees far less than it lists.
#
# So: run `just clean` first and READ IT. The reap set comes from ignore rules,
# a name-based protection list, and each family's own liveness evidence, and a
# protection list is exactly the kind of thing that is wrong once and then wrong
# silently. The KEEP, BLOAT and SPARE lines are how that gets caught before a
# removal rather than after one. `--only <family>` narrows to one section
# (`worktree`, `var-scratch`, `temp`); `--verbose` un-truncates the long tails.
#
# BOTH RECIPES ALWAYS EXIT 0, including `clean-apply`. This is deliberate -- a
# maintenance report has no verdict to fail a build on -- but it means the exit
# status carries NO information about what happened. An automated caller cannot
# use `$?` to tell a clean tree from a tree it just emptied; it has to read the
# output. Do not wire either recipe into a gate, a hook, or a pre-commit step.
# Neither recipe is a dependency of any aggregate.

# READ-ONLY. Report reclaimable disk across worktree output, var/ build scratch and temp storage, plus git-directory bloat. Deletes nothing, always exits 0.
[group('maintenance')]
clean *ARGS:
    uv run --no-sync python -m dev.env.clean {{ARGS}}

# DESTRUCTIVE AND IRREVERSIBLE. Deletes what `just clean` marked REAP, including outside this worktree (OS temp, other agent sessions, test-run evidence). Run `just clean` and read it first. Always exits 0, so the exit status proves nothing.
[group('maintenance')]
clean-apply *ARGS:
    uv run --no-sync python -m dev.env.clean --apply {{ARGS}}

# ── Static checks (Verify, Read-only) ────────────────────────────────────────

# Run every deterministic code-quality primitive to completion and report one
# blocking code verdict. Repository/control-plane checks, hooks, and the
# networked vulnerability check are separate surfaces below.
[doc('Run the blocking code-quality checks as one deterministic read-only subject aggregate.')]
[group('check')]
check-code:
    @uv run --no-sync python -m dev.quality.suite

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

# Refuse tracked identity canaries while retaining the value-free advisory report.
[doc('Verify that tracked content contains no configured identity canary.')]
[group('check')]
check-identity:
    @uv run --no-sync python -m dev.identity

# Verify every locale catalogue against the live code and registry surface.
[doc('Audit locale keys, values, placeholders, and codebase enrolment.')]
[group('check')]
[no-exit-message]
check-locales:
    @uv run --no-sync python -m dev.test_runs.command --family test-runs --label check-locales --signal locales-status -- uv run --no-sync python -m dev.locales status --json --check

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

# Answer the whole-registry question once. The collector unions validity,
# generated-target currentness, authority currency, runtime loading, and
# oracle bindings; the run wrapper persists detail and prints one bounded JSON
# envelope.
[doc('Verify all registry lifecycle lanes and persist one normalized health report.')]
[group('check')]
[no-exit-message]
check-registry:
    @uv run --no-sync python -m dev.test_runs.command --family test-runs --label check-registry --signal registry-health -- uv run --no-sync python -m dev.registry.analysis.registry_status --check --json

[doc('Prove one named generated registry target is current without publishing it.')]
[group('check')]
check-registry-target-current MODELO REVISION SOURCE_REF FILING_YEAR PERIOD:
    @uv run --no-sync python -m dev.registry.pipeline target-current {{MODELO}} {{REVISION}} {{SOURCE_REF}} {{FILING_YEAR}} {{PERIOD}}

# Verify every Sphinx cross-reference in a docstring names a symbol that
# still exists; a dangling target fails the build.
[doc('Verify every docstring cross-reference resolves to a real symbol.')]
[group('check')]
check-docstring-references:
    @uv run --no-sync python -m dev.quality.docstring_reference_targets

# ── Canonical code checks ────────────────────────────────────────────────────

[doc('Verify import boundaries and import forms; read-only and blocking.')]
[group('check')]
[no-exit-message]
check-import-boundaries:
    @uv run --no-sync python -m dev.test_runs.command --family test-runs --label check-import-boundaries --signal import-boundaries -- uv run --no-sync python -m dev.quality.import_gate

[doc('Verify dependency declarations against the source tree; read-only and blocking.')]
[group('check')]
check-dependency-declarations:
    @uv run --no-sync python -m dev.quality.quiet deptry src/cadrumo src/cadrumo_harness dev/registry --known-first-party cadrumo --known-first-party cadrumo_harness --known-first-party dev --non-dev-dependency-groups registry --extend-exclude ".*test_.*[.]py" --extend-exclude ".*_test_.*[.]py" --extend-exclude ".*[\\/]tests[\\/].*"

[doc('Verify product module reachability; read-only and blocking.')]
[group('check')]
check-module-reachability:
    @uv run --no-sync python -m dev.quality.unreachable_module_coverage

[doc('Verify production symbol usage; read-only and blocking.')]
[group('check')]
check-symbol-usage:
    @uv run --no-sync python -m dev.quality.unused_symbol_coverage

[doc('Verify exported names are consumed by production code; read-only and blocking.')]
[group('check')]
check-export-consumption:
    @uv run --no-sync python -m dev.quality.unconsumed_export_coverage

[doc('Verify every secure store has a production write path; read-only and blocking.')]
[group('check')]
check-secure-store-write-paths:
    @uv run --no-sync python -m dev.quality.secure_store_write_path

[doc('Verify every readable persistence surface has a production writer; read-only and blocking.')]
[group('check')]
check-persistence-write-paths:
    @uv run --no-sync python -m dev.quality.write_path_coverage

# ── Repository/control-plane checks ─────────────────────────────────────────

[doc('Run identity, API-stub, workflow, and gate-contract checks as one read-only repository aggregate.')]
[group('check')]
check-repository:
    @uv run --no-sync python -m dev.identity
    @uv run --no-sync python -m dev.docs.apidocs scaffold --check
    @uv run --no-sync python -m dev.actionlint
    @uv run --no-sync python -m dev.ci_contract

[doc('Verify committed API-reference stubs without rewriting them.')]
[group('check')]
check-api-stubs:
    @uv run --no-sync python -m dev.docs.apidocs scaffold --check

# Verify workflow syntax and shell contracts without changing workflows. If
# actionlint is unavailable, the check reports `just setup-repository-tools`.
[doc('Verify workflow syntax and shell contracts without changing workflows.')]
[group('check')]
check-workflows:
    @uv run --no-sync python -m dev.actionlint

[doc('Verify workflow-to-recipe gate contracts without changing repository files.')]
[group('check')]
check-gate-contracts:
    @uv run --no-sync python -m dev.ci_contract

# Convenience replay for hooks. It is intentionally not in check-code or
# check-repository because it duplicates the leaf checks and owns hook behavior.
[doc('Replay all pre-commit hooks; read-only convenience check excluded from aggregates.')]
[group('check')]
check-hooks:
    @uv run --no-sync python -m dev.quality.quiet uv run --no-sync prek run --all-files

# Gate on published vulnerability advisories for every pinned dependency. The
# check is read-only but needs network access; it exits 1 for findings and 7
# when advisory data cannot be obtained, so unavailable data is never green.
[doc('Gate on published vulnerability advisories for every pinned dependency; read-only, blocking, network required.')]
[group('check')]
check-dependency-vulnerabilities:
    @uv run --no-sync python -m dev.audit.dependency_audit

# Cheap dependency-surface preflight: verify pyproject, optional-extra registry,
# and frozen core/all-extras/all-groups exports before any artifact work.
[doc('Run the packaging dependency and lockfile preflight.')]
[group('test')]
test-packaging-dependencies:
    @uv run --no-sync python -m dev.packaging.dependency_surface

# Verify the packaging preflight command contracts. The marker expression is
# stated explicitly and kept equal to the campaign driver's parallel preflight
# pass (`dev.packaging.campaign`), so this local gate and a release leg select
# the same set. `dev/packaging/tests` is mixed-marker: inheriting the default
# `-m 'unit and ...'` expression from pyproject silently deselected every
# integration contract in it -- including the modules named for the
# packaging, Scoop, Homebrew, and Docker workflows the campaign runs this
# preflight ahead of -- and still exited zero.
# The excluded `serial` tests are not dropped silently: every one of them is
# owned by `test-packaging-serial`, and the installed-oracle cohort
# additionally by the narrower `test-installed-oracles`.
# `serial` is excluded by MARKER rather than left to the scheduler: an item
# selected here would be held out of the run by the collection hook behind a
# warning, which is a green summary over a test that never executed. `perf` is
# excluded by its registered policy, which holds it out of every per-push lane.
# The source-data preflight is a first-class packaging preflight concern. It
# stays separate from dependency checks so a caller can report which input
# failed before any cohort or artifact work begins.
[doc('Run the packaging source-data preflight.')]
[group('test')]
test-packaging-source:
    @uv run --no-sync python -m dev.packaging.source_preflight

# Structural packaging tests are the portable, non-serial contract population.
# Every marker is explicit because this directory mixes unit, integration,
# serial, performance, and capability-qualified tests.
[doc('Run portable non-serial packaging contract tests with explicit marker boundaries.')]
[group('test')]
test-packaging-contracts:
    @uv run --no-sync pytest -v -n auto -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" dev/packaging/tests

[doc('Run packaging dependency, source, and contract preflight as independent verdicts.')]
[group('test')]
test-packaging-preflight: test-packaging-dependencies test-packaging-source test-packaging-contracts

# Operator-run: generate the committed AEAT manual PDF corpus-text sidecars
# after a corpus PDF changes. The sidecars are load-bearing for registry
# evidence validation, so re-run this and commit the regenerated JSON.
[doc('Generate the committed AEAT manual PDF corpus-text sidecars after a corpus PDF changes; writes committed derived state.')]
[group('generate')]
generate-corpus-text:
    @uv run --no-sync python -m dev.corpus.extract_manual_corpus_text

# Freshness gate: fail (without writing) when any committed corpus-text sidecar
# is stale or missing against its source PDF.
[doc('Freshness gate: fail when any committed corpus-text sidecar is stale or missing against its source PDF.')]
[group('check')]
check-corpus-text:
    @uv run --no-sync python -m dev.corpus.extract_manual_corpus_text --check

# Operator-run: generate committed normative HTML and record-design workbook
# sidecars after their authoritative corpus sources change.
[doc('Generate committed corpus HTML and workbook sidecars after source changes; writes committed derived state.')]
[group('generate')]
generate-corpus-sidecars:
    @uv run --no-sync python -m dev.corpus.extract_corpus_sidecars

# Freshness gate: compare every enrolled HTML/workbook sidecar with the exact
# current extractor output without writing.
[doc('Freshness gate: fail when committed corpus HTML or workbook sidecars drift from source.')]
[group('check')]
check-corpus-sidecars:
    @uv run --no-sync python -m dev.corpus.extract_corpus_sidecars --check

# Build every distribution the release publishes, then refuse any file the index
# would reject on size. Same two operations the publish workflow performs, in the
# same order, so the local run and the hosted one can disagree only about the host.

[doc('Build exactly the distributions published to users.')]
[group('build')]
build-release: build-distributions

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

[doc('Construct the temporary Python packaging cohort once for artifact qualification.')]
[group('build')]
build-packaging-cohort: test-packaging-source
    @uv run --no-sync python -m dev.packaging.python_cohort build --output var/packaging-smoke-cohort/python

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
[doc('Run the portable packaging campaign against one sealed temporary cohort.')]
[group('test')]
test-packaging-portable:
    @uv run --no-sync python -m dev.packaging.campaign --profile portable

[doc('Run the CI packaging campaign and the held-out performance contracts.')]
[group('test')]
test-packaging-ci:
    @uv run --no-sync python -m dev.packaging.campaign --profile ci
    @uv run --no-sync pytest -v -n0 -m "perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" dev/packaging/tests

[doc('Run packaging artifact qualification against one sealed temporary cohort.')]
[group('test')]
test-installed-oracles: build-packaging-cohort
    @uv run --no-sync pytest -v -n0 -m "integration and serial" dev/packaging/tests/test_installed_oracles.py

[doc('Run non-performance serial packaging contracts against the sealed cohort.')]
[group('test')]
test-packaging-serial: build-packaging-cohort
    @uv run --no-sync pytest -v -n0 -m "serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" --ignore=dev/packaging/tests/test_installed_oracles.py dev/packaging/tests

[doc('Run packaging artifact qualification: installed oracles, serial contracts, runtimes, and channels.')]
[group('test')]
test-packaging-artifacts: test-installed-oracles test-packaging-serial test-python-compatibility test-channel-artifacts

# Per-push quick probe: cohort built once plus the single installed core smoke.
# Deliberately minimal (ten-minute per-push budget); every other flavor lane is
# a release-campaign proof carried by `test-packaging-portable` / `test-packaging-ci`.
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
    @uv run --no-sync pytest -v -n0 -m unit --ignore=dev/containers/tests/test_runner_capabilities.py dev/containers/tests

# ── Self-hosted runner image ─────────────────────────────────────────────────

# Build the Linux self-hosted runner image (`runner` stage of the same
# Dockerfile). Declarative replacement for the hand-provisioned stock
# container described in dev/runners/README.md.
[doc('Build the self-hosted Linux runner image (`runner` stage of the shared Dockerfile).')]
[group('build')]
build-runner-image:
    docker build --target runner -t cadrumo-runner-linux -f Dockerfile .

[doc('Build the explicit infrastructure images: devcontainer and runner image.')]
[group('build')]
build-infrastructure: build-devcontainer build-runner-image

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
    @uv run --no-sync pytest -v -n0 -m unit --ignore=dev/containers/tests/test_devcontainer_smoke.py dev/containers/tests

# Two questions about the same artifacts. actionlint asks whether the YAML is
# well-formed and its expressions resolve; the CI contract asks whether a `run:`
# step is calling a recipe or re-implementing one. A workflow can be perfectly
# valid YAML and still install `just` with an unpinned `scoop install`, which
# is what two Windows legs here did.

# ── Code mutations (Write) ──────────────────────────────────────────────────

# Apply deterministic mechanical source repairs owned by the quality tooling.
# This changes source files only; committed documentation and other generated
# derivatives have their own explicit generation commands.
[doc('Apply deterministic mechanical source repairs; source-mutating and never a verification gate.')]
[group('fix')]
fix-code:
    @uv run --no-sync python -m dev.quality.fixes

# Auto-repair every lint violation that carries a safe source fix (ruff check --fix).
[group('fix')]
fix-style:
    @uv run --no-sync ruff check --fix .

# Auto-sort imports only (ruff I-rule safe source fixes).
[group('fix')]
fix-imports:
    @uv run --no-sync ruff check --select I --fix .

# Auto-format Python source files (ruff format).
[group('fix')]
fix-format:
    @uv run --no-sync ruff format .

# Locale operations keep blocking observation, status reporting, generation,
# and curated catalogue mutation separate. The blocking audit is `check-locales`.
[doc('Report the authored, key-echo, blank, absent, and extra state of each locale catalogue; read-only.')]
[group('locale')]
[no-exit-message]
locales-status:
    @uv run --no-sync python -m dev.test_runs.command --family test-runs --label locales-status --signal locales-status -- uv run --no-sync python -m dev.locales status --json

[doc('Generate locale catalogue leaves from the live translation-key surface; writes catalogue source state.')]
[group('locale')]
locales-scaffold:
    uv run --no-sync python -m dev.locales scaffold

[doc('Set one curated locale value through the catalogue authority; mutates the named catalogue.')]
[group('locale')]
locales-set LOCALE KEY VALUE:
    uv run --no-sync python -m dev.locales set {{LOCALE}} {{KEY}} {{quote(VALUE)}}

[doc('Apply a locale value manifest through the catalogue authority; mutates only its named catalogues.')]
[group('locale')]
locales-set-batch MANIFEST:
    uv run --no-sync python -m dev.locales set-batch {{quote(MANIFEST)}}

[doc('Move a locale key subtree through the catalogue authority; refuses conflicts by default.')]
[group('locale')]
locales-move SOURCE *DESTINATIONS:
    uv run --no-sync python -m dev.locales move {{SOURCE}} {{DESTINATIONS}}

[doc('Move Modelo revision locale keys only to registry-declared destinations; refuses conflicts by default.')]
[group('locale')]
locales-move-revision MODELO SOURCE_REVISION *DESTINATION_REVISIONS:
    uv run --no-sync python -m dev.locales move-revision {{MODELO}} {{SOURCE_REVISION}} {{DESTINATION_REVISIONS}}

[doc('Canonicalize product-identity references in locale catalogues; mutates the selected catalogue set.')]
[group('locale')]
locales-canonicalize-product-identity LOCALE="":
    uv run --no-sync python -m dev.locales canonicalize-product-identity {{ if LOCALE == "" { "" } else { "--locale " + LOCALE } }}

[doc('Remove one exact locale key through the catalogue authority; refuses an absent key.')]
[group('locale')]
locales-remove LOCALE KEY:
    uv run --no-sync python -m dev.locales remove {{LOCALE}} {{KEY}}

[doc('Remove a locale key manifest through the catalogue authority; refuses missing keys by default.')]
[group('locale')]
locales-remove-batch MANIFEST:
    uv run --no-sync python -m dev.locales remove-batch {{quote(MANIFEST)}}

# Registry lifecycle mutations keep authority publication, target publication,
# and digest-bound republication as separate operator actions.
[doc('Publish only the validated runtime registry authority artifact.')]
[group('maintenance')]
registry-publish-authority:
    @uv run --no-sync python -m dev.registry.pipeline publish-authority

[doc('Publish only one named static generated registry target tree.')]
[group('maintenance')]
registry-publish-target MODELO REVISION SOURCE_REF FILING_YEAR PERIOD:
    @uv run --no-sync python -m dev.registry.pipeline publish-target {{MODELO}} {{REVISION}} {{SOURCE_REF}} {{FILING_YEAR}} {{PERIOD}}

[doc('Republish one named target only with its expected reviewed manifest digest.')]
[group('maintenance')]
registry-republish-target MODELO REVISION SOURCE_REF FILING_YEAR PERIOD EXPECTED_MANIFEST_SHA256:
    @uv run --no-sync python -m dev.registry.pipeline republish-target {{MODELO}} {{REVISION}} {{SOURCE_REF}} {{FILING_YEAR}} {{PERIOD}} {{EXPECTED_MANIFEST_SHA256}}

[doc('Scaffold one modelo revision through the registry-owned CLI.')]
[group('maintenance')]
registry-modelo-scaffold MODELO REVISION:
    @uv run --no-sync python -m dev.registry.newmodelo scaffold {{MODELO}} {{REVISION}}
    @echo "next_currentness=check-registry-valid-and-report-registry-status next_publication=registry-publish-authority-then-registry-publish-target"

[doc('Check one modelo revision scaffold without writing any skeleton files.')]
[group('check')]
check-registry-modelo-scaffold MODELO REVISION:
    @uv run --no-sync python -m dev.registry.newmodelo scaffold {{MODELO}} {{REVISION}} --check

[doc('Render the registry modelo contributor checklist.')]
[group('maintenance')]
registry-modelo-checklist:
    @uv run --no-sync python -m dev.registry.newmodelo checklist

[doc('Write declared registry governance provenance for one named revision.')]
[group('maintenance')]
registry-governance-stamp REGISTRY_ROOT MODELO REVISION ENGINEERED_BY="" CLEAR_ENGINEERED_BY="false" REVIEW_STATUS="" REVIEWED_BY="" REVIEWED_AT="":
    @uv run --no-sync python -m dev.registry.conformance stamp {{MODELO}} {{REVISION}} --registry-root {{quote(REGISTRY_ROOT)}}{{ if ENGINEERED_BY == "" { "" } else { " --engineered-by " + quote(ENGINEERED_BY) } }}{{ if CLEAR_ENGINEERED_BY == "true" { " --clear-engineered-by" } else { "" } }}{{ if REVIEW_STATUS == "" { "" } else { " --review-status " + quote(REVIEW_STATUS) } }}{{ if REVIEWED_BY == "" { "" } else { " --reviewed-by " + quote(REVIEWED_BY) } }}{{ if REVIEWED_AT == "" { "" } else { " --reviewed-at " + quote(REVIEWED_AT) } }}
    @echo "next_currentness=check-registry-valid-and-report-registry-status next_publication=registry-publish-authority-then-registry-publish-target"

[doc('Apply one named modelo edition migration after its round-trip proof; scratch stays under WORK_DIR and evidence under .logs.')]
[group('maintenance')]
registry-edition-migrate REGISTRY_ROOT MODELO WORK_DIR DECLARE_BLOCKED_ROOTS="false":
    @uv run --no-sync python -m dev.registry.edition_delta_migration --registry-root {{quote(REGISTRY_ROOT)}} --modelo {{MODELO}} --work-dir {{quote(WORK_DIR)}} --apply {{ if DECLARE_BLOCKED_ROOTS == "true" { "--declare-blocked-roots" } else { "" } }}
    @echo "next_currentness=check-registry-valid-and-report-registry-status next_publication=registry-publish-authority-then-registry-publish-target"

[doc('Stage one modelo edition migration under WORK_DIR and persist its report under .logs; never apply it to the registry.')]
[group('report')]
report-registry-edition-migration REGISTRY_ROOT MODELO WORK_DIR DECLARE_BLOCKED_ROOTS="false":
    @uv run --no-sync python -m dev.registry.edition_delta_migration --registry-root {{quote(REGISTRY_ROOT)}} --modelo {{MODELO}} --work-dir {{quote(WORK_DIR)}} {{ if DECLARE_BLOCKED_ROOTS == "true" { "--declare-blocked-roots" } else { "" } }}

[doc('Rename registry formula and binding identifiers through the owning CLI.')]
[group('maintenance')]
registry-binding-rename:
    @uv run --no-sync python -m dev.registry.rename_formula_binding_identifiers --apply
    @echo "next_currentness=check-registry-valid-and-report-registry-status next_publication=registry-publish-authority-then-registry-publish-target"

[doc('Report registry formula and binding identifier rename measurements without applying them.')]
[group('report')]
report-registry-binding-renames:
    @uv run --no-sync python -m dev.registry.rename_formula_binding_identifiers

[doc('Generate registry result-disposition fragments through the owning CLI.')]
[group('maintenance')]
registry-result-fragments-generate:
    @uv run --no-sync python -m dev.registry.result_disposition_fragment_generator --apply
    @echo "next_currentness=check-registry-valid-and-report-registry-status next_publication=registry-publish-authority-then-registry-publish-target"

[doc('Report registry result-disposition fragments that would be generated without writing them.')]
[group('report')]
report-registry-result-fragments:
    @uv run --no-sync python -m dev.registry.result_disposition_fragment_generator

# The dev.tui command family is limited to visual-review artefacts: inventory,
# render, snapshot, rasterise, and diff. It has no service-control or test
# authority, so one subject wrapper is truthful here.
[doc('Run visual-review inventory, rendering, snapshot, rasterisation, or diff operations.')]
[group('tui')]
tui-review *ARGS:
    @uv run --no-sync python -m dev.tui {{ARGS}}

# The harness command family owns one persistent interactive session: opening,
# replaying, inspecting, and capturing its current walk. It is not a test lane
# and is never an aggregate prerequisite.
[doc('Drive the persistent interactive TUI harness session.')]
[group('tui')]
tui-harness *ARGS:
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
calculation_exclusions := "--ignore=src/cadrumo/application/calculations --ignore=src/cadrumo/domain/calculations/registry/tests"

[doc('Run the tooling-owned pytest harness verdict before product populations.')]
[group('test')]
test-pytest-harness:
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
    @uv run --no-sync pytest -v -n {{pytest_workers}} --dist=loadfile -m 'unit and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service' {{calculation_exclusions}} {{ if durations == "" { "" } else { "--durations=" + durations } }}

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
    uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests || failed=1
    uv run --no-sync pytest -v -n0 -m "(unit or integration) and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests
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
    uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    uv run --no-sync pytest -v -n0 -m "(unit or integration) and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests
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
test-integration: test-integration-parallel test-integration-serial

[doc('Run the pytest harness first, then the portable product unit and integration populations.')]
[group('test')]
test-product: test-pytest-harness test-unit test-integration-parallel test-integration-serial

[private]
_test-registry-calculations-parallel:
    @uv run --no-sync pytest -v -n {{ pytest_workers }} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests

[private]
_test-registry-calculations-serial:
    @uv run --no-sync pytest -v -n0 -m "(unit or integration) and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" src/cadrumo/application/calculations src/cadrumo/domain/calculations/registry/tests

[private]
_test-registry-conformance:
    @uv run --no-sync pytest -v -n {{ pytest_workers }} -m "(unit or integration) and not serial and not perf and not resident_service and not external_tool and not os_keychain and not windows_only and not tui_render" --timeout=300 dev/registry/tests dev/registry/conformance/tests dev/registry/aeip/tests dev/registry/newmodelo/tests dev/registry/parity/tests dev/tests/test_no_casilla_is_routed_to_a_valueless_slot.py dev/tests/test_registry_conformance_gate.py dev/tests/test_registry_identity_enrolment.py --ignore=dev/registry/tests/test_workbook_parity.py

[doc('Run calculation and registry-conformance populations as one normalized registry test signal.')]
[group('test')]
[no-exit-message]
test-registry:
    @uv run --no-sync python -m dev.test_runs.command --family test-runs --label test-registry --signal pytest-summary --expected-lane _test-registry-calculations-parallel --expected-lane _test-registry-calculations-serial --expected-lane _test-registry-conformance -- uv run --no-sync python -m dev.test_runs lanes --json-events --no-evidence _test-registry-calculations-parallel _test-registry-calculations-serial _test-registry-conformance

[doc('Run the tooling-owned test-policy, repository-contract, and CI-contract populations.')]
[group('test')]
test-tooling: test-test-policy test-repository-contracts test-ci-contracts

[doc('Run repository test-policy and lane-contract tests, including the lane transport serial population.')]
[group('test')]
test-test-policy:
    @uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" dev/tests dev/test_runs/tests --ignore=dev/tests/test_no_casilla_is_routed_to_a_valueless_slot.py --ignore=dev/tests/test_registry_conformance_gate.py --ignore=dev/tests/test_registry_identity_enrolment.py
    @uv run --no-sync pytest -v -n0 -m "integration and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" dev/tests dev/test_runs/tests --ignore=dev/tests/test_no_casilla_is_routed_to_a_valueless_slot.py --ignore=dev/tests/test_registry_conformance_gate.py --ignore=dev/tests/test_registry_identity_enrolment.py

[doc('Run repository and developer-tool contract tests outside the registry, packaging, CI, and capability populations.')]
[group('test')]
test-repository-contracts:
    @uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" dev/agent_eval/tests dev/audit/tests dev/corpus/tests dev/docs dev/env/tests dev/identity/tests dev/ingest_harness/tests dev/locales/tests dev/quality/tests dev/readme/tests dev/sanitizer/tests dev/smoke/tests dev/tui/tests dev/tui/harness/tests --ignore=dev/docs/terminology/tests/test_sweep_live_service.py

[doc('Run CI, deployment, release, and benchmark contract tests with independent scheduler verdicts.')]
[group('test')]
test-ci-contracts:
    @uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" dev/ci/tests dev/deploy/tests dev/release/tests
    @uv run --no-sync pytest -v -n0 -m "serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" dev/ci/tests dev/deploy/tests dev/release/tests
    @uv run --no-sync pytest -v -n0 -m "perf" dev/ci/tests dev/deploy/tests dev/release/tests

# Run the registry conformance suite. It sits in its own lane rather than in
# `test-registry` because of cost, not category: a sequential local run
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
    @uv run --no-sync pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial and not perf and not resident_service and not external_tool and not os_keychain and not windows_only and not tui_render" --timeout=300 dev/registry/tests dev/registry/conformance/tests dev/registry/aeip/tests dev/registry/newmodelo/tests dev/registry/parity/tests dev/tests/test_no_casilla_is_routed_to_a_valueless_slot.py dev/tests/test_registry_conformance_gate.py dev/tests/test_registry_identity_enrolment.py --ignore=dev/registry/tests/test_workbook_parity.py

[doc('Run only the parallel integration lane, holding the isolation-sensitive serial tests out.')]
[group('test')]
test-integration-parallel:
    @uv run --no-sync pytest -v -n {{pytest_workers}} {{harness_exclusions}} {{calculation_exclusions}} -m "integration and not serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service"

# Run only the serial (isolation-sensitive) integration lane, no xdist workers.
[group('test')]
test-integration-serial:
    @uv run --no-sync pytest -v {{harness_exclusions}} {{calculation_exclusions}} -m "integration and serial and not perf and not external_tool and not os_keychain and not windows_only and not tui_render and not resident_service" -n0

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
[doc('Run the Windows-only packaging capability tests.')]
[group('test')]
test-windows:
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

[doc('Reindex the running resident search service, then run its retrieval contracts.')]
[group('test')]
test-resident-service:
    uv run --no-sync vaultspec-rag index --type code --port 8766
    uv run --no-sync pytest -v -n0 -m resident_service dev/docs/preprocess/tests/test_golden_queries.py dev/docs/terminology/tests/test_sweep_live_service.py

[doc('Run the opt-in registry live-read tests serially outside portable aggregates.')]
[group('test')]
test-registry-live:
    @uv run --no-sync pytest -v -n0 -m aeat_live src/cadrumo

# Run the produce, verify, and export end-to-end smoke tests.
[group('test')]
test-smoke:
    uv run --no-sync pytest -v src/cadrumo/application/modelo/tests/test_file_flow_calculation.py src/cadrumo/application/modelo/tests/test_file_flow_verify.py src/cadrumo/application/modelo/tests/test_file_flow_filing.py src/cadrumo/application/modelo/tests/test_export.py

# Run the LibreOffice workbook parity tests. These carry `external_tool`
# alongside the mandatory `unit` execution marker, so the default
# `unit and not external_tool` selector holds them out until this capability
# lane explicitly selects them.
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

# Compose the normalized advisory code scanners. Findings are rendered as
# advisory output and do not fail this aggregate; a scanner that cannot run is
# still reported as unavailable by the owning runner.
[doc('Run normalized advisory code scanners; findings are non-blocking and full results are persisted.')]
[group('audit')]
audit-code *ARGS:
    @uv run --no-sync python -m dev.audit.advisory {{ARGS}}

# List every type diagnostic verbatim (advisory; findings do not fail the audit).
[group('audit')]
audit-types:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-types -- uv run --no-sync python -m dev.quality.types --full

# Run the advisory complexity scanner for production code. Findings are
# non-blocking; unavailable scanner data remains visible as a broken audit.
[doc('Run the advisory complexity scanner; findings are non-blocking and unavailable data is reported.')]
[group('audit')]
audit-complexity:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label audit-complexity -- uv run --no-sync python -m dev.audit.complexity

# Scan for dead code. Findings are advisory and unavailable data is reported.
# The whitelist clears individually-justified
# false positives (contract-fixed signature params); see its docstring.
# The runner (dev.audit.dead_code) owns the vulture invocation AND its
# parsing, so this recipe and the advisory code aggregate's dead-code dimension cannot drift
# apart or disagree. Pass --full for the uncapped finding list.
# Scan for copy-paste code duplication. Findings are advisory and unavailable
# data is reported. Aggregate line + capped clone list.
# The runner owns the jscpd invocation AND its parsing, so this recipe and the
# health report's duplication dimension cannot drift apart or disagree.
[doc('Scan for duplication and dead code as one advisory dead-weight signal.')]
[group('audit')]
audit-dead-weight:
    @uv run --no-sync python -m dev.test_runs.command --family test-runs --label audit-dead-weight --signal audit-dead-weight -- uv run --no-sync python -m dev.audit.dead_weight

[doc('Scan code security posture with the normalized semgrep runner; advisory and non-blocking.')]
[group('audit')]
audit-code-security:
    @uv run --no-sync python -m dev.audit.security

# ── Explicit reports ─────────────────────────────────────────────────────────

# Finding-bearing product reports retain their scanner exit contracts:
# reachability and persistence reports exit 3 on findings, 1 when analysis is
# unavailable, and 0 only after a clean scan. They are never aggregate members.
[doc('Report unreachable product modules and persist run evidence; exit 3 on findings, 1 if unavailable, 0 when clean.')]
[group('report')]
report-product-reachability *ARGS:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label report-product-reachability -- uv run --no-sync python -m dev.audit.unreachable_code {{ARGS}}

[doc('Report product persistence write paths and persist run evidence; exit 3 on findings, 1 if unavailable, 0 when clean.')]
[group('report')]
report-product-write-paths *ARGS:
    @uv run --no-sync python -m dev.test_runs.command --family audit-runs --label report-product-write-paths -- uv run --no-sync python -m dev.audit.write_path_coverage {{ARGS}}

[doc('Render and persist code-health dimensions; exit 1 on RED, 0 on AMBER or GREEN.')]
[group('report')]
report-code-health *ARGS:
    @uv run --no-sync python -m dev.audit.report {{ARGS}}

[doc('Render and persist the uncapped monthly code-health report; exit 1 on RED, 0 otherwise.')]
[group('report')]
report-code-health-monthly:
    @uv run --no-sync python -m dev.audit.report --full

# Read-only registry reports. These commands disclose their observational
# posture; none publishes, repairs, or regenerates an artifact.
[doc('Report registry conformance observations; always exits zero.')]
[group('report')]
report-registry-conformance:
    @uv run --no-sync python -m dev.registry.conformance report

[doc('Report registry closure observations; always exits zero and never requests the blocking gate.')]
[group('report')]
report-registry-closure:
    @uv run --no-sync python -m dev.registry.conformance closure

[doc('Report the AEIP registry continuity inventory; always exits zero.')]
[group('report')]
report-registry-aeip:
    @uv run --no-sync python -m dev.registry.aeip inventory

# How far each modelo has moved from full-copy editions to delta authoring, and
# what still restates the edition its own directory names. Reads the authored
# corpus rather than the compiled authority, because a restated reference and an
# inherited one materialise identically and the authority cannot see the
# difference. Sibling to `delta_minimality`, which owns the separate question of
# whether a stated row equals the row it would inherit.
[doc('Report edition delta-authoring status and remaining restatement per modelo; always exits zero.')]
[group('report')]
report-registry-edition-delta-status *ARGS:
    @uv run --no-sync python -m dev.test_runs.command --family test-runs --label report-registry-edition-delta-status -- uv run --no-sync python -m dev.registry.analysis.edition_delta_status {{ARGS}}

[doc('Report only the corpus-wide edition delta-authoring totals, without the per-modelo worklist; always exits zero.')]
[group('report')]
report-registry-edition-delta-totals:
    @uv run --no-sync python -m dev.test_runs.command --family test-runs --label report-registry-edition-delta-totals -- uv run --no-sync python -m dev.registry.analysis.edition_delta_status --totals-only

# ── Documentation ────────────────────────────────────────────────────────────

# Documentation stays under one discoverable `docs-*` namespace while each
# recipe states whether it checks, generates committed state, writes disposable
# local output, serves locally, provisions infrastructure, or publishes bytes.

# Regenerate committed API-reference stubs through their owning generator.
[doc('Generate committed API-reference stubs from the live source module tree; review the resulting diff.')]
[group('docs')]
docs-generate-api-stubs:
    uv run --no-sync python -m dev.docs.apidocs scaffold

# Regenerate committed CLI-sequence goldens through their owning runner.
[doc('Generate committed CLI-sequence goldens through the owning sequence generator; review the resulting diff.')]
[group('docs')]
docs-generate-sequences:
    uv run --no-sync python -m dev.docs.sequences refresh

# Regenerate committed documentation gettext catalogues through the i18n owner.
[doc('Generate documentation gettext catalogues through the owning i18n generator; writes committed catalogue state.')]
[group('docs')]
docs-generate-catalogs:
    uv run --no-sync python -m dev.docs.i18n

# Regenerate the committed terminology coverage report through its generator.
[doc('Generate the committed terminology coverage report through its owning generator.')]
[group('docs')]
docs-generate-terminology-coverage:
    uv run --no-sync python -m dev.docs.terminology.coverage report

# Build changed narrative and API reference documents into disposable local output.
[doc('Build the full documentation tree into disposable local output; uploads nothing.')]
[group('docs')]
docs-build:
    uv run --no-sync python -m dev.docs.build docs/conf.py

# Build a single hand-authored page into disposable local output.
[doc('Build one hand-authored documentation page into disposable local output; uploads nothing.')]
[group('docs')]
docs-page PAGE:
    uv run --no-sync python -m dev.docs.build --single-page {{quote(PAGE)}}

# Serve the default user-scope documentation with live reload on docs/ edits.
# The owning CLI's `--scope full` is required when API/docstring source watching
# is needed. Binds every interface on the docs' canonical port 8788, claimed
# strictly: attaches to a healthy running server, evicts an invalid squatter,
# and errors rather than drifting to another port. The first serve builds
# before opening the browser. Local resident process; its state and build output
# are local only and it is never an aggregate prerequisite.
[doc('Serve documentation with live reload as a local resident process; writes only disposable local state.')]
[group('docs')]
docs-serve PORT="":
    uv run --no-sync python -m dev.docs.serve {{ if PORT == "" { "" } else { "--port " + PORT } }} --open-browser

# Re-execute committed CLI sequences and report divergence without rewriting.
[doc('Run the blocking read-only documentation sequence check; never rewrite goldens.')]
[group('docs')]
docs-sequences-check *ARGS:
    uv run --no-sync python -m dev.docs.sequences check {{ARGS}}

[doc('Report the curated Terminology Handbook health; read-only and observational.')]
[group('docs')]
docs-terminology-report:
    @uv run --no-sync python -m dev.docs.terminology_handbook audit

# Handbook scaffolding is the only mutation exposed here; set, relate,
# remove-term, retire, and seed remain direct owning-CLI operations so a single
# recipe cannot mix observation with unrelated curation verbs.
[doc('Reconcile the Terminology Handbook with live enrolment sources; mutates curated source state.')]
[group('docs')]
docs-terminology-maintain:
    uv run --no-sync python -m dev.docs.terminology_handbook scaffold

[doc('Mine synonym observations into the reviewed queue; mutates the curated synonym source.')]
[group('docs')]
docs-synonyms-maintain OBSERVATIONS:
    uv run --no-sync python -m dev.docs.terminology.synonyms mine {{quote(OBSERVATIONS)}}

# Build the user-scope documentation in one language (es/en/ca/hu) into that
# language's own root. `--out-dir` is what puts a build in a per-language
# subdirectory; `--language` alone only selects the catalogue, so without it the
# localized pages render into the canonical English root itself, leaving no
# language root at all and an English root full of translated pages.
[doc('Build one localized documentation root into disposable local output; uploads nothing.')]
[group('docs')]
docs-lang LANG:
    uv run --no-sync python -m dev.docs.build --scope user --language {{LANG}} --out-dir docs/_build/html/{{LANG}}

# Build the user-scope documentation for every translation language, each into
# its own root beside the English one. These are plain local builds: for the
# deploy-faithful multi-root artefact (strict, record-injected index, per-root
# canonical URLs) use `docs-site-preview`.
[doc('Build every localized documentation root into disposable local output; uploads nothing.')]
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
[doc('Build and validate every published documentation root without uploading; dry-run only.')]
[group('docs')]
docs-site-preview:
    uv run --no-sync python -m dev.deploy.docs_static_site dry-run

# Run blocking, read-only docstring structure and Sphinx checks with live
# per-test verdicts.
# `workers` bounds the pytest-xdist lane: CI passes 8 (machine-aware sizing,
# .github/ci-control-plane.md — the 24-core box is shared with other
# repositories' runners, and 8 is a working pin, not a derivation); local
# development keeps the `auto` default per the same control plane.
[doc('Run blocking read-only documentation checks; stream failure identities as they happen.')]
[group('docs')]
docs-check workers="auto":
    @uv run --no-sync pytest -v -n {{workers}} dev/docs/tests dev/docs/apidocs/tests src/cadrumo/tests/test_docstring_core_struct_links.py -m "docs or unit or (integration and not serial)"
    @uv run --no-sync doc8 docs
    @uv run --no-sync interrogate -c pyproject.toml src/cadrumo

# ── Database migrations ──────────────────────────────────────────────────────

# Source-controlled migration creation and database upgrade are separate
# mutations. Creation changes migration source; upgrade changes only the
# database selected by the local Alembic configuration. Point that
# configuration at an isolated local database before invoking the upgrade.
[doc('Create a source-controlled Alembic migration from the current model; mutates migration source state.')]
[group('database')]
db-migration-create MESSAGE:
    uv run alembic revision --autogenerate -m {{quote(MESSAGE)}}

[doc('Upgrade the database selected by local Alembic configuration to head; mutates database state and requires an isolated local target.')]
[group('database')]
db-upgrade:
    uv run alembic upgrade head

# ── Deployment ───────────────────────────────────────────────────────────────
#
# Its own lane, deliberately. Building documentation is a local
# check-and-balance verification with no bearing on deployment; publishing
# writes bytes to a live public destination. The `docs-build` group therefore holds
# only build and check verbs, and the three recipes below are the only ones in
# this file that reach outward at all.
#
# The release group is adjacent but disjoint, and nothing here re-declares
# any of it: every release recipe is read-only (`release-preview` is a dry-run preview,
# `release-rollback-plan` prints a procedure, `release-check` audits), and
# release publication itself lives in CI behind the `pypi` environment
# (`publish.yml`). The release lane deliberately publishes nothing.
#
# These three verbs do NOT share an automation posture, and this group must
# not be read as granting one. Each states its own authority below.

[doc('Provision the private Cadrumo documentation stack; external infrastructure mutation requiring explicit confirmation.')]
[group('docs')]
docs-stack-provision:
    uv run --no-sync python -m dev.deploy.docs_static_site provision --confirm provision-cadrumo-docs

[doc('Build and upload the Cadrumo documentation site; separate explicit publication confirmation required.')]
[group('docs')]
docs-publish:
    uv run --no-sync python -m dev.deploy.docs_static_site publish --confirm publish-cadrumo-docs

# ── Release ──────────────────────────────────────────────────────────────────

# Release preparation is read-only: readiness preserves blocking versus
# advisory findings, preview publishes nothing, and rollback planning prints
# recovery instructions without executing them. Release publication remains
# outside the justfile.
[doc('Check release readiness; blocking invariants fail while external-state findings remain advisory.')]
[group('release')]
release-check *ARGS:
    @uv run --no-sync python -m dev.release.readiness {{ARGS}}

[doc('Preview the next release as a dry run; publishes nothing.')]
[group('release')]
release-preview:
    @uv run --no-sync python -m dev.release preview

[doc('Print recovery instructions for VERSION; performs no rollback or other mutation.')]
[group('release')]
release-rollback-plan VERSION:
    @uv run --no-sync python -m dev.release rollback {{VERSION}}

# ===========================================================================
#  meta
# ===========================================================================

# The composed pipeline, in the order CI runs it, so a green local run means
# what a green CI run means. The composition is the fleet's, and the two
# rulings inside it are worth stating where they are made:
#
#   `check-dependency-vulnerabilities` and NOTHING else from the audit group. Every other audit
#   dimension is advisory by construction - each finding is a lead to confirm,
#   and a pipeline that fails on a lead teaches people to stop reading it. A
#   published advisory against a pinned version is not a lead, it is a verdict.
#
#   BUILD IS PART OF IT. A break on the release path otherwise surfaces at
#   release, when the tag is already cut and the only remedies are a revert or
#   a hotfix. The gates before it prove the source is well-formed and the tests
#   pass; only this one proves the artifact a user receives can still be
#   produced from it.

# Run the portable local policy gate from subject-level public aggregates.
[group('meta')]
gate-local:
    @just check-code
    @just check-registry
    @just check-repository
    @just check-dependency-vulnerabilities
    @just docs-check
    @just test-product
    @just test-registry
    @just test-tooling
    @just build-release
