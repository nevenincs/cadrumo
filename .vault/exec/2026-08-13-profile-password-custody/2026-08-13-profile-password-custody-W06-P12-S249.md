---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a1a1ec13878b4398c610787830da21c1e477428e11b542cbf19582b0c19384e3'
step_id: 'S249'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Reconcile profile and recovery provisioning sequences on check-aeat-notifications, quickstart, profile-setup, and troubleshooting with mandatory creation channels and current status/list composition

## Scope

- `docs/_sequences/contracts/ and docs/quickstart.md and docs/how-to/profile-setup.md and docs/troubleshooting.md`

## Description

- Grounded mandatory creation recovery and profile list/status composition through Vaultspec RAG, the accepted custody ADR, and current production code.
- Replaced three impossible headless password-only creation examples with truthful interactive recovery handoffs and exact active-profile list witnesses.
- Kept destructive pointer repair and passphrase login static behind honest operator-state/TTY blockers instead of fabricating custody or corruption.
- Reordered the profile guide so login-gated capability reads precede logout, and removed redundant troubleshooting login state changes.
- Regenerated only the five adjudicated goldens through the owning sequence CLI.

## Outcome

Complete. All four affected pages now execute cumulatively without bypassing mandatory recovery custody, and current profile list output owns the active-profile assertions.

## Notes

- Four affected page-coherence checks passed; five scoped golden checks passed.
- Parser/sequence-contract proof passed `61` tests; documented-command conformance passed `349` tests; focused Ruff passed.
- Scoped ty retains 18 pre-existing diagnostics in unchanged sequence Python, including the known S239 compare narrowing debt and unrelated runner/test diagnostics; S249 changes no Python.
- Product behavior was correct and unchanged: headless create refuses without passphrase plus paired recovery handoff/verification channels.
- Formal review's two medium prose findings were resolved: setup completeness now belongs to authenticated profile inspection, and every scoped custody explanation describes a per-profile random key wrapped by that profile's passphrase rather than a shared master key.
