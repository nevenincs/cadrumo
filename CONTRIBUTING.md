# Contributing to Cadrumo

This guide covers setting up a development environment from a source checkout.
It is for contributors working on Cadrumo itself. If you want to *use* Cadrumo,
follow the [installation guide](docs/workstation-setup.md) instead — end users
install a released package, never a checkout.

## Set up the development environment

Choose one of two paths: install directly on your machine, or open the
project in a ready-made container.

### Option A: install on your machine

Install the project and its tools in one step:

```bash
just bootstrap
```

This installs the Python environment, syncs every dependency group, and runs
the readiness check at the end.

### Option B: open in a devcontainer

The repository ships a `Dockerfile` and a `.devcontainer/devcontainer.json`
with Python 3.13, `uv`, and headless-Chromium already installed, so you skip
the manual `uv sync` / `playwright install` steps entirely.

With VS Code and the Dev Containers extension, open the project folder and
choose "Reopen in Container". The first build installs every dependency group
and pre-bakes the Playwright browser; later reopens reuse the cached image.

Without VS Code, build and run the image directly:

```bash
just devcontainer-build
docker run --rm -it -v "$(pwd)":/workspace cadrumo-devcontainer bash
```

Verify the image installs cleanly and its toolchain works end to end:

```bash
just devcontainer-test
```

The container has no interactive display, so live AEAT browser reads run
headless (`CADRUMO_BROWSER_HEADLESS=true` is set for you). Your digital
certificate is personal, per-machine data — it is never baked into the image.
Mount it or set `CADRUMO_CERTIFICATE_PATH` after the container starts if you need
`aeat app live ...` inside the container.

## Check the workstation

`just doctor` runs `aeat config check` against the checkout's environment. The
report lists each external dependency, whether it is available, and the exact
command to fix any gap.

Provision the optional Playwright browser and get guidance for the on-host
vision model:

```bash
just provision
```

Run `just doctor` again after each change to confirm the gap is closed.

## Check Python runtime compatibility

Cadrumo supports CPython 3.13 and every newer released minor listed in
[`dev/ci/python-runtime-matrix.json`](dev/ci/python-runtime-matrix.json). The
inventory is the source of truth for local and CI runtime selection. Its
separate `next` row is a prerelease watch only; it is not a stable support or
classifier claim until it has been promoted with evidence.

The `next` row uses a provisionable rolling minor selector (currently `3.15`)
while prereleases are available. Its evidence records the exact interpreter
patch (currently CPython `3.15.0b4`); do not replace the rolling selector with a
fixed RC identifier unless that exact interpreter can be provisioned.

The repository's [`.python-version`](.python-version) is the exact Python
identity used to build release artifacts. It is deliberately narrower than the
support floor and must not be changed just to add a runtime to the matrix. To
install selectors for local checks, run for example:

```console
uv python install 3.13 3.14 3.15
```

Then run the inventory-driven compatibility command from a clean checkout:

```console
just python-compatibility
```

The command writes evidence below `var/python-runtime-compatibility/`. Source
evidence builds distributions from the source snapshot. Binary evidence installs
the one sealed release cohort with wheels only. A source pass therefore does not
prove that native dependencies have compatible wheels; a missing binary wheel is
a distinct compatibility result and must remain visible rather than being
silently skipped.

## Work on the modelo registry

The registry conformance tool reports how much of the modelo registry is
checked, and records who engineered and reviewed each revision. Read
[REGISTRY-CONFORMANCE.md](REGISTRY-CONFORMANCE.md) before stamping a revision or
moving the conformance baseline.

## Releases

Release mechanics, publication gates, and rollback live in
[RELEASING.md](RELEASING.md).
