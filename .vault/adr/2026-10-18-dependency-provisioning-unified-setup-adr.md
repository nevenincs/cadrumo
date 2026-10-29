---
tags:
  - '#adr'
  - '#dependency-provisioning'
date: '2026-10-18'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:e081dca56b54f7ae496073930b75c8a5852f9321464e7c955e6e9827b190afe8'
related:
  - "[[2026-10-18-dependency-provisioning-mechanisms-reference]]"
  - "[[2026-06-15-dependency-provisioning-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-05-desktop-design-system-adr]]"
  - "[[2026-10-11-mcp-parity-full-parity-adr]]"
  - "[[2026-10-04-google-app-identity-adr]]"
  - "[[2026-07-14-google-optional-adapter-boundary-adr]]"
  - "[[2026-10-17-idle-churn-operation-observation-adr]]"
  - "[[2026-10-13-application-distribution-native-bundle-llm-extra-adr]]"
  - "[[2026-10-17-single-binary-process-tree-adr]]"
---
# `dependency-provisioning` adr: `One setup system for the browser and the local AI` | (**status:** `accepted`)

## Problem Statement

The owner's requirement, 2026-10-18: "Download and provision it. But this requires a lot of design work for data provisioning. Complex and difficult ask for implementing the signals, ui interfaces, async provisioning; approvals, actions; cmd+k support; settings buttons; Network checks. ... Retry, failure, recovery, double-checking, fast dependable smoke checks and error reporting are all important to integrate and implement."

The browser that the tax agency reads need and the local AI that the document readers use are hard requirements for the app to function, and neither is package data. The desktop is the person's only installation, so a dependency it cannot set up is a feature that does not work. Setup therefore has to be one system: one declaration of what exists, one state vocabulary, one approval contract, one progress shape and one set of plain error sentences (`2026-10-18-dependency-provisioning-mechanisms-reference`).

## Considerations

- The doctor contract is accepted: probes are read-only, return a typed status, and a missing dependency is a typed refusal with remediation (`2026-06-15-dependency-provisioning-adr`).
- Component setup is a desktop capability driven by the native engine of `native/application` (`2026-10-24-rust-component-provisioning-adr`). The desktop host links the engine in process, so setup needs no runtime connection and no signed-in profile (`2026-10-04-desktop-shell-adr`).
- Browsers, models and the model runtime are not package data. The model runtime is an external program with its own process tree (`2026-10-13-application-distribution-native-bundle-llm-extra-adr`, `2026-10-17-single-binary-process-tree-adr` constraint 7). Playwright's Python package and driver ship in the native bundle and launch the browser at use time.
- Ollama verifies layer digests and resumes partial pulls itself. Playwright installs per build and publishes no content hashes, and the Chrome for Testing builds carry no code signature. Cadrumo therefore pins the size and SHA-256 of every browser archive itself.
- Cadrumo defines no AI model name, digest, size, licence, default or ranking. cadrumo-agent's provider catalogue is the sole source of providers and models, local ones included (`2026-10-25-agent-owned-models-adr`).

## Considered options

- **One dependency registry, enumerated by the native engine, with setup run per element in the desktop and one panel rendering the engine's rows.** Chosen.
- **Polish each dependency's setup separately.** Rejected. It keeps separate state vocabularies and progress shapes, which is what makes the app unpredictable.
- **Bundle Chromium and model weights in the installer.** Rejected. The accepted packaging boundary keeps them out, and a GB-scale installer cannot track model licence changes.
- **Download automatically at startup, without asking.** Rejected. Multi-gigabyte network use without the person's act contradicts the doctor contract, and the owner asked for approvals.
- **Let Cadrumo build its own model runtime binary.** Rejected. Cadrumo manages a pinned upstream Ollama archive and builds none; the program stays external under the single-binary ruling.

## Constraints

Accepted 2026-10-18 on the owner's advance authorization: "Good, I forgo approval, all yours to deliver." Each open choice below was taken on the design lead's recommendation and records its reason. The commitments are binding; text marked as a hypothesis may change within them.

### D1. One typed dependency registry

- `native/application` holds the setup items. Each declares its identity, plain display key, required version source, network hosts, storage category, quick probe, full verification, provisioner, size estimate and recovery actions. Items and sizes are enumerated from the declarations and the pins the installation stages; no surface lists items, kinds, sizes or states of its own.
- The items are `browser` (the Chromium builds named by the bundled Playwright package) and `local_ai`. `local_ai` is the Ollama program plus the one model a desktop download names from the person's local model list; the program and that model are its parts, never items of their own. The item's state is the worst of its parts' readings: a computer below the model floor decides first, then a part that could not be read, a failure, a block, anything missing, and last anything that differs from what was tested.
- The engine's status rows are the only component state. The desktop host relays them and the window renders whatever rows the snapshot carries. Item names come from the canonical catalogues, keyed by the row's item. A row's size is the engine's figure; an unknown size is shown as unknown, never as zero.
- Reason for one registry: it is the only way the states, wording and recovery actions stay the same everywhere. A new external dependency must enrol here with a probe, verification and wording.

### D2. States

- Each item has exactly one state: `absent`, `provisioning`, `verifying`, `ready`, `stale`, `failed`, `blocked` or `unknown`.
- `blocked` carries a reason: `offline`, `needs_person` (approval or an outside install), `hardware` (below the model floor), or `not_in_this_build` (for example, a build that pins no browser archive for the installed driver).
- `failed` carries one closed failure category (D9). `stale` means the item is usable but differs from what this version requires or was tested with, such as a runtime below the minimum version. An older browser revision is not stale but absent, because the installed Playwright launches only its own pinned revision; the older revision is named in the reading's facts. A local model has no digest-based `stale` state.
- `unknown` means a probe could not read. It is never shown as absent or ready (architecture rule: preserve unavailable and unknown).
- State is computed from the probes, the install receipt (D12) and any running setup. It is never stored as a fact. A running setup wins, then a probe that could not read gives `unknown`, then the probe result. A receipt alone never yields `ready`.
- Cadrumo is set up when every item is `ready` or `stale`. A `hardware` block is reported as a reason Cadrumo cannot complete setup on this computer; it is not a failure the person can fix.

### D3. Setup runs per element in the native engine

- The engine serves status, plan, setup, verify, cancel and remove. The desktop host calls it in process. Setup names exactly one item; there is no setup of everything at once. Each item has its own run under its own writer lock, so the browser and the local AI are planned, approved, cancelled and resumed independently and at the same time. A second start of an item that is already running joins that item's run; a start of another item is never refused as busy because of it. Within an item, parts run in order under its one lock, and a failure stops the item at the first part that does not finish.
- Setup is idempotent per item and target version. Cancellation is cooperative between transfer chunks. Replacing a verified older install is a short irreversible section.
- The local AI program and its models are separate steps with separate progress. Downloading a model while the program is missing plans the program and then that model. The model list is the person's local model list: what cadrumo-agent's catalogue recommends for a turned-on keyless lane, plus the custom models the person adds by name, each with its own download, progress and remove (`2026-10-25-agent-owned-models-adr`).
- Setup is not a registered operation, has no journal and needs no signed-in profile. The engine keeps its own writer lock, activity record and atomic receipt under the storage root.

### D4. Approval is the person's act, bound to a plan

- Before any byte moves, setup computes a plan: items and parts, bytes, source hosts, destination folder and free space. The plan carries a digest. Applying it approves exactly that plan. A changed plan needs a new approval.
- The desktop shows the plan in the panel. Status reads and reachability checks need no approval; they move no taxpayer data and download nothing.
- Resume after an interruption is a new start. When the plan digest is unchanged and equals what the window approved, the person's Resume click is itself the approval and no second dialog appears.
- Reason: digest binding means an approval can only cover what is downloaded. A boolean could approve something other than what is downloaded.

### D5. Progress and signal contract

- Setup emits PHASE events for the steps plan, preflight, download, install, verify and cleanup, each naming its item. PROGRESS events carry the item as subject and `bytes` as the unit. An unknown total emits PHASE only, which shows as an indeterminate bar.
- Retries emit a NOTICE carrying the attempt number and the delay.
- Progress commits at most once per item per 500 ms, and only on a change of at least 1 %.
- The engine emits an event stream. The host re-reads on each event and pushes a typed snapshot on a Tauri channel; the snapshot carries `runs`, at most one per item, each naming its `item`. Nothing polls on a fixed interval.
- The window keeps one provisioning store fed by the pushed snapshot. Any element subscribes to it: the panel, the Settings section, the rail and the recovery offers.
- Hypothesis: the exact event message shapes.

### D6. Network checks, offline behaviour, retry and recovery

- Each item declares its hosts in the engine's declarations: the Playwright download hosts and the model registry.
- A preflight resolves each host, connects, completes TLS and sends a bounded HEAD request, with 3 s per host. It runs at the start of setup and in a full check, and never on a timer.
- The result classifies as `offline`, `host_unreachable`, `secure_connection_failed`, `blocked_by_network` (a proxy that refuses the tunnel or demands credentials) or `reachable`. Any HTTP answer from the host itself over the verified TLS connection, a 403, a 5xx or a redirect to another host included, is `reachable`, because the Playwright download host answers a bare request for its root with 403. Offline blocks only items that need the network. Items already ready stay ready offline.
- Traffic that Cadrumo starts follows the `CADRUMO_PROXY_*` settings declared in `native/application-environment.toml`. The proxy address, user name and bypass list are declared pass-through names; the password setting is a credential name, which the package declaration never carries (`2026-10-13-canonical-environment-application-internals-adr` constraint 12), so a proxy password travels inside the address, and the address is treated as a credential. Logs, diagnostics and "Copy details" carry no proxy address. A runtime started outside Cadrumo uses its own network settings, and the check says so.
- Transient failures are retried with exponential backoff and jitter: from 2 s, doubling to at most 60 s, for at most 6 attempts within 15 minutes. Transient means connection reset or refused, DNS temporary failure, timeout, HTTP 5xx or 429. Never retried: approval missing, disk full, permission, integrity mismatch, hardware, contention, HTTP 4xx other than 429, and a build without the item.
- Recovery resumes rather than restarting. The model runtime keeps partial blobs. A browser build without its completion marker is deleted and that build alone downloads again. An interrupted setup reads `failed` with category `interrupted` and offers Resume. Cadrumo never resumes a download at startup without the person.
- Before downloading, setup checks free space on the storage volume against the plan's size times 1.2 plus 1 GiB. Too little space is the `disk_full` refusal, and it names both sizes.

### D7. Verification and smoke checks

- **Quick check:** no network, no model load, bounded at 2 s in total. Browser: completion markers, the executable present and its digest matching the receipt. Model runtime: the program located and its loopback version endpoint answering. Model: present in the runtime inventory. Startup, the status indicator and the panel use the quick check.
- **Full check** (the last step of every setup, and on request): the quick check, plus network preflight, a headless launch of the browser with its version compared against the pins, and for the model a one-token generation on the managed server. The full check is bounded at 60 s per part.
- Post-install verification is always this independent full check. An installer's exit code or a stream's success line never decides readiness.
- A local model's integrity is Ollama's content-addressed manifest. Cadrumo keeps no expected digest. Role fitness is not component state, and Cadrumo performs no contention admission; cadrumo-agent admits model loads.
- Developer and CI smoke checks reuse the same engine probes rather than separate scripts. The packaged setup acceptance drives the staged packaged app against one throwaway storage root, with every storage, temporary, application-data and browser location pointed inside it, a before/after listing proving real storage unchanged, and verified removal of the root.

### D8. Recovery for a consumer whose component is not ready

- Every consumer checks its component before its first effect. A missing, stale, failed or blocked component refuses with a typed verdict that names the component. The desktop shows the component's sentence and opens the panel on that element (D10). The Sede browser panel does so in place of a generic refusal and logs the refusal locally as a warning with its category.
- The browser launch reads the component record the engine wrote, not a probe of its own.

### D9. Error reporting

- Each failure maps to one closed category with one plain sentence and at most one action:
  - `offline`
  - `host_unreachable`
  - `secure_connection_failed`
  - `blocked_by_network`
  - `disk_full`
  - `no_permission`
  - `damaged_download`
  - `not_enough_memory`
  - `memory_busy`
  - `program_missing`
  - `program_not_running`
  - `interrupted`
  - `needs_sign_in`
  - `not_in_this_build`
  - `cancelled`
  - `unexpected`
- Surfaces show the sentence and the action, never the category, an operation id, an exception name or internal vocabulary. Internal vocabulary includes runtime, provision, Playwright, headless, digest and Ollama API words.
- A "Copy details" action copies a redacted technical report: categories, phases, versions and hosts. It carries no tokens, paths outside the storage root, or profile data.
- The engine emits only closed codes and locale-neutral facts. The desktop words them from the `desktop.setup` subtree of the canonical locale catalogues, in four languages and the informal singular.

### D10. Desktop experience

- **One panel.** One React component lists and manages setup. It is the startup prompt, the Settings popup and the target of every blocked-feature offer. It has one row per element, each stating its status once, with its size, its own action (set up, update, try again, resume, check again, cancel, approve or reject its plan) and its own progress, plus a close button. Closing it never stops a run.
- **The local AI** appears as a dropdown: its program row with its own controls, and beneath it, grouped and linked to it, the model list. The panel and the agent settings' Ollama provider controls render the same one React component for the program and the model list; no second model list, download or remove control exists.
- **First run.** When setup is incomplete, the panel opens once per launch; closing it dismisses it for that launch.
- **Settings.** One provisioning section with one status label and one button that opens the panel.
- **Rail.** While any run is live, the rail's Settings button shows a spinner overlay in its corner. One toast reports completion or failure.
- **Palette.** Cmd+K gains per-element actions for setup, check, retry and cancel, declared once in the action registry.
- **Blocked features.** A consumer refused because its component is not ready shows the component's sentence and the button that opens the panel on that element.
- The browser scenario host gains synthetic scenarios for every state, category and phase.

### D11. Hard requirements

- The browser and the local AI are required for Cadrumo to function. Setup incomplete is therefore never presented as optional: the Settings status stays and the first-run panel returns each launch.
- The window is not locked. Sign-in, documentation, Settings and features that need no missing item keep working. Reason: a locked window would also block the person from fixing a network or disk problem, and reading local records needs none of the items.

### D12. Storage locations

- Installation-wide under the storage root, shared by all profiles and outside encrypted custody: the browser at `components/playwright`, the Ollama program at `components/ollama/<version>` installed from a pinned portable archive, and the models at `models/ollama`.
- The files are public artifacts, not taxpayer data, and a copy per profile would multiply gigabytes.
- A storage category, `DEPENDENCY_RECEIPTS` at `components/receipts`, holds one atomically written, non-secret receipt per item. A receipt records the version or revision, a digest manifest of the installed files, the verification time and the hosts used. Receipts are evidence for the stale and integrity checks, never authority. Superseded browser revisions are removed after the new revision verifies.

### D13. Browser archives are pinned and fetched by Cadrumo

- The repository pins every archive the bundled Playwright driver installs for Chromium on each supported platform (`win-x64`, `linux-x64`, `linux-arm64`, `mac-x64`, `mac-arm64`): its build directory, its path under the download host, the vendor's sources in order, its size and its SHA-256, with the driver version, in `src/cadrumo/_data/dependencies/browser_archives.toml`. `just pin-browser-archives` regenerates the table from the driver's own dry-run listing and one download of each archive. A gate test refuses a table that differs from the locked driver's listing or names a source outside the declared browser hosts, so a Playwright upgrade needs new pins. Native package assembly refuses a package whose pins do not cover the staged driver's Chromium builds on its target platform.
- The plan's size comes from the pins of the archives still missing and names exactly the declared browser hosts. Nothing is measured over the network, and no host a source answers with widens the plan.
- The engine downloads each pending archive itself, one build at a time, so an interruption keeps every finished build. Every hop must be HTTPS, on the default port and without credentials, to a host that is both declared and in the approved plan, and a chain may take at most five redirects. The body must have the pinned size and SHA-256. A mismatch is `damaged_download` and an unapproved hop is `blocked_by_network`; neither is retried, and no other source is tried after them. A network failure on one source gives way to the vendor's next source.
- Nothing downloaded is extracted or launched before its bytes have matched a pin. The engine extracts each archive into the build directory the driver's `browsers.json` names and writes the driver's completion marker. The vendor installer does not run. The full check's launch is therefore never the first check of what was downloaded.
- When this build pins no archives for the installed driver on this platform, a missing browser reads blocked `not_in_this_build`, so the panel offers no setup, the plan's size is unknown, and setup refuses with `not_in_this_build` before downloading anything. An installed browser stays ready.

### D14. Scope

Out of scope:

- any live filing or submission to the tax agency (permanently);
- bundling browsers or models in the package;
- a Cadrumo-built model runtime, and any model definition owned by Cadrumo;
- VRAM probing beyond NVIDIA;
- detecting the system proxy and using the system trust store (a secure-connection failure is reported in plain words instead);
- metered-connection detection;
- automatic or scheduled updates and background checks;
- cloud model-provider keys (`2026-10-13-provider-settings-adr`);
- Google sign-in, which is not a software dependency and belongs to the current profile (`2026-10-19-google-app-identity-profile-folder-scope-adr`);
- installing the model runtime on Linux, which keeps its plain instruction.

## Implementation

We will keep one dependency registry in the native engine, derive each item's state from probes and receipts, run every download and install per element under the desktop's approval of a digest-bound plan, and render the engine's rows, progress, retries and plain errors in the one panel. The sequence, ownership and smoke checks are in `2026-10-18-dependency-provisioning-plan`.

Hypotheses, free to change within the constraints: module names; the exact size and timeout constants; and the event message shapes.

## Rationale

The registry is what makes "the same everywhere" checkable: the panel either renders the engine's rows or it is wrong. Binding approval to a plan digest satisfies the owner's request for approvals and guarantees that an approval covers exactly what is downloaded. Independent post-install verification answers "double-checking": an installer's word is never taken. Bounded quick checks keep startup and status fast; full checks run only when the person or a setup asks. Per-element runs let the person fix the browser while a multi-gigabyte model downloads.

## Consequences

- One status sentence per item, a real approval for every download, visible progress, and recovery that resumes instead of restarting.
- Readiness is only as current as the last check. Nothing watches the network, so an offline change shows at the next action or check.
- The authenticity of model bytes still rests on HTTPS to the publisher and Ollama's own layer checks. Browser archives must match the digests this release pins, which proves they are the bytes the release was built against, not that the publisher's copy was genuine when it was pinned. The receipt detects later damage.
- Reconsider if Playwright publishes hashes or signatures, which would replace the pinned table as the browser's trust anchor, or if the model runtime becomes a Cadrumo binary.
