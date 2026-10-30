---
tags:
  - '#adr'
  - '#desktop-ledger-editor'
date: '2026-10-23'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:b08d53ea65a29b3a8ff9a07d4ff8482a861397f0f5e486a7744a3f062be596d3'
related:
  - "[[2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-05-desktop-design-system-adr]]"
  - "[[2026-10-18-dependency-provisioning-unified-setup-adr]]"
  - "[[2026-06-10-ledger-interface-contract-adr]]"
  - "[[2026-10-22-ledger-tui-doors-authenticated-stored-reads-adr]]"
  - '[[2026-10-23-desktop-ledger-editor-reference]]'
---

# `desktop-ledger-editor` adr: `The desktop Ledger page submits the ledger family's registered operations over the held person relay` | (**status:** `accepted`)

Accepted 2026-10-23 on the owner's instruction that day (session CADRUMO-UX-LEDGER): the desktop gets a table-based batch editor for movements, invoices and categorisation; everything the CLI and the TUI ledger already do must be available in it; and the work needs no further decision from the owner.

## Problem Statement

The owner wants to edit the ledger in the desktop window, not only in the TUI. That means a grid with filtering, sorting, grouping by category, multi-row selection, batch edits, import and export, at parity with the CLI's `aeat app ledger` family and the TUI's ledger workspace. `2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr` admits only named read-only views, and says to reconsider "if a view needs to change anything, if the number of views makes per-view commands a burden". The ledger page meets both conditions: it writes, and the family has about eighty registered operations.

## Considerations

- The family is already a closed set of registered operations. Each has typed request and result contracts and declared effect facts, and the two model reviews have digest-bound review interactions (`src/cadrumo/_data/operations/contract_manifest.json`, `src/cadrumo/application/operations/access_facts.py`).
- The window already holds the signed-in person's relay. The relay carries submit, observe, result, review, respond and cancel for any registered operation under the exact-profile session (`src/cadrumo_runtime/host/session_hold_operations.py`, `native/desktop/src-tauri/src/agent/person.rs`). The desktop is a person frontend, like the CLI and the TUI (`src/cadrumo/application/operations/person_acts.py`).
- The runtime decodes every payload against the definition's registered contract and refuses anything else. The access policy refuses person-only acts outside their channel (`src/cadrumo_runtime/host/operation_host.py`, `src/cadrumo/application/user_profile/operation_access_policy.py`). Typing the payloads a second time in the host would duplicate that authority.
- The ledger import and evidence operations read absolute paths in the worker. The window must not name paths (`2026-10-04-desktop-shell-adr`: the frontend names items and choices only).
- CLI, TUI and MCP stay at parity, and no surface adds its own approval gate (`2026-07-02-agent-harness-refoundation-adr`, R6 amendment).

## Considered options

- **Link to the TUI only.** This keeps the ruling but gives the owner nothing they asked for.
- **One host command per ledger operation.** This means about eighty typed Rust commands, each restating its request contract. The cost the capabilities record calls its control becomes a second copy of every contract, and drift between the two copies becomes a new class of defect.
- **A closed ledger family over the held relay (chosen).** One host module serves a command that names an operation from a closed, host-owned list of ledger definition ids. The runtime contract validates the payload.
- **The general operation bridge.** The window could name any definition id. Rejected again, for the reason the capabilities record gives: it makes the window an unreviewed operator surface.

## Constraints

- This adds one exception to `2026-10-04-desktop-shell-adr`, and widens `2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr` for the Ledger page only. The shell still holds no session, receipt, credential or runtime connection. The relay stays the held person's.
- The host owns a closed list of admitted definition ids: the `ledger.*` operations reached by `aeat app ledger` and by the TUI ledger workspace. The window names one of them together with a JSON payload. The host refuses any other id before it reaches the relay. Adding or removing an id amends this record.
- The registered contract in the runtime validates each payload; the host does not restate it. The host bounds payload size and never splits a batch silently. A batch larger than one request is sent as several requests, and the window shows them as parts of one apply.
- Files are chosen in native dialogs or dropped on the window, and the host gives the window opaque file tokens. The window never supplies a path. When it submits, the host substitutes the absolute path for the token. A token is valid only for the signed-in session that issued it.
- Results reach the window naming files, not locations. Where a result names a path, such as an import source, an evidence record's source or an export's output, the host reduces it to its file name before passing the result on. This was ruled on 2026-10-24 under the owner's standing authorization, because the window names items and never holds paths (`2026-10-04-desktop-shell-adr`), and a folder can carry the person's name.
- Secret inputs, such as an own account's IBAN or bank block, travel only in a raw request body to the host, as the password change does, and are wiped after submission.
- A review interaction is answered only with the digest of the review document the window showed. A changed document needs a new answer. A write whose outcome is unknown is shown as unknown and is never retried automatically; the page pauses writes until it re-reads.
- Ledger data and staged edits live only in the window's memory. They never reach the window's storage, logs, diagnostics or error messages, and they are discarded on sign-out, on a profile change and when the window closes. Presentation preferences may persist: columns, density, grouping, and the filter keys of saved views without their typed values.
- The page keeps the product's distinctions. Unknown is never drawn as zero, and never-captured and stale data are labelled as such. A model suggestion is a proposal that only the person applies. A missing exchange rate is a refusal, not a zero.

## Implementation

We will add a Ledger page to the desktop shell, and a `ledger` host module to serve it.

- Host (`native/desktop/src-tauri/src/shell/ledger/`): commands to:
  - submit an admitted ledger operation with a payload and settle it (submit, observe until settled, read the result);
  - read a pending review and answer it with its digest;
  - cancel at an observed revision;
  - pick files and a save location through native dialogs, returning file tokens;
  - submit the own-account secret body.

  The admitted list is a Rust constant, and a test checks it against the contract manifest.
- Frontend: a `ledger` port on `Host` (`native/desktop/frontend/src/shell/host.ts`), typed request and result shapes for the operations the page uses, a scenario answer built from synthetic fixtures, a grid primitive in `src/components/ui/`, and the page itself under `src/components/ledger/`. The page's interaction design is the reviewed prototype of this feature.
- These details are hypotheses that may change within the constraints: the exact command names, whether review answers share the setup module's helpers, and how large one bulk-classification request may be before the page splits it.

### Amendment 2026-10-24: the person sees the document they confirm

Accepted under the owner's standing authorization for this feature. The P03 usability review (`2026-10-24-desktop-ledger-editor-audit`, `document-no-preview`) found that the page asks the person to confirm a scanned receipt, such as which of two printed tax IDs is the supplier's, without ever showing it. No admitted read returns a stored document's bytes.

- **A registered read renders one page of a stored document as an image.** Its request names one evidence record or one attachment, a page number and a width bound. Its permitted effects are none or unknown.
  - The worker loads the encrypted bytes from custody and checks them against the record's digest. It renders a PDF page with the already-declared pdfplumber and pypdfium2. It passes a JPEG or PNG through, bounded.
  - The result carries the page image as a `data:` URL under the reply bound, with the media type, the page count, the source digest and the file name. It carries no path.
  - It refuses above a byte bound, and refuses any media type it cannot render.
- **The window never parses a PDF**, and no PDF renderer is added to the frontend. The current CSP already admits `data:` images, so it does not change.
- **The read joins the admitted list.** Bytes reach the window in memory only. They are dropped when the panel closes or the document changes, and never persisted or logged.
- **The CLI and MCP reach the same registered read**, as every registered operation does. The CLI writes the rendered page to a file the person names.

### Amendment 2026-10-24: a model review is held per movement and can be let go

Accepted under the owner's standing authorization for this feature. The P04.S17 review (`2026-10-24-desktop-ledger-editor-audit`, `model-review-subject-lease`, `tracked-ring-evicts-reviews`) found that `ledger.classify.review` takes the whole profile as its subject and cannot be cancelled. So only one model review can be pending per profile, and the runtime refuses every further ask while one waits, including the re-asks R5 and M4 call for and "Ask the model for each". A review nobody answers also blocks asks until it settles.

- **The review's subject is its movement.** The registered contract names `transaction_id` from the request as its subject (`payload_field`), so one review can wait per movement while reviews of other movements proceed. Two asks about the same movement still conflict, as they should.
- **A review waiting for its answer can be cancelled** (cooperative cancellation). It has written nothing yet, so cancelling it releases its subject with no effect. The page cancels a review it supersedes or abandons, and still never retries an unknown outcome.
- **The host fills the subject from the request**, as it already does for work-unit subjects. It keeps following every operation it can still answer or observe, so ordinary reads never push a waiting review out of memory.
- **Parity:** this is a registered-contract change, so the CLI, TUI and MCP get the same per-movement scope and cancellation.

### Amendment 2026-10-30: admit the shipped inventory closing and evidence operations

Accepted under the owner's standing authorization to complete ledger parity and repair the desktop contract gate. The shipped operation manifest and the CLI ledger inventory family include `ledger.inventory.closing-value.record` and `ledger.inventory.evidence.add`; both join the host's closed admitted list as writes. The frontend definition mirror and scenario write classes name the same operations, and the generated relay contract fixture retains the manifest's effect and subject facts.

The concurrently shipped `ledger.inventory.options` joins the same closed list as a read, exposing canonical form vocabularies without a new effect or path input.

Inventory evidence uses the existing document-pick custody path: the window supplies a document token in `source_path`, the host resolves it for the held session and supplies `source_directory`. Window-supplied paths, directories and tokens from another purpose remain refused. Runtime request validation and exact-profile authority continue to govern both operations.

## Rationale

The registered contracts are already the authority for every ledger request, and the relay already carries them for this person in this session. A closed list of ids in the host stops the window from naming arbitrary operations, which is what separated the capabilities record from a general bridge, and it does so without writing each contract twice. Paths and secrets stay with the host, as the shell record requires.

## Consequences

- The owner can do in the window everything the CLI and TUI ledger can do, and the three surfaces stay at parity by construction.
- The window becomes a writing surface for the ledger. Its tests must cover refusals, unknown outcomes, review digest binding, and the absence of taxpayer data from storage and logs, in the browser and in the packaged window.
- Where the product only offers per-row operations, as it does for most corrections, batch work costs one catalogue write per row. The page shows that progress honestly. A product batch operation for corrections would be a separate decision.
- Reconsider if a ledger operation gains an effect outside the profile beyond the existing exchange-rate lookup and model reads, if the admitted list starts to include non-ledger operations, or if the runtime gains a read-only client role.
