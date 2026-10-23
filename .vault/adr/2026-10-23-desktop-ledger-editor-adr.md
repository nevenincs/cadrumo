---
tags:
  - '#adr'
  - '#desktop-ledger-editor'
date: '2026-10-23'
modified: '2026-10-23'
body_schema: 'body-v2'
body_hash: 'sha256:ec7a6803308371d6150158c13b0c796a1a49d169be92a8af75a3b9df8e4c7706'
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

## Rationale

The registered contracts are already the authority for every ledger request, and the relay already carries them for this person in this session. A closed list of ids in the host stops the window from naming arbitrary operations, which is what separated the capabilities record from a general bridge, and it does so without writing each contract twice. Paths and secrets stay with the host, as the shell record requires.

## Consequences

- The owner can do in the window everything the CLI and TUI ledger can do, and the three surfaces stay at parity by construction.
- The window becomes a writing surface for the ledger. Its tests must cover refusals, unknown outcomes, review digest binding, and the absence of taxpayer data from storage and logs, in the browser and in the packaged window.
- Where the product only offers per-row operations, as it does for most corrections, batch work costs one catalogue write per row. The page shows that progress honestly. A product batch operation for corrections would be a separate decision.
- Reconsider if a ledger operation gains an effect outside the profile beyond the existing exchange-rate lookup and model reads, if the admitted list starts to include non-ledger operations, or if the runtime gains a read-only client role.
