---
tags:
  - '#adr'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:dbd0098a74baaf13c60f4f1e9c97114e8fbf6542faeae187e4bc229daddad547'
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

- **A Rust provisioning engine in the application library, linked in-process by the desktop, which alone sets up the local AI, and exposed as a native `components` role of the one binary through which the Python CLI, TUI and MCP set up the browser and read every item.** Chosen.
- **Rust only inside the desktop host, Python keeping its own path for the CLI, TUI and MCP.** Rejected: two provisioners break the one-registry rule.
- **The Python CLI, TUI and MCP as full thin clients that also set up the local AI.** Rejected by the owner on 2026-10-26: no Python module may be able to download or install the local AI program or pull a model, even by starting the role.
- **Keep Python provisioning and move only the desktop relay to Rust.** Rejected: it does not meet the requirement.
- **For the local AI program: Rust runs winget or Homebrew, or the person installs it.** Rejected in favour of a pinned portable archive. That gives the same integrity, approval and recovery story as the browser, with no elevation and no package manager.
- **Keep the Playwright vendor installer, driven from Rust.** Rejected: it keeps the Node driver in the provisioning path and the loopback server whose only job is to feed it.

## Constraints

Accepted 2026-10-24. The principal proposed it on the recommended options when the owner's answers to the scope, Ollama and sequencing questions did not arrive; the owner then replied "all approved, implemnet", accepting this record, its amendments to prior rulings and both plans.

1. **Ownership.** `native/application` owns component provisioning: the item declarations, derived states, the plan and its digest, approval binding, network preflight, transfer, retry and resume, extraction, installation, quick and full checks, receipts, locks, cancellation, progress, and cleanup of superseded versions. No Python process downloads, installs, extracts, verifies, removes, or decides the state of a component. Neither Python nor cadrumo-agent can download or install the local AI program or pull, remove or select a model.
2. **Exposure.** The desktop host links the engine in process and is the only surface that sets up or removes the local AI. Only the desktop hands the engine the person's local model selection, through the engine's local AI admission; an engine without it serves the local AI read-only. The engine also runs as `cadrumo --role components <status|plan|setup|verify|cancel|remove>`, with a line-delimited JSON protocol carrying rows, the plan and its digest, phase, progress and notice events, and the result. It is the first role that hosts no interpreter. The role never admits local AI provisioning and takes no model on its command line: it reports and fully checks the local AI program, plans, sets up and removes only the browser, refuses a plan, setup or removal that names `local_ai` as an invalid request, and gives the local AI row the recovery `set_up_in_desktop` wherever a set-up, update, retry or resume would be offered. The Python CLI (`aeat config provision`, `aeat config check`), the TUI setup screen and the MCP service start this role and render its codes; they make no decision and hold no second state, and a Python request cannot name `local_ai` for a plan, setup or removal. Where no built `cadrumo` binary exists, as in a source checkout without a native build, every Python surface reads the item as blocked `not_in_this_build`.
3. **Unchanged contracts.** States and blocked reasons (unified-setup D2), the approval bound to a plan digest (D4), and the phase, progress and retry vocabulary and its limits (D5, D6) are kept. So are the closed failure categories (D9), the desktop experience (D10 as amended 2026-10-19), and hard requirements (D11). The item ids are `browser` and `local_ai`, and the recovery actions are `operator.provision.browser` and `operator.provision.local_ai`; every surface routes `operator.provision.local_ai` to the desktop. The `local_ai` item is the Ollama program plus the models the person selected for local roles; with no local selection it is the program alone.
4. **Wording.** The engine emits only closed codes and locale-neutral facts. Each surface words them from the canonical locale catalogues, in four languages and the informal singular. The desktop uses the `desktop.setup` subtree; the CLI, TUI and MCP use the provisioning subtree. This replaces the 2026-10-18 amendment's "operations carry their own words".
5. **Pins are data.** The browser archive pins (`src/cadrumo/_data/dependencies/browser_archives.toml`) and the local AI program pins (`src/cadrumo/_data/dependencies/local_ai_program.toml`) are declarative data staged into the package, which Rust reads at run time. The local AI pins cover the program archive per platform only. They carry no model name, digest, size or licence. Regenerating program pins stays a developer tool under `dev/`.
6. **Browser.** Rust fetches each pinned archive under the 2026-10-21 hop rules: HTTPS, declared and approved hosts, at most five redirects, pinned size and SHA-256. It extracts each archive into the build directory the bundled driver's `browsers.json` names and writes the driver's completion marker. Neither the vendor installer nor the loopback server runs. The full check is a headless launch by the Rust engine of the pinned executable, with its version compared against the pins. Python's launch guard (`src/cadrumo/adapters/outbound/aeat/browser/session.py:218-248`) reads the Rust-written component record, not its own probe.
7. **Local AI program.** Rust downloads Ollama's official standalone release archive for the platform, pinned by version, size and SHA-256, into `components/ollama/<version>`. The runtime manager runs the server with the existing models root and home (amendment 2026-10-24), and the engine has it stopped before replacing or removing a version. The managed server is the one the cadrumo-agent `ollama` provider connects to. This amends unified-setup D13 "a Cadrumo-owned model runtime". Cadrumo manages the program but does not build it, and it stays an external program under `2026-10-17-single-binary-process-tree-adr` constraint 7. A system-installed Ollama is detected and reported, never modified.
8. **Models.** Rust pulls each model the person selected for a local role, through the pull endpoint of the server the manager supervises, with byte progress. The names come from the desktop as role, model-name and catalogue `size_bytes` triples read from cadrumo-agent's per-role selection and catalogue. Integrity is Ollama's content-addressed manifest, and Cadrumo compares no digest to a pin. A model missing from Ollama's installed list is `absent` and a failed pull is `failed`; there is no digest-based `stale`. The full check is a one-token generation on that server. Role fitness is not component state.
9. **Hardware floor.** Rust decides `blocked hardware` from total memory and, on NVIDIA, VRAM, against the `size_bytes` of the selected model's catalogue entry. A computer with no selected local model is not blocked. No floor table carries model figures.
10. **Network.** Rust performs the 3 s-per-host preflight, the classification, and the `CADRUMO_PROXY_*` settings declared in `native/application-environment.toml`. The proxy address is treated as a credential and is never logged.
11. **Durability.** Each item has one writer lock under the storage root, an activity record that survives a crash, and the atomic receipt (`components/receipts`). A lock held by no live owner, beside an unfinished activity, reads `failed interrupted` and offers Resume. A receipt alone never yields `ready`.
12. **Removed Python.** The registered `dependencies.status`, `dependencies.setup` and `dependencies.verify` operations are deleted, and so are the provisioning actions (start, remove) of `local-reader.provision`. Their transfer, network, receipt, installer, archive-server, archive-fetch, package-manager and pull modules, and the Python item declarations, go with them. All callers move in the same change, with no aliases. `aeat config provision pull` is deleted. Python keeps no hardware or contention admission; cadrumo-agent admits each model load.
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
- The Python CLI, TUI and MCP gain a dependency on the built native binary for browser setup and for every status read. Setting up the local AI needs the desktop. A source checkout without a native build reads `not_in_this_build`, and developer recipes must build the application crate first.
- Setup leaves the profile runtime's operation journal. Durability rests on the engine's lock, activity record and receipt, which must be crash-tested on all three platforms.
- The local AI program archive is large (CUDA libraries on Windows and Linux). The plan size and free-space rule decide what the person approves.
- Upgrading Playwright or Ollama needs new pins, as the browser does today.
- Reconsider if Ollama stops publishing standalone archives, if Playwright's layout or marker contract changes beyond what pins can track, or if setup ever needs profile authority.

### Amendment 2026-10-24: the runtime manager hosts the local AI server

Basis: taken 2026-10-24 by the principal on the recommended option while the owner was away, within the owner's approval of the Rust provisioning work ("all approved, implemnet"); the owner may reverse it. The alternatives put to the owner were starting the server on first use through a native request to the manager, and running it only while the desktop window is open, which breaks CLI, TUI and MCP parity.

Constraint 7 says the engine starts and stops the server as its own child, but no Step named the long-lived process that hosts the engine for CLI, TUI and MCP use, and the withdrawal forbids Python and the runtime from starting the program. This amendment settles it:

- The runtime manager, the long-lived per-user Rust supervisor, hosts the engine's local AI server. It starts the server whenever the local AI program is installed and verified, restarts it after a crash under its supervision policy, and stops it on exit, at session end, and before the engine replaces or removes the program. The server process is contained by the manager so nothing outlives it.
- The server listens on one fixed Cadrumo loopback address, declared once in the canonical environment definition (`native/application-environment.toml`) and never the upstream default port, so it cannot collide with a system Ollama. The engine records the address in the local AI component record; Python consumers read that record and only connect. The default of `cadrumo_llm_ollama_chat_url` derives from the same declaration.
- The desktop host's in-process engine does not run a second server; it observes the manager's. Where no manager runs (a development checkout), the local AI reads `program_not_running` and consumers refuse with the local AI setup verdict.
- A system-installed Ollama is still detected and reported, never started, stopped or modified.

### Amendment 2026-10-25: models belong to cadrumo-agent

Basis: the owner's first-hand rulings of 2026-10-25 in conversation, recorded in `2026-10-25-agent-owned-models-adr`: Cadrumo defines no AI model names, digests, sizes, licences, defaults, candidate lists or rankings; cadrumo-agent's provider catalogue is the sole source of providers and models, local ones included; every tax model call goes through the agent service. Constraints 3, 5, 8, 9 and 12 state the result. The managed server of the 2026-10-24 amendment is the one the cadrumo-agent `ollama` provider connects to, on the address that amendment fixes.

### Amendment 2026-10-26: only the desktop provisions the local AI

Basis: the owner's first-hand ruling of 2026-10-26 in conversation: "CLI should NEVER ever EVER allow to prvision models; every llm capability must be routed through to cadrumo-agent", with the architecture "cadrumo binary native ollama and model privisioning", "neither cadrumo-agent, nor src/cadrumo* python modules should have any capability to pull, download, install ollama or models", "The actual downloads are gui siude operations handled entirely. All divergent and old superseeded code to be deleted." Constraints 1, 2, 3, 8 and 12 and the chosen option state the result. Parity of local AI setup across the CLI, TUI and MCP (unified-setup D8) does not apply to the local AI: those surfaces report it and route its recovery to the desktop. The browser keeps its setup on every surface.

### Amendment 2026-10-26: the desktop removes one local model, and a turned-off lane is not admitted

Basis: the owner's first-hand answers of 2026-10-26 in conversation, given while the Ollama provider settings were designed: per-model remove ("Add per-model remove"), the lane switch gates setup ("Yes, off gates setup"), and a model is downloaded by picking its role and then running setup ("Pick role, then set up"). The `2026-10-25-agent-owned-models-adr` amendment of the same date places the controls.

- **Constraint 2 (exposure).** The desktop host may also remove one named local model the person picked, beside removing the whole `local_ai` item. It is a desktop command over a new engine operation that runs under the `local_ai` writer lock. It deletes that model's manifest and only the layers no remaining manifest uses, and it keeps the program, the receipt and every other model. When any remaining manifest cannot be read, every layer stays. The `components` role and every Python surface still cannot remove a model.
- **Constraint 8 (models).** Removing a model does not change the selection. The desktop clears every role selection that names the model before it asks the engine to remove it, so the next setup does not pull it again.
- **Admission.** The desktop admits the engine only with the selections whose keyless lane is turned on. A lane the person turned off (`mode` `disabled`) hands the engine none of its models, so setup pulls nothing for it, and with no other local selection the `local_ai` item is the program alone.
