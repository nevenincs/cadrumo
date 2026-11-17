# CI control plane

Which workflow runs what, on which machines, and why. The contract tests under
`dev/ci/tests/` assert the shape described here; a change to one is a change
to both.

## Branches

`feature/tui` is the development branch. Every landing goes there, and a push
to it runs the merge gate over the full population on the landed head (every
landed head keeps its own run; a newer push neither cancels nor replaces it);
it starts no release workflow. `main` is the release
branch, reached only by a promotion pull request from `feature/tui`. Release
automation reads, proposes and tags `main` alone.

## Two lanes: headless and native

Testing is split by what a job needs, not by what it tests.

**The headless lane** (`merge-gate.yml`, "Cadrumo Merge Gate") needs a Linux
shell, Python and Node, and nothing else: no display, no compiler toolchain, no
secret, no repository variable. Every job runs on a GitHub-hosted
`ubuntu-24.04` runner, a fresh machine per job. It holds lint, the registry
authority, the security scan, the registry gate, import boundaries, the fixture
and persona check, the committed sequence goldens, the unit and integration
tests, the CI contracts and the verification harness.

**The native lane** (`native.yml`, "Cadrumo Native") holds everything that
needs a compiler toolchain, a desktop session or Windows: the desktop
frontend's checks and browser specs (they run through the CMake build
directory), the Rust tests, the Windows-only contracts and the native package
verification. Every job runs on a self-hosted runner.

Tests are separated by the markers `pyproject.toml` registers. The headless
selection excludes `windows_only`, `os_keychain`, `external_tool`,
`resident_service`, `private_ingest_corpus` and `perf`; the native lane's
recipes select what they need. A test that fails on a hosted runner because it
needs a window, a credential store or a native tool is missing one of those
markers: mark it, never skip it.

## Who may run what

The repository is public, so a pull request can come from anyone, and its run
executes that pull request's workflow file and code.

| | headless lane | native lane |
| --- | --- | --- |
| runner | GitHub-hosted, disposable | self-hosted, keeps state between jobs |
| pull request from a fork | runs, once a maintainer approves the run | starts no job |
| pull request from this repository | runs | runs for an owner, a collaborator or the `nevenincs-release` App |
| secrets and repository variables | none | the agent-source path variable only |
| token | read-only | read-only |
| decides a merge | yes | no |

A fork's code therefore never reaches a self-hosted machine. The admission
clause sits in each native job's `if:`, which a fork could delete from its own
copy of the file; what actually holds a fork back is the repository setting
that requires approval before any outside contributor's run starts. The clause
keeps an approved run of the headless lane from also starting the native one.

No workflow runs on `pull_request_target`. Every checkout drops its
credentials. A newer push to a pull request cancels the run it supersedes; a
push to `feature/tui` cancels nothing (see Concurrency below).

A hosted job's caches (uv downloads, npm) are restored and saved only when the
run is not a fork's, so nothing a fork ran outlives its job. A pull request can
read caches written by its own earlier runs and by its base branch. The merge
gate's run on each push to `feature/tui` writes the base branch's caches, so a
pull request's first run restores them.

## The merge gate, job by job

Triggered by a pull request into `feature/tui` or `main`, by a push to
`feature/tui` (full population on the landed head), and called by the release
proof. It is never dispatched by hand: a dispatched run attaches its
checks to no pull request.

| job | check name | needs | what it does |
| --- | --- | --- | --- |
| `plan` | Check: Change scope (Linux) | | reads the changed paths, plans the test shards |
| `lint` | Check: Lint (Linux) | | style, format, types, module size, year literals, actionlint, zizmor |
| `authority` | Build: Registry authority (Linux) | | publishes the registry authority once, uploads it |
| `checks` | Check: Security, registry and import boundaries (Linux) | authority | semgrep, registry gate, import linter |
| `fixtures` | Check: Fixtures and personas (Linux) | authority | validates the personas, produces the generated window projections a fresh runner lacks, runs every fixture producer check (`just fixtures-gate`) |
| `goldens` | Check: Committed sequence goldens (Linux) | plan, authority | replays the documented CLI sequences a change can alter |
| `tests` | Test: Scoped tests (Linux, shard i/n) | plan, authority | one shard of the selected tests, parallel then serial |
| `contracts` | Test: CI contracts (Linux) | plan, authority | the workflow, deployment and release contracts |
| `harness` | Test: Verification harness (Linux) | authority | the harness proofs, outside every worker pool |
| `verdict` | **Check: Merge gate (Linux)** | all of the above | fails unless every job succeeded |

`Check: Merge gate (Linux)` is the one required check on both branches. It
runs after a failure, a skip or a cancellation alike, so it is never the
skipped check GitHub would count as passing, and it runs no repository code.
No other job in the gate may be skipped or advisory.

**Scope.** For a pull request into `feature/tui`, `dev.ci.change_scope` maps
the changed paths to the test directories they can affect, and the plan deals
those test files into shards (`dev.ci.gate_shards`): about 900 files to a
shard, eight shards at most, largest files first onto the lightest shard. A
typical pull request is one shard. A promotion pull request into `main`, and a
call from the release proof, read no change list and run the full population
in eight shards.

**Concurrency.** A pull request's runs share one group and a newer event
cancels the older run. A push run's group ends in its own commit, so the runs
of two landed heads never share one, and within the gate nothing but a pull
request event cancels a run in progress; a run the release proof calls ends
early only when that proof is itself superseded. The commit is in the group,
not only `cancel-in-progress: false`, because a group holds one running and
one pending run: a third landing would replace the pending run of the second,
and trains land faster than a run finishes. The cost is that the gate applies
no back-pressure. Runs for successive heads overlap, each starts its own
seventeen jobs at eight shards, and when landings outpace the account's
hosted-runner allowance the jobs wait in GitHub's queue, so a head's verdict
can arrive well after its landing.

**Worker containment.** The runtime launches every profile worker as a
transient systemd user unit and refuses with `runtime_containment_unavailable`
when it cannot drive the user manager. A hosted job runs as `runner` outside a
login session, so it has no `user@<uid>.service` and no bus at
`/run/user/<uid>/bus`. The setup action's `worker-containment` input enables
lingering, starts the user manager, waits for the bus and runs one transient
user unit the way the runtime does (fixed tool path, cleared environment, no
`DBUS_SESSION_BUS_ADDRESS`); any of those failing fails the job at its first
step. `goldens`, `tests` and `harness` start the runtime and ask for it. A
hosted job that runs a `test-*` recipe must ask, unless the recipe is named in
`dev/ci/tests/test_worker_containment.py` as launching no worker. No
self-hosted job asks: lingering is a lasting change to a machine that keeps
state, and its own session holds its user manager.

**Failed sandbox logs.** A documented sequence that fails keeps its sandbox's
diagnostic log under `.tmp/failed-sandboxes`, and its transcript names a
refusal only by its reason; the log names the module, function and line. When
`goldens`, a `tests` shard or `harness` fails, it uploads
`.tmp/failed-sandboxes/**/logs/cadrumo.log` as
`cadrumo-failed-sandbox-logs-<job>` for three days, and nothing else from the
sandbox. That file is written through the product's redacting log filter, from
the committed synthetic profile, on a runner that holds no secret. No job reads
the artifact back.

**Speed.** The expected critical path for a pull request is `authority`
(toolchain, then compiling the registry) followed by the longest of `tests`,
`goldens`, `checks`, `fixtures`, `contracts` and `harness`, then `verdict`:
three job starts in sequence, everything else in parallel. The target is a
verdict within fifteen minutes. The shard size and ceiling in
`dev/ci/gate_shards.py` are working figures; correct them from real run times.

## The native lane, job by job

Triggered by a pull request that touches `native/`, the CMake project files,
this workflow or the setup action; by manual dispatch; and by the release
proof.

| job | check name | runner | runs for |
| --- | --- | --- | --- |
| `desktop` | Check: Frontend and Rust (Linux) | self-hosted Linux X64 | pull request, dispatch, release proof |
| `windows-contracts` | Test: Windows-only contracts (Windows) | self-hosted Windows X64 | dispatch, release proof |
| `native-package` | Test: Native package verification (Windows) | self-hosted Windows X64 | dispatch, release proof |

The Windows runner is a shared workstation, so its two jobs never run for a
pull request. On a pull request the lane is advisory. In the release proof
every job is required.

## Release

- **Release-please** (`release-please.yml`) is the only release workflow that
  runs on a push, and only on a push to `main` (plus manual dispatch from `main` for
  recovery; a dispatch from any other ref runs no job). It cuts tags and
  releases with the default token, opens or updates the release pull request
  with the `nevenincs-release` App's token, so that pull request's own events
  run the merge gate, and dispatches `release.yml`'s prove and publish phases.
  The release commit carries the `uv.lock` version bump itself, through
  release-please's `extra-files`, so the release branch has one head.
- **Release** (`release.yml`) is dispatched only by release-please.
  `phase=prove` runs against the release pull request's head: the headless
  merge gate over the full population, the native lane, the full suites on
  each supported interpreter, the conformance checks, the sealed release
  cohort build, and smoke tests across Linux, Windows and macOS plus Homebrew
  and Scoop acquisition. macOS is mandatory, not optional. `phase=publish`
  runs against the tag: PyPI via trusted publishing, then the Homebrew tap and
  Scoop bucket (`HOMEBREW_TAP_TOKEN`, `SCOOP_BUCKET_TOKEN`,
  `SCOOP_BUCKET_REPOSITORY`), then the documentation site.

Apart from the two lanes it calls, the release proof still runs on the
self-hosted fleet.

## Worker counts

Every pytest invocation a workflow reaches carries an explicit worker count,
never `-n auto`.

A hosted runner has four cores and one tenant, so the headless lane pins
`CADRUMO_PYTEST_WORKERS` to 4.

The self-hosted fleet is shared, not a cloud. Other runners and interactive
work share each host, so `-n auto` sizes as though the box were idle and
oversubscribes it. Cadrumo has one Linux X64 runner, which every self-hosted
Linux job shares, so job duration on it matters more than raw throughput. The
macOS runner is power-gated by policy, so its absence is not a fault.

| where | pin | reason |
| --- | --- | --- |
| headless lane | `-n 4` | The hosted runner's core count. |
| release proof pytest, self-hosted Linux and Windows | `-n 8` | A working pin, not a derivation. It leaves room for co-resident runners. |
| packaging lane pool, Linux | 3 | The lanes are venv- and disk-bound rather than CPU-wide. |
| packaging lane pool, Windows | 2 | Same reasoning, lower because Windows venv installs are slower. |
| homebrew acquisition matrix | `max-parallel: 2` | Two of its three legs share one host. |

Before changing a self-hosted pin, measure the host, not the repository.
`dev/ci/perf_measurement.py` stamps CPU, memory and process counts into a
failure. A timing taken while the machine is saturated says nothing about the
change that produced it.

## Repository settings this design relies on

- Rulesets on `feature/tui` and `main` require the check
  `Check: Merge gate (Linux)`.
- Fork pull request workflows require approval for all outside contributors.
- The allowed-actions list admits every action the workflows pin, including
  `actions/cache` (through `setup-uv` and `setup-node`) and
  `lukka/get-cmake`, which the native lane's desktop job uses.
- The workflow token's default permission is read-only.
- The repository variables `CADRUMO_PACKAGE_AGENT_SOURCE_DIR_LINUX` and
  `CADRUMO_PACKAGE_AGENT_SOURCE_DIR_WINDOWS` name the cadrumo-agent checkout on
  the Linux and the Windows self-hosted runner; one path cannot serve both
  machines. Each job passes its own as `CADRUMO_PACKAGE_AGENT_SOURCE_DIR`.
