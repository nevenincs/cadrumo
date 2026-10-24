---
tags:
  - '#adr'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:03950a5c9dcd226d2eee0aaf0c94c6c78a1c26d5896cb7809d782dec786b23b1'
related:
  - "[[2026-10-24-rust-component-provisioning-reference]]"
  - "[[2026-10-18-dependency-provisioning-unified-setup-adr]]"
  - "[[2026-10-17-single-binary-process-tree-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-10-13-application-distribution-native-bundle-llm-extra-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
---

# `rust-component-provisioning` adr: `Rust owns component provisioning` | (**status:** `accepted`)

## Problem Statement

The owner's requirement, 2026-10-24: "Verify and ensure that product component provisioning is entirely rust managed without any python involved." The application must be on demand: when the person calls a feature that needs a provisioned component, every surface must say so. Two components exist today: the Playwright Chromium builds and the local AI, which is the program plus the model for each role.

`2026-10-24-rust-component-provisioning-reference` shows the opposite. Every download, install, check and readiness decision runs in Python under the registered `dependencies.setup` operation, which `2026-10-18-dependency-provisioning-unified-setup-adr` D1 and D3 place in `src/cadrumo/application`. The desktop only relays it. That accepted ruling has to change before code can move.

## Considerations

- Components are installation-wide public artifacts outside encrypted custody (unified-setup ADR D12). Acquiring them needs the storage root, not profile authority, so it does not have to run inside the profile runtime.
- Rust already has a bounded, locked, receipt-keeping component store with no caller (`native/application/src/component.rs`). It also has a native runtime client and operation relay (`native/application/src/runtime_client.rs`, `person_operations.rs`). The single binary selects roles by `--role` (`native/application/src/role.rs`).
- Python stays the consumer. Playwright launches Chromium for the tax agency reads, and the readers call Ollama over loopback HTTP. The layout each consumer expects is the interface Rust must produce (reference, "Interfaces a Rust provisioner must honour").
- Parity across CLI, TUI, MCP and the desktop is an accepted ruling (unified-setup D8, `2026-10-11-mcp-parity-full-parity-adr`), so a desktop-only engine is not enough.
- The Ollama install path uses winget or Homebrew. It pins nothing, may ask for elevation, and has no Linux path (`src/cadrumo/adapters/outbound/model_runtime/process_control.py:79-110`).
- The browser path runs the vendor's Node installer behind a loopback server only to get its extraction and completion marker (unified-setup ADR, 2026-10-21 amendment). The bytes are already fetched and pin-checked by Cadrumo.

## Considered options

- **A Rust provisioning engine in the application library, exposed as a native `components` role of the one binary, linked in-process by the desktop, with the Python CLI, TUI and MCP as thin clients of that role.** Chosen.
- **Rust only inside the desktop host, Python keeping its own path for the CLI, TUI and MCP.** Rejected: two provisioners break the one-registry rule and parity.
- **Native surfaces only; the Python CLI, TUI and MCP lose setup.** Rejected: it breaks parity for no gain, because a thin client adds no Python decision.
- **Keep Python provisioning and move only the desktop relay to Rust.** Rejected: it does not meet the requirement.
- **For the local AI program: Rust runs winget or Homebrew, or the person installs it.** Rejected in favour of a pinned portable archive. That gives the same integrity, approval and recovery story as the browser, with no elevation and no package manager.
- **Keep the Playwright vendor installer, driven from Rust.** Rejected: it keeps the Node driver in the provisioning path and the loopback server whose only job is to feed it.

## Constraints

Accepted 2026-10-24. The principal proposed it on the recommended options when the owner's answers to the scope, Ollama and sequencing questions did not arrive; the owner then replied "all approved, implemnet", accepting this record, its amendments to prior rulings and both plans.

1. **Ownership.** `native/application` owns component provisioning: the item declarations, derived states, the plan and its digest, approval binding, network preflight, transfer, retry and resume, extraction, installation, quick and full checks, receipts, locks, cancellation, progress, and cleanup of superseded versions. No Python process downloads, installs, extracts, verifies, removes, or decides the state of a component.
2. **Exposure.** The engine runs as `cadrumo --role components <status|plan|setup|verify|cancel|remove>`, with a line-delimited JSON protocol. The protocol carries rows, the plan and its digest, phase, progress and notice events, and the result. It is the first role that hosts no interpreter. The desktop host calls the same library in process. The Python CLI (`aeat config provision`, `aeat config check`), the TUI setup screen and the MCP service start this role and render its codes. They make no decision and hold no second state. Where no built `cadrumo` binary exists, as in a source checkout without a native build, every Python surface reads the item as blocked `not_in_this_build`.
3. **Unchanged contracts.** States and blocked reasons (unified-setup D2), the approval bound to a plan digest (D4), and the phase, progress and retry vocabulary and its limits (D5, D6) are kept. So are the closed failure categories (D9), the desktop experience (D10 as amended 2026-10-19), and hard requirements (D11). The item ids are `browser` and `local_ai`, and the recovery actions are `operator.provision.browser` and `operator.provision.local_ai`. A setup the person approved on any surface is the same act.
4. **Wording.** The engine emits only closed codes and locale-neutral facts. Each surface words them from the canonical locale catalogues, in four languages and the informal singular. The desktop uses the `desktop.setup` subtree; the CLI, TUI and MCP use the provisioning subtree. This replaces the 2026-10-18 amendment's "operations carry their own words".
5. **Pins are data.** The browser archive pins (`src/cadrumo/_data/dependencies/browser_archives.toml`) and new pins for the local AI move to declarative data staged into the package. The local AI pins cover the program archive per platform plus each role's model, with its manifest digest, size and licence. Rust reads that data at run time. Python reads the same file for role defaults at consumption, so `src/cadrumo/core/model_catalogue.py` loses its own pin copy. Regenerating pins stays a developer tool under `dev/`.
6. **Browser.** Rust fetches each pinned archive under the 2026-10-21 hop rules: HTTPS, declared and approved hosts, at most five redirects, pinned size and SHA-256. It extracts each archive into the build directory the bundled driver's `browsers.json` names and writes the driver's completion marker. Neither the vendor installer nor the loopback server runs. The full check is a headless launch by the Rust engine of the pinned executable, with its version compared against the pins. Python's launch guard (`src/cadrumo/adapters/outbound/aeat/browser/session.py:218-248`) reads the Rust-written component record, not its own probe.
7. **Local AI program.** Rust downloads Ollama's official standalone release archive for the platform, pinned by version, size and SHA-256, into `components/ollama/<version>`. It starts and stops the server as a child of the Rust engine with the existing models root and home, and it stops a server it started before replacing or removing a version. This amends unified-setup D13 "a Cadrumo-owned model runtime". Cadrumo manages the program but does not build it, and it stays an external program under `2026-10-17-single-binary-process-tree-adr` constraint 7. A system-installed Ollama is detected and reported, never modified.
8. **Models.** Rust pulls each role's model through the server's pull endpoint on the server it started, with byte progress. It then compares the installed manifest digest with the pin. A different digest is `stale`; a missing model or failed pull is `failed` or `absent`. The full check is a one-token generation on that server. Role fitness, meaning answer quality for a role, becomes a consumer admission check in Python. It is not part of component state.
9. **Hardware floor.** Rust decides `blocked hardware` from total memory and, on NVIDIA, VRAM, using the floors carried in the local AI pins.
10. **Network.** Rust performs the 3 s-per-host preflight, the classification, and the `CADRUMO_PROXY_*` settings declared in `native/application-environment.toml`. The proxy address is treated as a credential and is never logged.
11. **Durability.** Each item has one writer lock under the storage root, an activity record that survives a crash, and the atomic receipt (`components/receipts`). A lock held by no live owner, beside an unfinished activity, reads `failed interrupted` and offers Resume. A receipt alone never yields `ready`.
12. **Removed Python.** The registered `dependencies.status`, `dependencies.setup` and `dependencies.verify` operations are deleted, and so are the provisioning actions (start, remove) of `local-reader.provision`. Their transfer, network, receipt, installer, archive-server, archive-fetch, package-manager and pull modules, and the Python item declarations, go with them. All callers move in the same change, with no aliases. Load, unload and the fitness probe stay in Python as consumption.
13. **On demand.** Every consumer checks its component before its first effect. A missing, stale, failed or blocked component refuses with a typed verdict that names `operator.provision.<item>`, and every surface routes that verdict to its setup flow. This commitment is already in unified-setup D10. The consumer fixes land under that ruling and do not wait for this record.

Affected prior rulings, amended in place on acceptance 2026-10-24:

- `2026-10-18-dependency-provisioning-unified-setup-adr`: D1 (registry home), D3 (registered operations), D5 delivery (the journal cue is replaced by the role's event stream), D7 (fitness leaves component state), D12 (program location), D13 (runtime bullet), the 2026-10-18 wording amendment, and the 2026-10-21 installer and loopback bullets. Each one points here.
- `2026-10-13-application-distribution-native-bundle-llm-extra-adr`: "provisioned on demand into profile storage ... through the existing browser provisioning probe and install path" becomes the installation-wide storage root through the Rust engine. The `[browser]` extra still ships, because Playwright's Python package and driver launch the browser at use time.
- `2026-10-17-single-binary-process-tree-adr`: the roles list gains `components`, the first role without an interpreter.
- `2026-10-04-desktop-shell-adr`: setup uses the in-process engine, not the person-bridge relay.

## Implementation

We will extend `native/application` with a provisioning module built on `component.rs`, add the `components` role to the single binary, point the desktop setup host at it in process, make the Python surfaces thin clients of the role, and delete the Python provisioning path. The sequence is in `2026-10-24-rust-component-provisioning-plan`. The consumer on-demand fixes run first and separately in `2026-10-24-component-on-demand-plan`.

Hypotheses, free to change within the constraints:

- The protocol's exact message shapes.
- Whether the in-process desktop engine runs on a Tokio task or a thread.
- The Ollama archive formats per platform. Linux and macOS may need `tar` with `flate2` or `zstd`; adding those crates goes through cargo-deny.
- The exact completion-marker set the bundled driver checks. It is to be read from the driver's registry code before implementation.
- Whether the activity record shares the receipt's folder.
- Whether the MCP service exposes setup as one tool with a review or as a plan tool and a setup tool bound by digest.

## Rationale

Components need no profile authority, so the profile runtime's operation journal adds a Python hop without adding a guarantee. The Rust store already provides the hard parts: locking, staging, bounded extraction, receipts and cutover. Running the engine as a role of the one binary gives every surface the same decisions with no second state. That satisfies "no Python" and parity together. Pinning the Ollama archive gives the local AI the integrity and approval guarantees the browser already has. Dropping the vendor installer removes the Node driver and the loopback server from a path whose bytes Cadrumo already verifies.

## Consequences

- Provisioning no longer depends on a running profile runtime or a signed-in session. Status and setup work before sign-in, if the window chooses to offer them there.
- The Python CLI, TUI and MCP gain a dependency on the built native binary for setup. A source checkout without a native build reads `not_in_this_build`, and developer recipes must build the application crate first.
- Setup leaves the profile runtime's operation journal. Durability rests on the engine's lock, activity record and receipt, which must be crash-tested on all three platforms.
- The local AI program archive is large (CUDA libraries on Windows and Linux). The plan size and free-space rule decide what the person approves.
- Upgrading Playwright or Ollama needs new pins, as the browser does today.
- Reconsider if Ollama stops publishing standalone archives, if Playwright's layout or marker contract changes beyond what pins can track, or if setup ever needs profile authority.
