# CI control plane

Why the workflows pin explicit worker counts instead of letting tooling choose.

Twelve workflow comments cite this file as the authority for their `-n 8` and
lane-concurrency numbers. It did not exist, so every "why 8" pointed at
nothing. This is that answer, in one place, so the next person tuning a pin
reads a measurement rather than re-deriving one.

## The hardware is two machines, not a cloud

Every self-hosted runner in the `nevenincs` fleet lives on one of two hosts.
`ci-fleet` is the binding declaration; this file only explains what follows for
cadrumo's workflows.

Hosts are named by role here, not by hostname: `ci-fleet` is where machine
identity is declared, and what this file needs from a host is its shape.

| role | shape | notes |
| --- | --- | --- |
| the Windows workstation | 12 physical / 24 logical cores, 128 GB | Windows, plus WSL and Docker Desktop. Carries cadrumo's Windows runner AND its Linux X64 container. |
| the macOS laptop | 6-core laptop | Power-gated by deliberate policy: its runners serve on AC, and clamshell sleep takes them away. Not a fault. |

Two consequences the pins exist for:

**The 24 logical CPUs are not cadrumo's.** That host also runs runners for
`vaultspec-core`, `vaultspec-rag`, and the vaultspec dashboard, plus the
operator's own work. `-n auto` reads 24 and sizes as though the box were idle.
Measured on 2026-09-07 while three cadrumo workflows were queued: 148 running
Python interpreters, of which only 56 belonged to cadrumo; the rest were other
tooling, with a median age of 40 hours and one process resident for 142.

**cadrumo has ONE Linux X64 runner.** `fleetctl audit` resolves that selector
to a single runner serving 27 job declarations across 12 workflows. Anything
that holds it blocks everything else on it, which is why job duration on that
lane matters more than raw throughput.

## The pins

| where | pin | reason |
| --- | --- | --- |
| preflight pytest, Linux and Windows lanes | `-n 8` | A working pin, NOT a derivation. Eight of 24 logical CPUs leaves room for co-resident runners. Nobody has measured the optimum. |
| packaging lane pool, Linux | 3 | The lanes are venv- and disk-bound rather than CPU-wide, so more parallelism buys little and costs disk contention. |
| packaging lane pool, Windows | 2 | Same reasoning, lower because Windows venv installs are slower and the box carries co-resident jobs. |
| homebrew acquisition matrix | `max-parallel: 2` | Two of its three legs live on the one MacBook. |
| `MAX_WATCH_SECONDS` | 480 | Derived, unlike the others. See below. |

`-n auto` is never correct here and no workflow should reintroduce it.

## The one derived number

The queue watchdog's window is the only pin with an argument rather than a
working guess. A verdict requires `waited > THRESHOLD_SECONDS` (300) and must
then hold across `UNSCHEDULABLE_CONFIRMATIONS` (2) consecutive polls of
`POLL_SECONDS` (15), so nothing can fire before 330 seconds, and the verdict
path runs before the window check. 480 leaves ten polls of headroom.

It was 900 while a watched job could be created after the window closed.
`test_the_watchdog_is_created_no_later_than_the_lanes_it_watches` now forces
the watchdog to share the `needs:` of every off-lane job it watches, so they
are co-created and the long tail bought nothing — while the watchdog held the
single Linux runner for the difference. Two were measured burning 15m32 and
15m23 on one push.

## Before changing a pin

Measure the host, not the repository. `dev/ci/perf_measurement.py` stamps CPU,
memory and process counts into a failure, and it is the only reason a wedged
test can be told from a broken one on a box carrying other tenants. A timing
result taken while the machine is saturated says nothing about the change that
produced it.
