---
tags:
  - '#adr'
  - '#desktop-modelo-workspace'
date: '2026-10-23'
modified: '2026-10-23'
body_schema: 'body-v2'
body_hash: 'sha256:b1d2ca3ae76dc925bc0aa1cb10bc18b74be02e2a18660fab5e3e0d4fff63bc5b'
related:
  - "[[2026-10-23-desktop-ledger-editor-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr]]"
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-10-05-desktop-design-system-adr]]"
  - "[[2026-10-23-desktop-modelo-workspace-research]]"
---

# `desktop-modelo-workspace` adr: `The desktop Modelo workspace renders the form read model and submits the modelo family over the held person relay` | (**status:** `accepted`)

Accepted 2026-10-23 on the owner's instruction that day (session CADRUMO-UX-MODELO): the desktop gets a designed, polished workspace to list, create, fill, check, export, record and correct declarations, with each modelo's editor generated from data; the behaviour is settled by the CLI and the TUI, and the owner asked that no further decision be put to them.

## Problem Statement

Declarations can be worked in the CLI and the TUI only. The desktop shows filing deadlines but cannot open a declaration. The owner wants the Modelo work in the window, designed for the desktop rather than copied from the terminal, and generated for every modelo from the registry. `2026-10-04-desktop-shell-adr` and `2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr` admit only named read-only views; `2026-10-23-desktop-ledger-editor-adr` opened one writing family, the ledger, and the Modelo work is a second.

## Considerations

- The application already joins the declared registry layout with values, origin, editability, source policy, counts, result, deadline and filing state into one read model, and classifies every box so that a frontend renders and never classifies (`2026-09-30-modelo-editor-workbench-adr`, D2). The registered read `modelo.work.form` returns it as a public envelope with the admitted edit baseline or the typed refusal (`src/cadrumo/application/modelo/workbench_projection.py:366`).
- Every lifecycle act is a registered `modelo.*` operation: create, list, form, casilla help, edit renew, preflight, apply and prerequisite, calculate, verify, export, local filing, amend, rename, discard, reconcile and the spreadsheet, report and review-package exports (`2026-10-23-desktop-modelo-workspace-research`).
- The held person relay carries plain payloads only (`src/cadrumo_runtime/host/session_hold_operations.py:73`). Edit preflight and apply take their amounts through the runtime's transient financial-operand path (`src/cadrumo/application/modelo/edit_operator_input.py:47`, `src/cadrumo_runtime/host/operation_host.py:849`), which the relay does not reach.
- The largest current form envelope is about 430 KB compact (Modelo 390); the bridge caps one reply line at 1 MiB (`native/desktop/src-tauri/src/agent/person.rs:346`). A Modelo 100 form is expected to exceed that.
- The workbook export reuses the same declared layout but paints a hex palette onto cell geometry; the desktop design system admits only its own tokens (`2026-10-05-desktop-design-system-adr`).

## Considered options

- **Open the TUI in the window.** Gives the owner nothing they asked for.
- **Render the registry layout in the window.** Rejected: it repeats the classification the read model owns, and the form-projection decision already rejects runtime interpretation of layout data.
- **Reuse the workbook compiler's cell builder.** Rejected: it fuses value resolution with spreadsheet geometry and its palette is not the desktop's colour authority.
- **A closed Modelo family over the held relay, rendering the form read model (chosen).** The same shape as the ledger family: the host names admitted `modelo.*` ids, the runtime contract validates payloads, the window renders the application's projection.

## Constraints

- This adds a second writing family to `2026-10-04-desktop-shell-adr`, on the terms of `2026-10-23-desktop-ledger-editor-adr`: a host-owned closed list of admitted definition ids (the `modelo.*` operations reached by `aeat app modelo` and by the TUI workbench), payloads validated by the registered contract and not restated in the host, files through native dialogs and opaque tokens, review answers bound to the digest shown, unknown outcomes shown as unknown and never retried. Adding or removing an id amends this record.
- The held relay gains one action, a financial-operand submit, that carries a `ModeloEditOperatorInputV2` for `modelo.edit.preflight` or `modelo.edit.apply` to the runtime's existing financial-input admission. The body travels raw from the window to the host, as the password change does, and is wiped after transfer; it never enters a plain payload, a log or an error.
- A form read larger than one reply line is carried in bounded parts the host reassembles before handing it to the window; the window never sees a truncated form.
- Amended 2026-10-24, under the owner's standing direction that desktop Modelo behaviour is settled by the TUI and CLI and is decided without asking: a person reply is bounded by the relay's assembled-document size rather than one pipe line (`931da66b20`), so no separate part protocol was built for replies. The request direction takes the same bound. The financial-operand submit and the edit renewal carry the admitted baseline whole, as the TUI and CLI do, and the bridge and the relay bound such a request by the assembled-document size, not by one request line; a Modelo 303 baseline alone exceeds one line. The edit contract is unchanged and no worker state is added, which carrying the baseline by reference would require. The financial-operand submit reaches the runtime only through its streamed upload (an `operation_submit_payload` header, an `operation_payload_ready` acknowledgement naming the descriptor, then bounded secret frames), the path the Python client uses; the runtime refuses a bare `operation_financial_input` document as an invalid frame, so the direct form first written in `1706f66723` never worked live and must not be restored. A plain submission takes the same streamed path when it would not fit one frame.
- The window renders the read model's states and words and does not classify a box, a declaration or a finding. Missing is never drawn as zero; local filing, an exported file and what was observed at the AEAT stay visibly distinct; the window submits nothing to the AEAT.
- Declaration data and staged edits live in the window's memory only and are discarded on sign-out, profile change and window close, as for the ledger. Presentation preferences may persist.
- The visual design uses only the desktop design system; the interaction design is the reviewed prototype of this feature (`2026-10-23-desktop-modelo-workspace-research`).

## Implementation

- Host (`native/desktop/src-tauri/src/shell/modelo/`): read the declarations list and a form, submit an admitted `modelo.*` operation and settle it, read and answer reviews by digest, submit the financial-operand body, pick files and save locations as tokens. The admitted list is a Rust constant checked by test against the contract manifest.
- Runtime: the relay's financial-operand action and the bounded reply parts, in `src/cadrumo_runtime/host/session_hold_operations.py` and the bridge.
- Application: what the window would otherwise guess is exposed by the read models (a public declarations list-row read, the needs-the-filer rule, period and finding wording as catalogue keys), in their owning modules under `src/cadrumo/application/modelo/`.
- Frontend: a `modelo` port on `Host`, wire-mirror types, scenario answers from envelopes produced by the real builder, and the workspace under `src/components/modelo/`.
- Hypotheses that may change within these constraints: command names, whether the declarations list is one read or two, the part size for large forms, and how the workspace windows long forms.

## Rationale

The read model already makes every classification and is shared by every frontend; rendering it keeps the desktop a renderer and keeps the surfaces at parity by construction. The closed family reuses the ledger's reviewed boundary instead of inventing a second one. The relay action reaches an admission path the runtime already has, so no new financial custody is created, only a way for the held session to use the existing one.

## Consequences

- Every modelo the registry declares opens in the window with its own official sections, grids and repeated records, and coverage follows the registry's layouts.
- The runtime relay and the bridge change, so their tests must cover the financial-operand action's wiping, its refusal for any other definition, and the reassembly of large reads.
- The window becomes a writing surface for declarations; its tests must cover stale baselines, refusals, unknown outcomes, review digests and the absence of taxpayer data from storage and logs.
- Reconsider if a `modelo.*` operation gains an effect outside the profile, if the admitted list starts to include other families, or if the runtime gains a read-only client role.
