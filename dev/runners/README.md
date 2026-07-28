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

| Role                    | Labels                       | Platform | Location                                  | Script               |
| ----------------------- | ---------------------------- | -------- | ----------------------------------------- | -------------------- |
| Windows build host      | `self-hosted, Windows, X64`  | Windows  | `C:\actions-runner`                       | `cleanup-windows.ps1`|
| Linux container runner  | `self-hosted, Linux, X64`    | Linux    | docker container `cadrumo-runner-linux`   | `cleanup-linux.sh`   |
| Linux container runner 2| `self-hosted, Linux, X64`    | Linux    | docker container `cadrumo-runner-linux-2` | `cleanup-linux.sh`   |
| macOS build host        | `self-hosted, macOS, ARM64`  | macOS    | `~/actions-runner`                        | `cleanup-macos.sh`   |
| Linux ARM container     | `self-hosted, Linux, ARM64`  | Linux    | colima container `cadrumo-runner-mac-arm` | `cleanup-linux.sh`   |

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

### Linux docker runners (`cadrumo-runner-linux`, `-2`)

The in-container runner root is `/home/runner` (that is where `config.sh`,
`.runner`, `.env`, and `_work` live). Copy the script there and append the hook
var to `.env`, then restart the container **one at a time** — never both down
simultaneously, CI/smoke depend on the pair (the runner auto-resumes on
restart, which re-reads `.env`):

```bash
for c in cadrumo-runner-linux cadrumo-runner-linux-2; do
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

## Linux container provisioning (`runner-entry-linux.sh`)

The two Linux runners are containers built from the stock
`ghcr.io/actions/actions-runner` image, so everything that makes them *these*
runners lives outside the image. Two rules follow, and both were learned by
outage rather than by design.

**The entrypoint belongs in the runner's own state volume, never on a host
path.** `runner-entry-linux.sh` is copied to `/home/runner/entry.sh` inside the
`cadrumo-runner-state-<n>` volume and the container is created with
`--entrypoint /home/runner/entry.sh`. A container whose entrypoint is
bind-mounted from a scratch or temp directory dies the moment that directory is
cleaned up: Docker recreates the missing bind source as an empty **directory**,
exec fails, and the container exits **127** and stays down *even with*
`--restart always`. The tell is a mount whose source is a temp path, which
`Test-Path` reports as existing while reading it errors with "is a directory".

**Tools the image does not ship belong in the volume too**, under
`/home/runner/tools/bin`, which the entrypoint prepends to `PATH`. The image
carries `jq`, `git`, `curl`, `tar` and the docker client; it does **not** carry
`gh`. Workflows install `just` and `uv` themselves through actions, but nothing
installs `gh` — it is assumed present, as it is on GitHub-hosted runners. When
it is absent, `dev.release.version_identity` fails its forge check with
`REFUSED: forge check needs the gh CLI on PATH`, which surfaces mid-release as a
cohort-seal failure rather than as a missing-tool error. Installing into the
volume rather than the container's writable layer is the whole point: a
recreated container keeps the tools.

Recreate a Linux runner like this (the volume already holds `config.sh`,
`run.sh`, `.runner`, `.credentials`, and `.env`, so it does **not** re-register):

```bash
docker create --name cadrumo-runner-linux-2 --restart always \
  --user runner -w /home/runner \
  -v cadrumo-runner-state-2:/home/runner \
  -v /run/host-services/docker.proxy.sock:/var/run/docker.sock \
  -e RUNNER_MANUALLY_TRAP_SIG=1 -e ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=1 \
  --entrypoint /home/runner/entry.sh ghcr.io/actions/actions-runner:latest
```

Verify with `docker exec <container> bash -lc 'command -v gh && gh --version'`
before trusting the runner with a release lane.

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
- Linux: `docker exec cadrumo-runner-linux tail -5 /home/runner/_work/runner-hygiene.log`
- macOS: `ssh … tail -5 ~/actions-runner/_work/runner-hygiene.log`
