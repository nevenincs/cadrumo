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

This creates the pinned Python environment, installs the project and all
development dependencies, installs the repository tooling, provisions
`env/.env`, and runs the readiness check at the end. It is safe to run again
and costs nothing when there is nothing to do. `just init-check` reports
whether a worktree is ready without changing anything.

### Option B: open in a devcontainer

The repository ships a `Dockerfile` and a `.devcontainer/devcontainer.json`
with Python 3.13, `uv`, and headless-Chromium already installed, so you skip
the manual `uv sync` / `playwright install` steps entirely.

With VS Code and the Dev Containers extension, open the project folder and
choose "Reopen in Container". The first build installs every dependency group
and pre-bakes the Playwright browser; later reopens reuse the cached image.

Without VS Code, build and run the image directly:

```bash
docker build --target dev -t cadrumo-devcontainer -f Dockerfile .
docker run --rm -it -v "$(pwd)":/workspace cadrumo-devcontainer bash
```

The container has no interactive display, so live AEAT browser reads run
headless (`CADRUMO_BROWSER_HEADLESS=true` is set for you). Your digital
certificate is personal, per-machine data — it is never baked into the image.
Mount it or set `CADRUMO_CERTIFICATE_PATH` after the container starts if you need
`aeat app live ...` inside the container.

## Publish the runtime authority

A fresh clone cannot calculate or file anything until you publish the runtime
authority once. The authority is the compiled, digest-checked publication of
the tax-rule registry, and it is the only registry source an installed Cadrumo
process reads. A released package carries one; a checkout builds its own.

```console
just registry-publish-authority
```

The publication lands in `.authority/` at the repository root. It is roughly
eighty megabytes, it takes a few minutes, and it is excluded from version
control: it is regenerated output, it changes whenever the registry sources
do, and carrying it in history would add that much binary to every clone.
Commit the registry change on its own; never commit the result of this
command.

Republish whenever you change registry declarations or legal evidence, and
after a dependency or interpreter change — the publication records the
identity of the sources and the compiler that produced it, so either kind of
change makes it stale. `just check-registry` tells you when it has.

### Where the tooling looks for it

`CADRUMO_AUTHORITY_ROOT` names the directory to resolve the authority from,
and whether you set it depends on how you start the process:

| How you run | The variable |
| --- | --- |
| `just` recipes, `python -m dev.*`, `pytest` | Set for you, to this checkout's `.authority/`. |
| The `aeat` command from your checkout | You set it yourself. |

That split is deliberate and will not be closed. Cadrumo's runtime never
imports its development tooling and never searches upwards for a repository
root, so nothing in the product can discover a checkout's `.authority/` on its
own. The development tooling knows where the repository is and seeds the
variable; the product does not and cannot. To run the `aeat` command against
your checkout's authority, name it yourself:

```powershell
$env:CADRUMO_AUTHORITY_ROOT = "$PWD\.authority"
```

An explicit value always wins over the seeded one, so a run pointed at another
authority tree is never overridden by the checkout's own.

### The two refusals you will meet

Both name the command that fixes them. Which one you see says where the
process was looking.

Before you have published, `just`, `pytest` and the `dev` tooling report:

```text
CADRUMO_AUTHORITY_ROOT points at a directory that holds no registry authority
descriptor at <repo>\.authority\authority.current.json. Publish the authority
with `python -m dev.registry.pipeline publish-authority` or point the variable
at a published authority tree.
```

The `aeat` command with the variable unset looks in the packaged location
instead, finds nothing there in a checkout, and reports:

```text
No registry authority is published at <...>\cadrumo\_data\registry\authority\authority.current.json.
Publish it with `python -m dev.registry.pipeline publish-authority`, or set
CADRUMO_AUTHORITY_ROOT to a published authority tree.
```

Neither falls back to the other. A configured root is the whole answer, so a
checkout cannot silently answer from packaged bytes it believed it had
replaced.

For the publication format, the verification steps, and the release-only
candidate directory, see
[Publish a validated runtime authority](docs/how-to/publish-runtime-authority.md).

## Check the workstation

`just doctor-check` runs `aeat config check` against the checkout's environment. The
report lists each external dependency, whether it is available, and the exact
command to fix any gap.

Provision the optional Playwright browser and get guidance for the on-host
vision model:

```bash
just setup-playwright
```

Run `just doctor-check` again after each change to confirm the gap is closed.

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
just test-python-compatibility
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
