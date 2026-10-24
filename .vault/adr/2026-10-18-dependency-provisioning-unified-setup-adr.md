---
tags:
  - '#adr'
  - '#dependency-provisioning'
date: '2026-10-18'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:d119885024abb88d27b73e179cab176ceb231624c316b4e7f666591b85d280f9'
related:
  - "[[2026-10-18-dependency-provisioning-mechanisms-reference]]"
  - "[[2026-06-15-dependency-provisioning-adr]]"
  - "[[2026-08-07-unstructured-document-ingestion-provisioning-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-05-desktop-design-system-adr]]"
  - "[[2026-10-11-mcp-parity-full-parity-adr]]"
  - "[[2026-10-04-google-app-identity-adr]]"
  - "[[2026-07-14-google-optional-adapter-boundary-adr]]"
  - "[[2026-10-17-idle-churn-operation-observation-adr]]"
  - "[[2026-10-13-application-distribution-native-bundle-llm-extra-adr]]"
  - "[[2026-10-17-single-binary-process-tree-adr]]"
---

# `dependency-provisioning` adr: `One setup system for the local model, the browser and Google` | (**status:** `accepted`)

## Problem Statement

The owner's requirement, 2026-10-18: "Download and provision it. But this requires a lot of design work for data provisioning. Complex and difficult ask for implementing the signals, ui interfaces, async provisioning; approvals, actions; cmd+k support; settings buttons; Network checks; And because this is not the only provisioning calls this needs to be a LLM + playwright + google. All are hard requirements for the app to be functioning. ... Retry, failure, recovery, double-checking, fast dependable smoke checks and error reporting are all important to integrate and implement."

Pieces exist for each dependency, but they do not form one system (`2026-10-18-dependency-provisioning-mechanisms-reference`). The CLI provisions in its own process while the TUI and MCP go through registered operations. Nothing verifies downloaded content. There is no retry, disk check, network check or byte progress for the browser. Consent is a boolean. Google sign-in works only in a terminal and its status can claim a sign-in with no token. The desktop has no setup surface at all. The desktop is the person's only installation, so a dependency it cannot set up is a feature that does not work.

## Considerations

- The doctor contract is accepted: probes are read-only, return a typed status, and missing dependencies are typed refusals with remediation (`2026-06-15-dependency-provisioning-adr`). The model catalogue, contention admission and lifecycle verbs are implemented (`2026-08-07-unstructured-document-ingestion-provisioning-adr`, still `proposed`).
- Registered operations already provide the journal, `UNKNOWN` effects, digest-bound single-use REVIEW interactions and progress events. Clients wait on the `operation_changed` cue and never poll on a fixed interval (`2026-10-17-idle-churn-operation-observation-adr`).
- The CLI, TUI and MCP are at parity. MCP refuses nothing the CLI can do inside the profile, and the product has no approval gate of its own. Authentication and installation acts are person acts, not agent operations (`2026-10-11-mcp-parity-full-parity-adr`). In the desktop, every agent tool call already waits on the person's approval (`2026-10-12-desktop-agent-host-adr`).
- The shell holds no runtime connection. Its narrow exceptions run through token-checked host commands and the held person bridge (`2026-10-04-desktop-shell-adr`, language amendment of 2026-10-15).
- The Google client is a fixed package fact with `drive.file` only, and a token is bound to its client (`2026-10-04-google-app-identity-adr`).
- Browsers, models and the model runtime are not package data. The model runtime is an external program with its own process tree (`2026-10-13-application-distribution-native-bundle-llm-extra-adr`, `2026-10-17-single-binary-process-tree-adr` constraint 7). Playwright's Python package and driver are being added to the native bundle in a parallel lane; this record assumes they are present.
- Ollama verifies layer digests and resumes partial pulls itself. Playwright installs per build and publishes no content hashes, and the Chrome for Testing builds carry no code signature. Cadrumo therefore pins the size and SHA-256 of every browser archive itself (amendment of 2026-10-21).

## Considered options

- **One dependency registry, with downloads under one registered setup operation and every front end projecting it.** Chosen.
- **Polish each dependency's existing path separately.** Rejected. It keeps three state vocabularies, three progress shapes and the CLI-only path, which is what makes the app unpredictable today.
- **Bundle Chromium and model weights in the installer.** Rejected. The accepted packaging boundary keeps them out, a GB-scale installer cannot track model licence changes, and the agent-host ruling against runtime downloads covers only the bundled agent.
- **Download automatically at startup, without asking.** Rejected. Multi-gigabyte network use without the person's act contradicts the doctor contract, and the owner asked for approvals.
- **Let Cadrumo own a model runtime binary.** Rejected here. It stays external under the single-binary ruling, and a change would need its own decision.

## Constraints

Accepted 2026-10-18 on the owner's advance authorization, relayed by the coordinating session: "Good, I forgo approval, all yours to deliver. How cool and exciting we're implementing this!" Each open choice below was taken on the design lead's recommendation and records its reason. The commitments are binding; text marked as a hypothesis may change within them.

### D1. One typed dependency registry

- `src/cadrumo/application` holds one registry of setup items. Each item declares its identity, plain display key, required version source, network hosts, storage category, quick probe, full verification, provisioner, size estimate and recovery actions.
- The items are: `browser` (the Chromium builds named by the bundled Playwright package); `model_runtime` (the local model program); `local_model.<role>` (one per catalogue role); and `google` (client metadata in this build, plus the profile's sign-in). (Amended 2026-10-19 by the operator-review amendment below.)
- The registry extends the existing provisioning modules in place, with no second home (`2026-08-07-unstructured-document-ingestion-provisioning-adr` D1). `aeat config check`, the health report, `config provision status`, the TUI, MCP and the desktop all read it. A new external dependency must enrol here with a probe, verification and wording.
- Reason for one registry: it is the only way the states, wording and recovery actions stay the same on every surface.

### D2. States

- Each item has exactly one state: `absent`, `provisioning`, `verifying`, `ready`, `stale`, `failed`, `blocked` or `unknown`.
- `blocked` carries a reason: `offline`, `needs_person` (approval, sign-in or an outside install), `hardware` (below the model floor), or `not_in_this_build` (for example, Google client metadata missing).
- `failed` carries one closed failure category (D9). `stale` means the item is usable but differs from what this version requires or was tested with: a model digest different from the pinned one, a runtime below the minimum version, or a Google grant that has ended. The ended-grant case is shown as needs sign-in. An older browser revision is not stale but absent, because the installed Playwright launches only its own pinned revision; the older revision is named in the reading's facts (amended 2026-10-18 from implementation evidence: this list first named an older browser revision as stale).
- `unknown` means a probe could not read. It is never shown as absent or ready (architecture rule: preserve unavailable and unknown).
- State is computed from the probes, the install receipt (D12) and any running setup operation. It is never stored as a fact. A running operation wins, then a probe that could not read gives `unknown`, then the probe result. A receipt alone never yields `ready`.
- Cadrumo is set up when every item is `ready` or `stale`. A `hardware` block is reported as a reason Cadrumo cannot complete setup on this computer; it is not a failure the person can fix.

### D3. Setup runs as registered operations

- `dependencies.status` is a read with `quick` and `full` modes (D7).
- `dependencies.setup` takes a set of item ids, defaulting to every item that is not ready, plus an optional explicit model name. It is the only operation that downloads or installs.
- `dependencies.verify` runs a full verification of named items.
- `local-reader.provision` keeps only the actions that download nothing: start, load, unload, verify and remove. Its install, pull and setup actions, and the `browser-runtime.provision` operation, are removed and their callers moved in the same change (no forwarding aliases).
- Every CLI `config provision` verb maps to one of these operations through the runtime. The in-process CLI paths are deleted. Reason: one journal, one effect record and one parity surface.
- Setup is idempotent per item set and target version. A second submit while one is running returns the running operation for the client to observe. A per-item lock under the storage root guards against any writer outside the runtime.
- Items run one at a time, in the order browser, model runtime, models. Running them one after another keeps bandwidth and memory predictable and makes progress easy to read. Parallel download is a hypothesis for later.
- Setup supports cooperative cancellation between transfer chunks. Replacing a verified older install is a short irreversible section.

### D4. Approval is the person's act, bound to a plan

- Before any byte moves, setup computes a plan: items, bytes, source hosts, destination folder, free space, and whether an outside program will be installed. It raises one REVIEW interaction carrying the plan digest. Applying it approves exactly that plan. A changed plan needs a new approval. The `consent` boolean is removed.
- The CLI prints the plan and asks. `--yes` answers the review after printing it. Non-interactive use without `--yes` refuses with "needs your approval".
- The TUI and desktop show the plan in a dialog. MCP answers through its interaction tool, as for any review, so MCP refuses nothing the CLI does. When the agent column starts setup, the desktop's tool-call approval is the person's gesture.
- Google sign-in stays a person act: it is an authentication act, it is not served on MCP, and Google's own consent page is the approval. Installing the model runtime program goes through the same plan review. Its system installer may ask for elevation, which is the operating system's own approval.
- Status reads and reachability checks need no approval. They move no taxpayer data and download nothing.
- Resume after an interruption is a new submit. When the plan digest is unchanged, the desktop's Resume click is itself the person's act and no second dialog appears. The CLI needs `--yes` again.
- Reason: digest binding is the existing interaction contract, so approval works the same way on every front end. A boolean could approve something other than what is downloaded.

### D5. Progress and signal contract

- Setup emits PHASE events coded `dependencies.setup.<item>.<step>`, with the steps plan, preflight, download, install, verify and cleanup.
- PROGRESS events gain an optional `subject_code` naming the item, with `unit_code` `bytes`. Unknown totals emit PHASE only, which shows as an indeterminate bar.
- Retries emit a NOTICE carrying the attempt number and the delay.
- Progress commits at most once per item per 500 ms, and only on a change of at least 1 %. This bounds journal writes.
- Delivery is the existing journal commit followed by an `operation_changed` cue and a re-read. Nothing polls on a fixed interval.
- On the CLI, text mode draws one stderr progress line and JSON mode carries the events. The TUI renders the same events. MCP relays them as `notifications/progress` when the client supplied a token (`2026-07-08-mcp-protocol-hardening-adr` H1) and returns the latest figure on observe. In the desktop, the held person bridge forwards `operation_changed` as a new pushed event; the host re-observes and pushes a typed setup snapshot on a Tauri channel.
- The browser installer's output is read in bounded form and parsed tolerantly for byte progress. A line that does not parse falls back to the phase.
- Hypothesis: whether `subject_code` is an additive V1 field or needs a V2 event.

### D6. Network checks, offline behaviour, retry and recovery

- Each item declares its hosts in `core/external_constants.toml`: the Playwright download hosts, the model registry, and the Google sign-in and API hosts.
- A preflight resolves each host, connects, completes TLS and sends a bounded HEAD request, with 3 s per host. It runs at the start of setup and in a full check, and never on a timer.
- The result classifies as `offline`, `host_unreachable`, `secure_connection_failed`, `blocked_by_network` (a proxy that refuses the tunnel or demands credentials) or `reachable`. Any HTTP answer from the host itself over the verified TLS connection, a 403, a 5xx or a redirect to another host included, is `reachable`. Offline blocks only items that need the network. Items already ready stay ready offline. (Amended 2026-10-18 from live evidence: the Playwright download host answers a bare request for its root with 403, so a full check on an open network read `blocked_by_network`. This line first named a host's 403 and a redirect to another host as blocked.)
- Provisioning traffic that Cadrumo starts follows the `CADRUMO_PROXY_*` settings: the preflight, the browser installer child (through its proxy variables), and the model runtime when Cadrumo starts it. A runtime started outside Cadrumo uses its own network settings, and the check says so.
- Noted 2026-10-18; basis: principal took the integration agent's recommendation (option A). The runtime stripped `CADRUMO_PROXY_*` from the profile worker's environment, so setup started through the runtime ignored the operator's proxy. The proxy address, user name and bypass list are now admitted to the worker by the canonical declaration: `native/application-environment.toml` declares them as pass-through names of the `cadrumo-runtime` and `python` profiles, and the runtime's own worker policy relays the same three names (`relayed_setting_names`). The password setting is a credential name, which the package declaration never carries (`2026-10-13-canonical-environment-application-internals-adr` constraint 12), so across a process boundary a proxy password travels inside the address, and the address is treated as a credential. The worker withholds the proxy settings from the environment its own children inherit once its settings hold them; only the download tools that need the proxy (the browser installer and a model runtime Cadrumo starts) receive it, as the standard proxy variables. Logs, diagnostics and "Copy details" carry no proxy address. The acquisition lane proves both against a credential-demanding counting proxy. (Noted 2026-10-24 under `2026-10-24-rust-component-provisioning-adr` constraint 10: setup runs in the Rust `components` role, so the `aeat` and `cadrumo-mcp` images pass the proxy address, user name and bypass list to the role they start; the password stays out, and a counting-proxy test proves the role follows them without logging any value.)
- Transient failures are retried with exponential backoff and jitter: from 2 s, doubling to at most 60 s, for at most 6 attempts within 15 minutes. Transient means connection reset or refused, DNS temporary failure, timeout, HTTP 5xx or 429. Never retried: approval missing, disk full, permission, integrity mismatch, hardware, contention, HTTP 4xx other than 429, and a build without Google.
- Recovery resumes rather than restarting. The model runtime keeps partial blobs. A browser build without its completion marker is deleted and that build alone downloads again. An interrupted operation reconciles as interrupted with effect `PARTIAL` or `UNKNOWN`. The next status reports `failed` with category `interrupted` and offers Resume. Cadrumo never resumes a download at startup without the person.
- Before downloading, setup checks free space on the storage volume against the plan's size times 1.2 plus 1 GiB. Too little space is the `disk_full` refusal, and it names both sizes.

### D7. Verification and smoke checks

- **Quick check** (`dependencies.status quick`): no network, no model load, bounded at 2 s in total. Browser: completion markers, the executable present and its digest matching the receipt. Model runtime: the program located and its loopback version endpoint answering. Model: present in the runtime inventory with its digest. Google: client metadata valid, metadata and token both present and bound to the client. This fixes the metadata-only status. Startup, the status indicator and every surface's status use the quick check.
- **Full check** (`dependencies.status full`, `dependencies.verify`, and the last step of every setup): the quick check, plus network preflight, a headless launch of the browser with its version compared against `browsers.json`, and for the model, a one-token generation when contention admission permits and the role fitness verdict. When admission refuses, the model is ready with the note "downloaded, not loaded yet". Google adds a token refresh and a metadata read of Cadrumo's own root folder. The full check is bounded at 60 s per item.
- Post-install verification is always this independent full check. An installer's exit code or a stream's success line never decides readiness.
- The catalogue gains an expected digest per model. When the installed digest differs, a passing fitness probe makes the model `stale` ("a different version from the one Cadrumo was tested with") and a failing probe makes it `failed`. Reason: upstream tags are mutable, so refusing outright would break every installation on an upstream retag.
- The readiness probe's keep-alive is aligned with the explicit load, and its name says that it loads.
- Developer and CI smoke checks reuse the same registry probes rather than separate scripts (Verification in `2026-10-18-dependency-provisioning-plan`).
- Note 2026-10-18: the user has no disposable host and declined any change to the development machine. The packaged setup acceptance (P08.S27) therefore runs on the development host, driving the staged packaged app against one throwaway storage root under `build/windows-x64/testing`, with every storage, temporary, application-data and browser location pointed inside it, a before/after listing proving real storage unchanged, and verified removal of the root and of any keychain entry the run created. The browser is set up by default; the model runtime and models are opt-in. A true vanilla-machine run stays pending until a disposable host exists, and Google sign-in stays pending until a person completes it.

### D8. Front-end parity

- Every operation in D3 is submittable from the CLI, TUI and MCP with the same decision and the same result.
- The operator-action catalogue gains `operator.provision.setup`, `operator.provision.model`, `operator.provision.runtime` and `operator.provision.google_sign_in`, beside the existing browser entry. Every dependency refusal names one of them as its recovery. (Amended 2026-10-19 by the operator-review amendment below.)
- Google sign-in is the product's registered `config.google.login` operation, which admits only a person's session. The CLI submits it and keeps its controlling-terminal check before answering the consent review. The TUI submits the same operation on its own connection. The desktop host submits it through the held person bridge's generic relay and answers its consent review, because the person's click is the gesture and Google's consent page is the approval. MCP does not serve it. (Amended 2026-10-18 under the runtime-boundary ruling recorded in the amendment below. This line first said that sign-in runs as the runtime's authentication command, reached from the desktop by a closed person-bridge action, and that the interactive-terminal gate also admits a kernel-verified person connection.)

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
- A "Copy details" action copies a redacted technical report: categories, operation id, phases, versions and hosts. It carries no tokens, paths outside the storage root, or profile data.
- CLI text output prints the sentence plus the exact command. JSON carries the category and verdict.
- The wording lives once in the canonical locale catalogues, in four languages, in the informal singular. The upstream substring classification in the Google flow is replaced by typed mapping into these categories.

### D10. Desktop experience

Amended 2026-10-19 by the operator-review amendment below; the bullets that follow are the prior wording.

- **Settings.** The popover gains a Components section after the window section. It has one row per item: a plain name ("Browser for the tax agency website", "Local AI program", "Local AI model", "Google account"), a state sentence, the size where relevant, and one button (Set up, Update, Try again, Resume, Sign in, Check again). An "Open setup" button opens the setup dialog.
- **Setup dialog.** It lists the plan: what, how large, from where, and where it will be stored. It has one approval button with the total size, one progress bar per item, the retry notices, the error sentence with its action, "Copy details" and Cancel while running.
- **First run and blocked features.** After sign-in, when setup is incomplete, the dialog opens once per launch; "Not now" closes it. When an operation is refused for a dependency whose recovery is an `operator.provision.*` action, a short prompt names what is needed and opens the dialog on that item.
- **Status.** The Settings rail item carries a badge while setup is incomplete, and a busy badge while setup runs. Rail order and stable hooks are unchanged. One toast reports completion or failure.
- **Palette.** Cmd+K gains "Set up components", "Check components", "Set up the browser", "Set up the local AI model", "Sign in to Google", "Retry setup" (enabled after a failure) and "Cancel setup" (enabled while running). They are declared once in the action registry and hidden while signed out.
- The surfaces appear only while signed in, because every act runs in the signed-in profile. Signed out, only the sign-in view stays.
- The browser scenario host gains synthetic scenarios for every state, category and phase.

### D11. Hard requirements

- The owner ruled that all three are required for Cadrumo to function. Setup incomplete is therefore never presented as optional: the badge stays and the first-run dialog returns each launch.
- The window is not locked. Sign-in, documentation, Settings, the TUI and features that need no missing item keep working. Reason: a locked window would also block the person from fixing a network or disk problem, and reading local records needs none of the three.

### D12. Storage locations

- Installation-wide under the storage root, shared by all profiles and outside encrypted custody: the browser at `components/playwright`, the runtime home at `components/ollama/home`, and the models at `models/ollama`.
- The coordinating brief described the browser as going into "profile storage". The shipped layout and this ruling place it in the installation's storage root instead, for two reasons: the files are public artifacts, not taxpayer data, and a copy per profile would multiply gigabytes.
- A new storage category, `DEPENDENCY_RECEIPTS` at `components/receipts`, holds one atomically written, non-secret receipt per item. A receipt records the version or revision, a digest manifest of the installed files, the verification time and the hosts used. Receipts are evidence for the stale and integrity checks, never authority.
- Google tokens stay in profile custody, unchanged. Superseded browser revisions are removed after the new revision verifies.

### D13. Scope

Out of scope:

- any live filing or submission to the tax agency (permanently);
- bundling browsers or models in the package;
- a Cadrumo-owned model runtime;
- VRAM probing beyond NVIDIA;
- detecting the system proxy and using the system trust store (a secure-connection failure is reported in plain words instead);
- metered-connection detection;
- automatic or scheduled updates and background checks;
- cloud model-provider keys (`2026-10-13-provider-settings-adr`);
- Google scopes, Picker or publisher verification;
- installing the model runtime on Linux, which keeps its plain instruction.

### Affected prior rulings, amended in place 2026-10-18 with the prior wording noted

- `2026-06-15-dependency-provisioning-adr`: an amendment section says that provisioning acts run through the registered setup operation of this record, and that a person sees a plain sentence and an action while the CLI keeps the exact command.
- `2026-10-04-desktop-shell-adr`: one more exception lets the host read setup status and run setup, approval, cancellation and Google sign-in through closed person-bridge actions, with a Components section in Settings and setup palette actions.
- `2026-10-05-desktop-design-system-adr`: Settings gains the Components section and the scenario host gains setup scenarios.
- `2026-10-04-google-app-identity-adr`: "the desktop Connect interface" leaves its out-of-scope list, governed here, and status checks the token as well as the metadata.
- `2026-08-07-unstructured-document-ingestion-provisioning-adr` is `proposed`. It receives a note that its lifecycle, retry and verification commitments are decided here, and that the shipped install and start actions replace its "never a spawn" sentence.
- `2026-10-11-mcp-parity-full-parity-adr` needs no change. Setup is inside the profile and served on MCP, and Google sign-in is the authentication act it already withholds.
- `2026-10-12-desktop-agent-host-adr` needs no change. Its "nothing is downloaded at runtime" governs the bundled agent only.

### Amendment 2026-10-18: the person bridge stays generic

Basis: the owner's ruling of 2026-10-18, "be careful not to conflate runtime a higher level construct with the cli tui mcp. those require a runtime but do not manage them. ensure there's no runtime management code in the cadrumo/ src". The installed runtime is a generic host: it learns no product concept such as a setup item, and product code does not manage the runtime. The first implementation projected setup rows, wording, the plan review and Google sign-in inside the runtime's held person bridge; that placement is withdrawn.

- The held person bridge offers only product-neutral relay actions: submit a registered operation by the definition id, subject and request its parent names; observe it; read its settled result document; read its pending review with a digest of exactly that document; answer the review bound to that digest; and cancel at the observed revision. It forwards `operation_changed` only while an operation it relayed is unsettled. It names no definition id, item, wording or setup shape. A guard test and an import contract refuse a bridge module that imports the product's setup code or spells a `dependencies.*` id.
- The registered `dependencies.*` operations carry their own words. Each request may name a language. Status, verify and setup results and the setup review carry every row's words, every item's name, every failure's sentence, the retry notice and the "Copy details" report, rendered by the product's wording module. The CLI, TUI, MCP and desktop therefore read the same words from the same operations.
- The desktop host (`native/desktop/src-tauri/src/shell/setup/`) keeps what only its window knows: which check and setup it started, how far it read their events, the plan it approved and the plan it saw interrupted. "Resume applies without a second dialog only when the digest equals what this window approved" is decided there. The host builds the window's snapshot from the product's words. The window contract (`desktop_setup_*` commands, `DesktopSetup` and refusal codes) is unchanged.
- Google sign-in stays a person act, carried over the same generic relay as any registered operation: the host submits `config.google.login` and answers its consent review. The bridge has no authentication act of its own and pushes no sign-in cue; the operation change cue serves. The runtime's commands carry no Google sign-in of their own and import neither the Google adapters nor the setup code, and an import contract refuses either. The product's operation maps a refused sign-in to its closed failure category, which the refusal detail carries. (Noted 2026-10-18. This bullet first said that the bridge serves a generic authentication act by method, composed by the launch door from the runtime's sign-in command, and left open whether that command carried product knowledge in the runtime; it did, and that command is removed.)
- Before this amendment, D5 and D8 were implemented as setup-specific bridge actions that worded rows and reviews in the runtime. The wording of D5 and D8 stands; "a closed person-bridge action" now means a closed host command carried over the generic relay.

## Implementation

We will add one dependency registry with derived states, move every download and install into the registered `dependencies.setup` operation, and project its status, approval, progress, retries and plain errors identically to the CLI, TUI, MCP and desktop. The sequence, lane ownership and smoke checks are in `2026-10-18-dependency-provisioning-plan`.

Hypotheses, free to change within the constraints: module and operation names beyond those fixed above; whether the browser byte progress comes from installer output or from a dry-run URL list; the exact size and timeout constants; and whether the wording lives in a new catalogue file or a subtree of an existing one.

## Rationale

The registry is what makes "the same everywhere" checkable: a surface either renders the registry or it is wrong. Putting every download behind one registered operation reuses the strongest controls the product already has, namely the journal, `UNKNOWN`, digest-bound reviews and cue-driven observation, and removes the CLI's unjournaled second path. Binding approval to a plan digest satisfies the owner's request for approvals without adding a frontend-specific gate, which parity forbids. Independent post-install verification answers "double-checking": an installer's word is never taken. Bounded quick checks keep startup and status fast; full checks run only when the person or a setup asks.

## Consequences

- One status sentence per item on every surface, a real approval for every download, visible progress, and recovery that resumes instead of restarting.
- The CLI's `config provision` verbs keep their names but now need the runtime. Their results and the removed operation and actions change public schemas, with no forwarding.
- More protocol: a pushed setup event on the person bridge, a subject on progress events, and a receipt category.
- Readiness is only as current as the last check. Nothing watches the network, so an offline change shows at the next action or check.
- The authenticity of model bytes still rests on HTTPS to the publisher and Ollama's own layer checks. Browser archives must match the digests this release pins, which proves they are the bytes the release was built against, not that the publisher's copy was genuine when it was pinned. The receipt detects later damage.
- Reconsider if Playwright publishes hashes or signatures, which would replace the pinned table as the browser's trust anchor, if the model runtime becomes a Cadrumo binary, or if parallel download proves necessary.

### Amendment 2026-10-19: operator review of the setup experience

Basis: operator review 2026-10-19. The operator reviewed the setup dialog in the development scenarios and in the built app, rejected both, and gave five binding rulings. They are recorded here with the commitments that replace the reversed clauses; the reversed wording above stays as history and is marked.

1. **The local AI is one item.** "Local AI program" (the model runtime) and the four "Local AI model" rows (`local_model.<role>`) become one user-facing item, "Local AI", and one provisioning flow sources the program and every model it needs.
   - D1 now reads: the items are `browser` and `local_ai`. `local_ai` is the program and the model each catalogue role reads with; they are parts of its plan, never items of their own. The item's state is the worst of its parts' readings: a computer below the model floor decides first, then a part that could not be read, a failure, a block, anything missing, and last anything that differs from what was tested. It is ready only when the program and every role's model are.
   - D3 and D4: a plan entry may carry ordered parts (the program, then each role whose model is not ready). The entry's size, hosts, licence notices and outside-program install are exactly the sum of its parts, and the approval digest binds every part, so a changed part needs a new approval. Setup runs the parts in order under the item's one lock and stops at the first that does not finish. Roles sharing one model still download it once.
   - D5: phase codes and the progress subject name `local_ai`; progress is one figure over the whole item's known download.
   - D7: the full check covers every part, so the local AI's bound is 60 s per part.
   - D8: the catalogue's local AI recovery is `operator.provision.local_ai`, performed by `aeat config provision pull`, which now sets up the whole local AI. `operator.provision.model` and `operator.provision.runtime` are removed, `aeat config provision install` is removed, and `pull` and `verify` lose `--role` (no surface sets up a single role any more). `--model` still names one catalogue model for every role.
2. **Status once.** Every surface states a row's state exactly once: the product's sentence, marked by a glyph that repeats no word. The desktop's separate status pill and its words are removed, and the setup prompt's title is the item's name with its sentence beneath.
3. **Settings advisory.** Settings no longer lists components. While setup is unfinished it shows one line at the top, "Cadrumo setup is not complete. Click here to complete it.", with an action glyph; while setup runs, one line that it is running; clicking either opens the single setup flow. When setup is complete it shows nothing. This replaces D10's Components section and its "Open setup" button.
4. **Google leaves setup.** Google sign-in is not a software dependency and belongs to the current profile, not to the installation.
   - D1, D2 and D8: `google` is removed from the registry, its declaration, item grammar, wording, setup flow, rows, CLI provision verbs, TUI setup screen and the palette's setup group. The `person_sign_in` route, the `sign_in` recovery button and the `grant_ended` stale reason, which existed only for it, are removed, as are `operator.provision.google_sign_in` and the Google host group of the setup preflight. Every item is now set up by the setup operation.
   - The Google readiness checker built for the item is retired; its failure-category mapping stays and words any Google failure. The profile's sign-in is read through the existing `config.google.status` operation (a stored sign-in counts only when its record and a token minted by this installation's client are both present), and signed in and out through the existing `config.google.login` and `config.google.logout` operations. The desktop host carries them over the same generic person-bridge relay.
   - The desktop gives Settings its own "Google account" row (signed-in state with the account's address, and Sign in or Sign out), and Cmd+K gains "Authenticate with Google" in the account group. The setup snapshot carries the account beside, not among, the rows.
   - Unchanged by this amendment: where and how Google tokens are stored (D12, profile custody), the Google client and its scopes, and MCP's refusal of the sign-in act.
   - The TUI setup screen no longer offers Google sign-in. Offering it from the TUI's account controls is open follow-up work; the CLI's `config google login` and the desktop remain the sign-in surfaces meanwhile.
5. **A simpler setup flow.** The setup dialog leads with one summary and one primary action. Each component's detail (rows, plan entries with their parts, hosts and folders, and per-item progress) sits in a "Details" disclosure that is closed by default. While setup runs, the summary is one overall progress bar over every planned item in order, naming the item and step now running. What an approval also agrees to stays visible without opening the disclosure: the total size, the free-space reading, any outside-program install and every licence notice.

Before this amendment the registry held four kinds (`browser`, `model_runtime`, `local_model.<role>`, `google`), Google was an item set up by the person's sign-in, Settings embedded a Components section, and each row showed a status pill beside its sentence.

### Amendment 2026-10-21: browser archives are pinned and fetched by Cadrumo

Basis: the operator's selection of 2026-10-21 ("Pinned digests"), answering a security finding that setup approved hosts measured by a separate HEAD request while the vendor installer downloaded on its own, followed any redirect, checked no content, and the full check then launched the result.

- The repository pins every archive `playwright install chromium` downloads for the bundled Playwright driver on each supported platform (`win-x64`, `linux-x64`, `linux-arm64`, `mac-x64`, `mac-arm64`): its build directory, its path under the download host, the vendor's sources in order, its size and its SHA-256, with the driver version, in `src/cadrumo/_data/dependencies/browser_archives.toml`. `just pin-browser-archives` regenerates the table from the driver's own dry-run listing and one download of each archive. A gate test refuses a table that differs from the locked driver's listing or names a source outside the declared browser hosts, so a Playwright upgrade needs new pins. Native package assembly, which CMake runs for every package target, reads the staged pin table and the staged Playwright driver and refuses a package whose pins do not cover that driver's Chromium builds on its target platform.
- D4: the browser's plan entry takes its size from the pins of the archives still missing and names exactly the declared browser hosts. Nothing is measured over the network, and no host a source answers with widens the plan.
- D6: setup downloads each pending archive itself, at the moment the vendor installer asks for it, so builds still finish one at a time and an interruption keeps every finished build. Every hop must be HTTPS, on the default port and without credentials, to a host that is both declared and in the approved plan, and a chain may take at most five redirects. The body must have the pinned size and SHA-256. A mismatch is `damaged_download` and an unapproved hop is `blocked_by_network`; neither is retried, and no other source is tried after them. A network failure on one source gives way to the vendor's next source.
- The vendor installer still extracts each build and writes its completion marker, but its only download host is a loopback server that answers each pending archive's pinned path and nothing else, fetching it once and remembering a failed fetch rather than repeating it behind the setup's retry policy. The server hashes every response as it sends it and withholds the final chunk unless the bytes match the pin. The installer's environment carries no inherited Playwright, Node, npm or proxy variable.
- When this build pins no archives for the installed driver on this platform, a missing browser reads blocked `not_in_this_build`, so no surface offers its setup, the plan's size is unknown, and setup refuses with `not_in_this_build` before downloading anything. An installed browser stays ready.
- D7: nothing downloaded is extracted or launched before its bytes have matched a pin, so the full check's launch is never the first check of what was downloaded.

### Amendment 2026-10-24: Rust owns provisioning

Basis: the owner's approval of 2026-10-24, "all approved, implemnet", answering the presented `2026-10-24-rust-component-provisioning-adr` and its two plans.

`2026-10-24-rust-component-provisioning-adr` moves component provisioning out of Python into the Rust engine of `native/application`, run as the single binary's `components` role and linked in process by the desktop. The wording above stays as history; these clauses are replaced:

- D1: the registry lives in `native/application`, not `src/cadrumo/application`. Pins are declarative package data both languages read.
- D3: the `dependencies.status`, `dependencies.setup` and `dependencies.verify` registered operations, and the provisioning actions of `local-reader.provision`, are replaced by the role's status, plan, setup, verify, cancel and remove commands. The CLI, TUI and MCP become thin clients of the role.
- D5: delivery is the role's event stream, not the journal commit and `operation_changed` cue. The event vocabulary and the throttling stay.
- D6: preflight, proxy handling, retry and resume run in Rust with the same classification and limits.
- D7: role fitness leaves component state and becomes a consumer admission check. The one-token generation stays the model's full check.
- D12: the local AI program lives at `components/ollama/<version>`, installed from a pinned portable archive.
- D13: "a Cadrumo-owned model runtime" is narrowed. Cadrumo manages a pinned upstream Ollama archive and does not build one.
- The 2026-10-18 person-bridge amendment's "operations carry their own words" becomes: the engine emits codes and every surface words them from the canonical catalogues.
- The 2026-10-21 amendment's vendor installer and loopback server are removed. Rust extracts each pinned archive into the driver's layout and writes its completion marker. Pins, hop rules and the `not_in_this_build` reading stand.

D2, D4, D9, D10 as amended, D11 and the rest of D12 are unchanged.
