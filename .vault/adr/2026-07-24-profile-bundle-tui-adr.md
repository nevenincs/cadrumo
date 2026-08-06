---
tags:
  - '#adr'
  - '#profile-bundle-tui'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:4efe47a84303f5b95917323835917988266394b932958a77c7002092742f2ed2'
related:
  - "[[2026-05-27-profile-portability-adr]]"
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - '[[2026-07-24-profile-bundle-tui-canonical-bundle-path-reference]]'
---

# `profile-bundle-tui` adr: `interactive flow mode for the profile bundle verbs` | (**status:** `accepted`)

## Problem Statement

The portable profile bundle (per `2026-05-27-profile-portability-adr`) is reachable only through fully-specified `aeat config profile export` / `import` invocations. An operator working interactively must know the option surface (`--to`, `--encrypt` vs `--cleartext-local`) before the command will do anything; the setup wizard's paged flow substrate (per `2026-07-23-profile-setup-flow-adr`) exists precisely for this shape of guided collection but did not cover the bundle verbs. A decision was needed on where the interactive surface lives and how it composes with the single export/import authority.

## Considerations

Grounding: `2026-07-24-profile-bundle-tui-canonical-bundle-path-reference` (full reads of the bundle authority, CLI surface, flow substrate, and the modelo-work-wizard precedent).

- One write path: `export_profile_bundle` / `deserialize_profile_bundle` are the sole bundle authorities (`composition-service-no-parallel-write-path`); the TUI must be presentation only.
- Secrets: the bundle passphrase must never be persisted or echoed; the `_secure_input` hidden-prompt channel is its single home.
- Frontend selection is a single-probe contract (`detect_frontend_capability` + `select_flow_frontend`); no surface re-derives TTY capability.
- CLI roots stay `config` and `app`; scripted callers' behavior must not change.
- A concurrent layout-polish campaign holds `adapters/inbound/tui` screen files as WIP; new screen modules there were to be avoided.

## Considered options

- **Interactive mode of the existing verbs (chosen):** under-specified invocations on a prompt-capable host launch a flow collecting only the missing answers; fully-specified invocations are byte-identical. No new verbs, no new screens.
- **A new `aeat config profile wizard`-style verb:** rejected — grows the verb surface for what is a presentation concern and forks operator muscle memory across two entry points.
- **Bespoke Textual screens under `adapters/inbound/tui`:** rejected — the generic flow substrate already renders any `FlowDefinition` on both frontends; bespoke screens would duplicate rendering and collide with the in-flight layout campaign.
- **Passphrase as a SECRET flow page:** rejected — it would place the secret in the flow answer map and create a second passphrase-collection authority next to `_secure_input`.

## Constraints

- The flow substrate (engine, line frontend, Textual app, scripted driver) is stable and shipped with the setup flow; this decision only consumes its public facade.
- Copy is reference-only: static prose requires locale-catalogue keys (serialized through the coordinator's locale lane, with `_fstring_registry` registration for keys the AST scanner cannot see); profile display names ride a run-scoped `SCHEMA_FIELD` copy table.
- Checkpointing must be declared UNAVAILABLE in both modes: nothing collected may persist mid-run.

## Implementation

`entrypoints/cli/_config/_profile_bundle_flow.py` builds two small `FlowDefinition`s at the entrypoint tier (the tier permitted to name the TUI adapter). Export collects profile (SELECT over live bucket labels, defaulting to the active profile; included only when no NAME argument was given), destination (PATH), and transport (SELECT over the canonical `ProfileBundleExportTransport` values, encrypted default, with honest sensitivity copy on the cleartext arm). Import collects the bundle path (PATH) and, when `--label` was not given, an optional label (TEXT). The command in `_profile_bundle.py` launches the flow only when required values are missing, `--secrets-stdin` was not passed, and the capability probe reports a prompt-capable host; it then proceeds through the unchanged canonical calls, envelope, and notices. Non-interactive under-specified invocations refuse with typed, suggestion-carrying errors. Passphrase collection stays on the pre-existing hidden confirm-retype prompts after the flow exits.

## Rationale

The knockout criterion is single-authority composition: every alternative that adds a verb, a screen, or an in-flow secret page creates a second home for something that already has one (the verb surface, the flow rendering, the passphrase channel). Making interactivity a property of the existing verbs preserves scripted behavior exactly, reuses the substrate's tested engine/validation/review machinery on both frontends for free, and leaves zero collision surface with the concurrent TUI layout campaign.

## Consequences

- Operators get a guided export/import inside the terminal with the full-screen app where capable and line mode elsewhere; scripted and JSON callers see no change.
- `--to` (export) and PATH (import) are now optional at parse time; the missing-value refusal moved from a click parse error to a typed, localized refusal with a suggestion — a strictly more instructive gate, but a changed error shape for callers that matched click's text.
- The interactive render path depends on the locale batch landing (seven CopyRef-only keys plus two refusal keys); until then only the refusal keys gate CI parity.
- The flow deliberately cannot save-and-exit; an abandoned run discards answers loudly via the substrate's typed abandonment error.
