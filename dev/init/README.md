# Worktree initialization

`just init` is the canonical repository initialization command. It runs the
minimal checkout setup, installs the default Vaultspec resources, provisions and verifies
Playwright's bundled Chromium (and the configured browser channel when an
operator selects another one), provisions Vaultspec RAG and its managed external
dependencies, compiles and publishes the runtime authority under `.authority/`,
then reports the resulting configuration.

`just setup` remains the minimal convergence command for callers that need only
the locked Python environment, repository tooling, and local configuration.
`just init` delegates its Python and tooling phases to `just setup`, then adds
the browser, RAG, authority, and product configuration steps through their
existing owners. Both commands take no arguments, are non-interactive, and are
safe to run again.

The recipes:

| Recipe                        | What it does                                                  |
| ----------------------------- | ------------------------------------------------------------- |
| `just init`                   | Complete provisioning, including browsers, RAG and authority. |
| `just setup`                  | Locked Python, repository tooling and local configuration.     |
| `just setup-repository-tools` | Framework enrollment and pinned repository tooling; no Git hooks. |
| `just setup-check`            | Reports whether the worktree is initialized. Mutates nothing. |
| `just setup-workstation-tools` | Optional workstation CLI provisioning.                       |
| `just setup-browser`          | Check browsers and install missing binaries or Linux libraries. |

## The contract

**Idempotent, and cheap when there is nothing to do.** A phase is skipped when
a digest over its declared inputs — lockfiles, version pins, manifests, and
this package's own source — matches the one recorded in `.venv/.init-stamp.json`
*and* every artifact the phase promised is still present. Both halves matter:
the digest catches a changed lockfile, the artifact check catches a `.venv`
somebody deleted. The Python phase also asks `uv sync --check` whether installed
packages still match the lockfile; missing or extra packages trigger a sync.
Browser provisioning uses real headless launches, reuses working installations,
and repairs missing binaries or Linux libraries. System installations require
root or passwordless sudo on Linux. Authority publication reuses a generation
that still matches the source data and supported artifact format.

**Fail-fast, and complete in what it reports.** Unlike the fleet's `-all`
aggregates, which run every step because they chain independent inspectors,
the shared bootstrap phases form a dependency chain. The tooling phase runs
executables out of the environment the Python phase created. Initialization stops at
the first failing phase, and records the phases it did not attempt as `skipped`
with the upstream cause named. A non-zero `setup` names exactly one cause.

**Machine-readable bootstrap.** The shared phase runner writes `.venv/init-report.json` (or
`.init-report.json` when the environment does not exist yet — the path is
always printed). The report covers Python and repository tooling. Browser,
RAG, authority, and product configuration steps report through their own commands.
`VAULTSPEC_INIT_JSON=1`, or `--json`, additionally streams
NDJSON events on stdout while human prose stays on stderr. Exit codes come from
`dev/exit_codes.py` and are identical fleet-wide:

| Code | Meaning                                                                  |
| ---- | ------------------------------------------------------------------------ |
| `0`  | Initialized, or already initialized.                                     |
| `2`  | A required host tool is absent. The report names it and where to get it. |
| `3`  | `setup-check` only: the worktree is not initialized, or is stale.         |
| `4`  | A bootstrap step ran and failed.                                         |
| `5`  | Drift: a lockfile no longer matches its project metadata.                |
| `6`  | The environment is held open by another process. Close it and re-run.    |

Code `6` is the one worth knowing by sight. On Windows an editor, an MCP
server, or another agent's session holding a console-script `.exe` under
`.venv/Scripts` makes a dependency install fail in a way that looks like a
build error and is not one. The remedy is to close the process, never to debug
the repository.

**Multiplatform without shell branching.** The bootstrap phases run explicit
argument vectors through one Python runner. Full initialization composes the
same provisioning commands on each platform.

**It provisions the worktree, not the workstation.** `uv`, `just`, and the
required repository tools are the operator's responsibility; `setup` converges
the managed Python environment and repository tooling. The initializer probes
its host requirements before provisioning. Optional workstation tools are installed
only by `setup-workstation-tools`.

**It does not install commit hooks or change Git configuration.** `prek.toml`
is retained only for explicit `just check-hooks` replay over all files. Fast
mechanical repair is an explicit, caller-owned-path action (`just fix-code
path/to/file.py`) outside commit time.

**Minimal setup keeps external provisioning separate.** `setup` restores what
the lockfiles pin. Full `init` additionally provisions browsers and the default
RAG resources. `setup-browser` can repair browser resources independently.

## Layout

The initialization runtime follows the fleet contract. `plan.py` owns this
repository's phase data; no setup module owns Git-hook installation.

| File          | Role                                                           |
| ------------- | -------------------------------------------------------------- |
| `contract.py` | Phases, steps, results, the event stream, the report schema.   |
| `process.py`  | Running a step, and classifying its failure into an exit code. |
| `probe.py`    | Host-tool discovery and version comparison.                    |
| `stamp.py`    | Input digests and the idempotence stamp.                       |
| `plan.py`     | **This repository's** phases. The only file that differs.      |

The package imports only the standard library and `dev.exit_codes`. It must
never import `dev.toolchain`, `dev.runner`, or anything reached through
`uv run --no-sync python -m dev`: it runs *before* the virtual environment
exists, on an ephemeral interpreter, which is the whole reason it is separate
from the rest of the harness.

## Adding a step

Edit `plan.py` and nothing else. Add a `Step` to the right phase, and — this is
the part that is easy to forget — add whatever file decides that step's outcome
to that phase's `inputs`, and whatever the step produces to its `artifacts`.
A step whose input is not declared will be skipped after that input changes; a
step whose artifact is not declared will be skipped after somebody deletes it.
