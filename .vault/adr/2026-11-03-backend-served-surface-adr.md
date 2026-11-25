---
tags:
  - '#adr'
  - '#backend-served-surface'
date: '2026-11-03'
modified: '2026-11-03'
body_schema: 'body-v2'
body_hash: 'sha256:ebbac0914cbf64069a23752e6857d7f4f5fb5002097ade32ba984760f1bbe7a0'
related:
  - "[[2026-11-02-operation-refusal-words-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-11-02-desktop-renta-adr]]"
  - "[[2026-10-23-desktop-modelo-workspace-adr]]"
  - "[[2026-10-23-desktop-ledger-editor-adr]]"
  - '[[2026-11-03-backend-served-surface-reference]]'
  - '[[2026-11-02-operation-refusal-words-reference]]'
---

# `backend-served-surface` adr: `Every operation serves its words, facts, flags and capabilities` | (**status:** `accepted`)

Accepted 2026-11-03 on the operator's direct rulings of that date: "the frontend represents the backend's data and the frontend should never be allowed to hardcode tax facts or wording. that is what the backend is for."; "please build out all backend capability so that the frontend requires no frontend. Why? because cli tui and frontend should derive from the backend."; "ensure backend registers all required operations and data, frontend shouldn't need to hardcode tax details".

## Problem Statement

The window still decides tax meaning. The inventory in `2026-11-03-backend-served-surface-reference` found more than 110 places where the window maps a served token to its own sentence, holds a tax fact (the reporting currency "EUR", the annual period "0A", quarter arithmetic, Modelo 210 fields, column groups by tax area), decides an eligibility rule (which classification asks for a category, which invoice takes lease fields), or hardwires a capability to a modelo (the 303/390 evidence dialog, the 303 correction motive). The TUI holds parallel copies of register refusal sentences.

`2026-11-02-operation-refusal-words-adr` settled served words for refusals only. The 2026-10-27 amendment of `2026-10-04-desktop-shell-adr` ("the window holds no domain data or domain logic") forbids copied facts and rules, but its "Remap only" bullet still lets the window map served codes to "localized wording from the generated catalogue". The operator's rulings close that allowance: wording with tax meaning, like facts, comes from the backend, and every surface derives from it.

## Considerations

- Served sentences have a precedent: `refusal_words` and `refusal_words_language` on `OperationErrorDetailV1` (`src/cadrumo/application/operations/error_detail.py:161`), and `answer_words` and `answer_words_language` on credit resolution (`src/cadrumo/application/modelo/credit_resolution_contracts.py:146`).
- Served sentences live under `served` key families owned by their operation: `application.prorrata_register.served.*` and `application.modelo.credit_resolution.served.*` in `src/cadrumo/locales/*/application.yml`, `aggregation.retencion_soportada.served.*` in `src/cadrumo/locales/*/common.yml`.
- Several requests already carry `output_language: OutputLanguage` (`src/cadrumo/application/ledger/bulk_classify_operation.py:84`, `src/cadrumo/application/modelo/credit_resolution_contracts.py:89`, `src/cadrumo/application/actividad_asset/activity_asset_contracts.py:384`). Others render in `output_language()` (`src/cadrumo/core/i18n/render.py:181`) when the result is built.
- The CLI, TUI and desktop must show the same backend answer. A sentence that names a CLI flag or a TUI key is wrong in the window, and the reverse.
- Generic UI chrome (buttons, headings, empty states, progress verbs) is declared in `dev/locales/desktop_chrome.py` and has no tax meaning.
- Icons, glyphs and colours are presentation, not meaning.
- `dev/quality/tests/test_window_holds_no_tax_data.py` guards window tax data. It does not yet reject new tax wording.

## Considered options

- **Amend `2026-11-02-operation-refusal-words-adr`.** Same mechanism, but that record decides one field on one error detail. This decision reaches every operation's result contract, three surfaces, facts and capabilities, and narrows an older desktop ruling. Rejected as too broad for an amendment.
- **Keep words in each frontend's catalogue keyed by served tokens.** No contract change, but each surface words the same tax meaning separately, and the operator has forbidden it. Rejected.
- **Serve one token-to-words dictionary per session.** One read, but it separates the sentence from the record it describes and invites the window to pick a sentence for a token. Rejected.
- **Each operation serves the words, facts, flags and capabilities of its own records, in the request's language (chosen).** One owner per meaning, reused by every surface, on the existing precedent.

## Constraints

- **Served, not mapped.** Every registered operation serves, on its own records, the words, tax facts (currency, periods, applicable fields, validation limits), eligibility flags and capabilities a surface needs. No frontend maps a served code, reason token, state or field id to a sentence with tax meaning. This narrows the "Remap only" bullet of the 2026-10-27 amendment of `2026-10-04-desktop-shell-adr`: the window may still map served codes to layout and icons, but not to wording.
- **Field naming.** A served sentence is `<thing>_words`, a string, with `<thing>_words_language` beside it. Both are optional and travel together, as `refusal_words` and `answer_words` do. A label for a token on a row is a sibling field on that row, never a separate lookup. Facts are typed fields named for the fact (for example `reporting_currency`, `period`, `applicable_fields`), never words.
- **Keys.** Served sentences use `served` key families under the owning operation's namespace, `<owner namespace>.served.<reason or token>`. They are authored through `dev.locales` in all four locales (es, ca, en, hu) with real translations.
- **Language.** A request that serves words carries `output_language: OutputLanguage`, as the existing requests do. Where an operation has no request language yet, it renders in `output_language()` when the result is built and records the language served.
- **Surface neutrality.** Served words name no CLI flag, command, TUI key, window control or surface. They carry no private value beyond what the record already discloses under its definition's disclosure policy, and are worded only from scrubbed, bounded context, as `2026-11-02-operation-refusal-words-adr` requires.
- **Presentation stays in frontends.** Glyph, icon and colour maps keyed by served codes may stay in the window and the TUI.
- **Generic chrome stays.** UI chrome with no tax meaning stays as `desktop.*` keys declared in `dev/locales/desktop_chrome.py`. A string is chrome only if it would read the same in any tax domain. One that names a tax state, rule, box, modelo, period or reason is served.
- **Deletion protocol.** For each family: the backend serves it first, the relay contract admits it (`native/desktop/src-tauri/src/shell/ledger/relay_contracts.py`, `native/desktop/src-tauri/src/shell/modelo/relay_contracts.py`) and the operation contract manifest is regenerated. Then the desktop deletes its window copy, its `desktop.*` keys and any parity test guarding the copy, in one change. The TUI and CLI switch to the served field in the backend change or the change after it. The window keeps no copy once the field is served and adds no new copy while waiting. A copy that survives because its family is not yet served is named in this feature's plan.
- `2026-11-02-operation-refusal-words-adr` stays binding for refusals. This record extends its naming and wording rules to every served sentence.

## Implementation

We will make every registered operation serve the words, facts, flags and capabilities of its own records, and make the CLI, TUI and desktop render them only. Each served family is one backend change in its owning application module, with locale keys in the four catalogues, relay admission, manifest regeneration and a real-operation test per locale. The desktop deletes its matching copy as each family lands. `2026-11-03-backend-served-surface-plan` sequences the families. Which families exist, their order and their owner modules may change within these constraints. A protective gate that rejects new desktop tax wording follows once the families are served.

## Rationale

One owner per meaning is the only option that lets three surfaces agree without parallel catalogues, and the operator ruled for it. Words served on the record they describe stay bound to the data, unlike a session dictionary. The `_words` and `_words_language` pair and the `served` key families already exist, so the convention adds no mechanism. Glyphs and generic chrome stay in the frontends, because they carry no tax meaning.

## Consequences

- Result contracts of many operations gain optional `_words` fields and typed fact fields. Stored and older results stay valid, because the fields are optional.
- Locale catalogues gain many `served` keys. Sessions that commit a whole catalogue file must commit promptly, or they overwrite each other.
- The window and the TUI lose most of their tax word maps; their catalogues shrink to chrome.
- A served sentence's language can differ from the window's when the worker language is overridden; the `_words_language` field records it.
- Reconsider if the runtime result read gains a language, which would allow a release-time render, or if a family needs a window-side choice the backend cannot make.
