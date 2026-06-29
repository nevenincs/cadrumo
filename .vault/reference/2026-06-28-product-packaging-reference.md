---
tags:
  - '#reference'
  - '#product-packaging'
date: '2026-06-28'
modified: '2026-06-29'
related:
  - "[[2026-06-28-product-packaging-research]]"
---

# `product-packaging` reference: `Current packaging and provisioning implementation`

This reference maps the implementation surfaces that a future
`product-packaging` ADR and plan should rely on. It records current code
locations, existing tests, and official tool documentation consulted during the
research pass.

## Summary

### Packaging metadata and build backend

`pyproject.toml:2` declares distribution name `aeat`, `pyproject.toml:3`
declares version `0.1.0`, and `pyproject.toml:6` requires Python `>=3.13`.
`pyproject.toml:70` declares `PyYAML` as a core runtime dependency because
`src/aeat/core/i18n/_render.py:18` imports `yaml` during CLI startup.
`pyproject.toml:85` declares the `aeat` console script.

`pyproject.toml:93` starts optional dependencies. `pyproject.toml:109` declares
the `google` extra, `pyproject.toml:115` declares the `browser` extra with
`playwright` and `playwright-stealth`, `pyproject.toml:122` declares the
`anthropic` extra, and `pyproject.toml:126` declares aggregate `all`.

`pyproject.toml:132` selects hatchling. `pyproject.toml:136` configures the
wheel target, and `pyproject.toml:137` packages `src/aeat`. `pyproject.toml:141`
still explicitly includes the BIP-39 wordlist and `external_constants.toml`.

`pyproject.toml:168` starts the dev dependency group. `pyproject.toml:172`
documents `torch` as a dev-only vaultspec-rag dependency. `pyproject.toml:182`
documents that optional integration stacks are also installed in dev/test/CI.

External docs consulted: `https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#dependencies-optional-dependencies`,
`https://hatch.pypa.io/latest/config/build/`,
`https://docs.astral.sh/uv/guides/integration/docker/`.

### Bundled data resource boundary

`src/aeat/core/resources/_boundary.py:27` sets `_PACKAGE_DATA` through
`importlib.resources.files("aeat").joinpath("_data")`. `packaged_data` begins at
`src/aeat/core/resources/_boundary.py:32`, `bundled_path` begins at
`src/aeat/core/resources/_boundary.py:51`, and `as_path` begins at
`src/aeat/core/resources/_boundary.py:72`.

The top docstring in `src/aeat/core/resources/_boundary.py:3` is stale: it still
mentions hatchling `force-include` and top-level source trees. The accepted ADR
and current wheel guard say the actual mechanism is physical relocation under
`src/aeat/_data` plus `packages = ["src/aeat"]`.

`src/aeat/core/tests/test_resources.py:15` verifies the resource root,
`src/aeat/core/tests/test_resources.py:51` verifies representative leaves, and
`src/aeat/core/tests/test_resources.py:84` verifies `as_path`.

`src/aeat/tests/test_wheel_bundles_corpus_and_registry.py:1` describes the wheel
archive contract. `src/aeat/tests/test_wheel_bundles_corpus_and_registry.py:39`
enumerates tracked `_data` files with `git ls-files`. `src/aeat/tests/test_wheel_bundles_corpus_and_registry.py:77`
builds the wheel with `uv build --wheel`. `src/aeat/tests/test_wheel_bundles_corpus_and_registry.py:113`
asserts archive completeness.

### Optional extras and missing-dependency contract

`src/aeat/core/_optional_extras.py:1` defines the optional-extra registry and
guard. `OptionalExtra` begins at `src/aeat/core/_optional_extras.py:37`;
`install_hint` returns `pip install aeat[<extra>]` at
`src/aeat/core/_optional_extras.py:47`; the declared extras are at
`src/aeat/core/_optional_extras.py:55`; `MissingOptionalExtraError` starts at
`src/aeat/core/_optional_extras.py:62`; `optional_extra_available` starts at
`src/aeat/core/_optional_extras.py:79`; and `require_optional_extra` starts at
`src/aeat/core/_optional_extras.py:92`.

`src/aeat/tests/test_optional_extra_degradation.py:67` verifies the core CLI can
build with optional packages blocked. `src/aeat/tests/test_optional_extra_degradation.py:77`
verifies the Anthropic boundary emits the install hint. `src/aeat/tests/test_optional_extra_degradation.py:91`
verifies the browser boundary emits the install hint. `src/aeat/tests/test_optional_extra_degradation.py:103`
verifies the google extra probe observes absence.

### Product doctor and provisioning probes

`src/aeat/application/provisioning.py:40` defines `DependencyStatus`.
`probe_ollama_vision` begins at `src/aeat/application/provisioning.py:57` and
returns `ollama serve` / `ollama pull <model>` remediation. `probe_subprocess_providers`
begins at `src/aeat/application/provisioning.py:98`. `probe_playwright_browser`
begins at `src/aeat/application/provisioning.py:140` and returns
`playwright install chromium` when no Chromium build is present.
`probe_optional_extra` begins at `src/aeat/application/provisioning.py:168`, and
`probe_optional_extras` begins at `src/aeat/application/provisioning.py:191`.

`src/aeat/entrypoints/cli/_config/_check_cli.py:26` registers `aeat config check`.
`src/aeat/entrypoints/cli/_config/_check_cli.py:47` runs the probes, and
`src/aeat/entrypoints/cli/_config/_check_cli.py:55` collects opted-in capability
issues. `src/aeat/entrypoints/cli/_config/_check_cli.py:87` emits the envelope,
and `src/aeat/entrypoints/cli/_config/_check_cli.py:89` exits with code 2 when
the workstation is not ready for an opted-in capability.

`src/aeat/entrypoints/cli/_config/_check_payloads.py:1` documents the JSON
payload shape. `src/aeat/entrypoints/cli/tests/test_config_capabilities.py:67`
checks that `config check` reports capabilities and dependencies, including
`ollama-vision`, `playwright-chromium`, and `extra:*` rows.

### Justfile and CI surfaces

`justfile:10` documents the shared-worktree bootstrap constraint. `justfile:13`
runs `bootstrap`, `justfile:24` runs the product doctor, `justfile:30` runs
`provision`, `justfile:37` and `justfile:41` perform additive uv installs on
Windows and Unix, and `justfile:138` runs `playwright install chromium`.

`.github/workflows/ci.yml:60` currently runs `uv sync` rather than frozen sync
for ordinary CI bootstrap. `.github/workflows/ci.yml:100` documents and runs the
dependency audit export/pip-audit step. `.github/workflows/aeat-drift-detector.yml:56`
uses `uv sync --frozen`, and `.github/workflows/aeat-drift-detector.yml:60`
uses `uv run playwright install --with-deps chromium`.

Official uv Docker docs show the relevant release-gate pattern:
`uv sync --locked --no-install-project --no-editable` before copying the project,
then `uv sync --locked --no-editable` after copying. They also show
`UV_NO_DEV=1` for disabling dev dependencies in Docker installs.

### Playwright and browser health

`src/aeat/adapters/outbound/aeat/browser/_factory.py:284` is the Playwright
runtime chokepoint. It calls `require_optional_extra(BROWSER_EXTRA)` before
importing Playwright, so a missing Python package is reported as a typed
`BrowserError`.

`src/aeat/adapters/outbound/aeat/browser/health.py:1` defines a Playwright setup
smoke check that starts the production browser session factory, creates a
context, navigates to `https://example.com`, and closes the session. This is the
best existing no-secret browser smoke candidate for a fresh install gate, as long
as the gate owns the browser provisioning step first. The local packaging smoke
uses the same installed production browser factory and `BrowserSession.navigate`
path, but serves a local HTTP page to avoid public-network flakiness in release
artifact validation.

External docs consulted: `https://playwright.dev/python/docs/browsers`.

### LLM and evidence data boundaries

`src/aeat/application/ledger/_llm_classification.py:322` documents the preflight
around Ollama vision classification. `docs/how-to/classify-with-llm-evidence.md:13`
documents the safety conditions around cloud evidence classification.
`2026-06-13-llm-evidence-classification-adr` is the governing decision for LLM
evidence use.

`src/aeat/domain/attachments/_models.py:87` defines the attachment manifest
model. `src/aeat/domain/attachments/_service.py:59` stores attachment bytes from
disk and persists a manifest. `src/aeat/adapters/persistence/storage/attachment.py:1`
owns the attachment storage implementation. These surfaces are runtime state,
not distribution package data.

### Local installed-wheel smoke evidence

`dev/packaging/dependency_surface.py:1` owns the cheap dependency-surface
preflight, and `justfile:178` exposes it as `just packaging-smoke-dependencies`.
It runs `uv lock --check`, validates frozen core/all-extras/all-groups exports,
and checks optional-extra registry parity before any artifact work. It is
designed to remain runnable even when the source-data preflight is blocked by
concurrent `_data` WIP.
`dev/packaging/tests/test_dependency_surface.py:1` covers the dependency-surface
summary and JSON CLI contract, and `justfile:182` exposes it as
`just packaging-smoke-preflight-tests`.

`dev/packaging/source_preflight.py:1` owns the cheap shipped-data source
preflight, and `justfile:187` exposes it as `just packaging-smoke-source`. It
reuses the artifact lane's git-tracked `_data` completeness check and prints a
per-root count when every tracked shipped-data file exists on disk. Every wheel,
sdist, extras, browser, Docker, and fresh dev-environment packaging smoke lane
depends on this preflight so a deleted tracked data file fails before wheel,
virtualenv, or container work starts.

`dev/packaging/smoke_core.py:1` owns the repeatable core packaging smoke
runner, and `justfile:192` exposes it as `just packaging-smoke-core`. The runner
validates `uv lock --check`, frozen core export, frozen all-extras export, and
frozen all-groups export before building the wheel. Those export checks now
derive the expected production, optional, and dev package names from
`pyproject.toml`; current-platform markers are respected for export presence
checks, while wheel metadata still proves the declared marker rows exist. It
preflights every git-tracked shipped-data file under `src/aeat/_data/corpus`,
`src/aeat/_data/registry`, and `src/aeat/_data/terminology`, verifies those
files appear in the wheel archive, checks wheel metadata against
`pyproject.toml`, installs the wheel into a fresh virtualenv, runs
`uv pip check`, runs the installed CLI, verifies representative `_data` leaves
through `importlib.resources`, runs an installed encrypted `AttachmentStore`
round trip for evidence bytes/manifests, verifies the Anthropic LLM adapter
refuses from a bare core install with `pip install aeat[anthropic]`, and creates
an isolated profile with `--no-llm-vision --no-google-export` so installed
`config check` has an exit-0 core proof. It also parses
`src/aeat/core/_optional_extras.py` with `ast` and verifies the capability-gated
optional-extra registry names existing `pyproject.toml` extras and that the
`all` aggregate includes each registry extra.

`dev/packaging/smoke_pip_core.py:1` owns the plain-pip core packaging smoke
runner, and `justfile:197` exposes it as `just packaging-smoke-pip-core`. It
builds the same wheel, creates a stdlib virtualenv with `venv.EnvBuilder`,
installs the wheel with `python -m pip install`, runs `python -m pip check`, and
then reuses the installed `_data`, attachment, LLM optional-boundary, and CLI
probes from the core runner. This proves the artifact works in a vanilla Python
environment without relying on `uv pip` inside the target environment.

`dev/packaging/smoke_sdist_core.py:1` owns the source-distribution core
packaging smoke runner, and `justfile:202` exposes it as
`just packaging-smoke-sdist-core`. It preflights the same git-tracked
shipped-data source set, builds `aeat-*.tar.gz`, verifies every expected
shipped-data file is present inside the archive, creates a stdlib virtualenv,
installs the sdist with plain `python -m pip install`, runs `python -m
pip check`, and then reuses the installed `_data`, attachment, LLM
optional-boundary, and CLI probes.

`dev/packaging/smoke_extras.py:1` owns the aggregate optional-extra smoke
runner, and `justfile:207` exposes it as `just packaging-smoke-extras`. It
builds the wheel, creates a stdlib virtualenv, installs the wheel as
`aeat[all]` with plain `python -m pip install`, runs `python -m pip check`, and
verifies the Google, browser, and Anthropic Python packages import through the
installed optional-extra registry. This proves the convenience `all` extra
resolves as a real product install without relying on the dev dependency group.

`dev/packaging/smoke_dev.py:1` owns the fresh development-environment smoke
runner, and `justfile:212` exposes it as `just packaging-smoke-dev`. It sets
`UV_PROJECT_ENVIRONMENT` to an isolated path under `var/packaging-smoke`, runs
`uv sync --frozen --all-extras --all-groups --no-editable`, verifies
`uv sync --check`, runs `uv pip check`, starts the declared developer command
surface, imports the heavy optional/dev packages together, verifies `aeat
--version`, and checks representative bundled `_data` leaves. The packaging
workflow runs this before the product artifact lanes at
`.github/workflows/packaging-smoke.yml:44`.

`dev/packaging/smoke_browser.py:1` owns the repeatable browser-extra smoke
runner, and `justfile:217` exposes it as `just packaging-smoke-browser`. The
runner builds the wheel, verifies the wheel advertises the `browser` extra and
its `playwright` / `playwright-stealth` dependencies, installs the wheel as
`aeat[browser]` into a fresh virtualenv, imports both optional packages, sets an
isolated `PLAYWRIGHT_BROWSERS_PATH`, provisions Chromium with `python -m
playwright install chromium`, and drives the installed browser factory against a
local HTTP page. `justfile:221` exposes `just packaging-smoke-browser-linux`,
which passes Playwright's `--with-deps` flag for Linux/container lanes.
`justfile:225` exposes `just packaging-smoke-linux`, the CI-facing host Linux
aggregate of uv core, pip core, sdist core, all extras, and
browser-with-system-deps.

`dev/packaging/smoke_docker.py:1` owns the fresh Linux image harness. It
preflights Docker daemon responsiveness, prefers the native WSL `Ubuntu` Docker
daemon on Windows when it answers, translates Windows bind mounts through
`wslpath`, builds the wheel on the host, writes a small probe script into the
smoke work directory, mounts only the wheel directory and probe directory into
`python:3.13-slim`, installs the wheel with pip inside the container, and runs
the same installed CLI/resource, attachment, and LLM optional-boundary checks
without checkout imports.
`justfile:229` exposes `just packaging-smoke-docker-core`, `justfile:234`
exposes `just packaging-smoke-docker-browser`, and `justfile:238` exposes the
aggregate `just packaging-smoke-docker`.

`.github/workflows/packaging-smoke.yml:1` owns the CI release-artifact smoke
surface. It runs on Ubuntu with Python 3.13, runs the dependency-surface
preflight, runs the shipped-data source preflight before dependency sync, syncs
the development environment from the frozen lock, runs
`just packaging-smoke-preflight-tests`, runs `just packaging-smoke-dev`, runs
`just packaging-smoke-linux`, then runs `just packaging-smoke-docker`.

The earlier local 2026-06-28 packaging smoke built
`var/packaging-smoke/pyyaml-proof-wheel/aeat-0.1.0-py3-none-any.whl` with
`uv build --wheel`, inspected the wheel metadata, and confirmed
`Requires-Dist: pyyaml<7,>=6.0.3`.

Installing that wheel into
`var/packaging-smoke/wheel-venv-pyyaml-proof-20260628` with `uv pip install`
installed 66 packages. `uv pip check --python
var/packaging-smoke/wheel-venv-pyyaml-proof-20260628/Scripts/python.exe` passed.
The installed `aeat.exe --version` returned `aeat 0.1.0`.

The same installed wheel resolved bundled data through `importlib.resources` at
`Lib/site-packages/aeat/_data`; representative leaves
`registry/aeat/modelos/036/manifest.toml`,
`registry/aeat/user_profile/schema.toml`, and
`corpus/aeat_official/disenos_registro/modelo_100/manifest.json` existed.

`aeat --format json config check` in a bare no-profile install ran and emitted a
typed JSON report, exiting nonzero because default-on optional capabilities were
missing Ollama and the `google` extra. Creating an isolated throwaway profile
under `var/packaging-smoke/profile-smoke-root-20260628c` with
`--no-llm-vision --no-google-export` made the same installed `config check` exit
0 with `ok: true` and no issues.

The tracked command `just packaging-smoke-core` passed on 2026-06-28, producing
`var/packaging-smoke/core-20260628T173631Z/wheel/aeat-0.1.0-py3-none-any.whl`
as the proof wheel.

The tracked command `just packaging-smoke-browser` passed on 2026-06-28,
producing
`var/packaging-smoke/core-20260628T174613Z/wheel/aeat-0.1.0-py3-none-any.whl`
as the browser-extra proof wheel. The aggregate `just packaging-smoke` also
passed on 2026-06-28, running both the core and browser local lanes.
After the smoke runners were tightened to execute installed-package probes from
their isolated work directories rather than the checkout, `just packaging-smoke`
passed again on 2026-06-28. The current proof wheels were
`var/packaging-smoke/core-20260628T180451Z/wheel/aeat-0.1.0-py3-none-any.whl`
for the core lane and
`var/packaging-smoke/core-20260628T180626Z/wheel/aeat-0.1.0-py3-none-any.whl`
for the browser-extra lane.
After adding the installed evidence attachment and LLM optional-boundary probes,
`just packaging-smoke-core` passed again on 2026-06-28, producing
`var/packaging-smoke/core-20260628T181516Z/wheel/aeat-0.1.0-py3-none-any.whl`.
The aggregate `just packaging-smoke` then passed again on 2026-06-28 with the
enhanced core probe and browser lane, producing
`var/packaging-smoke/core-20260628T181837Z/wheel/aeat-0.1.0-py3-none-any.whl`
for core and
`var/packaging-smoke/core-20260628T181954Z/wheel/aeat-0.1.0-py3-none-any.whl`
for browser.
The first tracked plain-pip lane, `just packaging-smoke-pip-core`, passed on
2026-06-28, producing
`var/packaging-smoke/core-20260628T190756Z/wheel/aeat-0.1.0-py3-none-any.whl`.
After adding that lane to `just packaging-smoke`, the aggregate passed again on
2026-06-28, producing
`var/packaging-smoke/core-20260628T190946Z/wheel/aeat-0.1.0-py3-none-any.whl`
for uv core,
`var/packaging-smoke/core-20260628T191110Z/wheel/aeat-0.1.0-py3-none-any.whl`
for pip core, and
`var/packaging-smoke/core-20260628T191316Z/wheel/aeat-0.1.0-py3-none-any.whl`
for browser.
The first tracked sdist lane, `just packaging-smoke-sdist-core`, passed on
2026-06-28, producing
`var/packaging-smoke/core-20260628T191933Z/sdist/aeat-0.1.0.tar.gz`.
After adding that lane to `just packaging-smoke`, the aggregate passed again on
2026-06-28, producing
`var/packaging-smoke/core-20260628T192500Z/wheel/aeat-0.1.0-py3-none-any.whl`
for uv core,
`var/packaging-smoke/core-20260628T192630Z/wheel/aeat-0.1.0-py3-none-any.whl`
for pip core,
`var/packaging-smoke/core-20260628T192815Z/sdist/aeat-0.1.0.tar.gz`
for sdist core, and
`var/packaging-smoke/core-20260628T193351Z/wheel/aeat-0.1.0-py3-none-any.whl`
for browser.
After adding lane-specific work directory prefixes and the aggregate
optional-extra smoke, `just packaging-smoke-extras` passed on 2026-06-28,
producing
`var/packaging-smoke/extras-20260628T202938Z/wheel/aeat-0.1.0-py3-none-any.whl`.
The aggregate `just packaging-smoke` then passed again on 2026-06-28, producing
`var/packaging-smoke/core-20260628T203145Z/wheel/aeat-0.1.0-py3-none-any.whl`
for uv core,
`var/packaging-smoke/pip-core-20260628T203326Z/wheel/aeat-0.1.0-py3-none-any.whl`
for pip core,
`var/packaging-smoke/sdist-core-20260628T203547Z/sdist/aeat-0.1.0.tar.gz`
for sdist core,
`var/packaging-smoke/extras-20260628T204150Z/wheel/aeat-0.1.0-py3-none-any.whl`
for all extras, and
`var/packaging-smoke/browser-20260628T204329Z/wheel/aeat-0.1.0-py3-none-any.whl`
for browser.
After replacing sentinel-only export assertions with pyproject-derived
dependency-surface assertions, `just packaging-smoke-core` passed on 2026-06-28,
producing
`var/packaging-smoke/core-20260628T205447Z/wheel/aeat-0.1.0-py3-none-any.whl`.
`just packaging-smoke-extras` also passed with the stricter verifier, producing
`var/packaging-smoke/extras-20260628T205617Z/wheel/aeat-0.1.0-py3-none-any.whl`.
The first `just packaging-smoke-dev` run created
`var/packaging-smoke/dev-20260628T210222Z/dev-venv`, then failed on the Semgrep
console command: the persistent Windows package installed a broken script
(`resource` unavailable / native core path missing). After removing `semgrep`
from `[dependency-groups].dev` and using a pinned `uvx --from semgrep==1.168.0
semgrep` policy in CI and `just`, `just packaging-smoke-dev` passed on
2026-06-28 with `var/packaging-smoke/dev-20260628T210609Z/dev-venv`. The
latest isolated dev-environment smoke passed again on 2026-06-29 with
`var/packaging-smoke/dev-20260629T030848Z/dev-venv`. The
on-demand scanner path was verified separately with `uvx --from
semgrep==1.168.0 semgrep --version`, returning `1.168.0`.
`just packaging-smoke-core` then passed again against the updated lock, producing
`var/packaging-smoke/core-20260628T210954Z/wheel/aeat-0.1.0-py3-none-any.whl`.
After adding the full tracked shipped-data archive preflight, package artifact
smoke lanes fail early in the current dirty worktree because eight git-tracked
normative JSON files are absent on disk:
`ley-19-1994.json`, `ley-35-2006.json`, `ley-37-1992.json`,
`ley-58-2003.json`, `orden-hac-242-2025.json`, `rd-1065-2007.json`,
`rd-1624-1992.json`, and `rd-439-2007.json` under
`src/aeat/_data/corpus/normatives/`. The latest failed core/sdist proof
directories are `var/packaging-smoke/core-20260629T072556Z` and
`var/packaging-smoke/sdist-core-20260629T072556Z`; both stopped before artifact
install with the source-data preflight message.

The tracked command shape for `just packaging-smoke-docker` dry-runs to
`uv run --no-sync python -m dev.packaging.smoke_docker` and
`uv run --no-sync python -m dev.packaging.smoke_docker --browser`. A core Docker
execution on 2026-06-28 built
`var/packaging-smoke/docker-core-20260628T175811Z/wheel/aeat-0.1.0-py3-none-any.whl`,
then stopped at the runner's preflight with `docker daemon did not answer within
15 seconds`. Treat the Linux container lane as implemented but not execution
proven until Docker responds and the core/browser container probes pass.
A later core Docker invocation after the attachment/LLM probe was added built
`var/packaging-smoke/docker-core-20260628T182129Z/wheel/aeat-0.1.0-py3-none-any.whl`
and hit the same preflight failure before container execution.
The local Docker daemon blocker was removed on 2026-06-29 by replacing the
Docker Desktop dependency with a fresh WSL2 `Ubuntu` environment running native
Docker Engine. The verified WSL stack is Ubuntu 24.04 LTS with systemd, Docker
Client/Server `29.6.1`, Docker Compose `v5.2.0`, and Buildx `v0.35.0`; a repo
bind mount into `alpine:3.20` returned `bind-mount-ok`, and `docker run --rm
alpine:3.20 echo native-wsl-docker-ok` passed. The latest Windows-side core
Docker smoke selected `preflighting Docker daemon (wsl:Ubuntu)` and stopped at
the same shipped-data preflight in
`var/packaging-smoke/docker-core-20260629T072443Z`, before the container install
probe could run. That preflight now reports the complete eight-file absent set
and the required reconciliation: restore the tracked files, or remove them from
git tracking if they were intentionally retired.

The standalone dependency-surface preflight remains runnable in the same dirty
worktree because it does not build artifacts or read package data. On
2026-06-29, `uv run --no-sync python -m dev.packaging.dependency_surface --json`
passed with 24 project dependencies, 7 optional dependency packages, 53 dev
dependencies, 47 dev-only dependencies, and registry extras `anthropic`,
`browser`, and `google`.

To separate the packaging/WSL proof from the unrelated deleted data files in the
shared dirty worktree, a detached clean checkout at
`C:\Users\hello\aeat-packaging-clean-20260629T092758Z` was overlaid with the
packaging implementation and the Linux prompter import fix. In that clean
checkout, `python -m dev.packaging.source_preflight --json` passed and reported
17,174 tracked shipped-data files: 1,456 under `src/aeat/_data/corpus`, 15,599
under `src/aeat/_data/registry`, and 119 under `src/aeat/_data/terminology`.
Then `python -m dev.packaging.smoke_docker --timeout 900` passed through the
WSL-native Docker daemon at
`var/packaging-smoke/docker-core-20260629T073827Z`, and
`python -m dev.packaging.smoke_docker --browser --timeout 1800` passed at
`var/packaging-smoke/docker-browser-20260629T074305Z` after provisioning
Chromium with `playwright install --with-deps chromium`.

### Fresh-install gap to close

The existing tests prove source-tree resource lookup and wheel archive
completeness, and `just packaging-smoke` has previously proven the core wheel,
plain-pip wheel, plain-pip sdist, aggregate `aeat[all]`, and `aeat[browser]` in
fresh local virtualenvs after the PyYAML fix. The detached clean checkout now
also proves the fresh Linux Docker core and browser lanes through WSL-native
Docker. What remains missing in the current dirty worktree is successful
execution of the tracked artifact lanes after the deleted tracked normative JSON
files are reconciled.
