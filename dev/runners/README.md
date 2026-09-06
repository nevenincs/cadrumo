# Self-hosted runner disk hygiene

Auto-cleanup for the self-hosted GitHub Actions runner fleet. Hardware space is
limited, so each runner purges the artifacts that bloat its caches on **every**
job completion — success **and** failure — using the runner-native job hook
`ACTIONS_RUNNER_HOOK_JOB_COMPLETED`. This hook is the machine-level guarantee a
workflow cannot provide: it fires even when a job fails, cancels, or times out.

## Fleet

Runners are identified here by role, not by machine name — host names are
operator-identifying and are kept out of committed text (gated by
`dev/quality/tests/test_doc_privacy.py`). Substitute your own host wherever a
`<...>` placeholder appears.

| Role                  | Labels                       | Platform | Location                                  | Script               |
| --------------------- | ---------------------------- | -------- | ----------------------------------------- | -------------------- |
| Windows build host    | `self-hosted, Windows, X64`  | Windows  | `C:\action-runners\cadrumo`               | `cleanup-windows.ps1`|
| Linux container runner| `self-hosted, Linux, X64`    | Linux    | docker container `cadrumo-runner-linux-1` | `cleanup-linux.sh`   |
| macOS build host      | `self-hosted, macOS, ARM64`  | macOS    | `~/action-runners/cadrumo`                | `cleanup-macos.sh`   |
| Linux ARM container   | `self-hosted, Linux, ARM64`  | Linux    | colima container `cadrumo-runner-mac-arm` | `cleanup-linux.sh`   |

**Every runner root on a host lives under one canonical parent** —
`C:\action-runners\<repo>\` on Windows, `~/action-runners/<repo>/` on macOS.
Both machines also host runners for other repositories under the same parent;
they are separate registrations, because a personal account has no
organisation-level runner groups and a runner is therefore always scoped to
exactly one repository.

Moving a runner root is not a plain directory move. Three things embed its
absolute path and every one of them fails silently:

- **`bin` and `externals` are links** (NTFS junctions on Windows, symlinks on
  macOS) created by the runner's self-update, pointing at `bin.<version>`. After
  a move they dangle, `Runner.Listener` disappears, and `run.cmd` spins in its
  `:launch_helper` restart loop forever.
- **The launcher** is a scheduled task (Windows) or launchd plist (macOS)
  holding the old path. It fails at the next logon, not immediately.
- **The hygiene hook path** in `.env`, plus any hardcoded root inside the
  cleanup script itself.

There was ONE Linux X64 slot as of the 2026-08-06 consolidation, down from two.
The queue watchdog tolerates this: it excludes itself from its own scan and
treats a job queued against an OCCUPIED label set as demonstrably schedulable,
so jobs waiting behind it are skipped rather than flagged. The cost is
wall-clock, not correctness — a workflow carrying both the watchdog and another
Linux X64 job now serialises them, and because the run cannot reach a terminal
status while a job is still queued, the watchdog stands down only at its
`MAX_WATCH_SECONDS` window. Weigh that before adding another Linux X64 job to a
watchdog-bearing workflow.

A runner's REGISTERED name (what `gh api .../actions/runners` reports) and its
CONTAINER name (what `docker ps` reports) are NOT the same string for the two
Linux X64 runners. Reconcile the two views by position and label set, never by
matching names. The registered names are machine-identifying and so are kept out
of committed text — `dev/quality/tests/test_doc_privacy.py` gates this file and
will fail the build if they are pasted back in.

The two Linux runners are docker containers that mount the host docker socket,
so the smoke suite's nested containers create anonymous volumes and dangling
images on the **host** daemon. The Linux hook prunes those from inside the
container; the Windows hook (running on the docker host) prunes them too, so the
host daemon is cleaned whether or not a Linux job is the last to finish.

## What the hooks clean

Every hook, in order:

1. **Stale `_work/_temp`** — the runner clears the current job's temp; crashed
   jobs strand dirs here. Entries older than 24h are removed.
2. **Per-run lane roots** — `cadrumo-homebrew*`, `cadrumo-scoop*`, `cadrumo-claude-*`, `oracle-emit-work*`
   in `RUNNER_TEMP` and `_work`, older than 24h.
3. **Reused-checkout `var/`** — the checkout in `_work/<repo>/<repo>` is reused
   by the next job (incremental fetch) and is **left in place**; only its
   gitignored `var/` residue is purged (`release-cohort*`, `oracle-emit-work*`,
   `*.tar.gz`) older than 24h. `var/distribution-install-readiness` (evidence
   rows) is **exempt for 7 days**. The reused `.venv` is never touched.
4. **Bounded speed caches** — `uv cache prune` (fast, native) every job, then a
   hard size cap: uv 5GB, pip 3GB, npm 3GB, by oldest-first eviction of
   per-package cache entries (a cache miss is a re-download, never corruption).
5. **Docker hygiene** (Linux + Windows host) — `docker container prune`
   (stopped only), `image prune` (dangling only, never `-a`), `volume prune`
   (unreferenced only), `builder prune --keep-storage 5GB`.
6. **Platform residue** — macOS: uninstall/untap leftover `cadrumo-smoke*` test
   formulas and taps, `brew cleanup -s --prune=7`, clear stale `/tmp` lane dirs.
7. **Audit line** — one line per run appended to `<work-root>/runner-hygiene.log`
   (rotated at 2MB → `.log.1`): timestamp, job, run id, bytes freed, what pruned.

### Safety invariants (never violated)

- Never deletes tracked files in any checkout.
- Never touches runner binaries or credentials (`.runner`, `.credentials`).
- Never touches the reused checkout's `.venv`.
- Never touches named docker volumes (`cadrumo-runner-state*`) or the running
  runner containers — docker `prune` only removes **unreferenced** objects.
- Never touches real financial data (`%LOCALAPPDATA%\aeat`).
- Never touches the operator's real Homebrew packages — only `cadrumo-smoke*`.
- **Always exits 0.** A cleanup failure logs a note and is swallowed; it can
  never redden a green build.

### Performance

Hooks must stay fast (<30s typical) because they run on every job. The cheap
work runs every time (age-stat lane purge, `uv cache prune`); the expensive
work (recursive size measurement for cache caps, docker prune) is throttled to
run at most once every 6h via marker files in `<work-root>/.hygiene/`.

## Wiring a runner

The hook is enabled per runner by adding the environment variable to the runner
root's `.env` file and restarting the runner service.

### Windows build host

```powershell
# copy the script into the runner root (out of the reused checkout tree)
Copy-Item dev\runners\cleanup-windows.ps1 C:\actions-runner\cleanup-windows.ps1 -Force

# add the hook var to the runner .env (create if absent)
Add-Content C:\actions-runner\.env "ACTIONS_RUNNER_HOOK_JOB_COMPLETED=C:\actions-runner\cleanup-windows.ps1"
```

The Windows runner here runs **interactively** (`Runner.Listener` in a console
session), not as a Windows service — there is no `.service` marker and no
`actions.runner.*` service to `Restart-Service`. The `.env` hook takes effect on
the next listener start, so the runner must be stopped and relaunched in its own
console session (Ctrl-C the `run.cmd` window, then re-run `run.cmd`) when
`busy=false`. Killing the listener process does **not** auto-resume it. If the
runner is later reconfigured as a service (`svc.sh install` / `Install-Service`),
switch to `Get-Service 'actions.runner.*' | Restart-Service`.

### Linux docker runners (`cadrumo-runner-linux-1`, `-2`)

The in-container runner root is `/home/runner` (that is where `config.sh`,
`.runner`, `.env`, and `_work` live). Copy the script there and append the hook
var to `.env`, then restart the container **one at a time** — never both down
simultaneously, CI/smoke depend on the pair (the runner auto-resumes on
restart, which re-reads `.env`):

```bash
for c in cadrumo-runner-linux-1 cadrumo-runner-linux-2; do
  docker cp dev/runners/cleanup-linux.sh "$c":/home/runner/cleanup-linux.sh
  docker exec "$c" bash -lc 'chmod +x /home/runner/cleanup-linux.sh 2>/dev/null; \
    grep -q ACTIONS_RUNNER_HOOK_JOB_COMPLETED /home/runner/.env 2>/dev/null || \
    echo "ACTIONS_RUNNER_HOOK_JOB_COMPLETED=/home/runner/cleanup-linux.sh" >> /home/runner/.env'
  # restart ONLY when this container's runner is idle (busy=false); wait for the
  # other to be online before restarting the second.
  docker restart "$c"
done
```

### macOS build host

```bash
ssh <macos-build-host> '
  cp ~/actions-runner/cleanup-macos.sh ~/actions-runner/cleanup-macos.sh 2>/dev/null || true
  chmod +x ~/actions-runner/cleanup-macos.sh
  grep -q ACTIONS_RUNNER_HOOK_JOB_COMPLETED ~/actions-runner/.env 2>/dev/null || \
    echo "ACTIONS_RUNNER_HOOK_JOB_COMPLETED=$HOME/actions-runner/cleanup-macos.sh" >> ~/actions-runner/.env
  # restart via the runner service manager (svc.sh) only when idle
  cd ~/actions-runner && ./svc.sh stop && ./svc.sh start'
```

(Copy `cleanup-macos.sh` to the runner root first, e.g. `scp dev/runners/cleanup-macos.sh <macos-build-host>:~/actions-runner/`.)

## Capability verification

`uv run --no-sync python -m dev.containers.runner_capabilities` checks that a
runner carries what the workflows assume. The `host-capabilities` job of
`.github/workflows/runner-fleet-health.yml` runs it on every host-install runner;
the container runners are covered instead by `just runner-image-test`.

What counts as "assumed" is measured, not guessed. Parsing the `run:` blocks of
every workflow shows `uv`, `just`, and `node` are each installed by a pinned
setup action, while **`gh` is invoked by four workflows and installed by none**
(`packaging-campaign-trigger`, `packaging-homebrew`, `packaging-scoop` and
`release-please`). `packaging-scoop` requests the `windows-scoop` label that no
runner carries, so that lane never schedules and `scoop` is deliberately not
probed.

**`.path` beats `.env`, and that is how `gh` went missing on macOS.** The runner
root can hold both files. `.env` sets the service environment; `.path` sets the
PATH applied to job steps, and `.path` is what wins. The macOS runner shipped a
`.env` whose PATH included `/opt/homebrew/bin` and a `.path` whose PATH did not,
and `gh` exists only under the Homebrew prefix — so every macOS/ARM leg of
`packaging-homebrew` and `packaging-smoke` ran without a reachable `gh`, the
`REFUSED: forge check needs the gh CLI on PATH` failure, live and unnoticed.

The gap is invisible from an interactive SSH session, because a login profile
puts Homebrew on PATH there. Read the LISTENER process environment instead —
`ps eww -o command= -p "$(pgrep -f 'actions-runner/bin/Runner.Listener')"` — or
run the probe under `env -i PATH="$(cat ~/actions-runner/.path)"`. Editing
`.path` requires a runner restart to take effect, and the runner must be idle
(see *Restart discipline*).

## How the runners relate to the other container images

Three container surfaces exist in this repository and they are not independent.
All of them are declared in the **single repository-root `Dockerfile`**, one
stage each, one base image declaration each.

| Surface | Declared as | Base | Built by |
| ------- | ----------- | ---- | -------- |
| Self-hosted Linux runner | `--target runner` | `ARG RUNNER_BASE_IMAGE` (`ghcr.io/actions/actions-runner`, pinned) | `just runner-image-build` |
| Contributor devcontainer | `--target dev` | `ARG PYTHON_BASE_IMAGE` (`python:3.13-slim-trixie`) | `just devcontainer-build` |
| Base-image reader | `dev/packaging/_base_image.py` | reads `ARG PYTHON_BASE_IMAGE` back from the Dockerfile | consumed by the packaging gates |

The chain at CI time runs top to bottom: a workflow job labelled
`[self-hosted, Linux, X64]` lands in a **runner container**, which mounts the
**host** docker socket; the packaging smoke lanes then start **nested**
clean-Linux containers on the host daemon through that socket to prove a built
wheel installs from scratch. That is why the Linux cleanup hook prunes the
*host* daemon from inside the container — the residue it is cleaning was created
one level up.

The runner keeps a separate base **by necessity, not by drift**: its upstream
image carries the GitHub Actions runner agent itself (`run.sh`, `config.sh`,
`Runner.Listener`), built against Ubuntu. There is no build of that agent on the
Python base. The other two share one base, and share it by construction —
`dev/packaging/_base_image.py` parses `ARG PYTHON_BASE_IMAGE` out of the
Dockerfile so the string exists in exactly one place, and
`dev/packaging/tests/test_container_base_image_singularity.py` fails the build
if any surface re-declares it.

## Linux container provisioning (the `runner` image)

The Linux runners build from `--target runner`, which bakes in everything that
makes them *these* runners. Previously they ran the **stock**
`ghcr.io/actions/actions-runner` image and every such thing was hand-copied into
the `cadrumo-runner-state-<n>` volume, so a rebuild silently lost whatever
nobody remembered to re-copy. The lessons below were all learned by outage; they
are preserved because they explain why the image is shaped the way it is, and
because the pre-cutover fleet still runs the old scheme.

**The one placement rule: the state volume mounts over `/home/runner`, so
anything installed there is shadowed at runtime.** That single fact drives every
path choice in the `runner` stage. Tools go to `/usr/local/bin`, Homebrew to
`/home/linuxbrew`, the entrypoint to
`/usr/local/bin/cadrumo-runner-entry.sh` — all outside the shadowed path, and
therefore all surviving a container rebuild without living in the volume.

**The entrypoint must never come from a host path.** A container whose
entrypoint is bind-mounted from a scratch or temp directory dies the moment that
directory is cleaned up: Docker recreates the missing bind source as an empty
**directory**, exec fails, and the container exits **127** and stays down *even
with* `--restart always`. The tell is a mount whose source is a temp path, which
`Test-Path` reports as existing while reading it errors with "is a directory".
Baking it into the image removes the failure mode entirely.

**`gh` is assumed present the way it is on GitHub-hosted runners, and the
upstream image does not ship it.** The image carries `jq`, `git`, `curl`, `tar`
and the docker client only. Workflows install `just` and `uv` themselves through
actions, but nothing installs `gh`; the acquisition and campaign lanes that run
on this fleet invoke it directly, so when it is absent they fail mid-lane with a
command-not-found inside a step that never names the missing tool. The `runner`
stage pins the current
upstream release (Ubuntu 24.04's own package is several minor versions behind)
and installs it to `/usr/local/bin`.

**Homebrew must sit at the canonical prefix, never behind a symlink.** The
acquisition lane runs `brew` from `/home/linuxbrew/.linuxbrew/bin/brew` and
fails its very first step, `Verify declared Homebrew release row`, on `test -x
"$BREW_PATH"` if it is missing. Relocating the tree and symlinking
`/home/linuxbrew` at it is the obvious way to make it survive a rebuild and it
breaks `brew link`: `brew --prefix` still answers correctly, so an install
proceeds all the way through building every resource before failing at the very
end with

```
An unexpected error occurred during the `brew link` step
Permission denied @ dir_s_mkdir - /linuxbrew
```

Homebrew computes relative link traversals against the RESOLVED path, so through
a symlink the `..` walk climbs too far and lands at `/linuxbrew` on the
filesystem root. The stage installs at the real path and asserts
`readlink -f "$(command -v brew)"` stays inside `/home/linuxbrew/` at build
time, and clones with full history — a `--depth=1` clone leaves `brew --version`
reporting "shallow or no git repository" and Homebrew refuses to work from it.

Homebrew was previously described here as "the one dependency that genuinely
does not survive a container rebuild". In the image it does; that was a
consequence of provisioning by hand, not a property of Homebrew.

**Retired: the `libatomic1` gap.** The dev lane used to run `pyright`, a Python
wrapper around a JavaScript analyser. With no `node` on `PATH` it downloaded its
own, and that build needs `libatomic.so.1`, which the stock image does not
carry; the lane then died `exit 127` with `error while loading shared
libraries: libatomic.so.1`. Because a shared library could not live in the volume
the way `gh` did, it had to be reinstalled by hand on every container rebuild —
and a rebuild that skipped the step broke the packaging smoke without naming why.

The type checker is now `pyrefly`, a native binary with no JavaScript runtime
underneath, so this gap no longer exists and the apt step is retired. Nothing
needs installing for the dev lane's type check. Note that the failure class it
represents — a shared library that cannot live in a volume — is exactly what the
image-based scheme removes.

**A stopped runner is a doomed runner, and the volume dies with it.** This is the
third failure class and the most expensive, because it is silent. If a container
stops and stays stopped, the service deletes its registration after a period of
no contact. When the container next starts — a daemon restart, a host reboot,
the restart policy firing — it wakes with credentials naming a registration that
no longer exists, logs `the runner registration has been deleted from the
server, please re-configure`, and exits 1. With `--restart always` that becomes
an unrecoverable loop: re-registering needs a token the container has no way to
obtain, so it burns restarts forever. `docker container prune` then reaps it on
the next job completion anywhere on the host, and the runner is simply gone.

Three consequences worth internalising. **A state volume whose registration was
deleted is permanently dead** — never build a new container on it, because it
reproduces the loop indefinitely; register fresh into a fresh volume and leave
the old one for disposal. **Nothing in this fleet detects any of that**: the loop
is logged inside a container nobody watches, so the gap is invisible until
someone counts runners by hand. And because the whole chain begins with a
container that merely *stopped*, the cheap prevention is noticing within days
rather than weeks.

**Capability parity between the two Linux runners is load-bearing, not tidiness.**
They carry identical labels, so a job requesting `[self-hosted, Linux, X64]`
lands on whichever is free. Any tool present on one and absent on the other is a
coin-flip failure that reproduces only half the time — the worst debugging shape
there is. The image is what makes parity structural rather than a habit: two
containers from the same image tag cannot disagree about their tools. This is
also why `RUNNER_BASE_IMAGE` is pinned to a release tag and not `:latest` — a
base that moves between the two `docker create` calls reintroduces exactly the
drift the image removes.

### Building the image

```bash
just runner-image-build   # docker build --target runner -t cadrumo-runner-linux .
just runner-image-test    # gh, just, canonical-prefix brew, cache placement,
                          # pre-warmed ruby, entrypoint, agent, volume-shadowing
```

`runner-image-test` checks each capability whose absence caused a documented
outage, including that `brew` resolves with no symlink indirection — a condition
that otherwise only reveals itself at the very end of a real install — and it
mounts a tmpfs over `/home/runner` to prove the volume cannot shadow the tools.

### Distribution: build per host, no registry

Only TWO machines need the image, so a registry would be more moving parts than
the problem has. The docker host serving both Linux X64 containers builds it
once for both; the ARM host builds its own natively. `--target runner` means the
Python-based `dev` stage is never built, so neither build pulls the multi-gigabyte
dependency set.

- **Linux X64 host:** `just runner-image-build`, or the `runner-image` job of
  `.github/workflows/runner-fleet-health.yml`, which also reclaims the tagged
  image afterwards (the hygiene hook prunes only DANGLING images, so a tagged
  build would otherwise leave gigabytes behind on a space-constrained box).
- **ARM host:** build on the HOST, not inside the runner container — that
  container has no docker socket, so it cannot build. Copy the `Dockerfile` and
  `dev/runners/runner-entry-linux.sh` across, preserving the relative path, and
  build with `docker buildx build --load --target runner -t
  cadrumo-runner-linux:arm64 .`.

**buildx is required, not optional.** The LEGACY builder ignores stage
dependencies and builds every stage up to the target in file order, so
`--target runner` on it also builds `base` and `dev` — the latter fails outright
without a full repository context and, before failing, downloads the CUDA torch
stack onto the machine with the least disk. If `docker build` prints the
"legacy builder is deprecated" banner, install buildx before going further.

### Cutover, one runner at a time

The live fleet still runs the stock image; nothing swaps automatically. Cut over
deliberately, and **never both runners at once** — CI and smoke depend on the
pair.

1. Build and test the image on the docker host.
2. Poll busy state (see *Restart discipline*) and pick an **idle** runner.
3. Recreate it against its existing volume with the command below.
4. Confirm it comes back online and takes a job before touching the second.

```bash
# STOP GRACEFULLY, then WAIT for the daemon to actually report it stopped.
# `docker stop` returning is NOT the same as the container being stopped: the
# runner traps SIGTERM (RUNNER_MANUALLY_TRAP_SIG=1), and a `docker rm` issued
# straight after fails with "container is running", leaving the old container
# in place while the rest of the sequence half-executes.
docker stop -t 45 cadrumo-runner-linux-2
for i in $(seq 1 30); do
  [ "$(docker inspect -f '{{.State.Running}}' cadrumo-runner-linux-2)" = false ] && break
  sleep 2
done
docker rm cadrumo-runner-linux-2

docker create --name cadrumo-runner-linux-2 --restart always \
  --user runner -w /home/runner \
  -v cadrumo-runner-state-2:/home/runner \
  -v /run/host-services/docker.proxy.sock:/var/run/docker.sock \
  -e RUNNER_MANUALLY_TRAP_SIG=1 -e ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=1 \
  cadrumo-runner-linux
docker start cadrumo-runner-linux-2
```

**Prefer the graceful stop over `docker rm -f`.** A force-remove kills the agent
without releasing its server-side session, and the replacement then loops on
`POST .../session failed. HTTP Status: Conflict` until the stale session expires
— measured at roughly 90 seconds of downtime. The same cutover done with a
graceful stop was back online in 12 seconds.

**From Git Bash on Windows, prefix the command with `MSYS_NO_PATHCONV=1`.**
Otherwise the socket path is rewritten into a Windows path and `docker create`
fails with `mkdir C:\Program Files\Git\run: Access is denied` — after the old
container has already been removed, so the runner is down until you notice.

Two differences from the old command. There is no `--entrypoint` override: the
image declares it, at a path the volume cannot shadow. And the image is
`cadrumo-runner-linux`, not the upstream tag.

This works **only when the volume still holds a live registration**
(`config.sh`, `run.sh`, `.runner`, `.credentials`, and `.env` are already there,
so it does **not** re-register). If the registration was deleted, do not reuse
the volume — create a new one and run `config.sh` against a fresh registration
token first.

Note that the runner **agent** itself lives in the volume, seeded from whatever
image first populated it. Bumping `RUNNER_BASE_IMAGE` therefore does not upgrade
the agent in an existing volume; the runner self-updates from the service, so
this is normally a non-issue, but it is the reason an agent-version check reads
the volume's copy rather than the image's.

Verify before trusting the runner with a release lane — each gap costs a full
smoke run to rediscover, and none announces itself as a missing-dependency
error:

```bash
docker exec <container> bash -lc 'gh --version && just --version && brew --version'
docker exec <container> bash -lc 'readlink -f "$(command -v brew)"'  # must stay under /home/linuxbrew/
```

Do **not** keep a broken container around as a rollback: `cleanup-linux.sh`
runs `docker container prune` on every job completion, which removes *stopped*
containers, so a retained-but-stopped container is reaped by the next job that
finishes anywhere on the host.

## Restart discipline

**Never restart a runner mid-job.** Poll busy state first and only restart an
idle runner:

```bash
gh api repos/nevenincs/cadrumo/actions/runners \
  --jq '.runners[] | {name, busy}'
```

Restart a runner only when its `busy` is `false`. A restart of a busy runner
kills the in-flight job.

## Verifying the hook

After wiring, the next completed job appends a line to
`<work-root>/runner-hygiene.log`. Confirm the hook fired:

- Windows: `Get-Content C:\actions-runner\_work\runner-hygiene.log -Tail 5`
- Linux: `docker exec cadrumo-runner-linux-1 tail -5 /home/runner/_work/runner-hygiene.log`
- macOS: `ssh … tail -5 ~/actions-runner/_work/runner-hygiene.log`
