---
tags:
  - '#adr'
  - '#frontend-rental-rows'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:d5a16b63a891c75d62308320eb289de5bac747cf552fc66f4637a1c259a55eba'
related:
  - "[[2026-11-11-renta-rental-income-source-adr]]"
  - "[[2026-11-03-backend-served-surface-adr]]"
  - "[[2026-11-02-desktop-renta-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-23-desktop-ledger-editor-adr]]"
  - "[[2026-11-12-frontend-refusal-ways-out-adr]]"
  - "[[2026-11-12-frontend-operator-statements-adr]]"
  - '[[2026-11-12-frontend-rental-rows-reference]]'
---

# `frontend-rental-rows` adr: `Rental property and lease rows as one served record group in both frontends, linked from the ledger by served pickers` | (**status:** `accepted`)

## Problem Statement

`2026-11-11-renta-rental-income-source-adr` moved rental income from one scalar profile leaf to related rows: property rows (`renta_inmueble`, `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1497`), lease rows that name their property by row index (`renta_arrendamiento`, `schema.toml:1718`, field `inmueble` at `:1725`), and ledger rows linked to a lease (`arrendamiento_ref`) or to a property and an expense concept (`inmueble_ref`, `gasto_capital_inmobiliario`). Both frontends show profile rows as flat generic lists: the TUI through `src/cadrumo/entrypoints/tui/profile/overview_rendering.py:457` and `edit_screens.py:183`, the window through `native/desktop/frontend/src/components/profile/ProfileDetails.tsx` and `src/shell/profileRows.ts`. Neither shows a property with its leases, the derived art. 23.2 reduction, or a ledger link; neither offers the links while classifying. A decision is needed now because per-property Modelo 100 rows with `row_identity` and per-property carried-expense statements are coming, and payers and investment positions will need the same shape.

## Considerations

- Rows are edited only through the generic operations `user-profile.repeatable-row-mutation`, `user-profile.repeatable-row-update` and `user-profile.repeatable-row-remove` (`src/cadrumo/application/user_profile/operations.py:217-241`). Cross-row admission is the backend's: a lease must name an existing property, and removal is refused while a ledger row references the row (`src/cadrumo/application/user_profile/rental_records.py:117,204`).
- Field labels and enum words are served (`src/cadrumo/application/user_profile/overview.py:376`). A row has no served summary or label. A ledger ref is the row key as plain text (`rental_records.py:199`).
- `usos`, `valores_catastrales`, `mejoras` and `inquilinos` are encoded strings whose grammar lives only in schema prose (`schema.toml:1652-1676,1771`).
- The reduction tier is a derived selector over lease facts (`schema.toml:78-90`); nothing serves its result or its deciding facts to a surface.
- `arrendamiento end` is a CLI verb that edits `fecha_fin` (`src/cadrumo/entrypoints/cli/config/arrendamiento.py:112`); no operation and no served words exist for it.
- The ledger entry options read serves option families (`src/cadrumo/application/ledger/entry_options_operation.py:133`) but no expense-concept family and no rental row choices. Both frontends keep hand-written classify field lists (`src/cadrumo/entrypoints/tui/ledger/classification.py`, `entries_add.py`; `native/desktop/frontend/src/shell/ledgerStage.ts`, `src/components/ledger/editing/editingModel.ts`).
- Precedent: the window's household element renders a served grouped read on the profile page (`native/desktop/frontend/src/components/profile/Household.tsx`, `src/shell/profileHousehold.ts`) under the companion-read ruling of `2026-11-02-desktop-renta-adr`. Its table keyed by group key (`householdModel.ts:17`) is the kind of frontend-held relation this decision avoids.
- Served words only, and every profile field is edited in the window: `2026-11-03-backend-served-surface-adr` and the 2026-10-27 amendments of `2026-10-04-desktop-shell-adr`.

## Considered options

- **(a) Generic rows plus one served record group in the profile area (chosen).** A property, its leases, its accessory properties and its linked ledger rows appear as one object; generic rows stay the fallback editor. Reuses profile custody, the row operations and the household precedent; needs a served grouped read.
- **(b) A dedicated Rentals place.** Clear for landlords, but it duplicates profile editing, adds a navigation entry per income family (payers and positions next) and splits one profile into several editors. Rejected.
- **(c) Generic rows only.** No backend work, but the operator must join leases to properties by integer index, cannot see the reduction and cannot link a ledger row from either frontend. Rejected.

## Constraints

- A frontend authors no tax wording and no tax fact: no row label, summary, reduction tier, expense-concept word or end-lease wording is composed from stored facts. Words are served (`<thing>_words` with `<thing>_words_language`, `2026-11-03-backend-served-surface-adr`); generic chrome stays in chrome keys authored through `dev.locales`.
- Relations are served, not joined. No frontend reads `renta_arrendamiento.inmueble` to place a lease under a property, and no frontend code names a rental section key, field key or concept token. The group is rendered by payload kind and iterated, so the same element takes payers and investment positions without a branch.
- Edits go only through the existing row operations and the ledger classify and add operations; the group read adds no write path. Every refusal, including a removal refused for a ledger reference, renders through the component of `2026-11-12-frontend-refusal-ways-out-adr`.
- A ledger link is chosen from a picker over served choices: rental rows labelled by their served summary, concepts by their served words. The stored value is the served token. A designed surface never asks for a raw row index. The backend decides which link applies and refuses a row carrying both.
- Compound fields stay one served text input with their served help until the backend serves them as structured rows. A frontend never parses or composes the encoding.
- The derived reduction is shown only as served: its words, the facts that decided it, and a missing fact with its way out. A frontend computes no tier and shows none while it is not served.
- Ending a lease is offered only as a served action with served words; until then `fecha_fin` stays editable through the generic row editor.
- Parity is stated, not assumed. The window gets the designed group, the pickers and, once served, structured inputs. The TUI gets the same group as a read-only panel in its profile manager, edits through its existing generic row screens, and the same pickers in classification and entries-add. Bulk classification in both frontends takes the link columns the operation declares.
- Acceptance conditions (PRIME, 2026-11-12 10:15): the group's row identity is the stable row key that the ledger refs and the Modelo 100 `row_identity` use, never the integer row index; the record-group read is generic by payload kind from the start, and its linked-ledger-rows part is bounded and paged; summaries hold private facts, so stories, fixtures and logs carry no real data; nothing designed ships before its backend ask; the TUI scope is accepted as stated. Until the asks land, the group element and the pickers are built and storied against fixtures of the accepted shape and stay unwired.

## Implementation

We will render rental property and lease rows as one served record group on the profile page of both frontends, keep the generic rows beneath it, and link ledger rows through served pickers.

- Window: a record-group element beside the household, fed by a host read admitted through the relay. A property card shows its served summary, its leases with their served reduction, its accessory properties and its linked ledger rows, with edit, end and remove actions that open the generic row editor or stage the served action. Classify single and bulk and manual add gain the two pickers from the served entry options. Stories: no properties, one property with two leases, an accessory property, a missing deciding fact, removal refused for a ledger reference, and the pre-backend state (generic rows only, no group).
- TUI: a read-only group panel in the profile manager over the same read; the classification and entries-add screens gain the two pickers.
- Backend asks (routed by PRIME), each a precondition for the frontend part that uses it:
  - a served record-group read: each property with its leases, accessory properties and linked ledger rows, row identities, and summary words for every property and lease;
  - entry option families for the ledger links: rental row choices with their summary words, and the 12 expense concepts with words;
  - structured rows for `usos`, `valores_catastrales`, `mejoras` and `inquilinos`, in the profile view and the row operations;
  - the derived art. 23.2 reduction per lease: tier words, deciding facts, and a missing fact with its way out;
  - an end-lease action with words, as a registered operation or a served edit target;
  - a profile field view that marks a reference to a row of another section, so generic editors offer a picker.
- Hypotheses that may change: the read's name and payload shape, the element names, and whether linked ledger rows come inside the read or through a filtered ledger list.

## Rationale

Option (a) keeps one profile editor and one custody path, and the record group is the shape payers and investment positions will reuse. Serving the relation, the summaries and the reduction keeps both frontends free of tax wording and of rental-specific code, so the CLI, TUI and window agree. Pickers over served choices replace an integer the operator would otherwise have to know.

## Consequences

- Nothing designed ships before its backend ask lands; until then both frontends stay on generic rows, so no visible regression lands.
- The TUI gets reading and linking, not the designed editor; the gap is deliberate and visible.
- The six backend asks add served reads and fields to profile and ledger operations, with relay admission and manifest regeneration.
- No accepted wording needs an edit. The allowance to "order and group served rows for display" in the 2026-10-27 amendment of `2026-10-04-desktop-shell-adr` stays for layout; this record adds that a relation between rows is served.
- Reconsider when per-property Modelo 100 rows land: their `row_identity` must match the group's row identity so a form row opens its property, and per-property statements follow `2026-11-12-frontend-operator-statements-adr`. Reconsider also if the backend declines the group read.
