---
tags:
  - '#research'
  - '#product-packaging'
date: '2026-06-28'
modified: '2026-06-29'
related:
  - "[[2026-06-28-product-packaging-reference]]"
---

# `product-packaging` research: `Fresh install and self-managed provisioning`

This research evaluates how the product should package itself for a clean
environment while respecting already accepted decisions on bundled legal data,
capability-gated optional services, sensitive evidence handling, LLM calls, and
Playwright provisioning. The goal is not to reopen those decisions; it is to
define the missing release/install proof around them.

## Findings

### F1 - Existing decisions already constrain the packaging shape

The accepted `2026-05-15-corpus-registry-packaging-adr` makes the reviewed
corpus, registry, and terminology trees part of the wheel under `src/aeat/_data`.
The product package therefore must be self-contained for code plus reviewed
data, and must not post-install download or regenerate legal grounding.

The accepted `2026-06-15-dependency-provisioning-adr` makes external runtime
services a separate provisioning surface: missing dependencies are probed,
reported as typed dependency statuses, and paired with exact remediation
commands. The current `service-capabilities` line also makes service use depend
on profile capability opt-in plus dependency availability plus safety posture.

The accepted `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr` and
the `ledger-evidence-bytes-not-links` rule keep user evidence out of the product
distribution. Attachments and evidence bundles are runtime/user-state data
owned by secure storage and audit/export services, not files to ship in the
Python package.

Source locators: `2026-05-15-corpus-registry-packaging-adr`,
`2026-06-15-dependency-provisioning-adr`,
`2026-06-15-service-capabilities-research`,
`2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr`,
`ledger-evidence-bytes-not-links.md`.

### F2 - Current `pyproject.toml` mostly matches the desired product surface

The package declares Python `>=3.13`, a console script named `aeat`, a hatchling
wheel target with `packages = ["src/aeat"]`, and optional integration extras
for `google`, `browser`, `anthropic`, plus aggregate `all`. `PyYAML` is a
product dependency, not a tolerated transitive dependency, because the CLI
localization renderer imports `yaml` at startup. Runtime dependencies are capped
below their next major, and `torch` is in the dev group as a vaultspec-rag
dependency rather than the product core. The dev group intentionally pulls
optional stacks into contributor/CI installs so the broad test suite can exercise
every adapter without making a bare `pip install aeat` heavy.

The external docs grounding fits this structure: Python package metadata treats
optional dependencies as named extras, hatchling can include package files under
selected packages, and uv's Docker guidance supports locked/non-editable
project installs for container validation.

Source locators: `pyproject.toml:20`, `pyproject.toml:70`,
`pyproject.toml:85`, `pyproject.toml:93`, `pyproject.toml:132`,
`pyproject.toml:136`, `pyproject.toml:168`,
`src/aeat/core/i18n/_render.py:18`,
`https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#dependencies-optional-dependencies`,
`https://hatch.pypa.io/latest/config/build/`,
`https://docs.astral.sh/uv/guides/integration/docker/`.

### F3 - Bundled data has a real wheel guard, but installed-wheel execution is not yet proven

The current resource boundary reads from `importlib.resources.files("aeat")`
under `_data`, and `src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`
builds the wheel with `uv build --wheel`, opens the zip, and asserts every
tracked file under `src/aeat/_data/corpus`, `src/aeat/_data/registry`, and
`src/aeat/_data/terminology` appears in the archive.

That proves archive completeness, not clean-environment execution. A fresh
install can still fail if the wheel metadata is wrong, an import path relies on
checkout-only files, entry points are missing, or `aeat config check` reaches an
unguarded optional import. The missing proof is a clean Linux install of the
built wheel followed by no-secret product commands.

The local 2026-06-28 clean-venv proof confirmed why the installed-wheel lane is
needed. The first built wheel installed, but `aeat --version` and
`aeat --format json config check` failed with `ModuleNotFoundError: No module
named 'yaml'`. After declaring `PyYAML>=6.0.3,<7` as a direct runtime dependency
and removing `yaml` from the transitive-dependency suppression, the rebuilt wheel
metadata emitted `Requires-Dist: pyyaml<7,>=6.0.3`; a fresh venv installed the
wheel, `uv pip check` passed, `aeat --version` returned `aeat 0.1.0`, and an
installed-package `_data` probe found representative registry and corpus leaves.
The same core smoke now also runs an installed-package runtime-surface probe: it
opens a real encrypted `AttachmentStore` session using package modules only,
round-trips evidence bytes and a manifest, and verifies the Anthropic LLM
adapter refuses from a bare core install with the `pip install aeat[anthropic]`
hint rather than a raw `ModuleNotFoundError`.
An isolated profile with `llm_vision` and `google_export` disabled then made
`aeat --format json config check` exit 0 with `ok: true`. That proof has now
been codified as `dev.packaging.smoke_core` and exposed through
`just packaging-smoke-core`, which also validates frozen core, all-extras, and
all-groups dependency exports against the direct dependency sets derived from
`pyproject.toml`, with current-platform marker handling for Windows-bound rows.
The wheel build helper now preflights every git-tracked shipped-data file under
`src/aeat/_data/corpus`, `src/aeat/_data/registry`, and
`src/aeat/_data/terminology`, then verifies those files appear in the built
wheel archive. This exposed a real current worktree blocker: eight tracked
normative JSON files under `src/aeat/_data/corpus/normatives/` are deleted from
the working tree, so wheel and sdist smoke lanes now fail before artifact
execution.
A separate plain-pip lane,
`dev.packaging.smoke_pip_core`, now creates a stdlib virtualenv and installs the
same built wheel with `python -m pip` before running the same installed core
probes. The source-distribution lane, `dev.packaging.smoke_sdist_core`, builds
the `.tar.gz`, verifies the same tracked shipped-data source set is present in
the archive, installs that sdist with plain pip, and runs the same installed
core probes. The aggregate optional-extra lane, `dev.packaging.smoke_extras`,
builds the wheel, installs `aeat[all]` through plain pip in a stdlib virtualenv,
and verifies the Google, browser, and Anthropic Python packages import through
the installed optional-extra registry. The development-environment lane,
`dev.packaging.smoke_dev`, creates an isolated uv project environment from the
frozen lock with all extras and all dependency groups, installs the project
non-editably, runs `uv pip check`, and verifies declared developer tools and
heavy optional/dev imports start. The Docker harness is now codified as
`dev.packaging.smoke_docker` and exposed through
`just packaging-smoke-docker-core` and `just packaging-smoke-docker-browser`.
That dev lane exposed `semgrep` as an invalid persistent Windows dev dependency:
the synced package installed a non-working console script, while the repository's
existing pinned `uvx --from semgrep==1.168.0 semgrep` path resolves the
supported scanner. The dev group therefore no longer carries `semgrep`; CI and
`just` invoke it through pinned `uvx`.
The Docker runner now checks daemon availability before creating a smoke work
directory or building an artifact. The 2026-06-29 WSL rebuild replaced Docker
Desktop with a fresh Ubuntu 24.04 WSL2 distro running native Docker Engine;
Docker Client/Server `29.6.1`, Compose `v5.2.0`, Buildx `v0.35.0`, and repo bind
mounts were verified. The Windows-side Docker smoke now selects `wsl:Ubuntu` and
gets past daemon preflight. The shared dirty worktree still stops at the tracked
shipped-data preflight until the deleted normative JSON files are reconciled.
To isolate the infrastructure and packaging changes from that unrelated data
WIP, a detached clean checkout at
`C:\Users\hello\aeat-packaging-clean-20260629T092758Z` was overlaid with the
packaging implementation and the Linux import fix. In that clean checkout,
`python -m dev.packaging.smoke_docker --timeout 900` passed at
`var/packaging-smoke/docker-core-20260629T073827Z`, and
`python -m dev.packaging.smoke_docker --browser --timeout 1800` passed at
`var/packaging-smoke/docker-browser-20260629T074305Z`.

There is also local documentation drift: `src/aeat/core/resources/_boundary.py`
still describes hatchling `force-include`, while the accepted correction and the
current wheel guard use physical relocation under `src/aeat/_data` with
`packages = ["src/aeat"]`.

Source locators: `src/aeat/core/resources/_boundary.py:27`,
`src/aeat/tests/test_wheel_bundles_corpus_and_registry.py:1`,
`src/aeat/tests/test_wheel_bundles_corpus_and_registry.py:76`,
`src/aeat/tests/test_wheel_bundles_corpus_and_registry.py:113`,
`src/aeat/core/i18n/_render.py:18`, `pyproject.toml:70`,
`dev/packaging/smoke_core.py:237`, `dev/packaging/smoke_core.py:263`,
`dev/packaging/source_preflight.py:1`, `dev/packaging/smoke_core.py:378`,
`dev/packaging/smoke_pip_core.py:1`, `dev/packaging/smoke_sdist_core.py:40`,
`dev/packaging/smoke_extras.py:1`, `dev/packaging/smoke_dev.py:1`,
`justfile:178`, `justfile:183`,
`justfile:188`, `justfile:193`, `justfile:198`.

### F4 - Product self-management exists as doctor/provisioning, not exact sync

For local shared worktrees, `just bootstrap` intentionally uses additive
`uv pip install` through `just install`, then `vaultspec-core install`, then
`env/.env` provisioning, then `just doctor`. This avoids executable lock churn
in the highly parallel Windows worktree. That is the right developer bootstrap,
but it is not the right release proof for a fresh environment.

The product-side readiness check is `aeat config check`, exposed through
`just doctor`. It reports the active profile's capability posture and dependency
status rows for Ollama vision, subprocess provider CLIs, Playwright Chromium, and
all optional extras. It exits non-zero when an opted-in capability has a missing
dependency. This is the correct operator-facing self-management surface to run
inside a fresh-install smoke gate.

Source locators: `justfile:10`, `justfile:13`, `justfile:24`,
`justfile:30`, `justfile:37`, `src/aeat/entrypoints/cli/_config/_check_cli.py:47`,
`src/aeat/entrypoints/cli/_config/_check_cli.py:55`,
`src/aeat/entrypoints/cli/_config/_check_payloads.py:1`.

### F5 - Playwright browser binaries should be provisioned, not bundled

The current split is sound: `aeat[browser]` installs the Python packages
`playwright` and `playwright-stealth`; `playwright install chromium` installs the
browser binary into the Playwright cache. The application probe checks for a
Chromium build and reports `playwright install chromium` when it is missing.

For a Linux Docker/fresh-image gate, the browser lane should use
`playwright install --with-deps chromium` because the official Playwright Python
docs and the existing drift workflow use that shape to install browser system
dependencies as well as the Chromium browser. The product wheel should not bundle
Chromium; browser binaries are platform-specific external runtime assets.

Source locators: `pyproject.toml:114`, `justfile:137`,
`src/aeat/application/provisioning.py:140`,
`.github/workflows/aeat-drift-detector.yml:60`,
`https://playwright.dev/python/docs/browsers`.

### F6 - Optional LLM calls remain external and capability-gated

The product package should not ship Ollama models, cloud provider CLIs,
provider credentials, API keys, or LLM cache data. On-host vision depends on an
Ollama server and the configured model being present; cloud classification
depends on provider availability and explicit safety gates. `probe_ollama_vision`
uses a bounded reachability/model-presence probe and returns remediation
commands such as `ollama serve` or `ollama pull <model>`.

The clean install proof should verify the no-secret behavior: the core CLI starts,
`config check` reports missing optional LLM dependencies instructively, and no
raw provider import or network traceback escapes. Live LLM calls belong to
separate opt-in tests with credentials and usage controls.

Source locators: `src/aeat/application/provisioning.py:57`,
`src/aeat/application/provisioning.py:98`,
`src/aeat/application/ledger/_llm_classification.py:322`,
`docs/how-to/classify-with-llm-evidence.md:13`,
`2026-06-13-llm-evidence-classification-adr`.

### F7 - Evidence attachments are runtime state and need install-safe storage checks

Attachment manifests are content-addressed: `attachment_id` equals the SHA-256 of
stored bytes, and manifests record kind, source, linked transactions/invoices,
bucket id, capture actor, and metadata. The storage adapter owns blob persistence.
This supports audit handoff and replay without making attachments product
package data.

The product packaging gate should not seed real taxpayer evidence. It can still
include a no-secret smoke that creates a temporary storage root and exercises the
attachment storage boundary with synthetic bytes, proving the installed wheel can
write/read runtime evidence state without relying on checkout paths.

Source locators: `src/aeat/domain/attachments/_models.py:87`,
`src/aeat/domain/attachments/_service.py:59`,
`src/aeat/adapters/persistence/storage/attachment.py:1`.

### F8 - The missing proof is release-gate execution, not a new install philosophy

The worktree now has tracked local installed-wheel smoke runners for core and
browser-extra environments, plus a tracked Docker harness for fresh Linux
execution. `just packaging-smoke-dependencies` now exposes the dependency
surface preflight as a cheap standalone check for `pyproject.toml`, frozen
core/all-extras/all-groups exports, and optional-extra registry parity.
`just packaging-smoke-preflight-tests` verifies that preflight's summary and
JSON command contract.
`just packaging-smoke-source` exposes the tracked shipped-data source preflight
as a cheap standalone check before wheel, virtualenv, or Docker work starts, and
the artifact lanes depend on it. The Docker runner preflights daemon
responsiveness, prefers native
WSL Docker on Windows when `wsl:Ubuntu` answers, builds the wheel on the host,
mounts only the wheel and a generated probe into `python:3.13-slim`, installs
with pip inside the container, and avoids checkout imports. Docker is now
responsive locally through the fresh WSL2 Ubuntu environment, and a detached
clean checkout has passed both the core and browser container probes. The
remaining local blocker in the shared dirty worktree is source-data
reconciliation before the tracked lanes can pass there.
uv documentation still supports a locked/non-editable Docker install pattern for
CI images. The repository now has a dedicated
`.github/workflows/packaging-smoke.yml` workflow that runs the host-Linux lane
and then the clean Docker image lane on Ubuntu. The packaging ADR should
therefore decide a release/CI gate with two lanes:

- Core lane: build wheel, install the wheel into a clean Linux image or isolated
  virtualenv without dev dependencies, run `aeat --version`, run `aeat config
  check` once to assert typed dependency diagnostics, create a throwaway profile
  with optional capabilities off, rerun `aeat config check` for the exit-0 core
  proof, verify representative bundled data leaves through the installed
  package, and validate frozen core/all-extras/all-groups dependency exports.
  `just packaging-smoke-dependencies` is the standalone dependency-surface
  preflight; `just packaging-smoke-preflight-tests` covers that command's JSON
  contract; `just packaging-smoke-source` is the cheap source-state preflight
  shared by the artifact lanes.
  The local isolated-virtualenv form is implemented by `just packaging-smoke-core`;
  the plain-pip form is implemented by `just packaging-smoke-pip-core`;
  the source-distribution form is implemented by `just packaging-smoke-sdist-core`;
  the aggregate optional-extra form is implemented by `just packaging-smoke-extras`;
  the Linux container form is implemented by `just packaging-smoke-docker-core`
  and the CI-facing host lane is `just packaging-smoke-linux`. The detached
  clean-checkout WSL proof passed this lane at
  `var/packaging-smoke/docker-core-20260629T073827Z`.
- Browser lane: install the same wheel with `browser` extra in a Linux image,
  run `playwright install --with-deps chromium`, then run the existing browser
  health smoke against non-AEAT public test navigation or a no-secret local
  check. The local isolated-virtualenv form is implemented by
  `just packaging-smoke-browser`; `just packaging-smoke-browser-linux` carries
  the host `--with-deps` variant, and `just packaging-smoke-docker-browser`
  owns the `python:3.13-slim` proof. Do not run live AEAT auth or writes in this
  lane.

This complements the existing archive-manifest test. It does not replace
`just bootstrap`, because `bootstrap` is optimized for the shared Windows
developer worktree, not release hermeticity.

Source locators: `Docker version 29.6.1` from local tool output,
`uv 0.11.10` from local tool output, local clean-venv proof under
`var/packaging-smoke`, `dev/packaging/dependency_surface.py:1`,
`dev/packaging/smoke_core.py:1`,
`dev/packaging/smoke_extras.py:1`, `dev/packaging/smoke_browser.py:1`,
`dev/packaging/source_preflight.py:1`, `dev/packaging/tests/test_dependency_surface.py:1`,
`dev/packaging/smoke_docker.py:1`, `justfile:178`, `justfile:182`,
`justfile:187`, `justfile:207`, `justfile:217`, `justfile:229`,
`.github/workflows/packaging-smoke.yml:1`,
`src/aeat/adapters/outbound/aeat/browser/health.py:1`,
`https://docs.astral.sh/uv/guides/integration/docker/`.

## Recommendation

Create a `product-packaging` ADR that accepts this architecture:
self-contained wheel for project code plus reviewed package data, capability
extras for optional Python integration stacks, `aeat config check` as the
operator-facing readiness contract, and a clean Linux wheel-install smoke gate as
the release proof. External runtimes and user data stay outside the product
wheel and are provisioned or captured through typed application boundaries.

The ADR should explicitly reject post-install legal-data downloads, force-include
locator branching, bundling Playwright browsers or Ollama models, packaging
provider credentials, and treating user evidence attachments as package data.
