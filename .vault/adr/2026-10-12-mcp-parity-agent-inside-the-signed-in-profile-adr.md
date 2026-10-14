---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-12'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:e5ee415a3c47ad14df9dccf81d70bad820f5d2263624c560ddf4638ab148cfc5'
related:
  - "[[2026-10-11-mcp-parity-full-parity-adr]]"
  - "[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-07-08-mcp-protocol-hardening-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - '[[2026-10-10-mcp-parity-sign-in-doors-reference]]'
  - '[[2026-10-11-mcp-parity-audit]]'
---

# `mcp-parity` adr: `The agent works only inside the one signed-in profile and never handles authentication` | (**status:** `accepted`)

## Problem Statement

Under the parity ruling of 2026-10-11, the records were amended so that MCP carries whatever the command line carries. As a result an agent could sign in by password, take a typed secret or name one by reference, sign the person out, lock sessions, approve or request its own enrollment, enrol recovery, and reach installation acts such as listing, importing, repairing or resetting profiles. The owner rejected this on 2026-10-12. An agent that handles credentials puts secrets in its transcript and sends them to the model provider. An agent that can authenticate, or act outside the profile it was started in, can run against a locked profile or one the person never opened for it. The owner also restated that Cadrumo is a GUI application with a single signed-in profile. The accepted records still allow several profiles to be signed in at once.

## Considerations

- The owner, first-hand on 2026-10-12, quoted verbatim: "Please, on 6, revise all adrs and do not allow this to happen. THe agent should not be able toi opeartet against a locked profile. The data is encrypted in a securte srtorage, there's no sens in letting the agents opearte. I also explicitly demanded that the agent sessio nare coupled with the actual profiels. so if there's no logged in prfiles the agent simpley isn't even allowed to run. Cadrumo is aGUI app. There's only ONE proifle that can be actuive and logged in. TUI and CLI should be not bealbe to mopearte, nor the MCP if the user is not logged in. The tauri app already should emit signals to shot he login screen if the prfile login times out, inactive, or not profiel eixsts. The agent adheres to the design. .IOt sdoes not manage authentication. EXPLCIITYL forbdden to do that. It run only once the user authenticates. If the agent's sesion time out we treat ita s alogout event. The agent will never be able to login or manage autnhentiucation beceut he agent is alway inside a profile. It does not understand data outside the profile."
- Point 6, which that message refers to, given earlier the same day: "we should not let passwrods and screts travel in the trascscirpt or leave the local machine. There's a design concnern if the user is required to enter the password to the agents. this should nevr happen. In the cadrumo tui app th user shoul d manually login and authenbticate dand the agent should awlays operate against an iuncloed authed profile aqnd ask the user to authenticate if the profile locked or does not exist."
- The owner on API keys, the same day: "Do not retire API keys. API keys are outside of what I just descripbed. API keys give access to the agetns cli tui, etc access to a spcific user profile. For testing, you should explciitly exercie acpi keys to verify we can access and manage access = I'm assuming the runitme manages the api access also?"
- The runtime does manage API access. `2026-09-26-mcp-purpose-authentication-profile-access-adr` binds each key to a durable grant. In code:
  - Issuance: `src/cadrumo/application/user_profile/automation_approval_session.py:68-81` and `:119-125`, and `src/cadrumo_runtime/host/automation_execution.py:113`.
  - Scope: `src/cadrumo/application/user_profile/automation_enrollment.py:56-63` and `automation_administration_service.py:64-72`.
  - Expiry: `src/cadrumo/application/user_profile/access_contracts.py:132-147`, enforced at `session_authority_policy.py:180`.
  - Revocation: `automation_lifecycle.py:24-35` and `automation_lifecycle_service.py:362`, with the runtime wire type at `src/cadrumo_runtime/host/access_management.py:18-23`.
  - The person's commands: `config automation` (`src/cadrumo/entrypoints/cli/config/runtime_access_management_specs.py:52-317`).
  - Launch by reference: `cadrumo-mcp` takes `--profile-id` and `--credential-reference` (`src/cadrumo_harness/mcp/main.py:43-52`).
- In code the MCP server today does the following:
  - It takes a typed secret or a secret reference on `session`, `execute` and `installation` (`src/cadrumo_harness/mcp/protocol_contract.py:426-427`, `:491-550`, `:229-260`).
  - It signs in by password or key (`src/cadrumo_harness/mcp/runtime_adapter.py:679-700`).
  - It runs an enrollment flow in which the agent proposes its own scope, and the key is delivered into the installed automation store for the agent to name in `authenticate` (`runtime_adapter.py:747-890`).
  - It serves installation acts across profiles (`src/cadrumo_client/contracts/installation_requests.py:89-110`).
- The runtime keeps a host per profile (`src/cadrumo_runtime/host/profile_connections.py:116`, `profile_connection_admission.py:112`). A sign-in to one profile leaves another profile's sign-in in place (`src/cadrumo/application/user_profile/login_session.py:128-130`; `2026-10-04-application-sign-in-adr`, the 2026-10-06 profiles amendment). Several profiles can therefore be signed in at once today.
- The desktop shell polls `config sign-in-status` (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:618`, `observation.rs:14-30`). It withholds the TUI and shows its sign-in view when the person is signed out, when the state is unknown, or when no profile exists (`native/desktop/frontend/src/shell/signIn.ts:63-95`, `native/desktop/frontend/src/App.tsx:187-188`). It hands `PROFILE_LOCKED` to the TUI (`signIn.ts:97-101`). It has no event of its own for an expired or inactive sign-in, so it learns of one only when the poll reports the sign-in absent.

## Considered options

- **The agent works only inside the person's signed-in profile, or inside a profile through a key the person issued, and never handles authentication.** Chosen. It is what the owner ruled.
- **Parity of every act, authentication included, with secrets carried to the runtime's protected frame.** Rejected by the owner. It was the state after the 2026-10-12 amendments under `2026-10-11-mcp-parity-full-parity-adr`. Even a protected frame starts in the tool call, and so in the transcript.
- **Secrets named by reference in a tool call, never as text.** Rejected. The agent still decides which credential to use, and so it manages authentication.
- **Retire API keys and admit MCP only by resuming the sign-in.** Rejected by the owner: "Do not retire API keys."

## Constraints

Binding:

1. **No secret in the agent's path.** No password, key, recovery value or other secret travels in an MCP tool call, an MCP result, an agent transcript, or off the machine. No MCP tool has an argument that carries a secret, and none has an argument that names one by reference. The agent never names a credential. The person configures a credential, by reference, in the MCP server's launch configuration. An operation whose contract requires a secret is a credential act and is not an agent operation. On MCP it is refused with the typed sign-in result of constraint 3, naming the act as the person's. Managing a model-provider credential is a credential act whether or not the call carries a secret. That covers setting, replacing, removing or resetting one. Its masked status, which never returns the secret, is not. (Amended 2026-10-13 under `2026-10-13-provider-settings-adr`; before that a credential act was only an operation whose contract requires a secret.)
2. **The agent never authenticates or manages authentication.** MCP offers no sign-in by password, no sign-in by key from a tool call, no sign-out, no lock, no session listing or administration, no grant or key administration, no enrollment request or approval, no password change or reset, and no recovery enrolment. An MCP connection is admitted only in one of two ways:
   - by resuming the person's live sign-in for the active profile, through the runtime; or
   - by an enrolled API key the person issued for that profile and configured by reference in the server's launch configuration.

   Resuming the person's sign-in is not authentication by the agent. It couples the agent to a sign-in the person made.
3. **No sign-in, no agent.** With no live sign-in and no valid key, the MCP server answers the protocol handshake, the tool list and `status`, and nothing else. Every other call is refused with one typed result telling the person to sign in to Cadrumo. A locked profile, an expired sign-in and an absent profile get the same treatment. The agent never operates against a locked or absent profile.
4. **A timed-out agent session is a logout.** An agent session ends when the person's sign-in ends: by sign-out, by the idle or absolute deadline, by lock-down or by profile lock. It also ends when its own lease lapses. Either way it ends as a logout ends a session: nothing of it is kept, and no operation is admitted under it again. The agent does not renew it by authenticating. A later call is admitted only by resuming a sign-in the person holds at that moment, or by the configured key.
5. **Exactly one profile.** An MCP server is bound to one profile for its whole life:
   - With a key, the profile is the one the key was issued for.
   - Otherwise it is the profile of the sign-in it first resumes. Inside Cadrumo, the process that starts the server binds it, as `2026-10-10-mcp-parity-shared-sign-in-door-adr` rules.

   If the signed-in profile later differs, every call is refused, and the person starts a new agent session. MCP serves no installation acts and no profile acts outside the bound profile. That rules out listing, creating, selecting, deleting or importing profiles, resetting all profiles, and storage administration or repair across profiles. The agent never sees or acts on data outside its profile.
6. **One signed-in profile, and frontends only under it.** Cadrumo is a GUI application. At most one profile has a live human sign-in on a runtime at a time. The TUI, the CLI and MCP operate on a profile only while the person is signed in to it, or through an API key the person issued for that profile. A person's own password sign-in at the TUI, the CLI or the desktop is the person signing in and stays. A sign-in to profile B while profile A is signed in signs A out everywhere: A's human sessions, the agent sessions that resumed it, and the key sessions that depend on A's sign-in. Keys issued for A that work without a sign-in are not ended by it. (Amended 2026-10-13 and withdrawn the same day; see the note at the end of this record.) (Amended 2026-10-12 on the owner's ruling "i followw your recommedation"; before that whether a second sign-in was refused or ended the first was a hypothesis, and the plan applied ending it as a provisional default.) The desktop shell shows its sign-in view whenever the sign-in times out, goes inactive or is locked, or when no profile exists.
7. **API keys stay, managed by the runtime.** A key grants an agent, the CLI, the TUI or another client access to one specific profile. The runtime admits keys and manages that access: issuance, scope, expiry and revocation, as `2026-09-26-mcp-purpose-authentication-profile-access-adr` rules. The person issues, scopes, rotates and revokes keys from a signed-in human session on the CLI, the TUI or the desktop, never from MCP. A key session is not a sign-in, so it does not count against constraint 6. A profile-wide lock still suspends it. When the person issues a key with `config automation create`, on the CLI or the TUI, they choose its use, for an agent (MCP), and the data categories it may read. The key itself is the binding: results in those categories are released to whichever local MCP client presents that key. (Amended 2026-10-12 on the owner's ruling "i followw your recommedation"; before that the record did not say where a key's results are released, and a key issued from the CLI carried no disclosure, because the proposal was checked against a destination that `prepare_enrollment` had not yet minted (`src/cadrumo/entrypoints/cli/config/runtime_automation_request.py:108`, `src/cadrumo/application/user_profile/automation_administration_service.py:71`), so its MCP server could submit work but read no value back.)
8. **Parity inside the profile.** `2026-10-11-mcp-parity-full-parity-adr` holds for every operation inside a signed-in or key-admitted profile. Three kinds of act are not agent operations: authentication, session and access administration, and acts outside the bound profile. Withholding them from MCP is therefore not a parity refusal. The credential acts of constraint 1 are the same.
9. **Disclosures are summarised, and read in full on request.** The `status` and `session` replies, and any reply of the same kind, carry the count of the session's `effective_scope.disclosures` and a summary by category, not the full list. The full list is read on request through a paged read. Every frontend does the same, so this is parity and not a reduced result for the agent. (Amended 2026-10-12 on the owner's ruling "i followw your recommedation"; before that these replies carried the whole list, about 125,000 characters, over the output limits of agent clients.)

Fixed boundary, unchanged: nothing on any frontend sends anything to the tax agency.

Affected prior rulings, each amended in place on 2026-10-12 with a note of what it said before:

- `2026-10-11-mcp-parity-full-parity-adr`: constraints 4, 5 and 6, the affected-rulings paragraphs on the sign-in door and H8, the implementation, the hypotheses, the as-built notes and the consequences.
- `2026-10-10-mcp-parity-shared-sign-in-door-adr`: password sign-in, sign-out and lock on MCP, the enrollment tools, the session lifetime, and the binding to one profile.
- `2026-10-10-mcp-parity-parity-mechanism-adr`: admission of every operation, and storage administration on MCP.
- `2026-10-04-application-sign-in-adr`: the MCP password line and the sign-out line, the shared sign-in per profile, the 2026-10-06 profiles amendment, the 2026-10-09 admission amendment, and the 2026-10-12 parity amendment.
- `2026-09-26-mcp-purpose-authentication-adr`: the secret sentence and multiple served profiles.
- `2026-09-26-mcp-purpose-authentication-profile-access-adr`: the MCP row, enrollment steps 1 to 3, the secret paragraph and the 2026-10-12 parity amendment.
- `2026-07-02-agent-harness-refoundation-adr`: the 2026-09-26 amendment's secret sentence and the 2026-10-12 parity amendment.
- `2026-07-08-mcp-protocol-hardening-adr`: H8, the 2026-10-11 amendment of H8, and the security-practice line.
- `2026-10-04-desktop-shell-adr`: when the sign-in view is shown.

## Implementation

We will remove every credential and authentication act from MCP and bind each MCP server to one profile. The runtime will enforce a single signed-in profile, and the desktop will show its sign-in view on every loss of sign-in.

- **MCP surface.** Remove the `session` tool, the `installation` tool, the `authenticate` tool, and the `secret` and `secret_reference` arguments of `execute`. Remove the in-session enrollment tools, as confirmed below. Keep `status`, which reports whether a sign-in or key admits the server and, when none does, says to sign in to Cadrumo.
- **Runtime.**
  - Refuse password, key-presentation and enrollment frames from the MCP frontend.
  - Refuse every installation and session-administration request from the MCP frontend.
  - Refuse an operation that requires a secret on MCP.
  - Refuse, or end, a human sign-in to a second profile while another profile is signed in.
  - These refusals are keyed on the act, not on a frontend's choice. The frontend is a client claim, so the decisive control is that the MCP harness has no way to send these acts. The runtime refusal is defence in depth.
- **Desktop.** Show the sign-in view on expiry, inactivity, profile lock and absence, from pushed session events where they exist and from the status poll otherwise.
- **Tests.** Replace the tests that prove MCP sign-in, sign-out, lock, secret carriage and installation acts with tests that prove their refusal. The live-agent lane (`2026-10-12-live-agent-evaluation-adr`, proposed) exercises API-key access and its management with a live agent: the person issues a key, the agent works with it inside its scope, a call outside the scope is refused, and after revocation the agent is refused. Signing in and issuing the key are done by the harness acting as the person, never by the agent.

Confirmed by the owner: **remove the agent-initiated enrollment flow** (`authorization_prepare`, `authorization_request`, `authorization_poll`) from MCP. Keys are issued only by the person through `config automation` and given to the MCP server by reference in its launch configuration. (Amended 2026-10-12 on the owner's ruling "i followw your recommedation"; before that this was a recommendation to confirm with the owner, held to constraint 2 until confirmed.) The reasons:

- In it the agent asks for a credential for itself and proposes its own scope (`runtime_adapter.py:758-852`). It can also rotate its key through a grant change. It then names the delivered credential in `authenticate`.
- The secret itself never reaches the transcript, but the agent obtains, scopes and selects its own authentication. That is managing authentication under constraint 2.
- The person can already issue a key with `config automation` and start the server with `--credential-reference`, so nothing is lost.

Hypotheses, free to change within the constraints:

- The name and shape of the sign-in-required result.
- Whether `status` keeps its current name.

## Rationale

The owner ruled it first-hand and in terms that leave no exception. The data sits in encrypted custody. An agent that could open that custody, or carry the secret that opens it, would make the person's sign-in pointless. An agent bound to one profile it did not open cannot reach data outside it. Keys stay because the owner kept them and the runtime already governs them.

## Consequences

- An agent works only while the person is signed in, or through a key the person issued and can revoke. A locked or absent profile stops it with a message to sign in.
- No secret enters an agent transcript or leaves the machine through MCP. Credential acts are done by the person at the TUI, the CLI or the desktop.
- MCP loses the session, installation and authentication tools. The secret arguments of `execute` and the operations that need a secret go with them. This narrows MCP below the command line for those acts only, and constraint 8 says why that is not a parity refusal.
- Switching profiles means signing out first, and an agent session started under one profile does not follow the person to another.
- Reconsider if the owner wants agent-initiated enrollment back, or wants a timed-out agent session to sign the person out as well, which this record does not do.
- Acceptance records the decision. It is not evidence that any of it is built.

Accepted 2026-10-12 on the owner's first-hand instruction of that day, "Please, on 6, revise all adrs and do not allow this to happen".

Amended 2026-10-12 under `2026-10-12-mcp-parity-attended-live-sign-in-adr`: constraint 2 gains a third way to admit an MCP connection. A person holding a live, unpersisted password sign-in with `cadrumo-runtime session hold --profile-id UUID --password-stdin` approves that exact connection, identified by the process the kernel names, and it receives an attended child of the person's session. The agent still never authenticates, names a credential or sees a secret. The child ends when the person's session ends.

Amended 2026-10-12 on the owner's first-hand ruling "i followw your recommedation", which accepted the orchestrator's recommendations. The four defaults applied while the owner was away are confirmed and no longer provisional: (a) the MCP key-request flow is removed; (b) signing in to profile B signs A out, now in constraint 6, where it replaces the hypothesis that a second sign-in might be refused; (c) with no live sign-in and no valid key MCP answers only the handshake, the tool list and `status`, as constraint 3 says, the public reference and corpus queries included among what is refused; (d) an agent session timing out ends only that agent session, as constraint 4 and the consequences say. Constraint 7 gains the key issued for an agent and its release to the client presenting it, and constraint 9 the summarised disclosures with a paged full read. The off-host consent record keeps its schema: since commit `3f15f3bdcc` MCP cannot give off-host consent, so every recorded off-host consent is the person's. The attended route of `2026-10-12-mcp-parity-attended-live-sign-in-adr` stays as accepted.

Amended 2026-10-12, constraint 7. Adopted 2026-10-12 under the owner's instruction to follow the orchestrator's recommendations; awaiting the owner's explicit confirmation. A key issued for an agent stores its data categories as category grants bound to the key's destination, as `2026-09-26-mcp-purpose-authentication-profile-access-adr` now rules, and always includes profile values, on the owner's ruling of 2026-10-12 that "profile (user profile?) values must be readable writeable by the mcp, it is quite critical that agent can operate and modify userprofiels". Listing every projection instead named 289 disclosures, about 47 KB, against the 32 KiB automation inventory budget, so the person could not review the request. An agent session inside the profile, by key or by attended sign-in, patches the profile, mutates its fields and adds, updates and removes its rows, each against the revision it has just read; no human-only gate stood in the way, so no workbench or baseline ruling changed.

Amended 2026-10-13, constraint 7, extending the amendment above. Adopted under the owner's instruction to follow the orchestrator's recommendations; awaiting the owner's explicit confirmation. A key issued for an agent also stores its operations as one grant of every operation an agent may run, the person's own acts excluded, resolved against the live registry at admission, as `2026-09-26-mcp-purpose-authentication-profile-access-adr` now rules. Its stored proposal is 721 bytes, against about 47 KB listed and about 8 KB with category grants alone, and the person's review and inventory count listed disclosures by category and page the full list on request, so the inventory holds many agent keys.

Amended 2026-10-13, then withdrawn the same day on the owner's correction. On the ruling "there should be no agent capability at all if the user is not authenticated", relayed by UI-DESIGN1 after the desktop showed "Agent access you enabled stays on." following a sign-out, constraints 2, 3, 4, 6 and 7 and the consequences were amended so that an API key admitted only while the person was signed in, a sign-out, lock or expired sign-in ended every key session of the profile with its children, and the runtime refused a key with `sign_in_required` while nobody was signed in. The owner corrected that first-hand the same day: "incorrect, thats a defect: including ones that came in with an API key… the api key exists so that it isn't pegged to the login cycle". The constraints and consequences above are restored to their wording before that amendment. The ruling that no agent capability exists without a sign-in governs the agent Cadrumo itself hosts in the desktop; it does not govern keys the person issued, which still admit whether or not the person is signed in, and which a sign-out, lock, expiry or a sign-in to another profile does not end. The sign-out result keeps the persisted automation setting and reports separately, as `agent_access_remains`, whether an issued key can still admit an agent: true while automation is enabled and an active, unexpired key of an active unattended grant remains.
