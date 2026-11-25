---
tags:
  - '#adr'
  - '#operation-refusal-words'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:84b9bf5e02b5ace75d0d3733898fab208497288c5fe05f7d5358be9569ad3c5c'
related:
  - "[[2026-10-23-desktop-modelo-workspace-adr]]"
  - "[[2026-10-23-desktop-ledger-editor-adr]]"
  - '[[2026-11-02-operation-refusal-words-reference]]'
---

# `operation-refusal-words` adr: `Backend-served refusal words for operation refusals` | (**status:** `accepted`)

Accepted 2026-11-02 on the operator's ruling of that date: "Backend should absolutely send the refusal messages."

## Problem Statement

A desktop-submitted registered operation that the backend refuses reaches the window as a code at best. The window may not map refusal codes, condition ids or reason tokens to its own text: tax meaning stays in Python, and `dev/quality/tests/test_window_holds_no_tax_data.py` enforces it. So the operator saw a generic "not done" notice where the CLI shows the reason. The runtime relay also never released the generic error detail of a refusal that declared no typed refusal detail, so the desktop had nothing to show.

## Considerations

- The registered error catalogue already owns localized, redacted refusal sentences (`src/cadrumo/core/errors/error_codes.py`); the CLI renders them.
- Message interpolation can run before context redaction in the catalogue path; served words must be worded only from scrubbed, bounded context (`src/cadrumo/application/operations/error_detail.py`).
- The runtime result read carries no output language, so a render at release time needs a protocol change.
- Earlier workers already render served sentences in `output_language()` at build time (the `message_language` precedent in the source mesh and prorrata register).
- Stored operation error details must keep validating after the change.
- `public_error_detail` is a per-definition disclosure choice; a definition that withholds its error detail must keep withholding it.

## Considered options

- **Render at build time in the worker's language and store the sentence with its language (chosen).** No protocol change; the stored detail carries a finished sentence. Cost: one language per stored detail.
- **Render at release time in the requesting window's language.** Exact language match, but the result read has no language and the runtime would need tax catalogue access. Rejected.
- **Store a map of every language.** Language-safe, but quadruples redaction surface and size for every refusal. Rejected.
- **Patch each operation to add words to its own result.** Many divergent paths, and refusals without a typed detail stay silent. Rejected; the typed invoice add detail reuses the shared helper instead.

## Constraints

- The window shows served words as served and falls back only to its own generic notice keys. It never maps a code, condition id or reason token to text.
- Served words come from a registered catalogue key plus the detail's own scrubbed bounded context, never from free error text or raw context. If a sentence cannot be worded completely within the bound, the next key in order is used.
- Both new fields are optional and travel together; old stored details stay valid.
- Definitions with `public_error_detail=False` continue to store no error detail.
- Runtime relays the recorded error detail unchanged; Rust and the window do not reword it.

## Implementation

We will add `refusal_words` and `refusal_words_language` to `OperationErrorDetailV1`, rendered when the detail is built in the worker's output language. The wording order is: the error's key-shaped translated message unless the registry owns the message, then the code's registered message key, then a generic sentence naming the code. Record validation faults serve the registered rule carried as the validation cause, else a generic record-fault sentence. `operation_refusal_words` exposes the same wording for typed refusal details; invoice add uses it. The runtime relay releases a terminal refusal's error detail under its own schema when no typed refusal detail is declared. The desktop host relays it for refused and failed stops, and the window reads `refusal_words` through one helper. Which further definitions opt into `public_error_detail`, and which typed refusal details gain words, may change within these constraints.

## Rationale

Build-time rendering is the only option that needs no protocol change and keeps the tax catalogue out of the runtime and the window. It reuses the existing served-sentence precedent and the existing redaction boundary. Wording only from scrubbed context closes the interpolation-before-redaction gap for everything served.

## Consequences

- The window states the backend's reason for every refusal that stores an error detail, in four languages, with no tax text of its own.
- A settings or environment language override in the worker can make the served language differ from the window's; `refusal_words_language` records it.
- Refusals from definitions without a public error detail, and typed refusal details other than invoice add, still show the generic notice until they opt in.
- Error sites that pass free text get only their code's sentence.
- Reconsider if the result read gains a language, which would allow a release-time render.
