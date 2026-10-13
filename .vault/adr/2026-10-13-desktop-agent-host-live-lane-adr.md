---
tags:
  - '#adr'
  - '#desktop-agent-host'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:3b4e60baab240047d421e74f5bc8511180babf3f6cdd25b356b9184b9b9e648e'
related:
  - "[[2026-10-12-desktop-agent-host-adr]]"
  - "[[2026-10-12-desktop-agent-host-reference]]"
---

# `desktop-agent-host` adr: `A development live lane runs the real agent column on a disposable synthetic profile` | (**status:** `proposed`)

Revision 2, 2026-10-13. It answers the five reviews in `2026-10-13-desktop-agent-host-live-lane-review-audit` and goes back to those reviewers before any ruling.

Owner rulings this revision applies, all first-hand on 2026-10-13:
- "I don't want read only tools. I want to verify that the agent platform is functional."
- "I don't want you to improvise. You have to ask for reviews, ruling, check verifications."
- On API keys, in sequence:
  - "do not allow my api keys to be exposed"
  - "The processes can have the api keys in the env"
  - "in the env but do not save them to disk or upload them to providers"
  - "they're secret; the machine has them, if you upload them they're fucked"
  - Encrypted custody was confirmed safe.
  - For the hand-off to the agent, relayed by CADRUMO-ARCHITECTURE: "do standard input frame".
- "I don't care about anything but that we test the agent ui against the real agent backend so we can debug and iterate fast."

## Problem Statement

The owner wants the agent column tested and iterated against the real agent backend. That means the real desktop, the real cadrumo-agent, the real Anthropic API and the real Cadrumo runtime, including tool calls that change records, questionnaires and approvals. The production path in `2026-10-12-desktop-agent-host-adr` is not built, and it needs work in cadrumo-agent and in Cadrumo's packaging. The first revision of this record failed review with thirteen critical findings. This revision decides the live lane's topology and the controls those findings require.

## Considerations

- cadrumo-agent mounts the Cadrumo relay and earns its tool proofs only through its own hosted-parts assembly. Run from its source tree, that assembly is what its live tests use. A bundled, non-hosted service cannot mount the relay (audit: `agent-relay-unmountable-in-bundle`, `agent-proofs-unearnable-on-lane`).
- Bundling the agent's 39-package closure needs a lane lock, a widened assembly and a lane preset (audit: `packaging-closure-and-lane-lock`, `lane-build-option-wording`). None of that is needed to test the UI.
- With the full surface, the agent can apply its own review, and no person door answers a review an agent session raised (audit: `agent-self-approved-review`, `review-door-for-agent-reviews`).
- A new frontend kind inherits person authority wherever the refusal is written "is MCP" (audit: `agent-host-person-authority`, `agent-frontend-predicate`).
- The desktop owns no long-lived child and contains none, and cadrumo-agent's ports are fixed (audit: `desktop-child-containment`, `fixed-agent-ports`).
- cadrumo-agent's history and stream do not keep the turn order, ids or offsets the webview contract needs (audit: `history-cannot-serve-session-contract`).
- The owner has approved a provider-settings design, which CADRUMO-ARCHITECTURE is implementing:
  - the Anthropic key in an encrypted, person-only SECRET namespace;
  - one resolver for every consumer;
  - delivery to the agent on a standard-input frame;
  - an app-owned lifecycle that reaps the agent tree on logout, lock, expiry, key change or profile switch.

## Considered options

- **The packaged Cadrumo with cadrumo-agent run from its source tree under its own hosted-parts assembly (proposed).** Every component is real, and the relay mounts the way cadrumo-agent proves it. A UI or agent change needs no repackaging. Bundling moves to the last stage.
- The packaged Cadrumo with cadrumo-agent bundled and non-hosted. Rejected: the relay cannot mount there, its writes can repeat, and the bundle strips its variables.
- Waiting for the production path. Rejected by the owner's direction to test against the real backend now.
- A browser bridge, or the person's real profile. Rejected as in revision 1: the bridge is a second host and opens the network, and the real profile breaks the at-rest ruling.

## Constraints

Binding if accepted:

**Topology**
- These are real and run unmodified:
  - the packaged desktop with its Rust agent host;
  - the launcher `aeat app agent serve` in the same package;
  - cadrumo-agent from an explicit source path, in its own project environment, with its hosted-parts assembly;
  - the Anthropic API and the Cadrumo runtime.
  There is no mock host, scripted model or stand-in under test. The fixture host stays an appearance tool.
- The launcher builds on the provider-settings controller. It does not add a second lifecycle owner.

**Storage root**
- The lane runs only on a storage root it created empty and marked.
- The guard compares the root the connected runtime reports it serves, after canonical resolution (junctions, case folding, substituted drives), with the marked root, and refuses on any difference. A non-default root hosts its own supervisor, so the lane desktop does not attach to an installed manager on the default root (`native/desktop/src-tauri/src/manager.rs:370`, `:427-431`).
- The launcher starts the agent with:
  - its project root, home, workspace root, temporary directory and logs all under `<storage-root>/agent/<profile-id>/`;
  - no `.env` or operator settings file read;
  - tracing variables removed.
- The relay starts the lane package's `cadrumo-mcp` by absolute path, with the pinned storage root, never by bare name.

**Keys**
- Every provider key lives in Cadrumo's encrypted SECRET custody. It reaches cadrumo-agent through the provider-settings resolver on a standard-input frame, and is held in process memory. cadrumo-agent passes it to its worker over a pipe, never through an environment variable.
- The key is never:
  - written to disk in plaintext (files, `.env`, logs, caches, crash output);
  - put on a command line;
  - sent off the machine (model prompts or context, tool results, transcripts, telemetry, tracing, git);
  - shown in the webview.
- A child that does not need the key does not receive it. The `cadrumo-mcp` relay is already scrubbed (`agent:workspace/environment.py:155-183`).
- The key is entered through the protected input channel, never in a webview that is open to a debugger.
- Every lane run scans the started processes' command lines, and the root's files and logs, for any `sk-ant-` pattern. A hit fails the run.

**Authority**
- One predicate names the person frontends, `cli` and `tui`. Every person-act refusal and admission gate uses it in place of "is MCP": `src/cadrumo/application/operations/person_acts.py:81-83`, `src/cadrumo/application/user_profile/operation_access_policy.py:213-219`, `src/cadrumo/entrypoints/runtime/profile_connection_admission.py:161-163`, `:277`, `profile_connection_sessions.py:229-231`, `profile_connection_access.py:163-168`, `profile_connection_person_acts.py:37-40`, `src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:282-284`.
- A door-by-frontend matrix test proves that `mcp` and `agent-host` reach no person act.
- `agent-host` admits only by receipt resume (`src/cadrumo/entrypoints/runtime/profile_connection_attendance.py:81`).
- Reviews:
  - The agent never applies a review: `respond` with `apply` is refused on agent frontends.
  - A new person door lets the signed-in person answer a review that an agent session in the same profile raised.
  - The desktop shows the review, worded by Cadrumo. Only a deliberate gesture of the person releases it, through an `aeat` child on the person's frontend.
  - This is new runtime authority and amends `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`.
- Tool permissions and questionnaires raised by cadrumo-agent are answered only through the host's commands behind a person gesture. The model cannot answer them.
- Consent stays a person act checked before every send.

**Processes**
- The Rust host owns the launcher through a new supervised runner, distinct from the short-call runner (`native/desktop/src-tauri/src/shell/sign_in/process.rs:23-27`). It places the launcher in a kill-on-close Job Object.
- The launcher starts the agent tree inside `WindowsProcessScope` (`src/cadrumo/adapters/local_runtime/windows_process.py:189-232`), so the gateway, the worker and `cadrumo-mcp` end when it ends, however it ends.
- Every stop trigger also stops the launcher: sign-out, lock, idle or absolute expiry, a key change, a profile switch, the runtime becoming unavailable, and window close.
- The gateway and worker take ephemeral loopback ports, reported in `agent_ready`.

**Writes**
- Mutating Cadrumo operations through the agent are tested only after cadrumo-agent's write-proof cases pass in its own tests: refusal, exactly once, worker loss and repeat. Until then the lane runs the full surface, and stage 1 acceptance covers reads, questionnaires, tool permissions and refused writes.

## Implementation

We will run the live lane as the packaged Cadrumo plus cadrumo-agent from its source tree, in four stages.

- **Stage 1, the agent column against the real backend.**
  - Cadrumo backend:
    - the person-frontend predicate and its matrix test;
    - the `agent-host` frontend;
    - the launcher on the provider-settings controller;
    - the root guard;
    - consent person acts;
    - the review person door, with `respond` apply refused on agent frontends.
  - Rust host:
    - the supervised runner and Job;
    - the loopback gateway client;
    - the command list behind `native/desktop/frontend/src/shell/agentSession.ts`, including questionnaires and approvals;
    - the stream mapped onto a Tauri channel.
  - cadrumo-agent:
    - ordered turn records with stable ids, a turn in progress in history, text offsets, the person turn id, and continued runs without duplicated turns;
    - answered questionnaires and decided approvals kept in history as turns: what was asked, and the person's answer or decision, so the conversation is auditable and a reload shows it;
    - an optional `provider` filter on the catalog;
    - the settled-run fix and the write-proof tests;
    - committing its relay change without deleting its proof route.
  - Webview: questionnaire and approval views, owned by the desktop design session.
- **Stage 2, writes.** Mutating operations through the agent, once its write proofs are recorded.
- **Stage 3, documents.** Parent contract 5.
- **Stage 4, production.** Encrypted agent stores retire L1. Bundling follows BUILD1's route: a lane lock, an agent statement, and a lane preset refused by Release configurations. Hosted start retires L2. The lane collapses into the parent record's packaged verification.

Remaining deviations:
- **L1.** Plaintext agent stores on the marked root only, and tool results in them are synthetic profile data.
- **L2.** The hosted parts are assembled from cadrumo-agent's source tree rather than through a hosted root.

Test framework:
- A Playwright driver attaches to the packaged desktop's WebView2 over a remote-debugging port. Only the lane build opens that port, and only on loopback.
- One set of specs runs against two hosts: the fixture host, which is fast and free, and the real lane.
- For iteration, the lane desktop may load its webview from the development server with hot reload, while the Rust host, launcher and agent stay real.
- Each run follows the `dev/runtime_lifecycle` pattern:
  - a fresh marked root;
  - the password on standard input only;
  - a Job;
  - a check that no started process survives;
  - the key scan;
  - exits 0, 1 and 3.
- It can also check outcomes in the backend, by reading the gateway's history and the Cadrumo record through `aeat`.

Stage 1 passes when, live:
- a typed message streams the reply;
- stopping settles the reply as `stopped`;
- a reload shows the same turns;
- a questionnaire is answered;
- a tool permission is decided by the person;
- the agent's attempt to apply a review is refused;
- a send without consent is refused;
- signing out leaves no process and no key in any scanned place.

These stage contents are hypotheses within the constraints.

## Rationale

Running cadrumo-agent from its source tree under its own assembly is the only configuration in which its relay mounts, by its own records and tests, and it makes every UI or agent change testable without repackaging. That serves the owner's speed ruling. The authority constraints close the holes the reviews found before the full surface is reachable. The process and root constraints keep a lane from touching the person's real profile or leaving processes behind. Gating writes on cadrumo-agent's own write proofs keeps a repeated write off even synthetic data until it is proven.

## Consequences

- Most of stage 1's cadrumo-agent items belong to that project. Its owner relays by hand; no direct channel exists from this session.
- The person review door and the person-frontend predicate are new runtime authority. They need owner acceptance through the mcp-parity amendment.
- L2 assembles cadrumo-agent's test-tree hosted parts in a lane. Its relay-mount and capability-proofs records must allow that for a synthetic profile, or the lane waits on hosted start.
- The key frame is a cadrumo-agent change: a frame read in `agent:api/app.py` main(), and the worker's pipe in place of `DEVNULL`. Stage 1 waits on it.
