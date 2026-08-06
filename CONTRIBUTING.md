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

## Work on the modelo registry

The registry conformance tool reports how much of the modelo registry is
checked, and records who engineered and reviewed each revision. Read
[REGISTRY-CONFORMANCE.md](REGISTRY-CONFORMANCE.md) before stamping a revision or
moving the conformance baseline.

## Releases

Release mechanics, publication gates, and rollback live in
[RELEASING.md](RELEASING.md).
