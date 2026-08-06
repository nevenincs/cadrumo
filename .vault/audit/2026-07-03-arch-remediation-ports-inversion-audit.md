---
tags:
  - '#audit'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:1f7368a713b3ec4cc84e3a51997e9085301b880da8137c4853643d27d6ed5a4a'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# `arch-remediation-ports-inversion` audit: `ports-inversion campaign close honesty review`

## Scope

Fresh-context honesty review mandated by the campaign-close-honesty-review discipline before declaring `arch-remediation-ports-inversion` structurally complete. An independent read-only reviewer audited the campaign's closing commits — the three filing-repository relocations (S10/S11/S12), the modelos verification/records (S13/S16/S18 including the S18 participation-index port), and the seam closeout (S19 zero-production gate, S20 `domain-not-adapters` forbidden contract) — against the ADR and plan, verifying claims against real test runs and a pristine `git archive HEAD` extraction rather than working-tree state alone. Nine adversarial checks plus a silent-gap sweep.

## Findings

### filing-no-legacy-and-consumer-sweep | low | verified clean — no re-export bridge, all consumers swept

The three filing concretes (`ModeloDraftRepository`, `ModeloAmendmentRepository`, runtime helpers) live solely under `adapters.persistence.profile`; `domain.filing` exports only the Protocol ports, with no re-export bridge (no-legacy). Every production consumer imports the concrete from its new adapter home; zero stale `domain.filing._repository` imports remain. The secure-storage rotation / runtime-attached-repository matrix still registers both filing repos (rotation suite 22 passed). Filing and modelos roundtrip / anti-tautology suites are real (encrypted SQLite, on-disk mutation, strict equality, corruption-refusal) with zero mock/xfail/skip.

### seam-gates-enforce | low | S19 non-tautological, S20 contract KEPT, zero production edges

`test_zero_production_domain_to_adapters_edges` filters test edges and asserts the production `domain.* -> adapters.*` set is empty — it would fail on any new production edge. `lint-imports` against pristine HEAD reports the new `domain-not-adapters` forbidden contract KEPT; the only BROKEN contract is the pre-existing, separately-tracked `layered` application->adapters wiring (zero `domain.*` violations). Every `domain.* -> adapters.*` ledger line is `.tests.`/`.conftest`.

### process-deviations-disclosed | low | two deviations honestly self-recorded, not concealed

(1) The S13 work-unit relocation commit `8f9cb8772c` was not `relocation:`-tagged per convention — recorded in the S13 exec Notes. (2) The S18 port commit `7138bc2a9b` bundled a peer's 15-file `bienes_inversion`-advisory-removal via a no-pathspec `git commit` — independently re-verified here as non-destructive: HEAD coherent (zero dangling refs to the deleted module), clean collection at 11993 tests, peer worktree WIP preserved intact, nothing lost. `git revert` was deliberately avoided (would clobber the peer's newer worktree edits). Recorded fully in the S18 exec Notes. All subsequent commits used explicit pathspecs verified via `git diff --cached`.

### out-of-scope-red-gate | medium | test_import_hygiene_gate + test_lazy_import_policy RED at HEAD from unrelated peer work

Six tests across `src/aeat/tests/test_import_hygiene_gate.py` (2) and `src/aeat/tests/test_lazy_import_policy.py` (4) are RED at committed HEAD, reproduced against a pristine `git archive HEAD` extraction (genuine committed-state failure, not working-tree noise). Root cause is unrelated concurrent peer commits landing during this campaign's window — `#407` local-only run/session diagnostics (`adapters/outbound/llm/_run_telemetry.py`), `#422` sandboxed experiment workspace (`application/bucket_maintenance/_sandbox.py`), the `claude-ecosystem-packaging` campaign (`agent/_workspace.py`), plus three test files under `corpus_search`, `calc_sheets`, and `entrypoints/mcp`. None are in the ports-inversion ADR/plan scope or its touched files; the campaign's own edits to `test_lazy_import_policy.py` were surgical (only its own relocation edges). Per `full-tree-gate-must-distinguish-owner` this does not block ports-inversion closure, but it is a real red gate on the shared branch.

## Recommendations

- **Declare `arch-remediation-ports-inversion` structurally complete.** Reviewer verdict GO: 20/20 Steps closed with exec records, every ADR/plan claim independently verified, the zero-production `domain -> adapters` invariant holds by grep and by the new enforced gate, and both process deviations are honestly disclosed.
- **File the out-of-scope red gate as a follow-up owned by the introducing campaigns** (`#407` / `#422` / `claude-ecosystem-packaging` / the MCP-evidence / corpus_search / calc_sheets work), NOT ports-inversion. The likely mechanical fix (raise the import-hygiene allowlist edge ceiling and the adapter-internal-deferral site ceiling, register the new deferred first-party edges as test-debt) MUST be adjudicated by those owners: blindly bumping the ceilings could launder a genuine unsanctioned deferral rather than record a legitimate one. Do not absorb it into this campaign to force a green closeout (that is the anti-pattern `full-tree-gate-must-distinguish-owner` warns against).
