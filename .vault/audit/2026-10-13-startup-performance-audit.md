---
tags:
  - '#audit'
  - '#startup-performance'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:601302d5ab555d6e290e5865f3c9bde4616190b291747d6216d958d6fc97d061'
related: []
---

# `startup-performance` audit: `Startup and sign-in performance audit`

On 2026-10-13 a local password sign-in measured about 37 s. Owner, first-hand: "I'd expect the singin to take about 1-2 seconds. AT most and sub second signings should be the norm… 60x times is not acceptable", "CLI should import instantaniously sub 250ms", "login should be instantanous", and "find everything in the codebase that is degrading the project". Every figure below was measured on 2026-10-13 on the owner's machine under concurrent session load; load inflates absolute values, not the ranking.

### packaged-bootstrap-verification | critical | Every packaged Python process verified the whole installation before running any code

In the packaged build, each Python process (CLI, runtime, every profile worker, every KDF child) spent 11–15 s at start listing 1,786 package directories to confirm 18,652 files; the manager and desktop also walked and hashed every file of an installed version when selecting it, and the manager again when starting the runtime. `python -I -S -c pass` on the stage took 7–12 s; verification alone 11 s. A sign-in chains several of these processes, so this alone accounts for most of the measured 37 s on the packaged path. Fixed by BUILD1 in 090a4b9c49: a process start reads only `data/build.json` to refuse a mixed build; launch selection checks identity, target, the presence of about ten start-up files and the manager executable's digest; runtime start checks the target only. Full verification remains at installation, repair, rollback and `python.exe --check-package`. Development-tree runs never paid this cost. Re-measure every other finding on a stage rebuilt after 090a4b9c49.

### import-bloat-kdf-child | critical | The password-derivation child imports the ledger application layer and the error catalogue for 37 ms of Argon2

Argon2id at the configured parameters takes 37 ms. Importing `cadrumo.adapters.persistence.storage.master_key.master_key_derivation` in a fresh process takes 3.1 s: `storage.errors` 1.8 s pulls `application.ledger.persistence_ports` 1.5 s, then `core.errors.hierarchy` 1.47 s and `core.errors.error_codes` 1.45 s; `argon2` 0.88 s cold. The child should import only argon2 and its framing. Owner: sign-in path agent.

### import-bloat-worker | critical | The profile worker imports 3,002 modules, the whole operation registry and the tax registry, before it can serve a sign-in

`import cadrumo.entrypoints.runtime.worker` takes 58.6 s cumulative: `worker_service` 42.5 s, `worker_operation_requests` 40.8 s, `operation_host` 40.7 s, `operation_composition` 22.6 s, `application.auth.operation_definitions` 10.6 s, `domain.calculations.registry.authority` 9.9 s, `registry.schema` 8.0 s, `adapters.local_runtime.framing` 6.1 s. A sign-in starts this worker cold (`src/cadrumo/adapters/local_runtime/profile_worker.py:118-140`, `worker_arguments.py:10`). Operations must load on first use. Owner: worker loading agent.

### import-time-work | high | Modules build catalogues and tables at import time

Highest self import times in the worker: `core.errors.error_codes` 458 ms, `application.ledger.establishment_ladder` 396 ms, `domain.deadlines.models` 272 ms, `application.provider_settings.resolution` 239 ms (new 2026-10-13), `domain.calculations.registry.applicability` 210 ms, `application.filing.export_envelope` 206 ms, `registry.identifier_evolutions` 204 ms, `application.runtime.profile_worker` 180 ms, `registry.renta_codes_catalogue` 163 ms, `contribuyente.renta_codes` 163 ms, `domain.provider_settings.catalog` 156 ms. Construction belongs at first use, completeness checks in tests. Owners: CLI agent for core errors, i18n and logging; worker agent for the rest.

### import-bloat-cli | critical | `aeat` takes 6.8 s to import against a 250 ms target

`import cadrumo.entrypoints.cli.main`: `cli._command_runtime` 1.35 s, `typer` 1.14 s, `core.errors.hierarchy` 1.02 s, `core.i18n.render` 0.95 s, `core.logging` 0.51 s. Command handlers must load when their command runs. Owner: CLI agent.

### widened-deadlines | high | Deadlines were widened to make slow paths pass instead of fixing them

Commit d18c855730 (this session's) and neighbours raised: the KDF operation deadline 15 to 60 s (`src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py:74`); the worker human-proof timeout 30 to 90 s (`src/cadrumo/adapters/local_runtime/worker_admission_budget.py:10-11`); `PROFILE_ADMISSION_TIMEOUT_SECONDS` 75 to 120 s (`src/cadrumo/application/runtime/profile_access.py:84`); a 120 s exchange cap (`src/cadrumo/application/runtime/deadline_budget.py:16,55,71`) with client defaults raised from 5–75 s to 120 s across `frontend_client.py`, `enrollment_client.py` and `runtime_client.py:60`; secret delivery 20 to 120 s; MCP `_TIMEOUT` 30 to 120 s (`src/cadrumo_harness/mcp/admitted_operations.py:66`) and contract reads 10 to 120 s; TUI contract reads 30 and 10 to 120 s; `automation_requester.py:124` 10 to 120 s (edc9ff769b); a 300 s view-read budget (`src/cadrumo/entrypoints/cli/config/_runtime_profile_mutation.py:30`); test deadlines raised to match. These hid the defects above. Each is to be restored once the structural fixes land, then tightened to the fixed cost.

### polling-on-request-paths | medium | Request paths poll instead of waiting on events

CLI operation settlement backs off to 0.5 s between observations (`src/cadrumo/entrypoints/cli/registered_operation_deadlines.py:16,19`, `registered_operation_observations.py:131-165`), so a result can be seen up to 0.5 s late. The runtime polls the worker's startup channel in 0.1 s slices (`profile_worker.py:180-210`). The MCP attendance wait polls every 0.25 s (`src/cadrumo_harness/mcp/runtime_admission.py:178,199`); enrollment waits poll up to 5 s (`src/cadrumo/application/runtime/enrollment_recipient.py:31,234`); several CLI commands sleep 20 ms per turn. Request paths should block on the channel that carries the answer.

### entry-process-inventory | high | Every entry process measured, with module counts

Fresh-process imports under load (`-X importtime`): `aeat` CLI 388 modules, 9.0 s; TUI launcher (`cadrumo.entrypoints.tui.launcher`) 232 modules, 7.3 s; `cadrumo-mcp` 126 modules, 3.8 s; `cadrumo-runtime` bootstrap 80 modules, 0.7 s; profile worker 3,001 modules, 49.9–56.6 s; KDF child (`cadrumo.adapters.persistence.storage.custody._kdf_worker`, launched from `src/cadrumo/adapters/persistence/storage/custody/_kdf_process.py`) 171 modules, 2.4 s. `core.errors.error_codes` has the highest self time in the CLI (1.77 s), the TUI (1.01 s) and the worker (1.14 s). The worker also loads extraction composition at start: `invoice_draft_extraction_ports` 945 ms self. The interpreter alone takes 1.2–2.4 s here.

### filesystem-latency | high | File metadata calls cost about 300 times their normal latency on this machine

`os.stat` on stdlib files: 5.8 ms each (normal about 0.02 ms); reading a small file 4.6 ms; a bare `python -c pass` 1.4–1.8 s (normal 30–50 ms); a pure CPU loop about 3 times slower than normal. Defender real-time and on-access protection are on and tamper-protected; `<code-root>` and the interpreter's scoop path are excluded yet stats there remain slow, so the exclusion is ineffective for this pattern or another filter or disk-queue saturation is responsible. Installed copies run from a path with no exclusion, so the product must open few files at start: ship compiled bytecode, keep start-up imports small. Owner: BUILD1 (process launch, bytecode, storage, file access).

### host-cpu-outside-cadrumo | high | About 17 of 24 cores were busy before any Cadrumo work

Measured by BUILD1 over 10 s: `vmmemWSL` (a WSL VM) 3 cores continuously; `explorer.exe` 0.86 cores with 408 CPU-hours since 2026-09-23, which looks like a runaway shell; `WmiPrvSE` 0.8 cores, fed partly by agents' WMI monitoring queries; `MsMpEng` 0.6 cores with 182 CPU-hours. CPU saturation multiplies the filter-stack cost of every file open (0.84 ms per `os.stat` on an excluded path at rest, 5.8 ms under load; the filter stack on Y: is UCPD, WdFilter, bfs and aksdf, a Sentinel/HASP licence filter; disks idle at 5–12%). These are host conditions for the owner, not product defects; the product consequence is to open as few files per start as possible.

### dev-bytecode-under-B | low | `-B` makes development worker and KDF starts recompile edited modules every time

`-I -B` on worker and KDF child launches (`src/cadrumo/adapters/local_runtime/worker_arguments.py:10`, `profile_worker.py:133`) costs nothing in the packaged build, which ships compiled bytecode, but in a development tree any module newer than its bytecode is recompiled in memory on every start and never written back. The import restructuring shrinks it; the development launch could drop `-B`.

### agent-test-processes | low | Concurrent test lanes saturate the machine

Around 240 Python processes were running: about 241 vaultspec MCP servers (8.8 GB RAM, about 0.6 cores) and several `pytest -n 4` lanes, which carry the CPU load. Measurements should be repeated with test lanes idle.

## Recommendations

- Restore the widened deadlines after the structural fixes, in one reviewed change, and tighten each to the measured cost.
- Add deterministic import gates (module allow-lists, not wall time) for every entry process: CLI, TUI, MCP harness, runtime, worker, KDF child.
- Replace polling on request paths with blocking waits on the answering channel.
- A follow-on ADR should fix a start-up budget per entry process and the bytecode and packaging policy that meets it without antivirus exclusions.

### progress-2026-10-13 | info | Fixes landed so far, uncommitted unless noted

- Packaged bootstrap verification removed from every start (BUILD1, 090a4b9c49, pushed).
- KDF child: the base interpreter with `-S` replaces the venv launcher hop; the parent no longer rebuilds the child environment twice (400 stats each); argparse, pathlib and ctypes are off the child's path; one attested child is prewarmed and each derivation still gets a fresh child. The KDF child alone went from a 12.1 s median to 2.3 s; a warm password exchange from 2.0–3.6 s to 0.65 s. The KDF operation deadline is restored from 60 s to 15 s. Gate: `custody/tests/test_kdf_worker_import_graph.py`.
- Profile worker: from about 3,000 modules to about 660 at start; registry composition moved after the sign-in reply. Gate: `entrypoints/runtime/tests/test_worker_startup_import_graph.py`. Regression found: a second password sign-in on a warm worker times out in `bind_human` while the background composition runs; being fixed.
- Open: Home's first screen still composes every operation contract (about 22 s loaded), addressed by a generated operation-contract manifest; the tax authority still loads on profile read (about 1.5 s); `RuntimeAccessRefusal` lives in a hub module (0.85 s); the `argon2` package import (about 45% of the child's import time) could be replaced by the bindings directly.
