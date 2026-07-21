---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S23'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Run audit source installation brew test CLI tax work and MCP tax work for one tap snapshot

## Scope

- `dev/packaging/smoke_homebrew.py`

## Description

- Copy the generated formula into a disposable local Git-backed tap.
- Replace only the three immutable release URLs with loopback URLs serving the
  exact source archives while retaining and verifying every formula digest.
- Run strict formula audit, source installation, formula test, installed CLI
  and MCP tax oracles, uninstall, and untap through Homebrew under WSL2.
- Retain command logs, structured oracle evidence, artifact hashes, installed
  executable identities, and cleanup proof.

## Outcome

- Homebrew 6.0.11 on Ubuntu WSL2 x86-64 audited
  `cadrumo-smoke/acquisition/cadrumo` with exit code 0.
- `brew install --build-from-source` installed the generated `0.2.1` formula
  at `/home/linuxbrew/.linuxbrew/Cellar/cadrumo/0.2.1`; `brew test` then invoked
  the Cellar-owned `aeat --version` command and exited 0.
- Installed `aeat` calculated `DP200014:00562 == 23000.00` with formula
  `modelo-200-cuota-integra`, the applicable LIS references, and both
  authoritative source references.
- Installed `cadrumo-mcp` advertised the public tool surface, invoked the
  Cellar-owned CLI, and independently returned the same grounded tax result.
- The generated formula digest was
  `4db6b663816fb18127b6856b7d2659d82810502f2af00db98b903bf2eba62047`;
  the evidence inventories the root, manuals, and official source archives as
  `6d1b0980c3102ed8445a44f1eeeb6ea8f219290641577cf1980262ca5ca948c2`,
  `97d730c8f3fb9488baf12f7fd57f5ebdf82706e3acebc6e10b3891ca718533e6`,
  and `dab241eb00608c39c2e1f8419dbea56f4560345cc0d951ac486d83118e4d2e39`.
- The retained Homebrew, CLI-oracle, and MCP-oracle evidence digests were
  `5c81176443c837cc43db724f0e7e4aef0bf7d633134cd4c5a323ac274cda63ca`,
  `8136dd6156330678ebb31e95cedeb5cf2dc510607537e38ec6a47d1b5ead994f`,
  and `8ad959ad5b53fb12142cd120e44861801261e53db29890b8c0b64a6dcd483fe9`.
- Cleanup removed the installed formula and disposable tap; the recorded
  retained-formula, retained-tap, and cleanup-error collections are empty.

## Notes

- Retained evidence is under
  `var/distribution-install-readiness/s23-homebrew/final-verified-run/run-20260717T015226785744Z`.
- Earlier exploratory runs retained their failure evidence. They exposed audit
  invocation, Homebrew dependency-lock, and cleanup defects before the final
  passing run.
- Formal review found that an earlier retained root source archive no longer
  matched the tap snapshot even though Homebrew had tested the expected bytes
  from its cache. The harness now rejects any cohort archive whose bytes differ
  from the formula digest, records all three archive identities, and the final
  18-minute source-install run passed with the self-contained restored cohort.
- This closes the single Linux tap-snapshot installation proof in S23. It does
  not claim macOS or hosted-runner coverage; those platform rows remain S24.
