---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:427f35c7077b9497798238792a4faeed13664abcad061c635c4be1c216212b59'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` `W02.P05` summary

## Description

Aligned channel-neutral diagnostics across all four locale catalogues and removed obsolete command-local readers, payload models, fallback branches, and prompts outside the closed inventory while retaining separately governed programmatic settings.

- Modified: `src/cadrumo/locales/{en,es,ca,hu}/cli.yml`
- Modified: CLI handlers and conformance tests under `src/cadrumo/entrypoints/cli`
