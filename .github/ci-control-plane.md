# CI control plane

Why the workflows pin explicit worker counts instead of letting tooling choose.

Workflow comments across the three lanes cite this file as the authority for
their `-n 8` and lane-concurrency numbers, so the next person tuning a pin
reads a measurement rather than re-deriving one.

## The three lanes

- **Merge gate** (`merge-gate.yml`) is the only pull request workflow. It runs
  two Linux jobs, lint then gate (security scan, registry gate, import
  boundaries, scoped tests); the required check is
  `Check: Merge gate (Linux)`.
- **Release** (`release.yml`) is dispatched only by release-please, using the
  default `GITHUB_TOKEN`. `phase=prove` runs against the release pull request's
  head: the merge gate's full scan, the full test suites, conformance checks, the
  sealed release cohort build, and smoke tests across Linux, Windows, and
  macOS plus Homebrew and Scoop acquisition — macOS is mandatory, not
  optional. `phase=publish` runs against the tag: PyPI via trusted
  publishing, then the Homebrew tap and Scoop bucket
  (`HOMEBREW_TAP_TOKEN`, `SCOOP_BUCKET_TOKEN`, `SCOOP_BUCKET_REPOSITORY`),
  then the documentation site.
- **Release-please** (`release-please.yml`) is the only workflow that runs on
  a push to main (plus manual dispatch for recovery). It opens or updates the
  release pull request and dispatches `release.yml`'s prove and publish
  phases. It also dispatches the merge gate itself, as its last release-branch
  step: refs and pull requests written with the default token start no workflow
  runs, so the release pull request would otherwise never report the one check
  main requires. A dispatch is exempt from that rule, and running it last means
  it validates the lockfile commit pushed above it.

## The runners are shared, not a cloud

Every job runs on a small self-hosted fleet. Two consequences the pins exist
for:

**The host's CPUs are not cadrumo's alone.** Other runners and interactive work
share the machine, so `-n auto` sizes as though the box were idle and
oversubscribes it. Most of the interpreters measured on the host during queued
cadrumo runs belonged to other tenants.

**cadrumo has ONE Linux X64 runner.** Every self-hosted Linux job across the
three lanes above shares it. Anything that holds it blocks everything else on
it, which is why job duration on that lane matters more than raw throughput.
The macOS runner is power-gated by policy, so its absence is not a fault.

## The pins

| where | pin | reason |
| --- | --- | --- |
| preflight pytest, Linux and Windows lanes | `-n 8` | A working pin, NOT a derivation. It leaves room for co-resident runners. Nobody has measured the optimum. |
| packaging lane pool, Linux | 3 | The lanes are venv- and disk-bound rather than CPU-wide, so more parallelism buys little and costs disk contention. |
| packaging lane pool, Windows | 2 | Same reasoning, lower because Windows venv installs are slower and the box carries co-resident jobs. |
| homebrew acquisition matrix | `max-parallel: 2` | Two of its three legs share one host. |

`-n auto` is never correct here and no workflow should reintroduce it.

## Before changing a pin

Measure the host, not the repository. `dev/ci/perf_measurement.py` stamps CPU,
memory and process counts into a failure, and it is the only reason a wedged
test can be told from a broken one on a box carrying other tenants. A timing
result taken while the machine is saturated says nothing about the change that
produced it.
