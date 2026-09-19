---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:bc712d370813fd6ef370e019bbe317232125c3d783a7d4069b035ecd21c75cac'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W08.P28.S381 Review`

## Scope

Reviewed the S381 Home implementation in commits `9f10eec356`, `3e8bc1b2da`, and `56ae5030b9`, together with the checked S381 plan row and execution record. The review covered projection-only authority, the application-enforced three-action limit and agenda ordering, readiness and evidence-state rendering, responsive single-scroll and keyboard behavior, implicit-network absence, devtools dependency direction, clone removal, and focused quality gates.

## Findings

`HomeScreen` receives one immutable `HomeProjectionV1`, publishes only semantic selection and back messages, and contains no reader, adapter, CLI, filesystem, network, or action invocation. The projection validates the maximum three ranked actions, chronological three-row agenda, and unavailable-count honesty before rendering. The selected layout retains one page scroll owner, no table horizontal overflow, three keyboard tab stops, semantic focus targets, and non-colour textual status. Devtools consumes the production identity/address helpers in the permitted presentation direction, eliminating the duplicate helper bodies without adding an application or runtime authority edge.

### agenda-identity-collision | medium | Duplicate agenda addresses collide in selectable row keys

`HomeProjectionV1` accepts two agenda entries with the same Modelo, year, and period so long as their dates are chronological. `HomeScreen` creates each agenda row key from precisely that natural address through `home_agenda_identity`. A valid injected projection can therefore create duplicate keys, causing ambiguous selection and failed semantic focus restoration. The application projection must reject duplicate agenda natural addresses before the TUI receives them.

Focused evidence passed: `test_home.py` (7 tests), Ruff, ty, and basedpyright. The candidate suite is separately in progress elsewhere in the shared worktree, so this audit does not claim a second concurrent result for it.

### agenda-identity-collision-remediation | low | Remediation is implemented; independent review is pending

`HomeProjectionV1` now rejects duplicate agenda addresses using exactly `(modelo, filing_year, period.registry_token)` before the TUI renders a row. The focused contract rejects a repeated address even when its due date differs, while accepting the near neighbours that differ by Modelo, filing year, or period token. The existing TUI identity stays unchanged and no agenda ranking behavior changed.

Focused verification completed: the application Home projection tests and TUI Home tests (23 tests), plus Ruff, ty, and basedpyright on the changed application and Home surfaces. This entry records implementation evidence only; the S381 audit remained pending independent review.

### agenda-identity-collision-independent-review | low | Application-boundary remediation resolves the identity collision

Commit `823479cd0d` rejects duplicate `(modelo, filing_year, period.registry_token)` tuples in `HomeProjectionV1`, exactly matching `home_agenda_identity` before any row is created. The new negative contract proves that a duplicate with a different due date fails, while parameterized near-neighbour cases prove that different Modelo, filing year, or period remain valid. The original selection and focus-restoration identity is therefore again injective for every valid projection.

Independent focused verification passed: `uv run pytest -q -n 0 -m "" src/cadrumo/application/overview/tests/test_home_projection.py src/cadrumo/entrypoints/tui/tests/test_home.py` (23 passed), followed by Ruff, ty, and basedpyright on the affected application and TUI surfaces.
## Recommendations

1. No remaining S381 corrective action. The independent remediation review is complete.

The planned W08.P29 verification remains the owner of the broader locale, terminal-size, and installed-workbench proof.
