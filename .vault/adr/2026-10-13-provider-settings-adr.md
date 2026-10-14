---
tags:
  - '#adr'
  - '#provider-settings'
date: '2026-10-13'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:c29f1815600aa42e6238d5a4793792bceef9a355dae5f97b0ccfff5dc6f9ef5a'
related:
  - "[[2026-10-13-provider-settings-reference]]"
  - "[[2026-10-11-mcp-parity-full-parity-adr]]"
  - "[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-adr]]"
  - "[[2026-10-04-canonical-environment-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-13-profile-session-lifecycle-successor-adr]]"
  - "[[2026-08-13-profile-state-aggregate-successor-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-10-12-desktop-agent-host-adr]]"
  - "[[2026-10-13-desktop-agent-host-live-lane-adr]]"
  - "[[2026-07-14-google-optional-adapter-boundary-adr]]"
  - '[[2026-10-13-provider-settings-desktop-contract-reference]]'
---

# `provider-settings` adr: `Each signed-in profile owns its model-provider credentials in encrypted custody, and they reach cadrumo-agent only on a standard-input frame` | (**status:** `accepted`)

## Problem Statement

Cadrumo reads model-provider keys only from the process environment (`src/cadrumo/core/config_llm_fields.py:52-63`). That makes one key serve every profile on the installation. Nothing lets a person set, replace or remove a key, and nothing ties a key's use to a sign-in. The desktop agent column needs cadrumo-agent to reach a provider under the signed-in profile. Extraction needs a key too. Today extraction and the agent would each find a key their own way, and the agent would get its key from an environment block. The owner wants the keys kept from exposure, and wants every provider credential cadrumo-agent supports to be manageable. Grounding: `2026-10-13-provider-settings-reference`.

## Considerations

- The owner approved the handed-over proposal and implementation outline, first-hand, on 2026-10-13: "Noted and agreed. Provde a handover promtp for the cadrumo design session to implement this work".
- The owner ruled, first-hand to this session on 2026-10-13, "do standard input frame". Provider keys reach cadrumo-agent only on a standard-input frame, never in an environment block. This supersedes the environment hand-off in the approved proposal.
- The owner, first-hand to this session on 2026-10-13: "whatever you're doing that is not a comprehe sive list of support api keys. there's a lot more cadrumo agent supports." The settings cover every provider credential cadrumo-agent supports.
- The owner, first-hand to this session on 2026-10-13: "Development mode is essential. how aelse woudl e be , you developing?" Development work, including agent sessions and the live-agent evaluation lane, must run with no manual step.
- The owner, first-hand to UI-DESIGN2 on 2026-10-13, as quoted in `2026-10-13-desktop-agent-host-live-lane-adr`: "DO NOT ALLOW MY API KEYS TO BE EXPOSED".
- Which providers cadrumo-agent supports, which credential kinds each takes, and which it serves in hosted mode are cadrumo-agent's own decisions (`2026-10-13-provider-settings-reference`). Cadrumo decides none of them.
- Encrypted per-profile custody, the session lifecycle and the profile state aggregate already exist and stay the authority (`2026-08-13-profile-password-custody-rollup-adr`, `2026-08-13-profile-session-lifecycle-successor-adr`, `2026-08-13-profile-state-aggregate-successor-adr`). The Google OAuth token namespace shows how a profile secret is held.
- The agent lives inside one signed-in profile and never handles a secret (`2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`). Operations that require a secret are already person acts (`src/cadrumo/application/operations/person_acts.py:76`). Removing a key needs no secret, so that rule alone would not keep it from MCP.
- The desktop host (`2026-10-12-desktop-agent-host-adr`, proposed) already routes the provider credential through Cadrumo custody, a launcher, the agent's standard input and the worker's standard input pipe. Its live-lane child record (`2026-10-13-desktop-agent-host-live-lane-adr`, proposed) withdrew its environment hand-off and now delivers the key on a standard-input frame, passed to the worker over a pipe, so it agrees with constraint 8.

## Considered options

- **Per-profile encrypted provider settings resolved by Cadrumo, handed over on a standard-input frame.** Chosen. It is the approved proposal with the owner's frame ruling and full catalog.
- **One installation-wide key from the environment, as today.** Rejected. It does not isolate profiles, the person cannot manage it, and in production it would read whatever the environment holds.
- **Settings owned by cadrumo-agent.** Rejected. The agent holds no profile identity or session, and extraction would need a second store.
- **Hand-off in the agent's environment.** Rejected by the owner's ruling "do standard input frame". Environment blocks are inherited by descendants and readable by same-account tools.
- **A Cadrumo-chosen subset of providers.** Rejected by the owner's ruling that the list must be comprehensive: it is whatever cadrumo-agent supports.

## Constraints

Binding:

1. **Profile ownership.** Provider settings belong to one authenticated profile. They are kept as one typed record per provider in a dedicated secure-object namespace that is SECRET, PROFILE_LOCAL and PROCESS_LOCAL, after `GOOGLE_OAUTH_TOKEN_NAMESPACE` (`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:868-876`). Each record is written with a guarded revision. Each carries an opaque generation that is not secret and is never derived from the key. No credential goes into profile facts, global `Settings`, plaintext files, run definitions or prompts.
2. **Record shape.** A record holds:
   - its schema version and its provider;
   - `assistant_auth`, one of `direct_api`, `provider_sign_in` or `disabled`;
   - `credential.state`, one of `unset`, `configured` or `disabled`;
   - the credential material its kind requires, present only when `configured`, and an optional base URL, which is not secret;
   - preferences that are not secret and are validated;
   - its generation and `updated_at`.

   An absent record means `unset`. A record that is corrupt, unreadable or stale refuses; it never reads as absent.
3. **Provider catalog.** Cadrumo keeps no list of providers or lanes anywhere: not in data, code, settings fields, environment declarations, fixtures or tests. Which providers exist, their descriptors below, and which are selectable are cadrumo-agent's capability. Cadrumo obtains them from cadrumo-agent at run time, through the agent's own provider catalog, and stores credentials for whatever providers it reports. Every provider-specific name is constructed from the provider id the agent reports, never enumerated: the development environment value is `CADRUMO_LLM_<PROVIDER>_API_KEY`, and the record is keyed `{provider_id}`. Cadrumo decides nothing about which providers exist, which lanes they serve, which are hosted or which are proven, and gates nothing on it. When cadrumo-agent cannot report its providers, provider settings report that plainly, and the failure is not hidden behind a stored copy. (Amended 2026-10-14 on the owner's first-hand ruling: "we should not maintain any lists of providers … that is capability that is to be derived from the cadrumo-agent"; "user profile settings are constructable PREFIX_<provider>_API_KEY". Before that, the catalog was a committed, generated Cadrumo data file.)
   - `auth_kind` is one of `api_key`, `api_key_with_base_url`, `oauth_token_or_provider_sign_in` or `provider_sign_in_only`, as cadrumo-agent declares for each provider.
   - Each provider has a `display_name`, its brand name, the same in every locale.
   - A provider may carry a catalog `default_base_url`. The person may store a `base_url`. The effective URL is the stored one, else the default. A provider with no default refuses a key stored without a base URL.
   - Each provider names its `agent_credential_id`, the id cadrumo-agent keys that credential by, as cadrumo-agent declares it.
   - Each provider that takes a key has the development environment value constructed from its id, as above.
4. **Two axes.** How the assistant authenticates is a choice separate from the stored direct credential. Choosing provider sign-in never erases a stored key. Extraction always uses a direct key; a CLI subscription is not an extraction key. Provider CLI sign-in stays provider-owned in its redirected home. Cadrumo never imports, stores or encrypts that credential. (Superseded in part on 2026-10-13 by constraint 11.)
5. **Resolution.** Storage mode, as `detect_storage_mode` decides it (`src/cadrumo/core/storage_environment.py:288`), selects the path:
   - **Development mode.** A provider whose profile record is `unset` takes its key from the Cadrumo environment value constructed for that provider, with no manual step. This happens only after profile authentication. Status reports the source as `environment` automatically. Development sessions running from a checkout use this path.
   - **Lanes that run a packaged copy** are installed mode, so they have no fallback. This covers the live-agent evaluation lanes and the desktop agent lane. Each such lane's harness stores the developer's key into its throwaway profile through `aeat config provider set --secrets-stdin` before the run. The person still takes no manual step, and the run exercises the real set path. (Amended 2026-10-13 after review by the other sessions; before that this constraint said agent sessions and the live-agent evaluation lane use the development path, which is not true of a packaged copy.)
   - **Installed and release builds** have no environment path at all and no fallback. `unset` means unavailable.
   - In both modes a stored `configured` credential is used first. A persisted `disabled` blocks the fallback.
   - No `.env` file is loaded automatically anywhere.
6. **Actions and status.** Each provider has three actions, and all three are the person's acts:
   - **Set or replace.** Stores the key. The base URL is set with `--base-url <url>`, reverted to the catalogue default with `--clear-base-url`, and kept when neither is given. Changing only the base URL still takes the key, because the record is written as one unit. (Amended 2026-10-13 after review by the other sessions; before that the base-URL behaviour was unstated.)
   - **Remove.** Persists `disabled`, which blocks the environment fallback.
   - **Reset.** Returns the provider to `unset`. In development this re-enables the fallback; in an installed build `unset` means unavailable.

   There is no separate "use development environment" action. Every action:
   - is served by human frontends only;
   - takes the secret on the protected standard-input or secret channel, never in argv;
   - sends the `revision` it read as its guard;
   - is enrolled with the person's acts at application dispatch, so the runtime refuses it on MCP and through generic `execute`, not merely leaves it unlisted.

   Setting only stores the key. There is no remote validation, and readiness stays `not_verified` until first use. A key the provider rejects surfaces as a typed refusal from the consumer that used it, distinct from a storage error. A masked placeholder is never accepted as a new value.

   A single status read lists every provider. It is an ordinary read on every frontend. The envelope is `{development, providers}`, where `development` says whether the environment fallback applies. (Amended 2026-10-13 after review by the other sessions; before that the envelope did not say which mode applied.) Each entry carries:
   - `id`, `display_name`, `auth_kind` and `consumers`;
   - `mode`, one of `key`, `oauth_token`, `provider_sign_in`, `disabled` or `unset`;
   - `available` and `source` (`profile`, `environment` or `none`);
   - `readiness`, one of `ready`, `not_verified`, `missing`, `disabled`, `sign_in_required` or `unusable`;
   - an optional `reason`;
   - `default_base_url`, and `base_url` when the person stored one;
   - `revision`.

   Every field is a closed enumeration, starting from the values listed. `reason` is a closed code set covering each state that is not ready and each refusal. Status never returns the secret or a reversible fingerprint of it. The webview words every value except `display_name` from its stable id.

   Typed refusals for the actions are `not_signed_in`, `profile_locked`, `invalid_key_format`, `base_url_rejected`, `revision_conflict`, `committed_readback_failed`, `person_act_required` and `unknown`. `person_act_required` is returned when a frontend that may not change credentials, such as MCP or generic `execute`, asks for one of these actions.

   This is a narrow exception beside `2026-10-11-mcp-parity-full-parity-adr`; every business operation is unchanged.
7. **Desktop.** The desktop manages provider settings only through `aeat` children, the same pattern as its sign-in view, which runs `aeat config login --secrets-stdin` (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:174`, `:589-607`):
   - The key goes from the input straight to the child's standard input. The shell keeps no copy and holds no runtime connection, and nothing ever reads the key back.
   - The webview shows masked status only.
   - The agent panel reads the same status. It shows a provider with no usable key as unavailable, with a pointer to profile settings. Status is authoritative for what is configured. A refusal from the running agent is authoritative for the run in progress. After a change they can differ until the agent restarts with the new frame. (Amended 2026-10-13 after review by the other sessions; before that the record did not say which one wins.)
   - With no runtime connection in the shell, there is no push signal. Status is read on demand only: when the panel opens, before an agent send, after the person's own act, and on a sign-in or profile change. Nothing polls periodically.
   - The CLI publishes the command names, JSON output shapes and typed refusal codes of constraint 6 as the contract the desktop relies on, recorded in `2026-10-13-provider-settings-desktop-contract-reference`.
8. **Hand-off to cadrumo-agent.** An app-owned controller resolves credentials under the exact profile, login generation and settings generation. It writes the selected credentials once, on a bounded standard-input frame, when it starts the agent.
   - The controller runs in the runtime's profile host and binds the agent tree to the requesting session, in a kill-on-close job. No key ever crosses to a client process. The thin client `aeat app agent serve` only asks the runtime to start the agent and holds the session. (Amended 2026-10-13 after review by the other sessions; before that the controller was the client launcher that `2026-10-12-desktop-agent-host-adr` proposes.)
   - The frame is keyed by `agent_credential_id`. It also carries the gateway bearer that the desktop host minted. A provider-owned sign-in is never placed in it. The host accepts a ready line only for hosting contract version 1. (Amended 2026-10-13 after review by the other sessions; before that the frame carried provider credentials only.)
   - The launch image in every agent integration lane is the bundled agent, using the package's own interpreter and the installed agent's declared CLI module. CMake alone acquires, builds and installs that dependency; no `--agent-source` checkout or alternate Python environment is admitted. The `cadrumo-mcp` relay is launched as the running package's own entrypoint, by absolute path from the package inventory, with the pinned storage root, and never by a bare name. (Amended 2026-10-13 on the owner's subsequent native-build brief: the earlier amendment proposed `-m cadrumo_agent serve` and a development source-checkout exception; the pinned agent instead declares `cadrumo_agent.cli.main` as its CLI module.)
   - The key is never placed in an environment block, file, argv, log, transcript, trace, crash output, webview, model context or tool result.
   - Cadrumo children on the agent's path, such as the `cadrumo-mcp` relay, never receive a key.
   - cadrumo-agent reads the frame and passes keys to its worker over a pipe. That is cadrumo-agent's change, owned by its author.
   - The agent receives no profile identity, password, receipt or session policy, and gains no settings store.
   - Holding a usable key adds no consent per message and no grant before an agent run. The only gates are tool-call approvals (cadrumo-agent's `permission_request`) and Cadrumo operation reviews. This follows the owner's ruling of 2026-10-13, relayed by UI-DESIGN1: "tool calls are approval gated not messages", and "do not prompt me to confirm action I did already". Document-extraction consent bound to source bytes is unchanged.
9. **Lifecycle.**
   - Sign-out, lock, idle or absolute expiry, host loss and a credential change all do the same: close admission, discard stale results, cancel with a bounded grace period, stop and reap the whole agent tree, and retire scoped extraction clients. Rebuilding uses committed values only. A restart that fails reports stored-but-unavailable and never reuses the old key or process.
   - When authentication of candidate profile B fails, profile A is kept.
   - When it succeeds, A's work stops before B's pointer is published, at one canonical cross-process barrier that covers every entrypoint. Concretely, A's human sessions are retired, and their agent trees are stopped, after B's authentication succeeds but before B is admitted or its receipt minted. (Amended 2026-10-13 after review by tui-b3; before that the record named only the barrier; the runtime today retires A after admitting B.)
   - The agent tree is keyed to the exact human lease that started it. An attended child's routine retirement between reissues never stops it. A runtime stop or drain reaps it as surely as a retirement does. The retirement funnel only enqueues a non-blocking stop and never raises back into the funnel; a separate bounded owner does the cancel and reap, and runtime shutdown waits for that owner. (Amended 2026-10-13 after review by tui-b3; before that the record did not say where the stop runs.)
   - The agent host watches its lease's idle and absolute deadlines itself, because expiry is otherwise noticed only when requests arrive. It reads the deadlines without refreshing them, and it never re-mints or extends a receipt. (Amended 2026-10-13 after review by tui-b3; before that the record did not say who observes expiry.)
   - Work is bound to the exact login and configuration generations; a bucket identity alone is not enough.
   - Background polling never refreshes the idle deadline.
10. **Portability.**
   - Credentials are durable on this machine only. They are excluded from portable export, from remote mirroring (`remote_mirror_policy` `LOCAL_ONLY`) and from restorative backup. After a restore the person enters them again.
   - The namespace is enrolled in inventory, deletion, reset and uninstall.
   - Removing a key locally does not revoke it at the provider, and does not erase backups taken earlier.

11. **Owner rulings of the afternoon of 2026-10-13, first-hand, relayed by UI-DESIGN1.** These supersede the parts of constraints 3, 4 and 7 they contradict. (Amended 2026-10-13; before that the record served extraction as well, had one entry per provider, and placed the settings in the profile area.)
   - "The cadrumo app has no API keys to use, it doesn't make any sense. API keys are for MCPs that operate outside of the cadrumo application." Provider settings serve the agent's lanes only. The `extraction` consumer and the extraction-only entry are dropped. Cadrumo's own document reading keeps its existing key handling until the owner rules on it, and plan step P03.S12 is held for that ruling.
   - A provider reached both by API and by CLI is two separate entries that both need to be exposed. Each lane cadrumo-agent declares is its own entry with `transport` `api` or `cli`, taken from cadrumo-agent's declaration. `display_name` is the product name. A `cli` entry also reports whether its program is installed and signed in, without reading the provider's own credential files.
   - "The AI settings are bound to the agent panel." The desktop shows provider settings only in the agent column, not in profile management or sign-in.
   - "The user profile schema needs to be extended and enriched with the API keys." The user profile schema declares the provider-settings section. Its secret values are held only in the SECRET namespace of constraint 1. They are never profile facts, never readable through profile reads, MCP or the agent, and never exported.
   - "We have already established that the agent operates against a signed-in user profile, so there should be no agent capability at all if the user is not authenticated." This covers the agent Cadrumo itself hosts: signing out, a lock or expiry of the person's sign-in stops the desktop's agent tree (constraint 9). It does not cover API keys the person issued. Owner correction, first-hand, 2026-10-13: "the api key exists so that it isn't pegged to the login cycle". A key-admitted session survives sign-out, and a key admits whether or not the person is signed in. The sign-out result reports `agent_access_remains` truthfully: true while an issued key can still admit. (Amended 2026-10-13 on the owner's correction; before that this bullet also ended key-admitted sessions at sign-out and amended `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` accordingly, which was withdrawn.)

## Implementation

We will add typed records under Cadrumo's domain, application and persistence layers, and read the provider catalog (providers, kinds, base URLs and consumers) from cadrumo-agent at run time, never from a committed copy (amended 2026-10-14, constraint 3). We will build one resolver bound to the exact session generation, and route extraction and every `LLMClient` construction through it. We will build the hosted-agent controller with a single seam that writes the standard-input frame, and integrate the lifecycle barrier with the runtime's one-signed-in-profile rule (`src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:126`). The plan `2026-10-13-provider-settings-plan` sequences this work.

Hypotheses, free to change within the constraints:

- The namespace name (`cadrumo.provider_settings`), the object key (`{provider_id}`) and module placement (`domain/provider_settings`, `application/provider_settings`, `adapters/persistence/provider_settings`).
- Whether preferences later split into a portable record.
- The frame's exact field layout, within constraint 8. (Amended 2026-10-13: the controller's placement is no longer a hypothesis; constraint 8 now fixes it in the runtime's profile host.)
- The frame's field names, which follow the hosting-contract version that cadrumo-agent publishes.

## Rationale

Cadrumo already owns encrypted per-profile custody and the sign-in lifecycle, so the credential belongs there. An agent-side or installation-wide store would duplicate that authority or lose profile isolation. Making credential management the person's act keeps secrets out of agent transcripts, as the agent-inside record already requires. A standard-input frame is the only hand-off the owner allowed. It is also the one channel a descendant process does not inherit.

## Consequences

- A person manages every supported provider's credential per profile, at the TUI, the CLI or the desktop. An agent can read masked status but cannot change a credential.
- Installed and release builds stop reading provider keys from the environment, so installations that relied on `CADRUMO_LLM_*` must enter keys in the profile. Development checkouts keep working from named environment values with no manual step.
- cadrumo-agent must add a frame reader and a worker pipe before hosted use. Its provider-settings and hosting-contract records need amending in its own vault.
- Restoring a profile loses its provider keys by design.
- Secrets held in process memory, provider CLI files and the agent's existing plaintext history are outside this record's at-rest guarantee.
- Reconsider if the owner wants portable credentials, production environment fallback, or provider CLI credentials held by Cadrumo.

Accepted 2026-10-13 on the owner's first-hand approval of the design that day: "approved". It had been proposed earlier that day for review by the other sessions, on the owner's instruction. That review continues, and its findings arrive as amendments to this accepted record.

The basis also includes the owner's approval of the handed-over proposal on 2026-10-13, "Noted and agreed. Provde a handover promtp for the cadrumo design session to implement this work", and the rulings of the same day:
- "do standard input frame";
- "whatever you're doing that is not a comprehe sive list of support api keys. there's a lot more cadrumo agent supports.";
- "Development mode is essential. how aelse woudl e be , you developing?".

Acceptance records the decision. It is not evidence that any of it is built.

Affected records, amended in place on 2026-10-13, each with a dated note of what it said before:
- `2026-10-11-mcp-parity-full-parity-adr`, constraint 1: managing a provider credential is a person's act, refused at dispatch on MCP and generic `execute`.
- `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`, constraint 1: managing a provider credential is a credential act even without a secret.
- `2026-10-04-canonical-environment-adr`, the "Scope exclusion" constraint: installed builds read no provider key from the environment; development storage mode falls back for unset records.

Not amended by this record: `2026-10-12-desktop-agent-host-adr` and `2026-10-13-desktop-agent-host-live-lane-adr` belong to another session. Both agree with constraint 8. The live-lane record now delivers the key on a standard-input frame; its environment wording survives only as historical owner quotations. The desktop design sessions (UI-DESIGN1 and UI-DESIGN2) own the desktop side: the Tauri host commands and the webview, including the profile settings section and the agent panel's status.
