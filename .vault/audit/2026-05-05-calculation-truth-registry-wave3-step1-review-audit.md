---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave3-step1-exec]]'
---



# `calculation-truth-registry` Code Review

Wave 3 Step 1 local review found no blocking issue in the Modelo 115 registry
foundation.

Reviewed surfaces:

- `registry/aeat/modelos/115.toml`
- `registry/aeat/legal/irpf.toml`
- `corpus/normatives/rd-439-2007.json`
- `src/aeat/domain/calculations/registry/_schema.py`
- `src/aeat/domain/calculations/registry/_remote_state_guard.py`
- `src/aeat/domain/calculations/registry/__init__.py`
- `src/aeat/domain/calculations/registry/test_committed_registry.py`
- `src/aeat/domain/calculations/registry/test_remote_state_guard.py`
- `src/aeat/application/filing/test_export.py`
- `src/aeat/domain/deadlines/test_engine.py`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-05-calculation-truth-registry-wave3-step1.md`

Review checks performed:

- Registry closes legal/source references and source corpus hashes for Modelo
  115.
- Modelo 115 uses the current five-casilla official record-design shape rather
  than old six-casilla notes.
- Formula tests execute calculation behavior and trace output through the
  committed registry snapshot.
- Filing export test renders and parses the Modelo 115 registry layout through
  the application export surface.
- Deadline applicability uses the existing profile field via registry data.
- Committed cross-reference guard decisions are converted to executable
  remote-state guard policies and block HTTP/browser operations for static
  official documentation surfaces.
- No `legacy`, `migration`, `transient`, `wave`, `phase`, issue-number, PR, shim,
  disabled-state, or past-state guard language was added to the tested Python
  and TOML implementation surfaces.

CALC-TRUTH-W3-001 | INFO | Live filed-data fixture remains open

The implementation intentionally does not mark the live Modelo 115
filed-data rows complete. The registry has strict extraction profiles and a
static official cross-reference guard, but no authenticated read-only Modelo 115
submitted file or declaration-copy fixture was captured in this step.
