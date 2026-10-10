---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:83ed81d62c18c064820619546721bd20e3cf7e447324cb0ef8cc14ebc8e1b126'
related:
  - "[[2026-10-10-mcp-parity-file-exchange-reference]]"
  - "[[2026-10-10-mcp-parity-admission-rulings-adr]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-adr]]"
  - "[[2026-10-10-mcp-parity-approval-step-adr]]"
  - "[[2026-10-10-mcp-parity-admitted-surface-defects-reference]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - "[[2026-06-10-ledger-evidence-enforcement-adr]]"
  - "[[2026-08-13-secure-storage-hardening-successor-adr]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-08-03-canonical-storage-management-adr]]"
---

# `mcp-parity` adr: `Files pass between an agent and Cadrumo only through a per-profile exchange folder, by name and digest, under one standing consent` | (**status:** `proposed`)

## Problem Statement

Many registered operations read a file from, or write a file to, a path on the runtime host. The runtime opens the path itself and nothing checks where it points. The owner has ruled that an agent operates the person's data, and the admission record admits these operations "pending file exchange". Until that is decided, an agent can bring in no statement, invoice or PDF and can receive no export. This record decides where such files may be, how long plaintext stays there, how the path and the content are bound, what an agent's file is marked as, and what the person consents to once and approves each time.

Records named `2026-10-10-cadrumo-integration-...` belong to the vault of the cadrumo-agent repository, a separate project; they are cited by name and are not in this vault.

## Considerations

Code facts and the owner's words are in `2026-10-10-mcp-parity-file-exchange-reference`.

- No file-taking operation checks where a path points beyond an extension list, an absolute rule on some fields, and existence tests (`2026-10-10-mcp-parity-admitted-surface-defects-reference`, section 3).
- The project rule persists private payloads only through encrypted custody, says a path is not persisted evidence, and requires an export to follow a declared authorization, destination and lifetime.
- The owner ruled that the assistant's per-profile folder is plaintext, keyed to the profile and "Beside encrypted storage", and that attached documents may go to the hosted provider under "one standing consent" (`2026-10-10-cadrumo-integration-owner-rulings-research`). Both rulings are narrower than this record: the first is about the assistant's own data root and the second about a hosted model reading attachments.
- The owner ruled that an agent originates the reconciliation import and operates every ledger operation, with the person reviewing findings and approving sensitive acts (`2026-10-10-mcp-parity-admission-rulings-adr`).
- An accepted record says source evidence bytes do not enter MCP (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:166`).
- The taxonomy already has a profile-keyed root beside the bucket, the keystore, and one plaintext area, the console workspace, which all profiles share.
- The custody inventory digest and the profile-deletion steps cover the capsule and named artefacts only. A new area beside the bucket is seen by neither until enrolled.
- Statement import already has a digest hand-off between preview and apply. It is optional and only the terminal interface uses it.
- Evidence add and the reconciliation import have no size ceiling. The reconciliation import records the path string as its evidence reference.
- The modelo export sink already stages, refuses to replace, and publishes atomically. The ledger export and the audit ZIP do not use it.
- The frontend is declared by the client and cannot be verified. The owner has ruled that same-account reach is not a security concern.

## Considered options

- **Leave paths free for agents.** No new machinery. Rejected: an agent could read or overwrite any file the account can reach, and results would carry host paths.
- **Send document bytes in the request.** No folder. Rejected: it reverses the accepted rule that evidence bytes do not enter MCP, and a model cannot reproduce a binary file as tool-call text, so the digest would not bind the person's file.
- **Reuse the console workspace.** It exists. Rejected: one directory serves every profile and is the terminals' working directory.
- **A plaintext member inside the encrypted bucket directory.** Deleted with the profile for free. Rejected: the owner ruled beside, not inside, and every reader of the capsule would have to learn to skip it.
- **Confine an agent to the hosted assistant's own root.** What the consuming project expected. Rejected: that root's layout belongs to its service, the host removes nothing there, its files are working copies the assistant may change, and other MCP clients have no such root.
- **Clear the folder at sign-out.** Shortest plaintext lifetime. Rejected: a screen lock or an idle deadline would destroy files waiting to be ingested and exports not yet collected.
- **A per-profile exchange folder beside the encrypted storage, inbound and outbound apart, named by relative name and bound by digest.** Chosen.

## Constraints

Binding:

1. **Scope.** This record governs every registered operation that reads or writes a host file when an agent caller asks. An agent caller is a connection that declares the MCP frontend, or a process inside a hosted assistant's process tree whatever frontend it declares. How the runtime recognises the tree is decided in `2026-10-10-mcp-parity-approval-step-adr`, which is proposed. The live capture operations write encrypted stores under their own root and are not file exchange.
2. **The folder.** Each profile has one exchange folder. It is plaintext. It sits beside the profile's encrypted bucket, never inside it and never inside the hosted assistant's own root. The storage taxonomy declares it as a fixed, profile-keyed location, as it does the keystore. It has two children, inbound and outbound.
3. **Who creates it.** Cadrumo's runtime creates it, for the exact profile, with owner-only permissions, once the standing consent of line 13 is recorded. No caller creates or relocates it. A folder that is absent, or reached through a link, is refused.
4. **Two directions.** Callers place files in inbound; Cadrumo reads and removes them and writes nothing there. Only Cadrumo writes to outbound. Inputs are read from inbound. The one exception is an artefact Cadrumo wrote to outbound that a later operation continues from, such as a review package to sign; that request carries the digest Cadrumo reported, and a mismatch is refused.
5. **Confinement.** An agent caller names a file by a relative name. The operation opens it under the profile's folder and then checks the opened handle, not the path text: it is a regular file, it lies beneath the folder root, and no link, junction or redirect was followed. A write checks the parent directory the same way, stages in that directory, and publishes without following a link and without replacing an existing file. An absolute path, a parent step, or a name that lands elsewhere is refused before any byte is read or written. The check lives in the operation and runs for every caller and every frontend; callers differ in their permitted roots, never in whether the check runs.
6. **Content binding.** Cadrumo computes the digest from the bytes read through that handle: one open, no second read by path, so the bytes hashed are the bytes parsed or stored. A digest the caller sends is an expectation to compare, never the recorded identity. Where an operation has a preview and an apply, an agent caller's apply carries the digests the preview reported, and the operation refuses a file whose bytes differ. Every file-taking operation declares a size ceiling and a count ceiling and enforces them at the handle before it allocates; an operation without them is not admitted.
7. **What is recorded.** A record made from an exchanged file identifies it by a safe base name and by the digest and size Cadrumo computed. A result returned to an agent caller carries the name and the digest, never an absolute path. No record uses a path as its evidence reference.
8. **Provenance mark.** A record made from a file an agent caller submitted is marked as supplied through an agent. The mark comes from the session, never from a request field such as `actor`. A file is marked as supplied by the person only where Cadrumo itself recorded the person handing over those exact bytes; it is never inferred. The mark raises no evidentiary grade: a receipt still passes its digest, CSV, model and period, taxpayer and filing-chain checks before promotion.
9. **What an agent may originate.** Any file kind the admitted operations accept: statements, invoice books, invoice and receipt evidence, the PDFs the local imports read, and package envelopes. That includes the evidence-grade imports, as the owner ruled. An agent's file never stands in for the person's review, confirmation, attestation or signature; those stay behind the person's approval as the admission record rules.
10. **No document bytes in a request.** On the MCP frontend no document travels in a request or a result, in either direction. No result, page or resource returns evidence bytes or an exported file's bytes. A document reaches Cadrumo only as a file in inbound. Structured text that an operation already takes as an operand, such as the classification CSV, is data the agent composes and is unchanged.
11. **Lifetime of plaintext.** Inbound is transit: Cadrumo removes an inbound file when an applying operation that read it settles as succeeded. A preview, a refusal, and an unknown or settling outcome remove nothing. A file nobody ingested stays until the person removes it. An export stays in outbound until the person removes it. Cadrumo shows the person what the folder holds and lets them clear it. An agent caller has no operation that removes a file; that is storage administration. Whoever places a file on the person's behalf copies it and never moves it. Staged bytes of an export that did not publish are discarded.
12. **Sign-out and storage.** Sign-out, lock, the sign-in deadline and a runtime restart delete nothing in the folder; with no signed-in session nothing reads or writes it. Reclaim never deletes the folder, and the inventory reports it with the exports area for the active profile. It takes no part in the drift fingerprint or in the custody inventory digest. Profile deletion and the reset of all profiles each remove it as a journalled step of their own. It is never copied into the encrypted mirror, a sealed archive or a portable bundle.
13. **Standing consent.** There is one standing consent per profile. The person gives it in Cadrumo and Cadrumo records it. It is never a request field and cannot be given through MCP. It covers three things: a document the person attaches to a hosted assistant's conversation may be read by that assistant's model; Cadrumo may read a file in the profile's inbound folder when an agent caller asks; and Cadrumo may write a plaintext export into the outbound folder when an agent caller asks. Without it an agent caller's file-taking operation is refused and the host places no real document. It can be withdrawn; withdrawal stops further use and recalls nothing already sent or written. It is not available where the deployment is set to gestor mode.
14. **Approval each time.** The standing consent replaces no approval. Still behind the person's approval of the exact act: every operation the admission record reserves, including `modelo.export`, `modelo.work.file`, `modelo.quickfile`, signing and sharing, and anything that sends data off the machine; Cadrumo's own off-host read of evidence in custody, which keeps its per-invocation gate; and any export whose artefact would contain evidence bytes held in custody. Refused outright, with no approval path: a path outside the folder for an agent caller, and an agent caller's request to replace an existing file.
15. **The person's own session.** A person's command line or terminal interface session, outside any assistant tree, keeps today's freedom to name any path. The same guard checks the handle, the digest and the ceilings; its permitted roots are unrestricted. A command or script run inside the assistant's tree is an agent caller and is confined.
16. **What this is not.** The folder is readable and writable by any process of the person's account. An assistant that holds a terminal can read an export and place a file directly. This record states what Cadrumo offers on the typed path. It is not a barrier against same-account code, which the owner has ruled is not a security concern.

Fixed boundary, not open to any decision: an export is a local file. Nothing in this record sends anything to the tax authority.

The owner's ruling covers the first item of line 13. The second and third are this record's extension of it. To confirm with the owner, because each changes a binding line if answered otherwise: that one consent covers the folder as well as the hosted model's reading (line 13); that nothing but consumed inbound files is removed without the person (line 11); that gestor mode bars the consent (line 13); that a path outside the folder has no approval path for an agent (line 14); and that an export carrying evidence bytes out of custody needs approval each time (line 14).

Hypotheses, free to change within the commitments:

- The folder is `<storage root>/exchange/<profile key>/` with `inbound` and `outbound`, declared under a new scope modelled on the keystore root. The key is the bucket identifier or a derived opaque name.
- The guard is the shared host-path guard. The request field stays text and the MCP caller sends a relative name.
- Ceilings follow the existing 64 MiB financial ceiling and the 128-file limit. Each direction has a total bound per profile.
- The person-supplied mark is written by the host command that copies an attached file into inbound.
- The consent is a profile capability fact distinct from `cloud_evidence_upload`, appended to the consent history.
- The person sees and clears the folder in the desktop window and the terminal interface.
- Every local export moves to the staging sink the modelo export already uses.

Affected prior rulings, each needing an amendment the owner approves. The wording is listed under Consequences.

## Implementation

We will pass files between an agent and Cadrumo only through a per-profile exchange folder beside the encrypted storage, named by relative name, bound by a digest Cadrumo computes at the opened handle, under one standing consent.

- The storage taxonomy gains the folder and its two children. Profile deletion and the all-profile reset gain a step for it.
- Every file-taking operation routes its open through the shared guard, takes its digest and size from the same handle, and declares its ceilings.
- The preview-to-apply digest hand-off becomes mandatory for an agent caller.
- Records and results carry name and digest. The reconciliation import's path reference is replaced for every caller.
- The standing consent is recorded per profile and checked by the operations, not by a frontend.
- Each operation that waits on file exchange is then taken through the admission checklist.

## Rationale

The knockout is that a folder is the only route consistent with two accepted rules at once: evidence bytes do not enter MCP, and private payloads persist only in encrypted custody unless an export has a declared authorization, destination and lifetime. Bytes in a request break the first. Free paths break the second and give no destination to declare. Placing the folder beside the bucket follows the owner's ruling and the keystore precedent, and keeps plaintext out of everything that reads the capsule. Keeping inbound as transit holds the custody rule where it matters, on documents headed for custody. Leaving exports until the person removes them matches what a person's own export already does and avoids turning a time-out into lost work. Checking the opened handle is the only check a path swap cannot defeat (`2026-10-10-mcp-parity-file-exchange-reference`).

## Consequences

- Every operation ruled "pending file exchange" can be admitted, and results stop carrying host paths.
- The person's command line and terminal interface lose nothing. They gain the handle check, the digest and the ceilings.
- A person, or the assistant's own script, copies a file into inbound before an agent can ingest it. That is one step more than naming a path.
- Plaintext exports accumulate in outbound until the person clears them. Cadrumo has to show them.
- An inbound copy of a statement is removed after import, and statement bytes are not kept in custody. Whether source statements should be kept there is a separate decision.
- The custody rule gains a declared plaintext area, and accepted wording that says nothing sensitive is ever on disk outside secure storage is amended.
- A hosted model reads documents the person attached. That reverses the accepted first-run notice that source documents never leave the machine, and it applies only under the standing consent.
- Two sentences of the cadrumo-agent records read differently under this record and are relayed to that project: Cadrumo confines an agent to the profile's exchange folder, not to the assistant's own root; and a file the assistant copies into inbound lies outside its root.
- Confinement of a command run in the assistant's terminal waits on tree recognition, which does not exist in code.
- Amendments required once this record is accepted:
  - `2026-06-10-llm-evidence-classification-adr`, ruling 1 (lines 24-25) and its Constraints (lines 125-128), as one dated amendment note in that record's own convention. "Nothing sensitive is ever persisted outside it: no temp files, no scratch dirs, no plaintext side stores, no logs" gains "The one declared exception is the per-profile exchange folder of `2026-10-10-mcp-parity-file-exchange-adr`: a file waiting in inbound until it is ingested, and an explicit export in outbound. Evidence bytes held in custody are written there only on the person's approval of that export".
  - The same record, ruling 2 (lines 30-33), on the explicit per-invocation consent gate for cloud providers, gains "This binds Cadrumo's own read of evidence in custody and is unchanged. A document the person attaches to a hosted assistant's conversation is the person's own copy; that assistant's model reads it under the standing consent of `2026-10-10-mcp-parity-file-exchange-adr`, which the owner ruled on 2026-10-10 and which is refused in gestor mode". Its sentence on per-invocation re-affirmation (lines 138-146) gains "for evidence bytes read from custody".
  - `2026-06-10-ledger-evidence-enforcement-adr`, Decision 4 (lines 153-154). "so no plaintext financial document remains on disk outside these namespaces" becomes "so no evidence record's bytes remain on disk outside these namespaces. A file waiting in a profile's exchange inbound folder is not an evidence record and is removed once ingested".
  - `2026-08-13-secure-storage-hardening-successor-adr`, Considerations. "Financial payloads remain secure-storage-only" gains "apart from explicit exports and the declared exchange folder of `2026-10-10-mcp-parity-file-exchange-adr`".
  - `2026-07-02-agent-harness-refoundation-adr`, R9 (line 199). "your source documents never leave your machine" becomes "documents held in Cadrumo's custody never leave your machine through Cadrumo; a document you attach to a hosted assistant is read by its model only under the standing consent of `2026-10-10-mcp-parity-file-exchange-adr`", and "Evidence bytes never leave the host" becomes "Evidence bytes held in Cadrumo's custody never leave the host". Its Constraints (line 207) gain "a file in the exchange folder is governed by `2026-10-10-mcp-parity-file-exchange-adr`".
  - `2026-10-10-mcp-parity-admission-rulings-adr`. "An operation that takes or writes a host path is admitted only once file exchange is decided, which this record does not do" becomes "An operation that takes or writes a host path is admitted over the per-profile exchange folder decided in `2026-10-10-mcp-parity-file-exchange-adr`". The `ledger.export` row becomes "Admit; an agent's export is written to the profile's outbound folder". "Its host path is confined like the other open path operations" becomes "Its host path is confined to the profile's inbound folder". The list of sensitive acts in the rule of judgement gains "or an export that carries evidence bytes out of custody".
  - The rule source `.vaultspec/rules/05-persistence-and-secure-storage.md` is the owner's policy file and is changed only on request. Proposed sentence after "Observed plaintext gaps require remediation, not a new storage exception": "The per-profile exchange folder is the one declared plaintext hand-over area: inbound files are transit and are removed once ingested, outbound files are explicit exports kept until the person removes them, and both require the profile's standing consent".
  - Not accepted, so no edit is owed, but its author should know: `2026-08-07-unstructured-document-ingestion-operations-adr` says consent is per-invocation and that there is no standing grant.
- Reconsider if a client on another machine must exchange files, if a platform cannot verify an opened handle against a root, if the owner sets a retention period, or if a live run shows agents cannot work by relative name.
