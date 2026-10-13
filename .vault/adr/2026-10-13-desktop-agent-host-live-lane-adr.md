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

Not accepted. On 2026-10-13 the owner ruled first-hand on the tool surface: "I don't want read only tools. I want to verify that the agent platform is functional." That ruling is applied below. The owner also directed that this record is reviewed by the cadrumo-agent project and by Cadrumo's engineering sessions, and verified before any ruling on it: "I don't want you to improvise. You have to ask for reviews, ruling, check verifications." The remaining choices stay open for the owner.

## Problem Statement

On 2026-10-13 the owner asked for a running agent column they can use live against a real provider, "so we can for real begin working against the cadrumo api and agent backend". The production path in `2026-10-12-desktop-agent-host-adr` (proposed) needs encrypted agent stores, a key door, a recorded tool-server proof and bundling, and none of them is built. cadrumo-agent refuses every hosted start today. The development display on port 15370 runs the browser host, which serves nothing, so it can never run the agent (`2026-10-12-desktop-agent-host-reference`, fourth audit and live-lane reuse sections). This record decides how a real, interactive run happens before the production path is complete, without breaking the owner's 2026-10-12 rulings.

## Considerations

- The 2026-10-12 rulings bind: encrypted storage for private data, explicit consent naming the provider and the content, packaging through the normal build, no mock hosts, and the location supplied by Cadrumo (`2026-10-12-desktop-agent-host-adr`, Problem Statement).
- Synthetic test data may use ordinary storage. An observed plaintext gap with private data needs remediation, not a new storage exception (rule 05, private-data invariants).
- cadrumo-agent's non-hosted `serve` starts and streams a direct-lane turn today, with model ids taken from the Models API. Its hosted start is gated on a Cadrumo tool-server proof, and only a live, signed-in Cadrumo can record that proof (reference, fourth audit).
- Cadrumo can already stand a packaged bundle up on a fresh root with a synthetic profile, and admit an MCP server by a key the person issued, without the password (reference, live-lane reuse).
- An uncommitted change in the cadrumo-agent checkout moves its relay toward Cadrumo's served tools. Its owner is not reachable from this machine.

## Considered options

- **A development live lane (proposed).** Every component is real. The lane runs only on a storage root it created and marked, with a profile made there holding synthetic data. Three named deviations are allowed, each retired by a named delivery, and lane builds are the only builds that carry them. It gives live use within the first stage and builds the production pieces in production form.
- Wait for the full production path. This keeps every constraint, but there is no live use until contracts 3 and 4 and the tool-server proof land, and the last two belong to an unreachable owner.
- A browser development bridge that serves the host interface from the development server. Rejected: it is a second host implementation, it needs the CSP opened, and it exposes a signed-in profile on the network address the owner browses from.
- A live run on the person's own profile with plaintext agent stores. Rejected: it breaks the at-rest ruling.

## Constraints

Binding if accepted:

- Nothing under test is simulated:
  - the packaged desktop executable with its Rust agent host;
  - the launcher `aeat app agent serve`;
  - cadrumo-agent, built into the bundle from an explicit source path;
  - the Anthropic API and the Cadrumo runtime.
  There is no mock host, scripted model or stand-in.
- The lane runs only on a storage root that it created empty and marked as a live-lane root.
  - While any deviation is in effect, the launcher refuses a root without the mark, and refuses the per-user default root outright.
  - The person creates the profile on that root through the desktop's own flow, and it holds synthetic data only.
- The agent column shows a lasting notice: this is a development lane, conversations are kept unencrypted on this test root, and only synthetic data belongs in it.
- A build option, off by default and refused by release presets, compiles the deviations in. A release build has no code path for them.
- Allowed deviations, each named with what retires it:
  - **L1.** Agent stores, logs and the replay log are plaintext, under `<storage-root>/agent/<profile-id>/` only. Retired by contract 4 of the parent record (encrypted stores).
  - **L2.** cadrumo-agent runs in non-hosted mode with its `warn` proof policy. Retired by a recorded Cadrumo tool-server proof, which opens the hosted start.
  - **L3.** The Anthropic key and the gateway bearer reach the agent process through its own environment block. They never pass through the shell's environment, a file or a command line. Retired by the standard-input key frame.
- Everything else follows the parent record unchanged:
  - The shell holds no runtime connection, session or provider credential.
  - The provider key lives in Cadrumo custody, and only the admitted launcher receives it.
  - Consent is a Cadrumo person act, and the host checks it before every send.
  - Documents enter custody only.
- Only the direct Anthropic lane is offered. The host drops other providers from the catalog and never selects one. Model ids come from the catalog, which reads the Models API.
- A send the person makes in the lane is real private content to Anthropic. The consent prompt names Anthropic, the model and each item exactly as in production.

## Implementation

We will build a development live lane in four stages. Each stage builds the production pieces in their production form, and each stage retires a deviation.

- **Stage 1, a working agent.** Live chat with the full Cadrumo tool surface. There are no documents yet.
  - Cadrumo backend:
    - a stored provider credential, set by a person act with the secret on standard input;
    - the `agent-host` frontend;
    - the launcher's start, supervise and stop behaviour (parent contract 2, without encryption);
    - the agent root `<storage-root>/agent/<profile-id>/`;
    - consent grant, withdraw and list as person acts;
    - the live-lane mark check.
  - Rust host:
    - the launcher's lifecycle;
    - a loopback gateway client holding the bearer;
    - the closed command list behind `native/desktop/frontend/src/shell/agentSession.ts` and `shell/agentViews.ts`;
    - the stream mapped from gateway SSE onto a Tauri channel;
    - consent and credential acts through `aeat` children.
  - Webview: the wiring, owned by the desktop design session.
  - Tools:
    - The relay mounts `cadrumo-mcp --surface full` inside the signed-in profile, so the agent can read, run operations, and take reviews to the person.
    - The runtime still refuses the person's own acts on the MCP frontend (`src/cadrumo/application/operations/person_acts.py:1-24`). That is the accepted access rule, not a restriction added by this lane.
    - The first live run records cadrumo-agent's tool-access and tool-write proofs on this real Cadrumo. Recording them retires L2.
- **Stage 2, hosted mode.** The service restarts under its hosted root once the proofs are recorded.
- **Stage 3, documents.** Custody intake, conversation links and text projections (parent contract 5), with documents as consent items.
- **Stage 4, encryption.**
  - The SQLCipher stores and the key frame retire L1 and L3.
  - The mark check and the lane build option are removed.
  - The lane becomes the parent record's packaged-build verification.

Acceptance:

- Every stage is verified live on the signed-in Windows desktop by an opt-in, credit-spending project lane, and by the owner's own interactive use.
- Stage 1 passes when:
  - the agent completes a real Cadrumo operation that changes a record, with its review answered by the person, and the record reads back;
  - a typed message streams Claude's reply into the transcript;
  - stopping settles the reply as `stopped`;
  - a reload shows the same turns;
  - a send without consent is refused;
  - signing out stops the agent with no process left.

The stage contents are hypotheses that may change within these constraints.

## Rationale

The lane gives the owner live use at the first stage. It spends that effort on production pieces: the credential, the launcher, consent, the host commands and the wiring. Each deviation is confined to synthetic data on a marked, disposable root and named with the delivery that ends it. That satisfies the private-data rule as written, rather than opening a standing exception. Waiting would stall on work owned outside this machine. A bridge or a real profile breaks a ruling outright.

## Consequences

- The owner can use a real agent, with Cadrumo's full tool surface, once stage 1 lands. Hosted mode follows in stage 2, documents in stage 3, and real profile data only in stage 4.
- The notice informs the person but cannot stop them typing private information into the lane. The constraint relies on the person following it.
- The lane needs these remaining choices of the parent record settled first: the launcher identity, the Rust host owner, cadrumo-agent provisioning from a source path, model choice from the live list, and consent granularity. Each stays open for the owner. The parent record stays `proposed` for the production path.
- cadrumo-agent needs four things, to be raised through its handover:
  - a way to confine the catalog to the `anthropic` lane in non-hosted mode, so its other lanes' command-line handshakes do not run;
  - the relay change committed;
  - the joint access and write proof run;
  - the key frame and the encrypted stores.
- If the owner rejects any deviation, the lane waits for the delivery that removes it.
