---
generated: true
tags:
  - '#index'
  - '#profile-bundle-tui'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:7f128561861beeaec078a08f264560d6a34c4f6e7c921f32b67a75f38a1d0092'
related:
  - '[[2026-07-24-profile-bundle-tui-adr]]'
  - '[[2026-07-24-profile-bundle-tui-canonical-bundle-path-reference]]'
  - '[[2026-07-25-profile-bundle-tui-plan]]'
---

# `profile-bundle-tui` feature index

Auto-generated index of all documents tagged with `#profile-bundle-tui`.

## Documents

### adr

- `2026-07-24-profile-bundle-tui-adr` - `profile-bundle-tui` adr: `interactive flow mode for the profile bundle verbs` | (**status:** `accepted`)

### exec

- `2026-07-25-profile-bundle-tui-S01` - Build the export FlowDefinition at the entrypoint tier collecting profile as a SELECT over live bucket labels defaulting to the active profile and included only when no NAME argument was given, destination as a PATH, and transport as a SELECT over the canonical ProfileBundleExportTransport values with the encrypted arm as default
- `2026-07-25-profile-bundle-tui-S02` - Carry honest sensitivity copy on the cleartext transport arm so an operator choosing it is told what leaves encrypted storage, since the cleartext arm is the one selection that removes the confidentiality guarantee
- `2026-07-25-profile-bundle-tui-S03` - Build the import FlowDefinition collecting the bundle path as a PATH and, only when --label was not given, an optional label as TEXT
- `2026-07-25-profile-bundle-tui-S04` - Launch the flow from the bundle command only when required values are missing, --secrets-stdin was not passed, and the capability probe reports a prompt-capable host, then proceed through the unchanged canonical calls, envelope, and notices
- `2026-07-25-profile-bundle-tui-S05` - Keep passphrase collection on the pre-existing hidden confirm-retype prompts after the flow exits rather than moving secret entry into the flow, and prove a console-less host cannot reach an echoing fallback
- `2026-07-25-profile-bundle-tui-S06` - Refuse non-interactive under-specified invocations with typed suggestion-carrying errors rather than prompting or defaulting, verified by a headless regression that fails on timeout rather than exercising the helper in isolation

### plan

- `2026-07-25-profile-bundle-tui-plan` - `profile-bundle-tui` plan

### reference

- `2026-07-24-profile-bundle-tui-canonical-bundle-path-reference` - `profile-bundle-tui` reference: `canonical bundle path`
