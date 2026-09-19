---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:baa1a7ddf7bed79be9f7a75e4e57e9a0d039ff396fde7c1f0ab7d2f5fbfec5a6'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename` `W05.P12` summary

Phase W05.P12 cut command-help and four locale catalogues to Cadrumo while
preserving AEAT as the Spanish authority.

- Completed: S62 through S67 Step Records
- Updated: English, Spanish, Catalan, and Hungarian product copy
- Regenerated: 30 shared locale keys through the locale scaffold authority
- Verified: parity, translation honesty, coverage, Unicode, and CLI round trips

## Description

CLI help, command suggestions, and product-facing messages now use Cadrumo and
the `cadrumo` executable. AEAT remains in legal, portal, credential, registry,
evidence, filing-counterparty, and retired-state contexts.

Every catalogue mutation was routed through `python -m cadrumo.locales`; the
scaffold and audit report zero drift. The four catalogues gained the same 30 keys
with substantive translations and preserved placeholder sets. Twenty-two final
locale parity, honesty, coverage, and CLI tests pass.

Interrupted long-running locale writers exposed a direct-truncation hazard in
the mapping rewrite path. The manager now serializes beside the target and uses
an atomic replacement, preventing interruption from exposing malformed YAML.
Corrupted Catalan and Hungarian working bytes were recovered without rewriting
history, then revalidated through the authoritative CLI.
