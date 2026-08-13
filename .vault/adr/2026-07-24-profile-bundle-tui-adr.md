---
tags:
  - '#adr'
  - '#profile-bundle-tui'
date: '2026-07-24'
modified: '2026-08-13'
body_hash: 'sha256:4682ea8bb2d19dcb060c3689e354475f1e3487849e052cc891319103bf4de787'
related:
  - '[[2026-05-27-profile-portability-adr]]'
  - '[[2026-07-23-profile-setup-flow-adr]]'
  - '[[2026-07-24-profile-bundle-tui-canonical-bundle-path-reference]]'
  - '[[2026-08-11-tui-architecture-adr]]'
---

# `profile-bundle-tui` adr: `interactive flow mode for the profile bundle verbs` | (**status:** `accepted`)

## Problem Statement

The portable profile bundle (per `2026-05-27-profile-portability-adr`) is reachable only through fully-specified `aeat config profile export` / `import` invocations. An operator working interactively must know the option surface (`--to`, `--encrypt` vs `--cleartext-local`) before the command will do anything; the setup wizard's paged flow substrate (per `2026-07-23-profile-setup-flow-adr`) exists precisely for this shape of guided collection but did not cover the bundle verbs. A decision was needed on where the interactive surface lives and how it composes with the single export/import authority.

## Considerations

Grounding: `2026-07-24-profile-bundle-tui-canonical-bundle-path-reference` (full reads of the bundle authority, CLI surface, flow substrate, and the modelo-work-wizard precedent).

- One write path: `export_profile_bundle` / `deserialize_profile_bundle` are the sole bundle authorities (`composition-service-no-parallel-write-path`); the TUI must be presentation only.
- Secrets: the bundle passphrase must never enter a flow answer, persisted state, event, or diagnostic. `_secure_input` remains the CLI collection channel; the dedicated TUI may submit it only through the backend-owned exact ephemeral capability scheduled by `2026-08-11-tui-architecture-adr`, never by importing the CLI channel or inventing another custody authority.
- Host capability remains a single frontend-neutral application probe; per `2026-08-11-tui-architecture-adr`, each sibling entrypoint owns its projection and no CLI-to-TUI selector or import remains.
- CLI roots stay `config` and `app`; scripted callers' behavior must not change.
- A concurrent layout-polish campaign holds `adapters/inbound/tui` screen files as WIP; new screen modules there were to be avoided.

## Considered options

- **Interactive mode of the existing verbs plus the dedicated TUI projection (chosen):** under-specified CLI invocations on a line-capable host launch the line-mode flow collecting only the missing answers; fully-specified invocations are byte-identical. The dedicated TUI projects the same application-owned bundle operation through its profile area. No new CLI verbs and no bespoke bundle screen authority.
- **A new `aeat config profile wizard`-style verb:** rejected — grows the verb surface for what is a presentation concern and forks operator muscle memory across two entry points.
- **Bespoke Textual screens under `adapters/inbound/tui`:** rejected — the generic flow substrate already renders any `FlowDefinition` on both frontends; bespoke screens would duplicate rendering and collide with the in-flight layout campaign.
- **Passphrase as a SECRET flow page:** rejected — it would place the secret in the flow answer map and create a second passphrase-collection authority next to `_secure_input`.

## Constraints

- The flow substrate's engine, line frontend, and scripted driver remain frontend-neutral application authorities. Textual rendering is consumed only inside the dedicated TUI entrypoint, as governed by `2026-08-11-tui-architecture-adr`.
- Copy is reference-only: static prose requires locale-catalogue keys (serialized through the coordinator's locale lane, with `_fstring_registry` registration for keys the AST scanner cannot see); profile display names ride a run-scoped `SCHEMA_FIELD` copy table.
- Checkpointing must be declared UNAVAILABLE in both modes: nothing collected may persist mid-run.

## Implementation

`entrypoints/cli/_config/_profile_bundle_flow.py` builds two small `FlowDefinition`s and drives only the frontend-neutral line-mode projection. Export collects profile (SELECT over live bucket labels, defaulting to the active profile; included only when no NAME argument was given), destination (PATH), and transport (SELECT over the canonical `ProfileBundleExportTransport` values, encrypted default, with honest sensitivity copy on the cleartext arm). Import collects the bundle path (PATH) and, when `--label` was not given, an optional label (TEXT). The command in `_profile_bundle.py` launches that flow only when required values are missing, `--secrets-stdin` was not passed, and the application capability probe reports a line-capable host; it then proceeds through the unchanged canonical calls, envelope, and notices. Non-interactive under-specified invocations refuse with typed, suggestion-carrying errors. Passphrase collection stays on the pre-existing hidden confirm-retype prompts after the CLI flow exits.

The full-screen path starts only through `cadrumo.entrypoints.tui.launcher`. Its profile and operation projections consume public application bundle and operation facades; once the backend-owned exact ephemeral secret capability exists, its secret projection may submit the passphrase through that capability. It neither imports the CLI flow or `_secure_input` modules nor creates a second exporter, importer, flow engine, or passphrase store. The CLI does not import or launch the TUI. Both entrypoints preserve the same canonical bundle authorities, checkpoint prohibition, and exclusion of secrets from flow answers and durable operation state.

## Rationale

The knockout criterion is single-authority composition: every alternative that adds a verb, a screen, or an in-flow secret page creates a second home for something that already has one (the verb surface, the flow rendering, the passphrase channel). Making interactivity a property of the existing verbs preserves scripted behavior exactly, reuses the substrate's tested engine/validation/review machinery on both frontends for free, and leaves zero collision surface with the concurrent TUI layout campaign.

## Consequences

- Operators get guided export/import through the dedicated full-screen TUI or through line mode on the existing CLI verbs; scripted and JSON callers see no change.
- `--to` (export) and PATH (import) are now optional at parse time; the missing-value refusal moved from a click parse error to a typed, localized refusal with a suggestion — a strictly more instructive gate, but a changed error shape for callers that matched click's text.
- The interactive render path depends on the locale batch landing (seven CopyRef-only keys plus two refusal keys); until then only the refusal keys gate CI parity.
- The flow deliberately cannot save-and-exit; an abandoned run discards answers loudly via the substrate's typed abandonment error.
