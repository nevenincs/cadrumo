---
tags:
  - '#adr'
  - '#agent-attachments'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:f1e37902a0573bf0537869c94ec502101af10c761ef2f3c820a1f5801ac0a146'
related:
  - "[[2026-10-12-desktop-agent-host-adr]]"
  - "[[2026-10-13-provider-settings-adr]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - "[[2026-06-10-ledger-evidence-enforcement-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]"
  - "[[2026-10-10-mcp-parity-file-exchange-adr]]"
  - "[[2026-10-13-desktop-agent-host-live-lane-adr]]"
  - "[[2026-10-13-native-agent-adr]]"
  - "[[2026-10-12-desktop-agent-host-reference]]"
  - '[[2026-10-11-mcp-parity-full-parity-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]'
  - '[[2026-10-10-mcp-parity-approval-step-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
---

# `agent-attachments` adr: `Chat attachments enter Cadrumo encrypted custody and the agent reads them only as registered projections by opaque reference` | (**status:** `accepted`)

## Problem Statement

The desktop agent column lets a person add files to a conversation. Its "+ Add files" control is disabled until this record is decided. In cadrumo-agent today, an attachment is a plaintext file on disk:

- The host places the file at `<workspace_root>/attachments/<name>` (`cadrumo-agent: src/cadrumo_agent/control/attachments.py:56`). It then calls `POST /v1/conversations/attachments/register {workspace_root, name}` (`src/cadrumo_agent/api/routes/_gateway_attachment_endpoints.py:91-112`, `:152-158`; the request and response are at `src/cadrumo_agent/api/schemas/attachments.py:38-71`).
- Registration reads the file through one checked handle and returns its size and SHA-256 (`control/attachments.py:184-220`). It writes nothing: "the directory is the record". Listing and removal act on that directory (`:223-259`, `:262-276`). Files may be up to 50 MiB (`src/cadrumo_agent/domain_config.py:254-261`). Nothing is encrypted.
- The model reaches an attachment only through a workspace file-read tool, which returns UTF-8 text and refuses binary files. No message carries attachment content as a document block or an image block.
- A lane that runs its own program in the workspace can keep its own copy of anything it reads, outside cadrumo-agent's stores.
- Hosted runs are forced to run autonomously (`src/cadrumo_agent/api/routes/_gateway_run_start.py:169-180`), so relayed MCP tool calls run without a `permission_request`.
- Where permission options exist, cadrumo-agent always prefers the allow-once option over the remembering one.
- The workspace file read accepts any workspace path.
- Tool results are retained in run checkpoints. Nothing in cadrumo-agent's stores is encrypted today.
- `POST /v1/conversations/delete` (`api/routes/_gateway_conversation_endpoints.py:103`, which goes through `control/conversation_deletion.py`) removes the whole workspace. It has no hook that purges stored text for a single reference. With one workspace per profile, it deletes every conversation in the profile.

The result: the model cannot read an attached PDF or scan at all, and it can read a text file only from plaintext on disk. The owner has ruled that attachments must be encrypted.

This record decides five things:

- where attachment bytes live;
- how the model sees their content;
- what reaches the provider;
- how consent applies;
- how attachments are deleted.

## Considerations

- Owner ruling, first-hand on 2026-10-13, relayed by UI-DESIGN1: "we should encrypt attachments."
- The owner answered this record's open questions on 2026-10-13, first-hand, relayed by the coordinator:
  - Consent: "consent is that I see the message and click appvveo".
  - Page images: "I think that needs to be a user concent too to approve reading images by ht llms".
  - Scope: "once per session but concent should have two forms: allow once (so ever action is concented) and allow this session allow once and remembed choice for future asks. that is the norm in wevery agent ap".
  - The owner did not rule on deletion.
- `2026-10-12-desktop-agent-host-adr` (proposed) states: "No real document is written in plaintext to the agent root. Documents live in Cadrumo custody; the model reads only registered projections served by Cadrumo." Under that record:
  - Contract 5 links documents to custody with a typed conversation link and a role. It expands ZIP files in memory, within bounds. It produces text projections, and it deletes with holds.
  - Contract 1 keeps file paths in the Rust host, which hands them only to the `aeat` child that adds documents.
- Persistence is to secure storage only, with no exceptions. Decrypted bytes live only briefly in process memory (`2026-06-10-llm-evidence-classification-adr`, ruling 1). Evidence bytes ride in the encrypted attachment namespaces (`2026-06-10-ledger-evidence-enforcement-adr`, Decision 4).
- Source evidence bytes never enter MCP results; only registered projections cross to an agent host. Permission to read locally and consent to send a projection off the machine are separate (`2026-09-26-mcp-purpose-authentication-adr`, section "MCP discovery, output and replacement").
- The agent lives inside one signed-in profile and never handles a secret (`2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`). Provider keys and the agent data key reach the agent only on the standard-input frame (`2026-10-13-provider-settings-adr`, constraint 8).
- Owner rulings of 2026-10-13, recorded in `2026-10-13-provider-settings-adr`, constraint 8: "tool calls are approval gated not messages" and "do not prompt me to confirm action I did already".
- An off-host read is permitted only when four conditions all hold (`src/cadrumo/adapters/outbound/llm/consent.py:137-180`):
  - gestor mode is off;
  - the deployment has opted in;
  - the profile is eligible;
  - an acknowledgement exists for this call. Until now that acknowledgement was "never sticky" (`:155-157`).
- The consent token binds only a surface and a content address (`consent.py:183-201`; minted at `:259`). Today's extract operation mints it (`src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:150-176`, `:220`), and refuses an off-host acknowledgement from any frontend that is not a person's (`:282-284`). The consent ledger already records provider and model (`src/cadrumo/adapters/persistence/llm/consent_ledger.py:94-147`).
- Only the CLI and TUI frontends take a person's act (`src/cadrumo/application/operations/person_acts.py:52`).
- `2026-10-10-mcp-parity-approval-step-adr` (rejected) refused two routes: an agent approving its own act, and a host asserting an approval on the person's behalf.
- Cadrumo custody already holds content-addressed, encrypted attachment blobs and manifests:
  - The blob namespace is `FINANCIAL`, `PROFILE_LOCAL`, `FULL_CUSTODY_ONLY` (`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:809-818`).
  - The store is `src/cadrumo/adapters/persistence/storage/attachment.py:282-327`, and ingestion is `src/cadrumo/domain/attachments/service.py:114-135`.
  - The manifest links an attachment only to transactions and invoices (`src/cadrumo/domain/attachments/models.py:101-150`). Its `source_reference` may hold a path (`:139`).
  - `put_file` reads the whole file with no size bound (`attachment.py:305-313`).
- Reading on this machine already exists:
  - `DocumentTranscription` is held in memory only and refuses serialization (`src/cadrumo/application/ledger/document_transcription.py:125-150`).
  - The text-layer reader is `src/cadrumo/application/ledger/evidence_textlayer.py:107-128`.
  - Scans need the local vision transcriber from `2026-08-07-unstructured-document-ingestion-adr` (proposed).
  - No registered operation projects a transcription to a frontend.
- The plaintext exchange folder was rejected (`2026-10-10-mcp-parity-file-exchange-adr`).
- CMake builds the agent into the package (`2026-10-13-native-agent-adr`).

## Considered options

**A. Chosen: Cadrumo custody only.** The agent holds an opaque reference and reads registered projections through Cadrumo MCP.

- Files arrive in custody, encrypted, through a person act in the desktop.
- The agent gets an opaque reference for each file, plus display metadata.
- Content reaches the model only through an approved MCP projection call. Bytes are decrypted in memory for that call. Cadrumo then transcribes them on this machine or, with separate approval, renders page images.
- Cost: work for every party, and the model never sees the original file.

**B. Rejected: an agent-side encrypted store keyed by the frame-delivered key.**

- It creates a second custody of financial documents.
- It sends whole original files off the machine.
- It sits outside Cadrumo's deletion inventory, holds and consent ledger, and its files cannot be reused as ledger evidence.

**C1. Rejected by the owner's consent ruling: inline the projection into the person's message at send time.** Consent is seeing the approval card and clicking Approve. Attaching a file and sending a message is not consent.

**C2. Rejected: send raw source bytes to the provider as document blocks, fetched through MCP.** This reverses the rule that source bytes never enter MCP results.

**C3. Rejected: provider file-upload APIs.** The document would persist at the provider, beyond local deletion or holds.

**C4. Rejected: plaintext workspace files under operating-system encryption.** Any process running under the same account still reads them in plaintext.

**C5. Rejected: reviving the exchange folder.** It is plaintext by design.

**Approval mechanism.**

- **Chosen, (b):** cadrumo-agent wires per-call permission requests on every hosted lane it offers attachments on.
  - The owner ruled that tool calls in general are approval-gated, so this wiring is needed anyway.
  - Cadrumo still records and enforces the person's grant through an `aeat` person act, so the agent cannot fabricate consent.
- **Fallback, (a), favoured by UI-DESIGN1:** a review interaction raised by Cadrumo and answered through the person door for agent-raised reviews.
  - It is the fallback if (b) cannot be built.
  - It is not chosen because it depends on that cross-session door, which is still an open ruling (`2026-10-13-desktop-agent-host-live-lane-review-audit`, `review-door-for-agent-reviews`, UI-DESIGN2).

## Constraints

Binding:

1. **Custody is the only store.**
   - An attachment's bytes persist only in Cadrumo's encrypted attachment namespaces, in the profile the agent is bound to.
   - Nothing writes attachment bytes, transcriptions or page images to the agent root, a workspace, a temporary or scratch directory, a provider home, a log or the webview.
   - In hosted mode, cadrumo-agent refuses to register files from the workspace.

2. **Intake is a person act, and the path stays in the host.**
   - Files enter only through the desktop's file dialog, which runs in Rust, or through its drop target.
   - Drops are handled natively in Rust through Tauri v2 `WindowEvent::DragDrop`. The webview's default delivery of dropped paths is turned off. The webview receives only opaque handles and counts.
   - The Rust host passes paths only to an `aeat` child running the documents-add operation. That operation:
     - reads each file through one opened handle;
     - checks the handle, and enforces size and count ceilings before it allocates memory (`put_file` at `attachment.py:305-313` does not do this today);
     - takes the digest from the bytes it actually read;
     - records a safe display name and never a path;
     - stores no host path in `source_reference`.
   - ZIP files expand as contract 5 of `2026-10-12-desktop-agent-host-adr` sets out.
   - An agent cannot add a file, and no MCP request carries document bytes.

3. **Conversation link.**
   - Each attachment carries a typed link to one conversation of the bound profile, with the provenance mark `supplied by the person in an agent conversation`. The link is held encrypted in custody.
   - The conversation id is the contract-v2 `run_id` of the run-chain head, inside the per-profile `workspace_root` from `agent_ready`.
   - The first release has no role: contract 5 names one but gives no vocabulary for it, and nothing grounds one. Any future role will be a closed vocabulary, added by amendment.
   - The same bytes attached twice share one blob and carry two links.

4. **Opaque reference.**
   - The agent receives a random reference for each link. It never receives the content digest, the attachment id or a path.
   - Cadrumo resolves a reference only for the bound profile, and only while the link exists.
   - Any other reference is refused. The refusal does not say whether the reference exists elsewhere.

5. **Content reaches the model only as a registered projection.** There are two action kinds:
   - **Document text read:** text transcribed on this machine, paged, with the page count and the transcriber's identity.
   - **Page-image send:** page images that Cadrumo renders again from the document, never the source file's bytes. This kind applies only when no transcription made on this machine exists.

   For both kinds:
   - Bytes are decrypted in the runtime worker's memory for each call, then discarded.
   - A cached transcription persists only in encrypted custody.
   - No result carries source bytes, the digest or a path.
   - A document with neither a transcription nor a page-image grant is refused with `no_text_projection`. It is never returned as empty text.

6. **Consent: the person sees the approval card and clicks Approve.** Attaching a file and sending a message grant nothing, and need no prompt.

   The approval flow:
   1. The desktop receives cadrumo-agent's `permission_request` for a projection tool call.
   2. The desktop asks Cadrumo, through an `aeat` child, for the card fields for that reference, action kind, provider and model. Cadrumo returns:
      - display name;
      - media type;
      - page count, when known;
      - provider identity;
      - model id;
      - action kind;
      - whether a matching session or remembered grant already exists.
   3. If a matching grant exists, the desktop answers Allow without showing a card. Otherwise it shows the approval card, built only from Cadrumo's fields.
      - `permission_request` carries no tool input, so the card infers nothing from the frame.
      - For a page-image send, the card states that page images will be sent to the named provider.
   4. The card offers three choices and Deny:
      - **Allow once:** covers this action only.
      - **Allow for this session:** covers matching asks until the agent session ends, meaning sign-out, lock, expiry or the agent stopping.
      - **Allow and remember:** a persisted grant for future matching asks.

      On any Allow, the desktop records the grant in an `aeat` child, then answers the agent's permission request. On Deny, nothing is recorded.
   5. The agent's MCP call carries only the opaque reference, never an approval. The projection tool releases content only against a recorded grant that matches.

   A **matching** ask has:
   - the same action kind, either document text read or page-image send;
   - the same provider and the same model;
   - for document text reads, the same document as well.

   A page-image grant is therefore bound to a provider and a model, not to one document. The owner may narrow this.

   Where the person act is enforced:
   - Grants are recorded only by the desktop's `aeat` child, on the CLI frontend. The CLI is a person frontend (`PERSONS_FRONTENDS`, `person_acts.py:52`).
   - Every other frontend is refused with `person_act_required`, as off-host extraction already does (`invoice_evidence_extract_operation.py:282-284`).
   - Nothing on the MCP frontend, or on the proposed `agent-host` frontend, can create, assert or revoke a grant.
   - `PERSONS_FRONTENDS` is not widened.

   Grant storage and revocation:
   - Session and remembered grants are person acts, held in Cadrumo's encrypted custody. Cadrumo enforces them at the projection tool; the agent never does.
   - Session grants end with the agent session.
   - Remembered grants are listed in the agent panel's settings. The person can revoke one there through an `aeat` person act, and the revocation applies from the next projection call.
   - cadrumo-agent's own remembered permission never stands in for a Cadrumo grant.

   What is bound and ledgered:
   - Each grant and each consent token carries the action kind, provider, model and surface. For a document text read, it also carries the content address. `EvidenceConsentToken` gains the fields it lacks (`consent.py:197-201`).
   - Every release is the ledgered dispatch, whatever the grant's scope. The projection tool appends to the consent ledger (`consent_ledger.py:94-147`) before any text or image leaves Cadrumo. If the append fails, nothing is released.
   - Cadrumo cannot verify where released content goes after it reaches cadrumo-agent.

   Gate conditions:
   - A grant is refused, and a stored grant is not honoured, unless gestor mode is off, the deployment has opted in, and the profile is eligible (`cloud_evidence_read_permitted`).
   - Each failed condition has its own refusal code.
   - A model the person runs on this machine needs no grant.

   Why `2026-10-10-mcp-parity-approval-step-adr` (rejected) does not apply:
   - A grant is not an MCP `respond`, and MCP cannot reach it.
   - A grant is not a claim relayed by the host. The runtime executes it as a person act and enforces it at the projection tool.
   - Residual risk: the runtime does not authenticate a client's frontend kind (`2026-10-04-application-sign-in-adr`). The design therefore relies on the agent having no means to start a process, and constraint 7 requires that a lane offering attachments has none.

7. **Lanes.** Every lane cadrumo-agent offers attachments on must meet all three conditions:
   - everything the lane persists is kept under the agent data key;
   - every tool call raises a permission request with the three choices;
   - the lane's tools are Cadrumo MCP only, with no means to start a process or write files.

   Which providers and lanes meet them is cadrumo-agent's to decide and prove; Cadrumo makes no ruling on it. The backend serves a per-lane `attachments` capability from the provider catalog or host status. The column reads that capability and never hardcodes which lanes support attachments.

8. **Deletion and holds.**
   - Removing an attachment, or deleting a conversation, removes the link and its references. cadrumo-agent then purges stored projection content for those references.
   - Deleting one conversation removes only that run chain.
   - Bytes are removed only when nothing references them (no conversation, transaction or invoice link) and no legal hold covers them. This is contract 5's default; the owner did not rule on it and may change it.
   - Profile deletion and the all-profile reset remove everything, grants included.
   - Content already sent to a provider cannot be recalled, and the removal flow says so.

9. **Ledger use stays reviewed.** A conversation attachment is not ledger evidence until the person links or confirms it through the existing evidence operations. A projection read gives it no evidentiary grade.

10. **Typed refusals.** Refusals come from one closed set. The column words each code in all four chrome locales and never shows a failure as empty. The set is:
    - `no_text_projection`
    - `acknowledgement_missing` (no matching grant)
    - `reference_unknown` (does not say whether the reference exists elsewhere)
    - `document_removed`
    - `gestor_mode`
    - `cloud_upload_not_permitted`
    - `profile_not_eligible`
    - `lane_unsupported`
    - `file_too_large`
    - `too_many_files`
    - `unsupported_media_type`
    - `archive_refused`
    - `file_changed_during_read`
    - `not_signed_in`
    - `person_act_required`
    - `grant_revoked`

    Codes may be added by amendment. They are never replaced with free text.

Affected prior rulings:

- `2026-06-10-llm-evidence-classification-adr` was amended in place on 2026-10-13 under the owner's scope ruling. It now admits session and remembered scopes, bound to provider and model, with every release still ledgered and with revocation.
- These still need their own amendments:
  - `2026-10-12-desktop-agent-host-adr`, contracts 5 and 6 (owner: UI-DESIGN2);
  - `2026-09-26-mcp-purpose-authentication-adr`, to name the text and page-image projections;
  - cadrumo-agent's own records on attachments and hosting.

## Implementation

We will keep chat attachments only in Cadrumo's encrypted custody and give cadrumo-agent an opaque reference for each one. The model reads content only through an approved Cadrumo MCP projection, under grants that Cadrumo records and enforces.

Cadrumo backend:

- A documents-add operation that reads through one bound handle and enforces ceilings.
- The conversation link and the opaque reference.
- Text-read and page-image projection operations on the `full` MCP surface, served through `result_page`.
- A read that returns the card fields.
- Grant record, list and revoke operations, all person acts accepted only on `PERSONS_FRONTENDS`.
- An encrypted namespace for grants. Session grants are bound to the agent's lease.
- Provider, model and action-kind fields on `EvidenceConsentToken`.
- A consent-ledger append before every release.
- The per-lane `attachments` capability.
- The refusal set of constraint 10.
- Link removal and blob reaping that respect holds.
- Entries in the deletion and reset journals.

cadrumo-agent, owned by BUILD2. Items 2 and 4 are preconditions for every lane:

1. **Reference store.** Replace `control/attachments.py:184-276`, `api/routes/_gateway_attachment_endpoints.py:39` and `:91-158` with a store mapping each conversation id to its references and their metadata. Today the directory itself is the record (`:187`).
2. **Per-call approval on hosted lanes.** A `permission_request` before every relayed MCP call on every hosted lane offering attachments. Hosted runs stop being forced to run autonomously (`api/routes/_gateway_run_start.py:169-180`).
3. **The three choices.** `permission_request` offers Allow once, Allow for this session, and Allow and remember. Today the remembering options lose to the once-only option. The agent's own remembering never replaces Cadrumo's grant check.
4. **Encrypted stores.** Encrypt retained tool results and checkpoints, as contract 4 requires.
5. **Workspace read guard.** The workspace file read refuses `attachments/` paths. The old register route is refused in hosted mode.
6. **Per-chain deletion.** Deleting one run chain purges stored projection content for each of its references. This replaces the workspace-wide `conversations/delete` (`control/conversation_deletion.py`).
7. **Image relay.** Image content from the MCP page-image projection is relayed to the provider as image content in the tool result.
8. **Reference listing.** Tell the model which references a turn carries.
9. **Shipping.** Ship through the CMake-owned build.

Desktop, owned by UI-DESIGN1 and UI-DESIGN2:

- The file dialog in Rust, and native drop handling, as constraint 2 requires.
- The attachment well, with each refusal code worded.
- The approval card, with its three choices and Deny and the page-image warning. The card is skipped when Cadrumo reports a matching grant.
- The list of remembered grants, with revocation, in the agent panel's settings.
- Lane availability, read from the `attachments` capability.
- The removal flow, with its warning that content already sent cannot be recalled.
- "+ Add files" stays disabled until the prerequisites exist.

Hypotheses, free to change within the constraints: operation and namespace names, the reference format, the projection page size and image resolution, and whether the link extends the attachment manifest or sits beside it.

Verification, on the packaged build with a synthetic encrypted profile:

- After conversations that read a PDF and send page images, a byte scan finds no attachment content outside the encrypted stores.
- References belonging to another profile or conversation are refused.
- A projection with no grant is refused, and gestor mode always refuses.
- Every projection call on a hosted lane offering attachments waits on `permission_request`, and Deny prevents the call.
- A session grant ends at sign-out, lock, expiry and agent stop.
- A remembered grant survives a restart, and stops working once revoked.
- A grant attempted from MCP is refused with `person_act_required`.
- Every release appears in the consent ledger.
- Deleting one conversation leaves the others intact.
- A blob is reaped unless a hold or another link covers it.

## Rationale

Option A alone meets the owner's encryption ruling and the accepted rules together:

- Bytes stay in the one encrypted custody that deletion, holds and the consent ledger already cover.
- No source bytes enter MCP.
- The provider receives Cadrumo's reduced form of the document, never the file itself.

The owner's rulings settle consent. The card and its Approve click are the consent, and the three choices follow the norm the owner cited for agent apps. Grants are Cadrumo person acts, enforced at the projection tool and recorded in the consent ledger for every release. The agent therefore cannot grant itself consent.

## Consequences

- Attachments are encrypted at rest. They can be reused as ledger evidence after review, and deletion respects holds.
- The model sees Cadrumo's transcribed text or, with a separate approval, page images that Cadrumo renders. Layout and handwriting reach it only as well as Cadrumo renders them.
- The person decides at the scope they choose: one action, the session, or a remembered grant. Remembered grants persist until revoked. Content already sent stays with the provider under the provider's own retention.
- No lane offers attachments until BUILD2 items 2 and 4 land: per-call approval on hosted lanes, and encrypted agent stores. Until then, "+ Add files" stays disabled everywhere. Attachments also wait on:
  - Cadrumo's intake, projections and grants;
  - the agent's reference store;
  - the three choices;
  - per-chain deletion;
  - image relay.
- Reconsider if:
  - a lane proves it persists nothing in plaintext and cannot start processes;
  - the owner narrows page-image grants to one document;
  - the owner changes the deletion default.

Accepted 2026-10-13. It folds in the reviews by UI-DESIGN1, UI-DESIGN2, BUILD2 and tui-b3. The owner's first-hand rulings of 2026-10-13, quoted under Considerations, decide the open questions:

- "consent is that I see the message and click appvveo";
- "I think that needs to be a user concent too to approve reading images by ht llms";
- "once per session but concent should have two forms: allow once (so ever action is concented) and allow this session allow once and remembed choice for future asks. that is the norm in wevery agent ap".

Deletion was not ruled on, so constraint 8 applies the contract-5 default. Acceptance records the decision; it is not evidence that any of it is built.
