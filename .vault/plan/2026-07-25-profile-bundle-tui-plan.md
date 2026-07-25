---
tags:
  - '#plan'
  - '#profile-bundle-tui'
date: '2026-07-25'
modified: '2026-07-25'
tier: L1
related:
  - '[[2026-07-24-profile-bundle-tui-adr]]'
  - '[[2026-07-24-profile-bundle-tui-canonical-bundle-path-reference]]'
  - '[[2026-07-23-tui-wizard-substrate-plan]]'
---

# `profile-bundle-tui` plan

- [x] `S01` - Build the export FlowDefinition at the entrypoint tier collecting profile as a SELECT over live bucket labels defaulting to the active profile and included only when no NAME argument was given, destination as a PATH, and transport as a SELECT over the canonical ProfileBundleExportTransport values with the encrypted arm as default; `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`.
- [x] `S02` - Carry honest sensitivity copy on the cleartext transport arm so an operator choosing it is told what leaves encrypted storage, since the cleartext arm is the one selection that removes the confidentiality guarantee; `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`.
- [x] `S03` - Build the import FlowDefinition collecting the bundle path as a PATH and, only when --label was not given, an optional label as TEXT; `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`.
- [x] `S04` - Launch the flow from the bundle command only when required values are missing, --secrets-stdin was not passed, and the capability probe reports a prompt-capable host, then proceed through the unchanged canonical calls, envelope, and notices; `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`.
- [x] `S05` - Keep passphrase collection on the pre-existing hidden confirm-retype prompts after the flow exits rather than moving secret entry into the flow, and prove a console-less host cannot reach an echoing fallback; `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`.
- [x] `S06` - Refuse non-interactive under-specified invocations with typed suggestion-carrying errors rather than prompting or defaulting, verified by a headless regression that fails on timeout rather than exercising the helper in isolation; `src/cadrumo/entrypoints/cli/tests/`.
## Description

## Steps

## Parallelization

## Verification

## Context

Accepted ADR carrying no plan and no exec records. Depends on the completed tui-wizard-substrate campaign for its rendering substrate.
