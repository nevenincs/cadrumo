"""What initializing THIS repository means.

The only file in :mod:`dev.init` that differs between repositories. Everything
here is data: the host tools the workstation must already provide, the steps
each phase runs, and - the part that is easy to get wrong - the inputs whose
change makes a phase stale and the artifacts whose absence does the same.

``cadrumo`` already had `just bootstrap`, and it was the model the rest of the fleet
was standardized onto. This plan does not reimplement it: every step delegates
to :mod:`dev.env`, which is where the venv provisioning, the exclusive install
lock, and the `env/.env` materialization already live and where they stay.
What `init` adds here is the stamp - so a second run is a no-op rather than a
full locked synchronization - and the machine-readable report.

Two of that module's behaviours are load bearing and are preserved exactly:

``uv sync --locked`` is the sole environment operation
    The committed lockfile is authoritative, ``uv`` creates ``.venv`` when it
    is absent, and exact synchronization removes undeclared packages. The
    live-process guard below prevents Windows executable-lock collisions.

The exclusive, venv-scoped lock
    An ``O_CREAT | O_EXCL`` create, hashed to the resolved environment path so
    two worktrees on one machine do not serialize each other. A second
    installer targeting the same environment is refused immediately, which
    surfaces here as :data:`dev.exit_codes.INIT_LOCKED`.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import sys
from typing import Final

from dev.init.contract import Phase, Step
from dev.init.probe import Requirement

#: The ephemeral interpreter `init` is running on. Steps that are themselves
#: Python reuse it rather than assuming a `python` on PATH, because the whole
#: premise of this package is that the environment does not exist yet.
PY: Final = sys.executable

#: The delegation prefix. Every provisioning step is an action of
#: :mod:`dev.env`, which is stdlib-only and therefore reachable on the same
#: ephemeral interpreter that runs `init` itself.
ENV: Final[tuple[str, ...]] = (PY, "-m", "dev.env")

#: What the workstation must provide before `init` can do anything.
#:
#: `node` and `npx` are advisory: only the duplication audit shells out to
#: `jscpd` through them, and a worktree is entirely usable without it.
#: `just setup-workstation-tools` remains the recipe that INSTALLS them, opt-in and
#: separate, because provisioning the host is not `init`'s job.
REQUIREMENTS: Final[tuple[Requirement, ...]] = (
    Requirement(
        command="uv",
        purpose="It creates the pinned environment and installs into it.",
        install_url="https://docs.astral.sh/uv/getting-started/installation/",
    ),
    Requirement(
        command="node",
        purpose="Only the duplication audit needs it; `just setup-workstation-tools` installs it.",
        install_url="https://nodejs.org/",
        advisory=True,
    ),
    Requirement(
        command="npx",
        purpose="Only the duplication audit needs it; `just setup-workstation-tools` installs it.",
        install_url="https://nodejs.org/",
        advisory=True,
    ),
)

#: Steps that run before any phase, on every entry point. This repository keeps
#: its environment file under `env/`, and `dev.env` already owns the rule that
#: an existing one is never overwritten - so the preflight delegates there
#: rather than restating the paths.
PREFLIGHT: Final[tuple[Step, ...]] = (
    Step(
        name="dotenv",
        argv=(*ENV, "setup"),
        summary="Provision env/.env from env/.env.example when it is absent.",
    ),
)

PYTHON = Phase(
    name="python",
    summary="Synchronize the pinned environment exactly from uv.lock.",
    steps=(
        Step(
            name="sync",
            argv=(*ENV, "install"),
            summary="Run the canonical locked uv project synchronization.",
        ),
    ),
    inputs=("uv.lock", "pyproject.toml", ".python-version"),
    artifacts=(".venv",),
)

TOOLS = Phase(
    name="tools",
    summary="Install the Vaultspec tooling and diagnose the result.",
    steps=(
        Step(
            name="vaultspec-install",
            argv=("uv", "run", "--no-sync", "vaultspec-core", "install", "--upgrade"),
            summary="Install the repository tooling and refresh its builtin snapshots.",
        ),
        Step(
            name="doctor",
            # Advisory for the same reason the old recipe prefixed it with `-`:
            # a configuration report is the last word a person wants after a
            # successful provisioning, and never a reason to call it failed.
            argv=("uv", "run", "--no-sync", "aeat", "config", "check"),
            summary="Report the resulting configuration.",
            advisory=True,
        ),
    ),
    inputs=("uv.lock",),
    artifacts=(),
)

#: The phases, keyed by name. The runner reads this and nothing else.
#:
#: `just setup-playwright` is deliberately absent. Downloading two browser
#: channels is minutes of network for a capability most worktrees never
#: exercise, and CI already invokes it as its own step.
PHASE_PLAN: Final[dict[str, Phase]] = {
    "python": PYTHON,
    "tools": TOOLS,
}
