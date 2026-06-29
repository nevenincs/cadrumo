---
tags:
  - '#adr'
  - '#product-packaging'
date: '2026-06-28'
modified: '2026-06-29'
related:
  - "[[2026-06-28-product-packaging-research]]"
  - "[[2026-06-28-product-packaging-reference]]"
---

# `product-packaging` adr: `Self-contained wheel and clean-environment provisioning gate` | (**status:** `proposed`)

## Problem Statement

The project needs a product packaging decision that proves a vanilla
environment can install and run AEAT without relying on checkout-only files,
developer dependency groups, post-install legal-data generation, provider
credentials, or ad hoc runtime setup. Existing wheel tests prove archive
contents, but not clean installed-wheel execution.

The objective is broader than "the wheel builds." The release pipeline must also
prove that declared production dependencies, optional integration extras, and
developer-only dependencies are in the right places. A misplaced package can make
the bare product install too heavy, make an optional feature crash with a raw
`ModuleNotFoundError`, or leave a clean contributor environment without the
tooling needed to run the project gates.

## Considerations

The wheel must contain project code plus reviewed package data. Corpus,
registry, and terminology assets under `src/aeat/_data` are product data, not
downloadable install-time cache. The current hatchling wheel target packages
`src/aeat`, and the existing wheel guard verifies tracked `_data` files in the
archive.

The optional-service boundary already exists. `google`, `browser`,
`anthropic`, and `all` are declared as optional extras; the core optional-extra
registry provides install hints; and `aeat config check` reports dependency
availability for Ollama vision, subprocess provider CLIs, Playwright Chromium,
and optional Python packages.

The current dependency hygiene surface is useful but incomplete as a product
release proof. `just check-dependencies` runs `deptry` against production code,
`just env-pip-check` runs `uv pip check` against the local environment, and CI
runs `pip-audit` from a frozen `uv export`. Those should become explicit
packaging gates, alongside clean wheel install lanes, so production, optional,
and dev dependency intent is verified rather than inferred from a broad `uv sync`.
A local fresh-venv wheel proof already caught one concrete example:
`aeat --version` failed until `PyYAML`, imported by the CLI localization path,
was declared as a direct runtime dependency instead of being tolerated as a
transitive import.

`just bootstrap` remains a developer-worktree convenience. It intentionally uses
additive `uv pip install` in the shared Windows worktree to avoid executable-lock
churn. Release confidence must come from clean Linux install proof, not from the
shared-worktree bootstrap path.

## Considered options

Accept: ship a self-contained wheel for code plus reviewed data, use optional
extras for integration Python packages, keep dev-only tooling in dependency
groups, and prove release readiness through clean core, extras, browser, and
dependency-declaration smoke gates.

Reject: post-install legal-data downloads or regeneration. Legal grounding must
be reviewed before packaging; install-time fetching would bypass the accepted
corpus/registry authority flow.

Reject: `force-include` locator branching. The package should keep one
`importlib.resources` boundary and one installed data shape.

Reject: bundling Playwright browsers, Ollama models, provider CLIs, credentials,
or LLM caches. These are platform-specific or operator-owned runtime assets, and
their absence is reported through provisioning probes.

Reject: treating taxpayer evidence attachments as package data. Evidence is
runtime state owned by secure storage and export/audit services.

Reject: using `just bootstrap`, a broad dev `uv sync`, or the local virtualenv as
the release proof. Those paths prove the contributor environment, not the product
artifact.

## Constraints

This ADR relies on accepted corpus packaging, dependency provisioning, service
capability, LLM safety, and evidence-storage decisions. Those parent decisions
are stable enough to treat as constraints: reviewed data ships; optional
services require capability opt-in, dependency availability, and safety posture;
evidence and secrets never ship.

The release gate must avoid real taxpayer data, live AEAT authentication,
cloud-provider writes, and secret-dependent checks. Browser validation may
provision Chromium, but it must use no-secret navigation or local health checks.

The packaging pipeline must distinguish product runtime, optional runtime, and
developer tooling. A bare wheel install must not require the dev dependency
group; optional extras must be installable and fail instructively when absent;
the dev group must still provision quality tools such as `deptry`, `ruff`, type
checkers, docs tooling, vaultspec-rag support, and test plugins.

The shared worktree is dirty by design. Product packaging gates must therefore
use explicit artifacts and scoped commands rather than destructive cleanup or
workspace resets.

## Implementation

The package structure remains a self-contained hatchling wheel built from
`src/aeat`. Reviewed `_data` trees stay inside the distribution. The resource
boundary remains `importlib.resources` based; packaging code must not compute
checkout paths for corpus, registry, or terminology reads.

The packaging pipeline gains a core clean-install lane. It builds the wheel,
installs that wheel into a clean Linux environment without dev dependencies or
optional extras, then runs `aeat --version`, runs `aeat config check` to assert
typed diagnostics for missing opted-in optional services, creates a throwaway
profile with optional capabilities disabled, reruns `aeat config check` for an
exit-0 core proof, and runs an installed-package-data probe over representative
`_data` leaves. Before build/install, it also verifies every git-tracked
shipped-data file under the corpus, registry, and terminology trees exists in
the worktree and appears in the artifact archive, so stale tracked placeholders
or accidental deletions fail the packaging gate. It also runs installed-package
probes for the encrypted evidence attachment path and the LLM optional-extra
boundary: attachment bytes and manifest metadata must round-trip through the
real `AttachmentStore`, while the Anthropic adapter must refuse from a bare core
install with the declared `aeat[anthropic]` install hint. This lane also runs an
installed-environment dependency consistency check so wheel metadata and runtime
imports are validated together. The dependency-surface check is also available
as `just packaging-smoke-dependencies`, so `pyproject.toml`, frozen exports, and
the optional-extra registry can be verified even when artifact work is blocked
by source-data WIP; `just packaging-smoke-preflight-tests` covers that command's
JSON summary contract. The tracked source-data existence check is available as
`just packaging-smoke-source`, which every artifact lane depends on so missing
tracked data fails before wheel, virtualenv, or Docker work starts.
The current local implementations are `just packaging-smoke-core` for uv-managed
fresh virtualenv installation and `just packaging-smoke-pip-core` for a stdlib
virtualenv installed with plain `python -m pip`. The source-distribution form is
`just packaging-smoke-sdist-core`; it verifies the full tracked shipped-data set
in the `tar.gz`, installs the sdist through pip build isolation, and runs the
same installed core probes. The fresh Linux image form is
`just packaging-smoke-docker-core`, which preflights Docker daemon availability,
prefers the native WSL `Ubuntu` Docker daemon on Windows when it answers, builds
the wheel on the host, mounts only the wheel and probe directory into
`python:3.13-slim`, and installs with pip inside the container. Local execution
on 2026-06-29 now reaches the WSL-backed Docker daemon. The shared dirty
worktree still stops at the tracked shipped-data preflight until the deleted
normative JSON files are reconciled, but a detached clean checkout overlaid with
the packaging implementation passed the core container proof at
`var/packaging-smoke/docker-core-20260629T073827Z`.
The dedicated CI surface is `.github/workflows/packaging-smoke.yml`, which runs
the host-Linux wheel smoke and then the clean Docker image smoke on Ubuntu from
the frozen lock.

The pipeline gains optional-extra lanes. `just packaging-smoke-extras` installs
the same wheel with `all` through plain pip in a stdlib virtualenv and verifies
the Google, browser, and Anthropic optional packages import through the installed
optional-extra registry. A separate browser lane installs with `browser`, runs
`playwright install --with-deps chromium`, and executes the existing no-secret
browser health smoke. The browser binary remains provisioned, not bundled. The
current local browser implementation is `just packaging-smoke-browser`; the
Linux/container form is `just packaging-smoke-browser-linux` for host Linux
provisioning and `just packaging-smoke-docker-browser` for a clean
`python:3.13-slim` proof.
The detached clean-checkout WSL proof passed the browser container lane at
`var/packaging-smoke/docker-browser-20260629T074305Z`.

The pipeline makes dependency declaration checks first-class. Production source
continues to run through `deptry` with the existing focused exclusions so missing,
unused, transitive, and misplaced runtime declarations surface. The locked
runtime exports are checked against the direct dependency sets declared in
`pyproject.toml`: core exports must contain production dependencies and exclude
optional/dev-only packages, all-extras exports must contain production plus
optional packages and exclude dev-only packages, and all-groups exports must
contain production, optional, and dev dependencies. The locked runtime export
continues to feed `pip-audit`. The dev environment continues to run
`uv pip check` and tool-version checks so developer-only dependencies remain
installable. A dedicated dev lane creates an isolated uv project environment
from the frozen lock with all extras and all dependency groups, then starts the
declared tool surface from that environment. Tools that are not valid persistent
Python dev dependencies, such as Semgrep on Windows, stay out of the dev group
and are invoked through the repository's explicit pinned `uvx` command path. Any
allowed `deptry` suppression must remain narrowly documented in `pyproject.toml`.

`aeat config check` remains the operator-facing readiness contract, and
`just provision` remains the local convenience entry point for external runtime
setup. Fresh-install gates consume those surfaces instead of adding a parallel
doctor.

## Rationale

The research and reference records show that the current repository already has
the right conceptual split: code and reviewed data in the wheel, optional Python
integration packages behind extras, external runtimes behind provisioning
probes, and user evidence in runtime secure storage. The missing piece is proof
that this structure works from a clean install and stays honest as dependencies
move between product, optional, and dev surfaces.

Making clean install and dependency declaration checks part of the packaging
pipeline closes that gap. It proves not only that the archive contains the right
files, but that the package metadata, entry point, resource boundary, optional
extras, Playwright provisioning, and dependency hygiene all agree in an
environment that resembles an operator machine more than a contributor checkout.
The PyYAML failure demonstrates that this is not theoretical: archive contents
were correct, but the installed console script was broken until metadata and
runtime imports were checked together.

## Consequences

Release validation becomes stricter and more representative. A package can fail
before release because a dependency sits in the wrong table, an optional import is
not guarded, a wheel omits reviewed data, a console script is broken, or a
browser provisioning command no longer matches Playwright's runtime needs.

The wheel remains intentionally larger because reviewed legal and registry data
are part of the product. Optional integrations stay lean for core users but
require explicit provisioning when used.

The main operational risk is gate cost. Building a wheel, starting clean Linux
environments, installing browser system dependencies, and auditing dependency
exports are slower than local unit tests. That cost is appropriate for release
and packaging CI lanes; local developer bootstrap remains additive and lighter.

The second risk is drift between `pyproject.toml`, `aeat config check`,
`just provision`, and the smoke lanes. The plan that follows this ADR must keep
those surfaces wired to the same optional-extra registry and provisioning probes
rather than duplicating dependency knowledge in a separate packaging script.
