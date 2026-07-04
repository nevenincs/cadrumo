---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S17'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Make the four aeat app registry verification verbs refuse instructively when the companion is required and absent

## Scope

- `src/aeat/entrypoints/cli/registry.py`

## Description

- Add `guard_corpus_companion` to the registry corpus CLI module and wire it into the five verification surfaces: registry verify, workbooks verify, parity run, parity replay, and manuals verify — each refuses with `CliRefusedBoundaryError` naming the capability and the exact `aeat[corpus-sources]` install command when the companion is required and absent.
- Add the `cli.registry.errors.capability.*` and `corpus_companion_absent` locale keys across en/es/ca/hu.
- Export the companion vocabulary through the registry package facade.
- Add `test_registry_corpus_companion_guard.py` (2 passed).
- Commit `5ed126e524`.

## Outcome

- The CLI gate is instructive, never a silent black hole: split-install users are told exactly what capability is missing and how to install it.

## Notes

The executing agent's session was terminated by the account rate limit AFTER writing the implementation but BEFORE gating and committing. The coordinator verified the working-tree WIP (guard test 2 passed; locale `scaffold --check` ok across all four catalogues; JSON-schema conformance 116 passed; ruff clean), separated the S17 hunks from entangled peer WIP in the four locale files (an unrelated diagnostics campaign's uncommitted keys plus serialiser reflow), and landed the commit via a temp-index build with a compare-and-swap HEAD guard so neither the shared index nor the peer working-tree WIP was touched. Four pre-existing conformance failures observed during gating (`REFUSED_DOMAIN_RETENTION_FLOOR` citing a not-yet-registered `profile erase` verb, and related suggestion-conformance reds) were attributed to peer commit `3e5abe8190` (GDPR retention campaign) — outside this step's surface, not absorbed, reported per full-tree-gate-must-distinguish-owner.
