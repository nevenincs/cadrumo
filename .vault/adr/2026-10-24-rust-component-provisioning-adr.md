---
tags:
  - '#adr'
  - '#rust-component-provisioning'
date: '2026-10-24'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:ee584b2c54a84add0abee32451f4e14d7cbd9240119349ea6c10f57211fad1a4'
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

The owner's requirement, 2026-10-24: "Verify and ensure that product component provisioning is entirely rust managed without any python involved." The application must be on demand: when the person calls a feature that needs a provisioned component, the desktop must say so. Two components exist: the Playwright Chromium builds and the local AI, which is the program plus the models the person downloads for it.

`2026-10-24-rust-component-provisioning-reference` records the interfaces a native provisioner must honour: the layout Playwright expects for its browser builds and the address and home the local model program serves from.

## Considerations

- Components are installation-wide public artifacts outside encrypted custody (`2026-10-18-dependency-provisioning-unified-setup-adr` D12). The engine uses the storage root, not profile custody, and needs no signed-in profile.
- Rust already has a bounded, locked, receipt-keeping component store (`native/application/src/component.rs`).
- Consumers use the result. Playwright launches Chromium for the tax agency reads, and the model reads go to the managed Ollama server through the cadrumo-agent `ollama` provider. The layout each consumer expects is the interface the engine must produce (reference, "Interfaces a Rust provisioner must honour").
- A system install of the Ollama program through winget or Homebrew pins nothing, may ask for elevation, and has no Linux path.
- The vendor's Node installer only provides extraction and a completion marker for the browser; the bytes are already fetched and pin-checked by Cadrumo.

## Considered options

- **A Rust provisioning engine in the application library, linked in process by the desktop host, which sets up, checks and removes every component.** Chosen.
- **For the local AI program: Rust runs winget or Homebrew, or the person installs it.** Rejected in favour of a pinned portable archive. That gives the same integrity, approval and recovery story as the browser, with no elevation and no package manager.
- **Keep the Playwright vendor installer, driven from Rust.** Rejected: it keeps the Node driver in the provisioning path and the loopback server whose only job is to feed it.

## Constraints

Accepted 2026-10-24: the owner replied "all approved, implemnet", accepting this record and its plans.

1. **Ownership.** `native/application` owns component provisioning: the item declarations, derived states, the plan and its digest, approval binding, network preflight, transfer, retry and resume, extraction, installation, quick and full checks, receipts, locks, cancellation, progress, and cleanup of superseded versions. The engine is the sole owner of component state and effects. cadrumo-agent does not download or install the local AI program or pull or remove a model.
2. **Exposure.** The desktop host links the engine in process and calls it for status, plan, setup, verify, cancel and remove. It is the only caller that hands the engine a local model, through the engine's `admit_local_ai` admission, and only for a download the person started from the local model list; an engine without that admission serves the local AI read-only. The host may also remove one named local model, beside removing the whole `local_ai` item: an engine operation that runs under the `local_ai` writer lock, deletes that model's manifest and only the layers no remaining manifest uses, and keeps the program, the receipt and every other model. When any remaining manifest cannot be read, every layer stays. A desktop download is admitted only from a keyless lane the person turned on; a lane turned off (`mode` `disabled`) offers no download.
3. **Contracts.** States and blocked reasons (unified-setup D2), the approval bound to a plan digest (D4), the phase, progress and retry vocabulary and its limits (D5, D6), the closed failure categories (D9), the desktop experience (D10) and the hard requirements (D11) are kept. The item ids are `browser` and `local_ai`. The `local_ai` item is the Ollama program, plus the one model a desktop download names; a setup, check, verification or removal that names no download is the program alone.
4. **Wording.** The engine emits only closed codes and locale-neutral facts. The desktop words them from the `desktop.setup` subtree of the canonical locale catalogues, in four languages and the informal singular.
5. **Pins are data.** The browser archive pins (`src/cadrumo/_data/dependencies/browser_archives.toml`) and the local AI program pins (`src/cadrumo/_data/dependencies/local_ai_program.toml`) are declarative data staged into the package, which Rust reads at run time. The local AI pins cover the program archive per platform only. They carry no model name, digest, size or licence. Regenerating program pins is a developer tool under `dev/`.
6. **Browser.** Rust fetches each pinned archive under the hop rules of unified-setup D13: HTTPS, declared and approved hosts, at most five redirects, pinned size and SHA-256. It extracts each archive into the build directory the bundled driver's `browsers.json` names and writes the driver's completion marker. Neither the vendor installer nor a loopback server runs. The full check is a headless launch by the engine of the pinned executable, with its version compared against the pins. The browser launch guard (`src/cadrumo/adapters/outbound/aeat/browser/session.py:218-248`) reads the component record the engine wrote, not a probe of its own.
7. **Local AI program.** Rust downloads Ollama's official standalone release archive for the platform, pinned by version, size and SHA-256, into `components/ollama/<version>`. The runtime manager runs the server with the existing models root and home, and the engine has it stopped before replacing or removing a version. The managed server is the one the cadrumo-agent `ollama` provider connects to. Cadrumo manages the program but does not build it, and it stays an external program under `2026-10-17-single-binary-process-tree-adr` constraint 7. A system-installed Ollama is detected and reported, never modified.
8. **Models.** Cadrumo defines no model names, digests, sizes, licences, defaults or rankings; cadrumo-agent's provider catalogue is the sole source (`2026-10-25-agent-owned-models-adr`). Rust pulls the model a desktop download names, through the pull endpoint of the server the manager supervises, with byte progress. The desktop host reads the person's local model list from the agent service and admits a name only when the catalogue recommends it for a turned-on keyless lane or the list holds it. It passes the catalogue's positive `size_bytes` when the catalogue states one; the frontend invents neither a name nor a size. A model of unknown size is planned with an unknown download, and its pull progress follows the totals the server streams. The plan digest binds the model and its size, known or unknown. Integrity is Ollama's content-addressed manifest, and Cadrumo compares no digest to a pin. A model missing from Ollama's installed list is `absent` and a failed pull is `failed`; there is no digest-based `stale`. The full check is a one-token generation on each admitted model on that server. Role fitness is not component state, and the engine consults no service for a setup, check, verification or removal that names no download.
9. **Hardware floor.** Rust decides `blocked hardware` from total memory and, on NVIDIA, VRAM, against the `size_bytes` of the downloaded model's catalogue entry when the catalogue states one. A model of unknown size, and a computer with no model to download, are not blocked. No floor table carries model figures.
10. **Network.** Rust performs the 3 s-per-host preflight, the classification, and honours the `CADRUMO_PROXY_*` settings declared in `native/application-environment.toml`. The proxy address is treated as a credential and is never logged.
11. **Durability.** Each item has one writer lock under the storage root, an activity record that survives a crash, and the atomic receipt (`components/receipts`). A lock held by no live owner, beside an unfinished activity, reads `failed interrupted` and offers Resume. A receipt alone never yields `ready`.
12. **Local model server.** The runtime manager, the long-lived per-user Rust supervisor, hosts the engine's local AI server. It starts the server whenever the local AI program is installed and verified, restarts it after a crash under its supervision policy, and stops it on exit, at session end, and before the engine replaces or removes the program. The manager contains the server process so nothing outlives it. The server listens on one fixed Cadrumo loopback address, declared once in the canonical environment definition (`native/application-environment.toml`) and never the upstream default port, so it cannot collide with a system Ollama. The engine records the address in the local AI component record, and consumers read that record and only connect. The desktop host's in-process engine does not run a second server; it observes the manager's. Where no manager runs (a development checkout), the local AI reads `program_not_running`.
13. **On demand.** Every consumer checks its component before its first effect. A missing, stale, failed or blocked component refuses with a typed verdict that names the component, and the desktop routes that verdict to the panel on that element (unified-setup D8, D10).

## Implementation

We will extend `native/application` with a provisioning module built on `component.rs`, point the desktop setup host at it in process, and keep the engine free of any interpreter. The sequence is in `2026-10-24-rust-component-provisioning-plan`. The consumer on-demand fixes run first and separately in `2026-10-24-component-on-demand-plan`.

Hypotheses, free to change within the constraints:

- The engine's exact message shapes.
- Whether the in-process desktop engine runs on a Tokio task or a thread.
- The Ollama archive formats per platform. Linux and macOS may need `tar` with `flate2` or `zstd`; adding those crates goes through cargo-deny.
- The exact completion-marker set the bundled driver checks. It is read from the driver's registry code before implementation.
- Whether the activity record shares the receipt's folder.

## Rationale

Component files need no profile custody and the desktop needs no runtime connection to set them up. The Rust store already provides the hard parts: locking, staging, bounded extraction, receipts and cutover. Pinning the Ollama archive gives the local AI the integrity and approval guarantees the browser already has. Dropping the vendor installer removes the Node driver and the loopback server from a path whose bytes Cadrumo already verifies. Having the manager host the model server gives every consumer one long-lived process on one fixed address.

## Consequences

- The desktop provisions through its native Rust engine without a signed-in profile.
- The local AI program archive is large (CUDA libraries on Windows and Linux). The plan size and free-space rule decide what the person approves.
- Upgrading Playwright or Ollama needs new pins, as the browser does today.
- The engine's lock, activity record and receipt must be crash-tested on all three platforms.
- Reconsider if Ollama stops publishing standalone archives, or if Playwright's layout or marker contract changes beyond what pins can track.
